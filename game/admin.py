from django.contrib import admin
from django.utils.html import format_html
from .models import Level, Tile, StartingVehicle, PlayerVehicle, PlayerLevelState
import random

@admin.register(Level)
class LevelAdmin(admin.ModelAdmin):
    list_display = ("name", "width", "height", "tile_count")
    actions = ["generate_full_level", "randomize_enemy_vehicles", "reset_all_players"]
    readonly_fields = ("map_preview",)
    fields = ("name", "width", "height", "map_preview")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)

        if not change:
            # Automatically generate full level right after creation
            self.generate_full_level(request, [obj])

    @admin.display(description="Map Preview")
    def map_preview(self, obj):
        TILE_SIZE = 22  # Slightly larger for clarity

        COLORS = {
            "LAND": "#4CAF50",
            "WATER": "#2196F3",
            "DOCK": "#9E9E9E",
        }

        # Small icons or letters for each vehicle type
        VEHICLE_ICON = {
            # Player vehicles
            ("TANK", False): "🟩T",
            ("BOAT", False): "🟦B",
            ("PLANE", False): "🟨P",

            # Enemy vehicles
            ("ENEMY_TANK", True): "🔴T",
            ("ENEMY_BOAT", True): "🔵B",
            ("ENEMY_PLANE", True): "⚫P",
        }

        # Preload tiles for fast lookup
        tiles = {(t.x, t.y): t for t in obj.tiles.all()}

        # Preload vehicles mapped by (x,y)
        vehicles = {}
        for v in obj.vehicles.all():
            if v.tile:
                vehicles[(v.tile.x, v.tile.y)] = v

        # Start HTML output
        html = '<div style="border:1px solid #ccc; display:inline-block;">'

        for y in range(obj.height):
            html += '<div style="display:flex;">'

            for x in range(obj.width):
                tile = tiles.get((x, y))
                color = COLORS.get(tile.terrain_type, "black") if tile else "black"

                vehicle = vehicles.get((x, y))

                # If there's a vehicle, draw it
                if vehicle:
                    key = (vehicle.vehicle_type, vehicle.is_enemy)
                    icon = VEHICLE_ICON.get(key, "❓")

                    html += (
                        f'<div style="width:{TILE_SIZE}px; height:{TILE_SIZE}px; '
                        f'background:{color}; border:2px solid #000; '
                        f'display:flex; justify-content:center; align-items:center; '
                        f'font-size:14px; font-weight:bold;">'
                        f'{icon}</div>'
                    )
                else:
                    # Normal tile cell
                    html += (
                        f'<div style="width:{TILE_SIZE}px; height:{TILE_SIZE}px; '
                        f'background:{color};"></div>'
                    )

            html += '</div>'  # end row

        html += '</div>'
        return format_html(html)

    def tile_count(self, obj):
        return obj.tiles.count()
    tile_count.short_description = "Tiles"


    @admin.action(description="Generate full level (tiles + vehicles)")
    def generate_full_level(self, request, queryset):
        for level in queryset:
            # --- CLEAN SLATE ---
            level.tiles.all().delete()
            level.vehicles.all().delete()

            width, height = level.width, level.height

            # --- 1️⃣ CREATE BASE GRID (LAND/WATER) ---
            grid = [["WATER" for _ in range(width)] for _ in range(height)]

            num_islands = max(1, (width * height) // 50)
            for _ in range(num_islands):
                island_x = random.randint(1, width - 2)
                island_y = random.randint(1, height - 2)
                island_size = random.randint(3, 6)

                for y in range(island_y - island_size, island_y + island_size):
                    for x in range(island_x - island_size, island_x + island_size):
                        if 0 <= x < width and 0 <= y < height:
                            distance = ((x - island_x) ** 2 + (y - island_y) ** 2) ** 0.5
                            if distance < island_size * random.uniform(0.6, 1.0):
                                grid[y][x] = "LAND"

            # --- 2️⃣ CREATE NORMAL TILES ---
            tiles_to_create = []
            for y in range(height):
                for x in range(width):
                    tiles_to_create.append(
                        Tile(level=level, x=x, y=y, terrain_type=grid[y][x])
                    )
            Tile.objects.bulk_create(tiles_to_create)

            # --- 3️⃣ CREATE INVISIBLE DOCK TILES (for player vehicles only) ---
            dock_tiles = []
            dock_x = -1
            for i in range(3):  # 3 player vehicles: tank, boat, plane
                dock_tiles.append(Tile(level=level, x=dock_x - i, y=height, terrain_type="DOCK"))
            Tile.objects.bulk_create(dock_tiles)

            # reload all tiles after bulk_create so they have IDs
            all_tiles = list(level.tiles.all())
            land_tiles = [t for t in all_tiles if t.terrain_type == "LAND"]
            water_tiles = [t for t in all_tiles if t.terrain_type == "WATER"]
            plain_tiles = [t for t in all_tiles if t.terrain_type != "DOCK"]
            dock_tiles = list(level.tiles.filter(terrain_type="DOCK"))
            used_tile_ids = set()

            def random_tile(terrain=None):
                if terrain == "LAND":
                    candidates = [t for t in land_tiles if t.id not in used_tile_ids]
                elif terrain == "WATER":
                    candidates = [t for t in water_tiles if t.id not in used_tile_ids]
                else:
                    candidates = [t for t in plain_tiles if t.id not in used_tile_ids]
                return random.choice(candidates) if candidates else None

            # --- 4️⃣ CREATE ENEMY VEHICLES ---
            for vtype, terrain in [("ENEMY_TANK", "LAND"), ("ENEMY_BOAT", "WATER"), ("ENEMY_PLANE", None)]:
                tile = random_tile(terrain)
                if tile:
                    StartingVehicle.objects.create(
                        level=level,
                        tile=tile,
                        vehicle_type=vtype,
                        is_enemy=True,
                    )
                    used_tile_ids.add(tile.id)

            # --- 5️⃣ CREATE PLAYER VEHICLES (start on DOCK) ---
            player_types = ["TANK", "BOAT", "PLANE"]
            for i, vtype in enumerate(player_types):
                if i < len(dock_tiles):
                    StartingVehicle.objects.create(
                        level=level,
                        tile=dock_tiles[i],
                        vehicle_type=vtype,
                        is_enemy=False,
                    )

        self.message_user(request, "✅ Levels fully generated: tiles + vehicles created successfully!")

    # ---------------- RANDOMIZE ENEMY VEHICLES ----------------
    @admin.action(description="Randomize enemy vehicle positions")
    def randomize_enemy_vehicles(self, request, queryset):
        for level in queryset:

            # 1. Reset all players (moves player vehicles to docks)
            self.reset_all_players(request, [level])

            # 2. Randomize enemy StartingVehicles
            tiles = list(level.tiles.all())

            land_tiles = [t for t in tiles if t.terrain_type == "LAND"]
            water_tiles = [t for t in tiles if t.terrain_type == "WATER"]
            valid_tiles = [t for t in tiles if t.terrain_type != "DOCK"]

            used_tile_ids = set(
                level.vehicles.exclude(tile=None).values_list("tile_id", flat=True)
            )
            enemy_vehicle_ids = set(
                level.vehicles.filter(is_enemy=True).values_list("tile_id", flat=True)
            )
            used_tile_ids -= enemy_vehicle_ids

            for vehicle in level.vehicles.filter(is_enemy=True):

                if vehicle.vehicle_type == "ENEMY_TANK":
                    candidates = [t for t in land_tiles if t.id not in used_tile_ids]

                elif vehicle.vehicle_type == "ENEMY_BOAT":
                    candidates = [t for t in water_tiles if t.id not in used_tile_ids]

                else:
                    candidates = [t for t in valid_tiles if t.id not in used_tile_ids]

                if not candidates:
                    continue

                new_tile = random.choice(candidates)
                vehicle.tile = new_tile
                vehicle.save()
                used_tile_ids.add(new_tile.id)

            # 3. Sync new enemy positions to ALL players
            self.sync_enemy_player_vehicles(level)

        self.message_user(request, "🎲 Enemy vehicles randomized for all players!")

    def sync_enemy_player_vehicles(self, level):
      # Ensure every player's enemy vehicles match the updated StartingVehicle positions.
      starting_enemies = list(level.vehicles.filter(is_enemy=True))

      for player_state in level.playerlevelstate_set.all():

          # Delete old enemy PlayerVehicles
          player_state.vehicles.filter(is_enemy=True).delete()

          # Create new PlayerVehicles at updated positions
          new_enemy_vehicles = [
              PlayerVehicle(
                  player_state=player_state,
                  tile=sv.tile,
                  vehicle_type=sv.vehicle_type,
                  is_enemy=True,
                  health=100,
              )
              for sv in starting_enemies
          ]

          PlayerVehicle.objects.bulk_create(new_enemy_vehicles)

    # ---------------- RESET ALL PLAYERS ----------------
    @admin.action(description="Reset players")
    def reset_all_players(self, request, queryset):
        for level in queryset:
            dock_tiles = list(level.tiles.filter(terrain_type="DOCK").order_by('x', 'y'))

            for player_state in level.playerlevelstate_set.all():
                player_state.game_started = False
                player_state.turn_number = 1
                player_state.save()

                player_vehicles = list(player_state.vehicles.filter(is_enemy=False))
                if len(dock_tiles) < len(player_vehicles):
                    self.message_user(request, f"Not enough dock tiles for player {player_state.user.username}")
                    continue

                for vehicle, dock_tile in zip(player_vehicles, dock_tiles):
                    vehicle.tile = dock_tile
                    vehicle.save()
        self.message_user(request, "✅ All players reset to dock.")

@admin.register(Tile)
class TileAdmin(admin.ModelAdmin):
    list_display = ("x", "y", "terrain_type", "level", "colored_preview")
    list_filter = ("terrain_type", "level")
    search_fields = ("x", "y")

    def colored_preview(self, obj):
        color_map = {
            "LAND": "green",
            "WATER": "blue",
            "DOCK": "gray",
        }
        color = color_map.get(obj.terrain_type, "black")
        return format_html(
            '<div style="width:20px;height:20px;background:{};border-radius:4px;"></div>',
            color
        )
    colored_preview.short_description = "Preview"


@admin.register(StartingVehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ("vehicle_type", "level", "tile", "is_enemy", "terrain_type")
    list_filter = ("vehicle_type", "level", "is_enemy")
    search_fields = ("vehicle_type",)

    def terrain_type(self, obj):
        return obj.tile.terrain_type if obj.tile else "None"
    terrain_type.short_description = "Tile Type"
