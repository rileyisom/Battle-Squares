from ..models import PlayerLevelState, PlayerVehicle
from .combat import vehicle_stats


# LEVEL
def initialize_player_state(user, level):
    """
    Ensure a PlayerLevelState exists for this user and level,
    and copy starting vehicles into PlayerVehicle if needed.
    Optimized to O(n) by minimizing database queries.
    """
    player_state, created = PlayerLevelState.objects.get_or_create(user=user, level=level)

    if player_state.game_started:
        # Once a battle is underway, a missing (vehicle_type, is_enemy) row means
        # that vehicle was destroyed in combat, not that it was never created.
        # Don't resurrect it just because the player reloaded the page.
        return player_state

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


def reset_player_state(player_state, dock_tiles):
    """
    Reset a player's level state back to pre-battle: clears turn/phase/status,
    restores every vehicle's health and dock/starting position (recreating any
    that were destroyed in battle), and clears the has_acted flag.
    """
    player_state.game_started = False
    player_state.turn_number = 1
    player_state.current_phase = PlayerLevelState.Phase.PLAYER
    player_state.status = PlayerLevelState.Status.IN_PROGRESS
    player_state.save()

    starting_vehicles = list(player_state.level.vehicles.select_related("tile").all())
    existing = {(v.vehicle_type, v.is_enemy): v for v in player_state.vehicles.all()}

    to_create = []
    for sv in starting_vehicles:
        max_health = vehicle_stats(sv.vehicle_type)["max_health"]
        pv = existing.get((sv.vehicle_type, sv.is_enemy))
        if pv:
            pv.tile = sv.tile
            pv.health = max_health
            pv.has_acted = False
            pv.save()
        else:
            to_create.append(
                PlayerVehicle(
                    player_state=player_state,
                    tile=sv.tile,
                    vehicle_type=sv.vehicle_type,
                    is_enemy=sv.is_enemy,
                    health=max_health,
                )
            )
    if to_create:
        PlayerVehicle.objects.bulk_create(to_create)

    vehicles = list(player_state.vehicles.filter(is_enemy=False))
    if len(dock_tiles) < len(vehicles):
        raise ValueError("Not enough dock tiles")

    for vehicle, dock_tile in zip(sorted(vehicles, key=lambda v: v.id), dock_tiles, strict=False):
        vehicle.tile = dock_tile
        vehicle.save()
