import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from ..models import Level, PlayerLevelState, PlayerVehicle, Tile


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


def json_error(message, status=400):
    return JsonResponse({"status": "error", "message": message}, status=status)
