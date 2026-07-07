"""
Sets up known DB states for the Playwright combat-loop regression scripts in
this folder, against whatever database the dev server is configured to use
(see .env). Uses the 'combattest' user and Level 1 (id=24) so results are
reproducible run to run.

Usage (from repo root, with the project venv):
    ./.venv/Scripts/python.exe e2e/setup_scenarios.py <scenario>

Scenarios:
    placed       - 3 vehicles placed in the player zone, game started, full
                   3-enemy roster untouched. Used by combat_check.js.
    tight_win    - a lone ENEMY_TANK placed directly adjacent to the player
                   TANK so a handful of attacks reaches the win condition.
                   Used by win_check.js.
    mid_battle   - game started, player TANK damaged, turn 3, still
                   IN_PROGRESS. Used by reset_check.js to prove Reset Game
                   restores a battle in progress (not just a finished one).
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "battlesquares.settings")

import django  # noqa: E402

django.setup()

from django.contrib.auth import get_user_model  # noqa: E402

from game.models import Level, PlayerLevelState  # noqa: E402
from game.services.player_state import initialize_player_state, reset_player_state  # noqa: E402

LEVEL_ID = 24
USERNAME = "combattest"
PASSWORD = "***REMOVED-PASSWORD***"


def get_test_state():
    User = get_user_model()
    user, _ = User.objects.get_or_create(username=USERNAME)
    user.set_password(PASSWORD)
    user.is_active = True
    user.save()

    level = Level.objects.get(pk=LEVEL_ID)
    ps = initialize_player_state(user, level)
    dock_tiles = list(level.tiles.filter(terrain_type="DOCK").order_by("x", "y"))
    reset_player_state(ps, dock_tiles)
    return ps, level, dock_tiles


def place_in_zone(ps, level):
    bottom_start = level.height - int(level.height * 0.4)
    zone_tiles = list(level.tiles.filter(y__gte=bottom_start).exclude(terrain_type="DOCK"))
    land = next(t for t in zone_tiles if t.terrain_type == "LAND")
    water = next(t for t in zone_tiles if t.terrain_type == "WATER" and t.id != land.id)
    plane_tile = next(
        t for t in zone_tiles if t.terrain_type != "WATER" and t.id not in (land.id, water.id)
    )

    tank = ps.vehicles.get(vehicle_type="TANK")
    boat = ps.vehicles.get(vehicle_type="BOAT")
    plane = ps.vehicles.get(vehicle_type="PLANE")
    tank.tile, boat.tile, plane.tile = land, water, plane_tile
    tank.save()
    boat.save()
    plane.save()
    return tank, land


def scenario_placed():
    ps, level, _ = get_test_state()
    place_in_zone(ps, level)
    ps.game_started = True
    ps.save()
    print("Scenario 'placed' ready: 3v3, vehicles placed, game started.")


def scenario_tight_win():
    ps, level, _ = get_test_state()
    ps.vehicles.filter(is_enemy=True).exclude(vehicle_type="ENEMY_TANK").delete()
    enemy_tank = ps.vehicles.get(is_enemy=True)

    tank, land = place_in_zone(ps, level)

    adjacent = next(
        t
        for t in level.tiles.exclude(terrain_type="DOCK")
        if t.terrain_type == "LAND" and abs(t.x - land.x) + abs(t.y - land.y) == 1
    )
    enemy_tank.tile = adjacent
    enemy_tank.health = 100
    enemy_tank.save()

    ps.game_started = True
    ps.save()
    print(f"Scenario 'tight_win' ready: player TANK at ({land.x},{land.y}), "
          f"lone ENEMY_TANK adjacent at ({adjacent.x},{adjacent.y}).")


def scenario_mid_battle():
    ps, level, _ = get_test_state()
    place_in_zone(ps, level)

    tank = ps.vehicles.get(vehicle_type="TANK")
    tank.health = 40
    tank.save()

    ps.game_started = True
    ps.turn_number = 3
    ps.save()
    print("Scenario 'mid_battle' ready: game started, player TANK at 40 hp, turn 3.")


SCENARIOS = {
    "placed": scenario_placed,
    "tight_win": scenario_tight_win,
    "mid_battle": scenario_mid_battle,
}


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in SCENARIOS:
        print(f"Usage: python setup_scenarios.py <{'|'.join(SCENARIOS)}>")
        sys.exit(1)
    SCENARIOS[sys.argv[1]]()
