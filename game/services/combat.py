from ..models import PlayerLevelState, PlayerVehicle

VEHICLE_STATS = {
    "TANK": {"max_health": 100, "move_range": 2, "attack_range": 1, "damage": 25},
    "BOAT": {"max_health": 100, "move_range": 3, "attack_range": 2, "damage": 20},
    "PLANE": {"max_health": 75, "move_range": 4, "attack_range": 2, "damage": 30},
}


def base_type(vehicle_type):
    """Normalize e.g. ENEMY_TANK -> TANK to key into VEHICLE_STATS."""
    return vehicle_type.replace("ENEMY_", "")


def vehicle_stats(vehicle_type):
    return VEHICLE_STATS[base_type(vehicle_type)]


def manhattan(tile_a, tile_b):
    return abs(tile_a.x - tile_b.x) + abs(tile_a.y - tile_b.y)


def _terrain_allowed(vehicle_type, terrain_type):
    kind = base_type(vehicle_type)
    if kind == "TANK":
        return terrain_type in ("LAND", "DOCK")
    if kind == "BOAT":
        return terrain_type in ("WATER", "DOCK")
    return True  # PLANE can go anywhere


def valid_move_tiles(vehicle, all_tiles, occupied_tile_ids):
    """all_tiles: iterable of Tile (excluding DOCK tiles - movement is on-board only)."""
    stats = vehicle_stats(vehicle.vehicle_type)
    origin = vehicle.tile
    moves = []
    for tile in all_tiles:
        if tile.id == origin.id or tile.id in occupied_tile_ids:
            continue
        if manhattan(origin, tile) > stats["move_range"]:
            continue
        if not _terrain_allowed(vehicle.vehicle_type, tile.terrain_type):
            continue
        moves.append(tile)
    return moves


def valid_attack_targets(vehicle, opposing_vehicles):
    stats = vehicle_stats(vehicle.vehicle_type)
    origin = vehicle.tile
    return [
        target
        for target in opposing_vehicles
        if target.tile and manhattan(origin, target.tile) <= stats["attack_range"]
    ]


def apply_damage(attacker, defender):
    """Returns True if defender was destroyed."""
    stats = vehicle_stats(attacker.vehicle_type)
    defender.health -= stats["damage"]
    if defender.health <= 0:
        defender.delete()
        return True
    defender.save()
    return False


def check_game_over(player_state):
    """Evaluate and persist WON/LOST status. Returns the resulting status string."""
    if player_state.status != PlayerLevelState.Status.IN_PROGRESS:
        return player_state.status

    enemies_left = player_state.vehicles.filter(is_enemy=True).exists()
    players_left = player_state.vehicles.filter(is_enemy=False).exists()

    if not enemies_left:
        player_state.status = PlayerLevelState.Status.WON
    elif not players_left:
        player_state.status = PlayerLevelState.Status.LOST
    else:
        return player_state.status

    player_state.save()
    return player_state.status


def run_enemy_turn(player_state):
    """Move/attack with every enemy vehicle, one simple action each."""
    board_tiles = list(player_state.level.tiles.exclude(terrain_type="DOCK"))

    enemy_vehicles = list(
        player_state.vehicles.filter(is_enemy=True).select_related("tile").order_by("id")
    )

    for enemy in enemy_vehicles:
        if player_state.status != PlayerLevelState.Status.IN_PROGRESS:
            break
        if enemy.tile is None:
            continue

        player_vehicles = list(
            player_state.vehicles.filter(is_enemy=False).select_related("tile")
        )
        if not player_vehicles:
            break

        nearest = min(player_vehicles, key=lambda p: manhattan(enemy.tile, p.tile))
        targets = valid_attack_targets(enemy, [nearest])

        if targets:
            apply_damage(enemy, nearest)
            check_game_over(player_state)
            continue

        occupied_tile_ids = {
            v.tile_id
            for v in player_state.vehicles.exclude(pk=enemy.pk)
            if v.tile_id is not None
        }
        candidates = valid_move_tiles(enemy, board_tiles, occupied_tile_ids)
        if not candidates:
            continue

        current_distance = manhattan(enemy.tile, nearest.tile)
        closer = [c for c in candidates if manhattan(c, nearest.tile) < current_distance]
        if not closer:
            continue

        best_tile = min(closer, key=lambda t: manhattan(t, nearest.tile))
        enemy.tile = best_tile
        enemy.save()

    check_game_over(player_state)


def serialize_board_state(player_state):
    vehicles = player_state.vehicles.select_related("tile").all()
    return {
        "status": player_state.status,
        "current_phase": player_state.current_phase,
        "turn_number": player_state.turn_number,
        "vehicles": [
            {
                "id": v.id,
                "tile_id": v.tile_id,
                "health": v.health,
                "max_health": vehicle_stats(v.vehicle_type)["max_health"],
                "is_enemy": v.is_enemy,
                "has_acted": v.has_acted,
            }
            for v in vehicles
        ],
    }
