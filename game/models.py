from django.conf import settings
from django.db import models


class Level(models.Model):
    name = models.CharField(max_length=100)
    width = models.IntegerField(default=10)
    height = models.IntegerField(default=10)

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
    
class StartingVehicle(models.Model):
    """Template vehicle — shared across all players (defines starting positions)."""
    class VehicleType(models.TextChoices):
        TANK = "TANK", "Tank"
        BOAT = "BOAT", "Boat"
        PLANE = "PLANE", "Plane"
        ENEMY_TANK = "ENEMY_TANK", "Enemy Tank"
        ENEMY_BOAT = "ENEMY_BOAT", "Enemy Boat"
        ENEMY_PLANE = "ENEMY_PLANE", "Enemy Plane"

    level = models.ForeignKey(Level, on_delete=models.CASCADE, related_name="vehicles")
    tile = models.ForeignKey("Tile", on_delete=models.CASCADE, related_name="vehicles")
    vehicle_type = models.CharField(
        max_length=20,
        choices=VehicleType.choices,
        default=VehicleType.TANK
    )
    is_enemy = models.BooleanField(default=False)
    def __str__(self):
        return f"{self.vehicle_type} ({'ENEMY' if self.is_enemy else 'TEMPLATE'})"
    
class PlayerLevelState(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    level = models.ForeignKey("Level", on_delete=models.CASCADE)
    game_started = models.BooleanField(default=False)
    turn_number = models.IntegerField(default=1)

    class Meta:
        unique_together = ("user", "level")

    def __str__(self):
        return f"{self.user.username} - {self.level.name} (Turn {self.turn_number})"
    
class PlayerVehicle(models.Model):
    """Tracks user-specific vehicle states, including enemies."""
    player_state = models.ForeignKey(PlayerLevelState, on_delete=models.CASCADE, related_name="vehicles")
    tile = models.ForeignKey(Tile, on_delete=models.CASCADE, related_name="player_vehicles")
    vehicle_type = models.CharField(max_length=20, choices=StartingVehicle.VehicleType.choices)
    is_enemy = models.BooleanField(default=False)
    health = models.IntegerField(default=100)

    def __str__(self):
        return f"{'ENEMY' if self.is_enemy else 'PLAYER'} {self.vehicle_type} ({self.player_state.user.username})"