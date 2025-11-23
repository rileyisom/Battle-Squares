from ..models import PlayerLevelState, PlayerVehicle


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
