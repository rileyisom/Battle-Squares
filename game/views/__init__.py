# AUTHENTICATION
# API
from .api import (
    attack,
    end_turn,
    mark_game_started,
    move_vehicle,
    update_vehicle_position,
    vehicle_actions,
)
from .auth import RegisterView

# GRID
from .grid import grid_view, initialize_player_state

# LEVELS
from .levels import level_list

# RESET FUNCTIONS
from .resets import reset_level, reset_level_for_all_users

# Optional: export all for convenient wildcard imports
__all__ = [
    "RegisterView",
    "level_list",
    "grid_view",
    "initialize_player_state",
    "update_vehicle_position",
    "mark_game_started",
    "reset_level",
    "reset_level_for_all_users",
    "vehicle_actions",
    "move_vehicle",
    "attack",
    "end_turn",
]
