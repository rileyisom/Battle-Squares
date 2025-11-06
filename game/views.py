from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from .models import Level, Tile, Vehicle
import json
import random


def level_list(request):
    levels = Level.objects.all()
    return render(request, 'game/levels.html', {'levels': levels})


def get_used_tiles(level):
    return {v.tile_id for v in level.vehicles.all() if v.tile_id}


def create_vehicle(level, vehicle_type, terrain_filter=None, exclude_tiles=None):
    """Create a vehicle on a random valid tile."""
    if exclude_tiles is None:
        exclude_tiles = set()

    tiles = level.tiles.all()
    if terrain_filter:
        tiles = tiles.filter(terrain_type=terrain_filter)

    tiles = tiles.exclude(id__in=exclude_tiles)
    tile = tiles.order_by("?").first()
    if not tile:
        print(f"⚠️ No available tiles for {vehicle_type} in level {level.name}")
        return None

    vehicle = Vehicle.objects.create(level=level, tile=tile, vehicle_type=vehicle_type)
    exclude_tiles.add(tile.id)
    print(f"✅ Created {vehicle_type} on tile {tile.id} ({tile.terrain_type})")
    return vehicle


def create_player_vehicle(level, vehicle_type, exclude_tiles=None):
    """Create a player vehicle on a free dock tile."""
    if exclude_tiles is None:
        exclude_tiles = set()

    dock_tiles = level.tiles.filter(terrain_type="DOCK").exclude(id__in=exclude_tiles)
    if not dock_tiles.exists():
        print("⚠️ No docks found — placing vehicle randomly.")
        return create_vehicle(level, vehicle_type, terrain_filter=None, exclude_tiles=exclude_tiles)
    tile = dock_tiles.order_by("?").first()
    if not tile:
        print(f"⚠️ No available dock tile for {vehicle_type} in level {level.name}")
        return None

    vehicle = Vehicle.objects.create(level=level, tile=tile, vehicle_type=vehicle_type)
    exclude_tiles.add(tile.id)
    print(f"🚢 Created {vehicle_type} on dock tile {tile.id}")
    return vehicle


def ensure_player_vehicles(level):
    """Ensure the player has one tank, boat, and plane (placed on dock tiles)."""
    vehicles = {v.vehicle_type: v for v in level.vehicles.all()}
    used_tiles = get_used_tiles(level)

    if "TANK" not in vehicles:
        vehicles["TANK"] = create_player_vehicle(level, "TANK", exclude_tiles=used_tiles)

    if "BOAT" not in vehicles:
        vehicles["BOAT"] = create_player_vehicle(level, "BOAT", exclude_tiles=used_tiles)

    if "PLANE" not in vehicles:
        vehicles["PLANE"] = create_player_vehicle(level, "PLANE", exclude_tiles=used_tiles)

    return vehicles


def ensure_enemy_vehicles(level):
    """Ensure the enemy has land, water, and air units."""
    vehicles = {v.vehicle_type: v for v in level.vehicles.all()}
    used_tiles = get_used_tiles(level)

    for vtype, terrain in [("ENEMY_TANK", "LAND"), ("ENEMY_BOAT", "WATER"), ("ENEMY_PLANE", None)]:
        if vtype not in vehicles:
            v = create_vehicle(level, vtype, terrain_filter=terrain, exclude_tiles=used_tiles)
            if v:
                vehicles[vtype] = v
    return vehicles


def grid_view(request, level_id):
    """Render the grid view for a given level."""
    level = get_object_or_404(Level, pk=level_id)
    tiles = level.tiles.all().order_by("y", "x")

    # Ensure vehicles exist
    ensure_player_vehicles(level)
    ensure_enemy_vehicles(level)

    # Filter out dock tiles so they aren't rendered
    visible_tiles = [tile for tile in tiles if tile.terrain_type != "DOCK"]

    # Build grid dict only from visible tiles
    grid = {}
    for tile in visible_tiles:
        grid.setdefault(tile.y, []).append(tile)
    grid = dict(sorted(grid.items()))

    # Separate player and enemy vehicles
    player_vehicles = level.vehicles.filter(vehicle_type__in=["TANK", "BOAT", "PLANE"])
    enemy_vehicles = level.vehicles.exclude(vehicle_type__in=["TANK", "BOAT", "PLANE"])
    dock_tiles = list(level.tiles.filter(terrain_type="DOCK").order_by('x', 'y'))

    return render(
        request,
        "game/grid.html",
        {
            "level": level,
            "grid": grid,
            "player_vehicles": player_vehicles,
            "enemy_vehicles": enemy_vehicles,
            "game_started": level.game_started,
            "dock_tiles": dock_tiles,
        },
    )


@require_POST
def update_vehicle_position(request, vehicle_id):
    """Handles AJAX updates for moving player vehicles."""
    try:
        data = json.loads(request.body)
        tile_id = data.get("tile_id")
        vehicle = Vehicle.objects.get(pk=vehicle_id)
        if tile_id:
            tile = Tile.objects.get(pk=tile_id)
            vehicle.tile = tile
        else:
            vehicle.tile = None
        vehicle.save()
        vehicle.save()
        print(f"✅ Updated {vehicle.vehicle_type} -> tile {tile_id}")
        return JsonResponse({"status": "ok"})
    except (Vehicle.DoesNotExist, Tile.DoesNotExist):
        return JsonResponse({"status": "error", "message": "Not found"}, status=404)
    except Exception as e:
        print(f"❌ Error updating vehicle: {e}")
        return JsonResponse({"status": "error", "message": str(e)}, status=500)
    
@csrf_exempt
def mark_game_started(request, level_id):
    if request.method == "POST":
        level = get_object_or_404(Level, pk=level_id)
        level.game_started = True
        level.save()
        return JsonResponse({"success": True})
    return JsonResponse({"error": "Invalid request"}, status=400)

@csrf_exempt
@require_POST
def reset_level(request, level_id):
    """Reset a level: game_started=False, move player vehicles back to dock."""
    try:
        level = get_object_or_404(Level, pk=level_id)
        # Reset the game flag
        level.game_started = False
        level.save()

        # Get all dock tiles for this level (terrain_type='DOCK')
        dock_tiles = list(level.tiles.filter(terrain_type="DOCK").order_by('x', 'y'))
        player_vehicles = list(level.vehicles.filter(vehicle_type__in=["TANK", "BOAT", "PLANE"]))

        if len(dock_tiles) < len(player_vehicles):
            return JsonResponse({
                "status": "error",
                "message": f"Not enough dock tiles ({len(dock_tiles)}) for player vehicles ({len(player_vehicles)})"
            }, status=500)

        # Move each player vehicle to a dock tile
        for vehicle, dock_tile in zip(player_vehicles, dock_tiles):
            vehicle.tile = dock_tile
            vehicle.save()

        return JsonResponse({"status": "ok"})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)
