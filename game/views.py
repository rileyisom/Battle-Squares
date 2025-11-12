from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from django.shortcuts import render, redirect
from django.contrib import messages

from .models import Level, Tile, StartingVehicle, PlayerLevelState, PlayerVehicle
import json
import random

# AUTHENTICATION
def register_view(request):
    if request.method == "POST":
        print(f"POST data:", request.POST)
        username = request.POST["username"]
        password = request.POST["password"]
        password2 = request.POST["password2"]

        if password != password2:
            messages.error(request, "Passwords do not match.")
        elif User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists.")
        else:
            user = User.objects.create_user(username=username, password=password)
            login(request, user)
            print(f"User {username} registered and logged in")
            return redirect("level-list")  # or your home/game page

    return render(request, "game/register.html")


def login_view(request):
    if request.method == "POST":
        username = request.POST["username"]
        password = request.POST["password"]
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            print(f"User {username} logged in successfully")
            return redirect("level-list")  # or your home/game page
        else:
            print(f"Failed login attempt for {username}")
            messages.error(request, "Invalid username or password.")
    return render(request, "game/login.html")


def logout_view(request):
    logout(request)
    return redirect("login")


# LEVEL LIST
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
    print(f"🧩 initialize_player_state: user={user.username}, created={created}")

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
            print(f"✅ Created PlayerVehicle for {user.username}: {v.vehicle_type} (enemy={v.is_enemy})")

    print(f"Total player vehicles for {user.username}: {player_state.vehicles.count()}")
    return player_state


def get_used_tiles(level):
    return {v.tile_id for v in level.vehicles.all() if v.tile_id}


# def create_vehicle(level, vehicle_type, terrain_filter=None, exclude_tiles=None):
#     """Create a vehicle on a random valid tile."""
#     if exclude_tiles is None:
#         exclude_tiles = set()

#     tiles = level.tiles.all()
#     if terrain_filter:
#         tiles = tiles.filter(terrain_type=terrain_filter)

#     tiles = tiles.exclude(id__in=exclude_tiles)
#     tile = tiles.order_by("?").first()
#     if not tile:
#         print(f"⚠️ No available tiles for {vehicle_type} in level {level.name}")
#         return None

#     vehicle = StartingVehicle.objects.create(level=level, tile=tile, vehicle_type=vehicle_type)
#     exclude_tiles.add(tile.id)
#     print(f"✅ Created {vehicle_type} on tile {tile.id} ({tile.terrain_type})")
#     return vehicle


# def create_player_vehicle(level, vehicle_type, exclude_tiles=None):
#     """Create a player vehicle on a free dock tile."""
#     if exclude_tiles is None:
#         exclude_tiles = set()

#     dock_tiles = level.tiles.filter(terrain_type="DOCK").exclude(id__in=exclude_tiles)
#     if not dock_tiles.exists():
#         print("⚠️ No docks found — placing vehicle randomly.")
#         return create_vehicle(level, vehicle_type, terrain_filter=None, exclude_tiles=exclude_tiles)
#     tile = dock_tiles.order_by("?").first()
#     if not tile:
#         print(f"⚠️ No available dock tile for {vehicle_type} in level {level.name}")
#         return None

#     vehicle = StartingVehicle.objects.create(level=level, tile=tile, vehicle_type=vehicle_type)
#     exclude_tiles.add(tile.id)
#     print(f"🚢 Created {vehicle_type} on dock tile {tile.id}")
#     return vehicle


# def ensure_player_vehicles(level):
#     """Ensure the player has one tank, boat, and plane (placed on dock tiles)."""
#     vehicles = {v.vehicle_type: v for v in level.vehicles.all()}
#     used_tiles = get_used_tiles(level)

#     if "TANK" not in vehicles:
#         vehicles["TANK"] = create_player_vehicle(level, "TANK", exclude_tiles=used_tiles)

#     if "BOAT" not in vehicles:
#         vehicles["BOAT"] = create_player_vehicle(level, "BOAT", exclude_tiles=used_tiles)

#     if "PLANE" not in vehicles:
#         vehicles["PLANE"] = create_player_vehicle(level, "PLANE", exclude_tiles=used_tiles)

#     return vehicles


# def ensure_enemy_vehicles(level):
#     """Ensure the enemy has land, water, and air units."""
#     vehicles = {v.vehicle_type: v for v in level.vehicles.all()}
#     used_tiles = get_used_tiles(level)

#     for vtype, terrain in [("ENEMY_TANK", "LAND"), ("ENEMY_BOAT", "WATER"), ("ENEMY_PLANE", None)]:
#         if vtype not in vehicles:
#             v = create_vehicle(level, vtype, terrain_filter=terrain, exclude_tiles=used_tiles)
#             if v:
#                 vehicles[vtype] = v
#     return vehicles


@login_required
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


@login_required
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


@login_required
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


@login_required
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
