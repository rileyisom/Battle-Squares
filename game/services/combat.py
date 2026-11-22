import math

from ..models import PlayerLevelState, PlayerVehicle

# Move ranges were cut from the pre-Chebyshev values (2/3/4) because switching
# metrics doubled the reachable area at the same range number. TANK was then
# put back to 2 after playtesting: at 1 it could only shift a single tile per
# turn and took nine turns to cross a 10x10 board, which made it feel inert.
# It now ties BOAT on raw area, and that is fine — one is land-locked and the
# other water-locked, so they rarely contest the same tiles, and their real
# identities are reach (1 vs 2) and damage (25 vs 20), not mobility.
VEHICLE_STATS = {
    "TANK": {"max_health": 100, "move_range": 2, "attack_range": 1, "damage": 25},
    "BOAT": {"max_health": 100, "move_range": 2, "attack_range": 2, "damage": 20},
    "PLANE": {"max_health": 75, "move_range": 3, "attack_range": 2, "damage": 30},
}

# --- Damage tuning -------------------------------------------------------
# Damage is a *band*, not a fixed number. Tactics (type matchup, terrain,
# range, flanking) decide where the band's ceiling sits and how wide it is;
# the attacker's aim accuracy decides where inside the band the shot lands.
# A strong position yields a high ceiling and a tight band, so even a sloppy
# shot lands well. A weak one yields a wide band with a low floor — good aim
# can rescue it, but it's a gamble.

CRIT_MULTIPLIER = 1.25  # applied to the ceiling, so crits stay in band's orbit
PEAK_BONUS = 1.2  # a perfectly aimed shot exceeds the old flat damage by this much

MATCHUP_MULTIPLIER = 1.5  # attacker counters the defender
MATCHUP_PENALTY = 0.75  # defender counters the attacker

# Each base type counters exactly one other, in a cycle.
COUNTERS = {"TANK": "PLANE", "PLANE": "BOAT", "BOAT": "TANK"}

# Damage reduction granted to a defender standing on this terrain. Planes are
# airborne and ignore cover entirely — that, plus their lower HP, is what
# distinguishes them defensively. DOCK is deliberately absent: dock tiles are
# only a pre-game staging area for placing vehicles and are never part of the
# board once a battle starts, so they carry no combat meaning.
TERRAIN_COVER = {"WATER": 0.0, "LAND": 0.15}

# Band width, as a fraction below the ceiling, interpolated by shot quality.
MAX_SPREAD = 0.60  # worst-case shot: anything from 40% of ceiling upward
MIN_SPREAD = 0.15  # best-case shot: reliably near the ceiling

# Share of the top of the accuracy range that counts as a critical hit, also
# interpolated by shot quality — good positioning widens the crit window.
MIN_CRIT_ZONE = 0.03
MAX_CRIT_ZONE = 0.22

# Contribution of each factor to overall shot quality. Must sum to 1.0.
QUALITY_WEIGHTS = {"range": 0.30, "matchup": 0.30, "cover": 0.20, "flank": 0.20}

# The worst score each factor can contribute. Needed because no real shot ever
# scores 0 overall (a neutral matchup alone is 0.5), so the raw weighted score
# only spans ~0.33-1.0. Normalizing against that range is what lets the spread
# and crit-window knobs above actually reach their endpoints in play.
QUALITY_FACTOR_MIN = {
    "range": 0.0,
    "matchup": 0.25,
    "cover": 1.0 - max(TERRAIN_COVER.values()),
    "flank": 0.5,
}
_QUALITY_RAW_MIN = sum(QUALITY_WEIGHTS[k] * QUALITY_FACTOR_MIN[k] for k in QUALITY_WEIGHTS)

# Accuracy of an auto-resolved shot: lands mid-band. Used when no aim minigame
# has run (accessibility/fast-forward) and as the enemy AI's skill level, which
# is the natural difficulty dial — raise it on later levels.
DEFAULT_ACCURACY = 0.5
ENEMY_ACCURACY = 0.5


def base_type(vehicle_type):
    """Normalize e.g. ENEMY_TANK -> TANK to key into VEHICLE_STATS."""
    return vehicle_type.replace("ENEMY_", "")


def vehicle_stats(vehicle_type):
    return VEHICLE_STATS[base_type(vehicle_type)]


def manhattan(tile_a, tile_b):
    """Orthogonal steps only — a diagonal neighbour is two tiles away."""
    return abs(tile_a.x - tile_b.x) + abs(tile_a.y - tile_b.y)


def chebyshev(tile_a, tile_b):
    """King moves — a diagonal neighbour is one tile away, same as orthogonal."""
    return max(abs(tile_a.x - tile_b.x), abs(tile_a.y - tile_b.y))


# The metric behind all movement, targeting and AI distance checks. Chebyshev
# because a diagonally adjacent enemy *looks* adjacent on the board, and under
# Manhattan it silently wasn't — players read that as the game ignoring their
# clicks. Swap this alias to `manhattan` to go back; nothing else needs to
# change, but keep every caller on the same metric or the enemy AI will
# misjudge its own range.
distance = chebyshev


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
        if distance(origin, tile) > stats["move_range"]:
            continue
        if not _terrain_allowed(vehicle.vehicle_type, tile.terrain_type):
            continue
        moves.append(tile)
    return moves


def tiles_in_attack_range(vehicle, all_tiles):
    """
    Every board tile this vehicle could strike from where it stands.

    Shown in the UI so the reach of an attack is visible even when nothing is
    standing in it, which is what makes the shape of a unit's range legible.
    """
    stats = vehicle_stats(vehicle.vehicle_type)
    origin = vehicle.tile
    if origin is None:
        return []
    return [
        tile
        for tile in all_tiles
        if tile.id != origin.id and distance(origin, tile) <= stats["attack_range"]
    ]


def valid_attack_targets(vehicle, opposing_vehicles):
    stats = vehicle_stats(vehicle.vehicle_type)
    origin = vehicle.tile
    return [
        target
        for target in opposing_vehicles
        if target.tile and distance(origin, target.tile) <= stats["attack_range"]
    ]


def _lerp(a, b, t):
    return a + (b - a) * t


def parse_accuracy(value):
    """
    Validate an untrusted aim accuracy from a request body.

    Accuracy is a single normalized float: 0.0 is the worst possible shot, 1.0
    a perfect one. Keeping it abstract is what makes the aim minigame
    pluggable — any future minigame only has to produce this one number, and
    the server never has to know which one ran. Raises ValueError on garbage.
    """
    if value is None:
        return DEFAULT_ACCURACY
    # bool is an int subclass, so reject it explicitly.
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Accuracy must be a number between 0 and 1.")
    if not math.isfinite(value):
        raise ValueError("Accuracy must be a number between 0 and 1.")
    return min(max(float(value), 0.0), 1.0)


def _cover(defender):
    """Damage reduction from the terrain the defender is standing on."""
    if base_type(defender.vehicle_type) == "PLANE" or defender.tile is None:
        return 0.0
    return TERRAIN_COVER.get(defender.tile.terrain_type, 0.0)


def _matchup(attacker_type, defender_type):
    """Returns (damage_multiplier, quality_score) for this type pairing."""
    attacker_kind = base_type(attacker_type)
    defender_kind = base_type(defender_type)
    if COUNTERS[attacker_kind] == defender_kind:
        return MATCHUP_MULTIPLIER, 1.0
    if COUNTERS[defender_kind] == attacker_kind:
        return MATCHUP_PENALTY, 0.25
    return 1.0, 0.5


def _flank_score(attacker, defender, allies):
    """Allies of the attacker adjacent to the defender make the shot easier."""
    if defender.tile is None:
        return 0.5
    adjacent = sum(
        1
        for ally in allies
        if ally.pk != attacker.pk and ally.tile and distance(ally.tile, defender.tile) == 1
    )
    if adjacent >= 2:
        return 1.0
    if adjacent == 1:
        return 0.75
    return 0.5


def damage_band(attacker, defender, allies=()):
    """
    The damage envelope for one attack, before aim is applied.

    This is the single source of truth for both the forecast shown in the UI
    and the damage actually dealt, so the two can never drift apart. `allies`
    are the attacker's own vehicles, used for the flanking bonus; omit them
    and flanking scores neutral.
    """
    stats = vehicle_stats(attacker.vehicle_type)
    matchup_mult, matchup_q = _matchup(attacker.vehicle_type, defender.vehicle_type)
    cover = _cover(defender)

    attack_range = max(stats["attack_range"], 1)
    if attacker.tile and defender.tile:
        gap = distance(attacker.tile, defender.tile)
    else:
        gap = attack_range
    # Point blank is the cleanest shot; the edge of your range is the worst.
    range_q = min(max(1.0 - (gap - 1) / attack_range, 0.0), 1.0)

    raw_quality = (
        QUALITY_WEIGHTS["range"] * range_q
        + QUALITY_WEIGHTS["matchup"] * matchup_q
        + QUALITY_WEIGHTS["cover"] * (1.0 - cover)
        + QUALITY_WEIGHTS["flank"] * _flank_score(attacker, defender, allies)
    )
    quality = (raw_quality - _QUALITY_RAW_MIN) / (1.0 - _QUALITY_RAW_MIN)
    quality = min(max(quality, 0.0), 1.0)

    peak = stats["damage"] * PEAK_BONUS * matchup_mult * (1.0 - cover)
    spread = _lerp(MAX_SPREAD, MIN_SPREAD, quality)

    max_damage = max(1, round(peak))
    min_damage = min(max(1, round(peak * (1.0 - spread))), max_damage)

    return {
        "min": min_damage,
        "max": max_damage,
        "crit_damage": max(1, round(peak * CRIT_MULTIPLIER)),
        "crit_zone": _lerp(MIN_CRIT_ZONE, MAX_CRIT_ZONE, quality),
        "quality": round(quality, 3),
    }


def resolve_damage(band, accuracy):
    """Map a normalized aim accuracy onto a band. Returns {damage, is_crit}."""
    accuracy = min(max(accuracy, 0.0), 1.0)
    if accuracy >= 1.0 - band["crit_zone"]:
        return {"damage": band["crit_damage"], "is_crit": True}
    damage = _lerp(band["min"], band["max"], accuracy)
    return {"damage": max(1, round(damage)), "is_crit": False}


def attack_forecast(attacker, defender, allies=()):
    """
    What the UI shows before the player commits to a shot.

    Derived from the same `damage_band` used to resolve the attack, so the
    forecast can never promise something the resolution won't honour.
    `crit_window` is the share of the aim range that crits — with a skill-based
    minigame it's the size of the window you have to hit, not a probability.
    """
    band = damage_band(attacker, defender, allies)

    if band["min"] >= defender.health:
        lethality = "certain"
    elif band["max"] >= defender.health:
        lethality = "likely"
    elif band["crit_damage"] >= defender.health:
        lethality = "crit_only"
    else:
        lethality = "no"

    return {
        "target_id": defender.id,
        "min": band["min"],
        "max": band["max"],
        "crit_damage": band["crit_damage"],
        "crit_window": round(band["crit_zone"], 3),
        "quality": band["quality"],
        "target_health": defender.health,
        "lethality": lethality,
    }


def apply_damage(attacker, defender, accuracy=DEFAULT_ACCURACY, allies=()):
    """
    Resolve one attack and persist the result.

    Returns the full outcome so callers can report damage, crits and the band
    that produced them. Deletes the defender if it was destroyed.
    """
    band = damage_band(attacker, defender, allies)
    outcome = resolve_damage(band, accuracy)

    defender.health -= outcome["damage"]
    destroyed = defender.health <= 0
    if destroyed:
        defender.delete()
    else:
        defender.save()

    return {
        "damage": outcome["damage"],
        "is_crit": outcome["is_crit"],
        "destroyed": destroyed,
        "target_health": 0 if destroyed else defender.health,
        "band": band,
    }


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

        nearest = min(player_vehicles, key=lambda p: distance(enemy.tile, p.tile))
        targets = valid_attack_targets(enemy, [nearest])

        if targets:
            # Enemies take the identical resolution path as the player; their
            # fixed accuracy is the difficulty dial.
            apply_damage(enemy, nearest, accuracy=ENEMY_ACCURACY, allies=enemy_vehicles)
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

        current_distance = distance(enemy.tile, nearest.tile)
        closer = [c for c in candidates if distance(c, nearest.tile) < current_distance]
        if not closer:
            continue

        best_tile = min(closer, key=lambda t: distance(t, nearest.tile))
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
