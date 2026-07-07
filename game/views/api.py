import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from ..models import Level, PlayerLevelState, PlayerVehicle, Tile
from ..services import combat


@login_required(login_url="/login/")
@require_POST
def update_vehicle_position(request, vehicle_id):
    """Handles AJAX updates for moving player vehicles."""
    try:
        data = json.loads(request.body)
        tile_id = data.get("tile_id")

        # Only allow the user to update their own vehicles
        vehicle = get_object_or_404(PlayerVehicle, pk=vehicle_id, player_state__user=request.user)

        if tile_id:
            tile = Tile.objects.select_related("level").get(pk=tile_id)
            if tile.terrain_type != Tile.TerrainType.DOCK:
                level = tile.level
                bottom_zone_start = level.height - int(level.height * 0.4)
                if tile.y < bottom_zone_start:
                    return json_error("Vehicles must be placed in the bottom 40% of the map.", 400)
            vehicle.tile = tile
        else:
            vehicle.tile = None

        vehicle.save()
        print(f"✅ Updated {vehicle.vehicle_type} -> tile {tile_id}")
        return JsonResponse({"status": "ok"})
    except (PlayerVehicle.DoesNotExist, Tile.DoesNotExist):
        return json_error("Not found", 404)
    except Exception as e:
        print(f"❌ Error updating vehicle: {e}")
        return json_error(str(e), 500)


@login_required(login_url="/login/")
def mark_game_started(request, level_id):
    """Mark the user's PlayerLevelState as started for this level."""
    if request.method == "POST":
        level = get_object_or_404(Level, pk=level_id)
        player_state, _ = PlayerLevelState.objects.get_or_create(user=request.user, level=level)
        player_state.game_started = True
        player_state.save()
        return JsonResponse({"success": True})
    return json_error("Invalid request", 500)


def _get_active_player_state(user, level_id):
    """Fetch the PlayerLevelState for an in-progress, started game, or raise ValueError."""
    player_state = get_object_or_404(PlayerLevelState, user=user, level_id=level_id)
    if not player_state.game_started:
        raise ValueError("Game has not started.")
    if player_state.status != PlayerLevelState.Status.IN_PROGRESS:
        raise ValueError("This level has already ended.")
    return player_state


@login_required(login_url="/login/")
def vehicle_actions(request, vehicle_id):
    """Return the valid move tiles and attack targets for one of the player's own vehicles."""
    try:
        vehicle = get_object_or_404(
            PlayerVehicle, pk=vehicle_id, player_state__user=request.user, is_enemy=False
        )
        player_state = _get_active_player_state(request.user, vehicle.player_state.level_id)

        if player_state.current_phase != PlayerLevelState.Phase.PLAYER:
            return json_error("It is not your turn.", 400)
        if vehicle.has_acted:
            return json_error("This vehicle has already acted this turn.", 400)
        if vehicle.tile is None:
            return json_error("Vehicle is not on the board.", 400)

        board_tiles = list(player_state.level.tiles.exclude(terrain_type="DOCK"))
        occupied_tile_ids = {
            v.tile_id
            for v in player_state.vehicles.exclude(pk=vehicle.pk)
            if v.tile_id is not None
        }
        moves = combat.valid_move_tiles(vehicle, board_tiles, occupied_tile_ids)

        enemies = list(
            player_state.vehicles.filter(is_enemy=True).select_related("tile")
        )
        targets = combat.valid_attack_targets(vehicle, enemies)

        return JsonResponse(
            {
                "status": "ok",
                "moves": [t.id for t in moves],
                "targets": [v.id for v in targets],
            }
        )
    except ValueError as e:
        return json_error(str(e), 400)
    except (PlayerVehicle.DoesNotExist, PlayerLevelState.DoesNotExist):
        return json_error("Not found", 404)


@login_required(login_url="/login/")
@require_POST
def move_vehicle(request, vehicle_id):
    """Move one of the player's vehicles to a tile within its move range."""
    try:
        data = json.loads(request.body)
        try:
            tile_id = int(data.get("tile_id"))
        except (TypeError, ValueError):
            return json_error("Invalid tile.", 400)

        vehicle = get_object_or_404(
            PlayerVehicle, pk=vehicle_id, player_state__user=request.user, is_enemy=False
        )
        player_state = _get_active_player_state(request.user, vehicle.player_state.level_id)

        if player_state.current_phase != PlayerLevelState.Phase.PLAYER:
            return json_error("It is not your turn.", 400)
        if vehicle.has_acted:
            return json_error("This vehicle has already acted this turn.", 400)

        board_tiles = list(player_state.level.tiles.exclude(terrain_type="DOCK"))
        occupied_tile_ids = {
            v.tile_id
            for v in player_state.vehicles.exclude(pk=vehicle.pk)
            if v.tile_id is not None
        }
        moves = combat.valid_move_tiles(vehicle, board_tiles, occupied_tile_ids)
        if not any(t.id == tile_id for t in moves):
            return json_error("Invalid move.", 400)

        vehicle.tile_id = tile_id
        vehicle.has_acted = True
        vehicle.save()

        return JsonResponse({"status": "ok", "tile_id": tile_id})
    except ValueError as e:
        return json_error(str(e), 400)
    except (PlayerVehicle.DoesNotExist, PlayerLevelState.DoesNotExist):
        return json_error("Not found", 404)


@login_required(login_url="/login/")
@require_POST
def attack(request, vehicle_id):
    """Attack an enemy vehicle within range."""
    try:
        data = json.loads(request.body)
        target_id = data.get("target_id")

        vehicle = get_object_or_404(
            PlayerVehicle, pk=vehicle_id, player_state__user=request.user, is_enemy=False
        )
        player_state = _get_active_player_state(request.user, vehicle.player_state.level_id)

        if player_state.current_phase != PlayerLevelState.Phase.PLAYER:
            return json_error("It is not your turn.", 400)
        if vehicle.has_acted:
            return json_error("This vehicle has already acted this turn.", 400)

        target = get_object_or_404(
            PlayerVehicle, pk=target_id, player_state=player_state, is_enemy=True
        )
        targets = combat.valid_attack_targets(vehicle, [target])
        if not targets:
            return json_error("Target out of range.", 400)

        destroyed = combat.apply_damage(vehicle, target)
        vehicle.has_acted = True
        vehicle.save()

        game_status = combat.check_game_over(player_state)

        return JsonResponse(
            {
                "status": "ok",
                "target_destroyed": destroyed,
                "target_health": 0 if destroyed else target.health,
                "game_status": game_status,
            }
        )
    except ValueError as e:
        return json_error(str(e), 400)
    except (PlayerVehicle.DoesNotExist, PlayerLevelState.DoesNotExist):
        return json_error("Not found", 404)


@login_required(login_url="/login/")
@require_POST
def end_turn(request, level_id):
    """End the player's turn, run the enemy AI turn, and return the updated board state."""
    try:
        player_state = _get_active_player_state(request.user, level_id)

        if player_state.current_phase != PlayerLevelState.Phase.PLAYER:
            return json_error("It is not your turn.", 400)

        player_state.current_phase = PlayerLevelState.Phase.ENEMY
        player_state.save()

        combat.run_enemy_turn(player_state)

        if player_state.status == PlayerLevelState.Status.IN_PROGRESS:
            player_state.vehicles.filter(is_enemy=False).update(has_acted=False)
            player_state.turn_number += 1
            player_state.current_phase = PlayerLevelState.Phase.PLAYER
            player_state.save()

        return JsonResponse({"status": "ok", "board": combat.serialize_board_state(player_state)})
    except ValueError as e:
        return json_error(str(e), 400)
    except PlayerLevelState.DoesNotExist:
        return json_error("Not found", 404)


def json_error(message, status=400):
    return JsonResponse({"status": "error", "message": message}, status=status)
