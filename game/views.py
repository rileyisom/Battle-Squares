import json
from collections import defaultdict

from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import FormView

from .forms import SimpleUserCreationForm
from .models import Level, PlayerLevelState, PlayerVehicle, Tile


# AUTHENTICATION
class RegisterView(FormView):
    template_name = "game/register.html"
    form_class = SimpleUserCreationForm
    success_url = reverse_lazy("level-list")

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)  # Log user in automatically
        return super().form_valid(form)


# LEVEL LIST
@login_required(login_url="/login/")
def level_list(request):
    levels = Level.objects.all()
    return render(request, "game/levels.html", {"levels": levels})


# LEVEL
def initialize_player_state(user, level):
    """
    Ensure a PlayerLevelState exists for this user and level,
    and copy starting vehicles into PlayerVehicle if needed.
    Optimized to O(n) by minimizing database queries.
    """
    player_state, created = PlayerLevelState.objects.get_or_create(user=user, level=level)

    level_vehicles = list(level.vehicles.select_related("tile").all())

    existing = set(player_state.vehicles.values_list("vehicle_type", "is_enemy"))

    to_create = []

    for v in level_vehicles:
        key = (v.vehicle_type, v.is_enemy)
        if key not in existing:
            to_create.append(
                PlayerVehicle(
                    player_state=player_state,
                    tile=v.tile,
                    vehicle_type=v.vehicle_type,
                    is_enemy=v.is_enemy,
                )
            )

    if to_create:
        PlayerVehicle.objects.bulk_create(to_create)

    return player_state


def get_used_tiles(level):
    return {v.tile_id for v in level.vehicles.all() if v.tile_id}


@login_required(login_url="/login/")
def grid_view(request, level_id):
    """
    Render the grid view for a given level and user.
    This uses PlayerLevelState and PlayerVehicle so that
    each user's progress is tracked independently.
    """
    level = get_object_or_404(Level, pk=level_id)
    player_state = initialize_player_state(request.user, level)
    print(f"gamestarted: {player_state.game_started}")

    # Fetch all tiles for this level
    all_tiles = list(level.tiles.order_by("y", "x"))
    print(f"tile count: {len(all_tiles)}")
    tiles = [t for t in all_tiles if t.terrain_type != "DOCK"]
    dock_tiles = [t for t in all_tiles if t.terrain_type == "DOCK"]

    grid = defaultdict(list)
    for tile in tiles:
        grid[tile.y].append(tile)

    grid = dict(grid)

    # Get this user's player and enemy vehicles
    player_vehicles = player_state.vehicles.filter(is_enemy=False).select_related("tile")
    enemy_vehicles = player_state.vehicles.filter(is_enemy=True).select_related("tile")

    return render(
        request,
        "game/grid.html",
        {
            "level": level,
            "grid": grid,
            "player_vehicles": player_vehicles,
            "enemy_vehicles": enemy_vehicles,
            "game_started": player_state.game_started,
            "dock_tiles": dock_tiles,
        },
    )


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
            tile = get_object_or_404(Tile, pk=tile_id)
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


@login_required(login_url="/login/")
@require_POST
def reset_level(request, level_id):
    """Reset a level for the current user: game_started=False, move player vehicles back to dock."""
    try:
        level = get_object_or_404(Level, pk=level_id)
        player_state, _ = PlayerLevelState.objects.get_or_create(user=request.user, level=level)
        dock_tiles = list(level.tiles.filter(terrain_type="DOCK").order_by("x", "y"))

        reset_player_state(player_state, dock_tiles)

        return JsonResponse({"status": "ok"})
    except Exception as e:
        return json_error(str(e), 500)


@login_required(login_url="/login/")
@require_POST
def reset_level_for_all_users(request, level_id):
    """Reset a level for all players: game_started=False, move player vehicles back to dock."""
    try:
        level = get_object_or_404(Level, pk=level_id)
        # Get all dock tiles for this level
        dock_tiles = list(level.tiles.filter(terrain_type="DOCK").order_by("x", "y"))

        # Loop through all players who have a state for this level
        for player_state in PlayerLevelState.objects.filter(level=level):
            reset_player_state(player_state, dock_tiles)

        return JsonResponse({"status": "ok"})

    except Exception as e:
        return json_error(str(e), 500)


def reset_player_state(player_state, dock_tiles):
    player_state.game_started = False
    player_state.turn_number = 1
    player_state.save()

    vehicles = list(player_state.vehicles.filter(is_enemy=False))
    if len(dock_tiles) < len(vehicles):
        raise ValueError("Not enough dock tiles")

    for vehicle, dock_tile in zip(sorted(vehicles, key=lambda v: v.id), dock_tiles, strict=False):
        vehicle.tile = dock_tile
        vehicle.save()


def json_error(message, status=400):
    return JsonResponse({"status": "error", "message": message}, status=status)
