from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from ..models import Level, PlayerLevelState
from ..services.player_state import reset_player_state
from .api import json_error


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
