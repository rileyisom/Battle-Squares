from django.contrib import admin
from .models import Level, Tile, Vehicle
import random

# Register your models here.

@admin.register(Level)
class LevelAdmin(admin.ModelAdmin):
    list_display = ("name", "width", "height", "tile_count")
    actions = ["generate_full_level"]

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
            dock_tiles = list(level.tiles.filter(terrain_type="DOCK"))

            # --- 4️⃣ CREATE ENEMY VEHICLES ---
            all_tiles = list(level.tiles.all())
            used_tile_ids = set()

            def random_tile(terrain_filter=None):
                candidates = [t for t in all_tiles if t.id not in used_tile_ids and t.terrain_type != "DOCK"]
                if terrain_filter:
                    candidates = [t for t in candidates if t.terrain_type == terrain_filter]
                return random.choice(candidates) if candidates else None

            # Create each enemy one by one
            for vtype, terrain in [("ENEMY_TANK", "LAND"), ("ENEMY_BOAT", "WATER"), ("ENEMY_PLANE", None)]:
                tile = random_tile(terrain)
                if tile:
                    Vehicle.objects.create(level=level, tile=tile, vehicle_type=vtype)
                    used_tile_ids.add(tile.id)

            # --- 5️⃣ CREATE PLAYER VEHICLES (start on DOCK) ---
            player_types = ["TANK", "BOAT", "PLANE"]
            for i, vtype in enumerate(player_types):
                Vehicle.objects.create(level=level, tile=dock_tiles[i], vehicle_type=vtype)

        self.message_user(request, "✅ Levels fully generated: tiles + vehicles created successfully!")


@admin.register(Tile)
class TileAdmin(admin.ModelAdmin):
    list_display = ("x", "y", "terrain_type", "colored_preview")
    list_filter = ("terrain_type",)
    search_fields = ("x", "y")

    def colored_preview(self, obj):
        color_map = {
            "LAND": "green",
            "WATER": "blue",
            "DOCK": "gray",
        }
        color = color_map.get(obj.terrain_type, "black")
        return f'<div style="width:20px;height:20px;background:{color};border-radius:4px;"></div>'
    colored_preview.allow_tags = True
    colored_preview.short_description = "Preview"


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ("vehicle_type", "level", "tile")
    list_filter = ("vehicle_type", "level")
    search_fields = ("vehicle_type",)