from django.db import models

class Level(models.Model):
    name = models.CharField(max_length=100)
    width = models.IntegerField(default=10)
    height = models.IntegerField(default=10)
    game_started = models.BooleanField(default=False)

    def __str__(self):
        return self.name

class Tile(models.Model):
    class TerrainType(models.TextChoices):
        WATER = "WATER", "Water"
        LAND = "LAND", "Land"
        DOCK = "DOCK", "Dock"

    level = models.ForeignKey(Level, on_delete=models.CASCADE, related_name='tiles')
    x = models.IntegerField()
    y = models.IntegerField()
    terrain_type = models.CharField(
        max_length=20,
        choices=TerrainType.choices,
        default=TerrainType.WATER
    )

    def __str__(self):
        return f"Tile ({self.x}, {self.y}) - {self.get_terrain_type_display()}"

class Vehicle(models.Model):
    class VehicleType(models.TextChoices):
        TANK = "TANK", "Tank"
        BOAT = "BOAT", "Boat"
        PLANE = "PLANE", "Plane"
        ENEMY_TANK = "ENEMY_TANK", "Enemy Tank"
        ENEMY_BOAT = "ENEMY_BOAT", "Enemy Boat"
        ENEMY_PLANE = "ENEMY_PLANE", "Enemy Plane"

    level = models.ForeignKey("Level", on_delete=models.CASCADE, related_name="vehicles", default=1)
    tile = models.ForeignKey("Tile", on_delete=models.CASCADE, related_name="vehicles", default=1)
    
    vehicle_type = models.CharField(
        max_length=20,
        choices=VehicleType.choices,
        default=VehicleType.TANK
    )

    def __str__(self):
        return f"Vehicle ({self.tile.x}, {self.tile.y}) - {self.get_vehicle_type_display()}"