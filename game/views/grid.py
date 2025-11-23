from collections import defaultdict

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from ..models import Level
from ..services.player_state import initialize_player_state


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
        "game/grid/grid.html",
        {
            "level": level,
            "grid": grid,
            "player_vehicles": player_vehicles,
            "enemy_vehicles": enemy_vehicles,
            "game_started": player_state.game_started,
            "dock_tiles": dock_tiles,
        },
    )
