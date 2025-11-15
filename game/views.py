from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.views.generic import FormView
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.shortcuts import render, redirect
from django.contrib import messages
from django.urls import reverse_lazy
from .forms import SimpleUserCreationForm

from .models import Level, Tile, StartingVehicle, PlayerLevelState, PlayerVehicle
import json
import random

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
@login_required(login_url='/login/')
def level_list(request):
    levels = Level.objects.all()
    return render(request, 'game/levels.html', {'levels': levels})


# LEVEL
def initialize_player_state(user, level):
    """
    Ensure a PlayerLevelState exists for this user and level,
    and copy starting vehicles into PlayerVehicle if needed.
    Skips creating enemy vehicles if they already exist.
    """
    player_state, created = PlayerLevelState.objects.get_or_create(user=user, level=level)
    # print(f"🧩 initialize_player_state: user={user.username}, created={created}")

    # Copy starting vehicles if they don't already exist for this player state
    print(f"vehicle count: {level.vehicles.count}")
    for v in level.vehicles.all():
        exists = player_state.vehicles.filter(
            vehicle_type=v.vehicle_type,
            is_enemy=v.is_enemy
        ).exists()
        if not exists:
            PlayerVehicle.objects.create(
                player_state=player_state,
                tile=v.tile,
                vehicle_type=v.vehicle_type,
                is_enemy=v.is_enemy
            )
            # print(f"✅ Created PlayerVehicle for {user.username}: {v.vehicle_type} (enemy={v.is_enemy})")

    # print(f"Total player vehicles for {user.username}: {player_state.vehicles.count()}")
    return player_state


def get_used_tiles(level):
    return {v.tile_id for v in level.vehicles.all() if v.tile_id}


@login_required(login_url='/login/')
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
    tiles = level.tiles.all().order_by("y", "x")

    # Filter out dock tiles for the main grid
    visible_tiles = [tile for tile in tiles if tile.terrain_type != "DOCK"]

    # Build grid as a dict {y-coordinate: [tiles in row]}
    grid = {}
    for tile in visible_tiles:
        grid.setdefault(tile.y, []).append(tile)
    grid = dict(sorted(grid.items()))

    # Get this user's player and enemy vehicles
    player_vehicles = player_state.vehicles.filter(is_enemy=False)
    enemy_vehicles = player_state.vehicles.filter(is_enemy=True)

    # Get dock tiles for display in the dock container
    dock_tiles = list(level.tiles.filter(terrain_type="DOCK").order_by("x", "y"))

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


@login_required(login_url='/login/')
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
        return JsonResponse({"status": "error", "message": "Not found"}, status=404)
    except Exception as e:
        print(f"❌ Error updating vehicle: {e}")
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@login_required(login_url='/login/')
@csrf_exempt
def mark_game_started(request, level_id):
    """Mark the user's PlayerLevelState as started for this level."""
    if request.method == "POST":
        level = get_object_or_404(Level, pk=level_id)
        player_state, _ = PlayerLevelState.objects.get_or_create(user=request.user, level=level)
        player_state.game_started = True
        player_state.save()
        return JsonResponse({"success": True})
    return JsonResponse({"error": "Invalid request"}, status=400)


@login_required(login_url='/login/')
@csrf_exempt
@require_POST
def reset_level(request, level_id):
    """Reset a level for the current user: game_started=False, move player vehicles back to dock."""
    try:
        level = get_object_or_404(Level, pk=level_id)
        player_state, _ = PlayerLevelState.objects.get_or_create(user=request.user, level=level)

        # Reset the game flag for this user
        player_state.game_started = False
        player_state.save()

        # Get all dock tiles for this level
        dock_tiles = list(level.tiles.filter(terrain_type="DOCK").order_by('x', 'y'))
        player_vehicles = list(player_state.vehicles.filter(is_enemy=False))

        if len(dock_tiles) < len(player_vehicles):
            return JsonResponse({
                "status": "error",
                "message": f"Not enough dock tiles ({len(dock_tiles)}) for player vehicles ({len(player_vehicles)})"
            }, status=500)

        # Move each player vehicle back to a dock tile
        for vehicle, dock_tile in zip(player_vehicles, dock_tiles):
            vehicle.tile = dock_tile
            vehicle.save()

        return JsonResponse({"status": "ok"})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)
    
@login_required(login_url='/login/')
@csrf_exempt
@require_POST
def reset_level_for_all_users(request, level_id):
    """Reset a level for all players: game_started=False, move player vehicles back to dock."""
    try:
        level = get_object_or_404(Level, pk=level_id)
        # Get all dock tiles for this level
        dock_tiles = list(level.tiles.filter(terrain_type="DOCK").order_by('x', 'y'))

        # Loop through all players who have a state for this level
        for player_state in PlayerLevelState.objects.filter(level=level):
            player_state.game_started = False
            player_state.turn_number = 1
            player_state.save()

            player_vehicles = list(player_state.vehicles.filter(is_enemy=False))
            if len(dock_tiles) < len(player_vehicles):
                return JsonResponse({
                    "status": "error",
                    "message": f"Not enough dock tiles ({len(dock_tiles)}) for player vehicles ({len(player_vehicles)})"
                }, status=500)

            # Move each player vehicle back to a dock tile
            for vehicle, dock_tile in zip(player_vehicles, dock_tiles):
                vehicle.tile = dock_tile
                vehicle.save()

        return JsonResponse({"status": "ok"})

    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)
