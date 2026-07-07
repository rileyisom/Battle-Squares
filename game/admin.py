# admin.py
import random

from django.contrib import admin, messages
from django.db import transaction
from django.utils.html import format_html

from .models import Level, PlayerVehicle, StartingVehicle, Tile
from .services.player_state import reset_player_state


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
        tile_size = 22

        colors = {
            "LAND": "#4CAF50",
            "WATER": "#2196F3",
            "DOCK": "#9E9E9E",
        }

        # Icon map: (vehicle_type, is_enemy) -> icon
        vehicle_icon = {
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
                color = colors.get(tile.terrain_type, "black") if tile else "black"
                vehicle = vehicles.get((x, y))

                if vehicle:
                    key = (vehicle.vehicle_type, vehicle.is_enemy)
                    icon = vehicle_icon.get(key, "❓")
                    html.append(
                        f'<div style="width:{tile_size}px; height:{tile_size}px; '
                        f"background:{color}; border:2px solid #000; "
                        f"display:flex; justify-content:center; align-items:center; "
                        f'font-size:14px; font-weight:bold;">{icon}</div>'
                    )
                else:
                    html.append(
                        f'<div style="width:{tile_size}px; height:{tile_size}px; '
                        f'background:{color};"></div>'
                    )
            html.append("</div>")
        html.append("</div>")
        return format_html("".join(html))

    def tile_count(self, obj):
        return obj.tiles.count()

    tile_count.short_description = "Tiles"

    # ----------------------
    # Grid generation helpers
    # ----------------------
    _MAX_GRID_ATTEMPTS = 10

    def _generate_grid(self, width, height):
        """Produce one candidate grid (no validation)."""
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
        return grid

    def _grid_meets_zone_requirements(self, grid, width, height):
        """
        Return True only if both the top 40% and bottom 40% of rows each contain
        at least 25% of all land tiles and at least 25% of all water tiles.
        """
        top_cutoff = int(height * 0.4)
        bottom_start = height - int(height * 0.4)

        total_land = sum(1 for y in range(height) for x in range(width) if grid[y][x] == "LAND")
        total_water = sum(1 for y in range(height) for x in range(width) if grid[y][x] == "WATER")

        if total_land == 0 or total_water == 0:
            return False

        land_top = sum(1 for y in range(top_cutoff) for x in range(width) if grid[y][x] == "LAND")
        land_bottom = sum(
            1 for y in range(bottom_start, height) for x in range(width) if grid[y][x] == "LAND"
        )
        water_top = sum(1 for y in range(top_cutoff) for x in range(width) if grid[y][x] == "WATER")
        water_bottom = sum(
            1 for y in range(bottom_start, height) for x in range(width) if grid[y][x] == "WATER"
        )

        return (
            land_top / total_land >= 0.25
            and land_bottom / total_land >= 0.25
            and water_top / total_water >= 0.25
            and water_bottom / total_water >= 0.25
        )

    # ----------------------
    # Core generator (single-level) — extracted helper
    # ----------------------
    def _generate_full_level(self, level):
        """
        Generate tiles and starting vehicles for a single level.
        This runs inside the admin and is used by both save_model and the admin action.
        Raises ValueError if a valid grid cannot be produced within _MAX_GRID_ATTEMPTS tries.
        """
        width, height = level.width, level.height

        # Retry grid generation until zone-distribution requirements are met.
        for _ in range(self._MAX_GRID_ATTEMPTS):
            grid = self._generate_grid(width, height)
            if self._grid_meets_zone_requirements(grid, width, height):
                break
        else:
            raise ValueError(
                f'Could not generate a valid grid for "{level.name}" after '
                f"{self._MAX_GRID_ATTEMPTS} attempts. "
                "Each zone (top 40% / bottom 40%) requires at least 25% of all land "
                "and 25% of all water tiles. Try a larger grid."
            )

        top_cutoff = int(height * 0.4)
        bottom_start = height - int(height * 0.4)
        total_land = sum(1 for y in range(height) for x in range(width) if grid[y][x] == "LAND")
        total_water = sum(1 for y in range(height) for x in range(width) if grid[y][x] == "WATER")
        land_top_pct = (
            100
            * sum(1 for y in range(top_cutoff) for x in range(width) if grid[y][x] == "LAND")
            // total_land
        )
        land_bot_pct = (
            100
            * sum(
                1 for y in range(bottom_start, height) for x in range(width) if grid[y][x] == "LAND"
            )
            // total_land
        )
        water_top_pct = (
            100
            * sum(1 for y in range(top_cutoff) for x in range(width) if grid[y][x] == "WATER")
            // total_water
        )
        water_bot_pct = (
            100
            * sum(
                1
                for y in range(bottom_start, height)
                for x in range(width)
                if grid[y][x] == "WATER"
            )
            // total_water
        )
        print(
            f"[{level.name}] Grid generated — "
            f"Land: top {land_top_pct}% / bot {land_bot_pct}%  |  "
            f"Water: top {water_top_pct}% / bot {water_bot_pct}%"
        )

        # Use a transaction to avoid partial state if something fails
        with transaction.atomic():
            # Remove existing tiles & vehicles (starting vehicles)
            # Note: This preserves PlayerVehicle / PlayerLevelState records;
            # we're regenerating the starting-level content.
            level.tiles.all().delete()
            level.vehicles.all().delete()

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
                dock_tiles_to_create.append(
                    Tile(level=level, x=dock_x - i, y=height, terrain_type="DOCK")
                )
            Tile.objects.bulk_create(dock_tiles_to_create)

            # 4) Get dock tiles for player vehicle placement
            dock_tiles = list(level.tiles.filter(terrain_type="DOCK"))

            # 5) Place enemy StartingVehicles via shared helper
            self._place_enemy_vehicles(level)

            # 6) Create StartingVehicle player entries at the dock
            player_starting_vehicles = []
            for i, vtype in enumerate(["TANK", "BOAT", "PLANE"]):
                if i < len(dock_tiles):
                    player_starting_vehicles.append(
                        StartingVehicle(
                            level=level, tile=dock_tiles[i], vehicle_type=vtype, is_enemy=False
                        )
                    )
            if player_starting_vehicles:
                StartingVehicle.objects.bulk_create(player_starting_vehicles)

    # ----------------------
    # Enemy vehicle placement helper (shared by generation and randomization)
    # ----------------------
    def _place_enemy_vehicles(self, level):
        """
        Pick tiles for each enemy vehicle type, respecting terrain and zone constraints,
        then replace all existing enemy StartingVehicle records for the level.

        Placement rules (all enemies restricted to the top 40% of rows):
          - ENEMY_TANK: random LAND tile in the top 40%
          - ENEMY_BOAT: random WATER tile in the top 40%
          - ENEMY_PLANE: random non-DOCK tile in the top 40%
        """
        top_cutoff = int(level.height * 0.4)
        tiles = list(level.tiles.exclude(terrain_type="DOCK"))
        land_tiles = [t for t in tiles if t.terrain_type == "LAND"]
        water_tiles = [t for t in tiles if t.terrain_type == "WATER"]

        used_tile_ids = set()
        enemy_vehicle_objs = []

        for vtype, terrain, top_zone_only in [
            ("ENEMY_TANK", "LAND", True),
            ("ENEMY_BOAT", "WATER", True),
            ("ENEMY_PLANE", None, True),
        ]:
            if terrain == "LAND":
                candidates = [t for t in land_tiles if t.id not in used_tile_ids]
            elif terrain == "WATER":
                candidates = [t for t in water_tiles if t.id not in used_tile_ids]
            else:
                candidates = [t for t in tiles if t.id not in used_tile_ids]

            if top_zone_only:
                candidates = [t for t in candidates if t.y < top_cutoff]

            if not candidates:
                continue

            tile = random.choice(candidates)
            enemy_vehicle_objs.append(
                StartingVehicle(level=level, tile=tile, vehicle_type=vtype, is_enemy=True)
            )
            used_tile_ids.add(tile.id)

        level.vehicles.filter(is_enemy=True).delete()
        if enemy_vehicle_objs:
            StartingVehicle.objects.bulk_create(enemy_vehicle_objs)

    # ----------------------
    # Admin action wrappers
    # ----------------------
    @admin.action(description="Generate full level (tiles + vehicles)")
    def generate_full_level(self, request, queryset):
        succeeded, failed = [], []
        for level in queryset:
            try:
                self._generate_full_level(level)
                succeeded.append(level.name)
            except ValueError as e:
                failed.append(str(e))

        if succeeded:
            self.message_user(
                request,
                f'Levels fully generated: {", ".join(succeeded)}',
                messages.SUCCESS,
            )
        for error in failed:
            self.message_user(request, error, messages.ERROR)

    # ----------------------
    # Randomize enemy vehicles action
    # ----------------------
    @admin.action(description="Randomize enemy vehicle positions")
    def randomize_enemy_vehicles(self, request, queryset):
        for level in queryset:
            # Reset players first (to ensure no collisions)
            self.reset_all_players(request, [level])

            # Re-place all enemy StartingVehicles using the shared placement logic
            self._place_enemy_vehicles(level)

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
                try:
                    reset_player_state(ps, dock_tiles)
                except ValueError:
                    self.message_user(
                        request, f"Not enough dock tiles for player {ps.user.username}"
                    )
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
        return format_html(
            '<div style="width:20px;height:20px;background:{};border-radius:4px;"></div>', color
        )

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
