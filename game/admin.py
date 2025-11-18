# admin.py (refactored)
from collections import defaultdict
import random

from django.contrib import admin
from django.db import transaction
from django.utils.html import format_html

from .models import Level, Tile, StartingVehicle, PlayerVehicle, PlayerLevelState


@admin.register(Level)
class LevelAdmin(admin.ModelAdmin):
    list_display = ("name", "width", "height", "tile_count")
    actions = ["generate_full_level", "randomize_enemy_vehicles", "reset_all_players"]
    readonly_fields = ("map_preview",)
    fields = ("name", "width", "height", "map_preview")

    # Use raw_id_fields for large related sets (nice UX/performance)
    raw_id_fields = ()

    # ----------------------
    # Save hook
    # ----------------------
    def save_model(self, request, obj, form, change):
        """
        If a new Level is created, auto-generate tiles & starting vehicles.
        If width/height change on an existing level, we *could* regenerate;
        for now we only auto-generate on create to match previous behavior.
        """
        super().save_model(request, obj, form, change)

        if not change:
            # New level — generate content (no message_user here; action will do that)
            self._generate_full_level(obj)

    # ----------------------
    # Map preview
    # ----------------------
    @admin.display(description="Map Preview")
    def map_preview(self, obj):
        """
        Render a compact HTML preview of the map inside the admin.
        Uses select_related where appropriate to avoid N+1 queries.
        """
        TILE_SIZE = 22

        COLORS = {
            "LAND": "#4CAF50",
            "WATER": "#2196F3",
            "DOCK": "#9E9E9E",
        }

        # Icon map: (vehicle_type, is_enemy) -> icon
        VEHICLE_ICON = {
            ("TANK", False): "🟩T",
            ("BOAT", False): "🟦B",
            ("PLANE", False): "🟨P",
            ("ENEMY_TANK", True): "🔴T",
            ("ENEMY_BOAT", True): "🔵B",
            ("ENEMY_PLANE", True): "⚫P",
        }

        # Load tiles and vehicles efficiently
        tiles_qs = obj.tiles.all()
        tiles = {(t.x, t.y): t for t in tiles_qs}

        # Use select_related to avoid fetching tile per vehicle
        vehicles_qs = obj.vehicles.select_related("tile").all()
        vehicles = {}
        for v in vehicles_qs:
            if v.tile:
                vehicles[(v.tile.x, v.tile.y)] = v

        html = ['<div style="border:1px solid #ccc; display:inline-block;">']
        for y in range(obj.height):
            html.append('<div style="display:flex;">')
            for x in range(obj.width):
                tile = tiles.get((x, y))
                color = COLORS.get(tile.terrain_type, "black") if tile else "black"
                vehicle = vehicles.get((x, y))

                if vehicle:
                    key = (vehicle.vehicle_type, vehicle.is_enemy)
                    icon = VEHICLE_ICON.get(key, "❓")
                    html.append(
                        f'<div style="width:{TILE_SIZE}px; height:{TILE_SIZE}px; '
                        f'background:{color}; border:2px solid #000; '
                        f'display:flex; justify-content:center; align-items:center; '
                        f'font-size:14px; font-weight:bold;">{icon}</div>'
                    )
                else:
                    html.append(
                        f'<div style="width:{TILE_SIZE}px; height:{TILE_SIZE}px; '
                        f'background:{color};"></div>'
                    )
            html.append('</div>')
        html.append('</div>')
        return format_html(''.join(html))

    def tile_count(self, obj):
        return obj.tiles.count()
    tile_count.short_description = "Tiles"

    # ----------------------
    # Core generator (single-level) — extracted helper
    # ----------------------
    def _generate_full_level(self, level):
        """
        Generate tiles and starting vehicles for a single level.
        This runs inside the admin and is used by both save_model and the admin action.
        """
        width, height = level.width, level.height

        # Use a transaction to avoid partial state if something fails
        with transaction.atomic():
            # Remove existing tiles & vehicles (starting vehicles)
            # Note: This preserves PlayerVehicle / PlayerLevelState records; we're regenerating the starting-level content.
            level.tiles.all().delete()
            level.vehicles.all().delete()

            # 1) Generate base grid
            grid = [["WATER" for _ in range(width)] for _ in range(height)]
            num_islands = max(1, (width * height) // 50)
            for _ in range(num_islands):
                island_x = random.randint(1, max(1, width - 2))
                island_y = random.randint(1, max(1, height - 2))
                island_size = random.randint(3, 6)
                for y in range(island_y - island_size, island_y + island_size + 1):
                    for x in range(island_x - island_size, island_x + island_size + 1):
                        if 0 <= x < width and 0 <= y < height:
                            distance = ((x - island_x) ** 2 + (y - island_y) ** 2) ** 0.5
                            if distance < island_size * random.uniform(0.6, 1.0):
                                grid[y][x] = "LAND"

            # 2) Bulk create tiles for the grid
            tiles_to_create = [
                Tile(level=level, x=x, y=y, terrain_type=grid[y][x])
                for y in range(height)
                for x in range(width)
            ]
            Tile.objects.bulk_create(tiles_to_create)

            # 3) Create dock tiles (invisible area for player start positions)
            dock_tiles_to_create = []
            dock_x = -1
            # Fixed count for player start dock slots (3), but you can parameterize later
            for i in range(3):
                dock_tiles_to_create.append(Tile(level=level, x=dock_x - i, y=height, terrain_type="DOCK"))
            Tile.objects.bulk_create(dock_tiles_to_create)

            # 4) Reload tiles now that they have IDs
            all_tiles = list(level.tiles.all())
            land_tiles = [t for t in all_tiles if t.terrain_type == "LAND"]
            water_tiles = [t for t in all_tiles if t.terrain_type == "WATER"]
            plain_tiles = [t for t in all_tiles if t.terrain_type != "DOCK"]
            dock_tiles = [t for t in all_tiles if t.terrain_type == "DOCK"]
            used_tile_ids = set()

            def random_tile(terrain=None):
                if terrain == "LAND":
                    candidates = [t for t in land_tiles if t.id not in used_tile_ids]
                elif terrain == "WATER":
                    candidates = [t for t in water_tiles if t.id not in used_tile_ids]
                else:
                    candidates = [t for t in plain_tiles if t.id not in used_tile_ids]
                return random.choice(candidates) if candidates else None

            # 5) Create StartingVehicle enemy entries (single per type)
            starting_vehicle_objs = []
            for vtype, terrain in [("ENEMY_TANK", "LAND"), ("ENEMY_BOAT", "WATER"), ("ENEMY_PLANE", None)]:
                tile = random_tile(terrain)
                if tile:
                    starting_vehicle_objs.append(
                        StartingVehicle(level=level, tile=tile, vehicle_type=vtype, is_enemy=True)
                    )
                    used_tile_ids.add(tile.id)

            # 6) Create StartingVehicle player entries at the dock
            player_types = ["TANK", "BOAT", "PLANE"]
            for i, vtype in enumerate(player_types):
                if i < len(dock_tiles):
                    starting_vehicle_objs.append(
                        StartingVehicle(level=level, tile=dock_tiles[i], vehicle_type=vtype, is_enemy=False)
                    )

            if starting_vehicle_objs:
                StartingVehicle.objects.bulk_create(starting_vehicle_objs)

    # ----------------------
    # Admin action wrappers
    # ----------------------
    @admin.action(description="Generate full level (tiles + vehicles)")
    def generate_full_level(self, request, queryset):
        for level in queryset:
            self._generate_full_level(level)
        self.message_user(request, "✅ Levels fully generated: tiles + vehicles created successfully!")

    # ----------------------
    # Randomize enemy vehicles action
    # ----------------------
    @admin.action(description="Randomize enemy vehicle positions")
    def randomize_enemy_vehicles(self, request, queryset):
        for level in queryset:
            # Reset players first (to ensure no collisions)
            self.reset_all_players(request, [level])

            # Pre-categorize tiles
            tiles = list(level.tiles.all())
            land_tiles = [t for t in tiles if t.terrain_type == "LAND"]
            water_tiles = [t for t in tiles if t.terrain_type == "WATER"]
            valid_tiles = [t for t in tiles if t.terrain_type != "DOCK"]

            # used_tile_ids should exclude enemy positions so we can move enemies
            used_tile_ids = set(level.vehicles.exclude(tile=None).values_list("tile_id", flat=True))
            enemy_tile_ids = set(level.vehicles.filter(is_enemy=True).values_list("tile_id", flat=True))
            used_tile_ids -= enemy_tile_ids

            # Pull all enemy StartingVehicle objects into memory (small set)
            enemy_starting_vehicles = list(level.vehicles.filter(is_enemy=True))

            updated_vehicles = []
            for sv in enemy_starting_vehicles:
                if sv.vehicle_type == "ENEMY_TANK":
                    candidates = [t for t in land_tiles if t.id not in used_tile_ids]
                elif sv.vehicle_type == "ENEMY_BOAT":
                    candidates = [t for t in water_tiles if t.id not in used_tile_ids]
                else:
                    candidates = [t for t in valid_tiles if t.id not in used_tile_ids]

                if not candidates:
                    continue

                new_tile = random.choice(candidates)
                sv.tile = new_tile
                updated_vehicles.append(sv)
                used_tile_ids.add(new_tile.id)

            # Bulk-update StartingVehicle positions where possible
            if updated_vehicles:
                StartingVehicle.objects.bulk_update(updated_vehicles, ["tile"])

            # Sync the new enemy positions to all players
            self.sync_enemy_player_vehicles(level)

        self.message_user(request, "🎲 Enemy vehicles randomized for all players!")

    # ----------------------
    # Sync helper
    # ----------------------
    def sync_enemy_player_vehicles(self, level):
        """
        Ensure every player's enemy PlayerVehicles match the StartingVehicle positions.
        This deletes previous enemy PlayerVehicles for each player_state and bulk_creates new ones.
        """
        starting_enemies = list(level.vehicles.filter(is_enemy=True).select_related("tile"))

        player_states = level.playerlevelstate_set.all()
        for ps in player_states:
            # Remove old enemy vehicles
            ps.vehicles.filter(is_enemy=True).delete()

            # Build new PlayerVehicle objects (not saved yet)
            new_enemy_vehicles = [
                PlayerVehicle(
                    player_state=ps,
                    tile=sv.tile,
                    vehicle_type=sv.vehicle_type,
                    is_enemy=True,
                    health=100,
                )
                for sv in starting_enemies
            ]

            if new_enemy_vehicles:
                PlayerVehicle.objects.bulk_create(new_enemy_vehicles)

    # ----------------------
    # Reset all players action
    # ----------------------
    @admin.action(description="Reset players")
    def reset_all_players(self, request, queryset):
        for level in queryset:
            dock_tiles = list(level.tiles.filter(terrain_type="DOCK").order_by("x", "y"))

            # Iterate through each player's PlayerLevelState
            for ps in level.playerlevelstate_set.all():
                ps.game_started = False
                ps.turn_number = 1
                ps.save()

                player_vehicles = list(ps.vehicles.filter(is_enemy=False))
                if len(dock_tiles) < len(player_vehicles):
                    self.message_user(request, f"Not enough dock tiles for player {ps.user.username}")
                    continue

                # Assign dock tiles deterministically by vehicle id order
                updated = []
                for vehicle, dock_tile in zip(sorted(player_vehicles, key=lambda v: v.id), dock_tiles):
                    vehicle.tile = dock_tile
                    updated.append(vehicle)

                if updated:
                    PlayerVehicle.objects.bulk_update(updated, ["tile"])
        self.message_user(request, "✅ All players reset to dock.")

# ------------------------------
# TileAdmin
# ------------------------------
@admin.register(Tile)
class TileAdmin(admin.ModelAdmin):
    list_display = ("x", "y", "terrain_type", "level", "colored_preview")
    list_filter = ("terrain_type", "level")
    search_fields = ("x", "y")

    def colored_preview(self, obj):
        color_map = {"LAND": "green", "WATER": "blue", "DOCK": "gray"}
        color = color_map.get(obj.terrain_type, "black")
        return format_html('<div style="width:20px;height:20px;background:{};border-radius:4px;"></div>', color)
    colored_preview.short_description = "Preview"

# ------------------------------
# StartingVehicleAdmin
# ------------------------------
@admin.register(StartingVehicle)
class StartingVehicleAdmin(admin.ModelAdmin):
    list_display = ("vehicle_type", "level", "tile", "is_enemy", "terrain_type")
    list_filter = ("vehicle_type", "level", "is_enemy")
    search_fields = ("vehicle_type",)
    raw_id_fields = ("level", "tile")

    def terrain_type(self, obj):
        return obj.tile.terrain_type if obj.tile else "None"
    terrain_type.short_description = "Tile Type"
