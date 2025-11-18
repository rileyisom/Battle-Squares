export class GameGrid {
  constructor(rootEl, config) {
    this.root = rootEl;
    this.gridWidth = config.gridWidth;
    this.levelId = config.levelId;
    this.urls = config.urls;
    this.gameStarted = config.gameStarted;

    this.startBtn = document.getElementById("start-btn");
    this.resetBtn = document.getElementById("reset-btn");
    this.tiles = this.root.querySelectorAll(".tile");
    this.dock = document.getElementById("vehicle-dock");

    this.vehicles = this.root.querySelectorAll(
      ".vehicle[data-vehicle-type]:not([alt*='ENEMY'])"
    );

    this._assignDockTileIds();
    this._bindUI();
    this._bindDragDrop();
    this._applyInitialState();
  }

  // ---------- INITIALIZE ----------
  _assignDockTileIds() {
    this.vehicles.forEach(v => {
      if (!v.dataset.dockTileId) {
        v.dataset.dockTileId = v.dataset.tileId || null;
      }
    });
  }

  _bindUI() {
    this.startBtn.addEventListener("click", () => this.startGame());
    this.resetBtn.addEventListener("click", () => this.resetLevel());
  }

  _bindDragDrop() {
    // Use event delegation instead of binding to every tile
    document.addEventListener("dragstart", e => this._onDragStart(e));
    document.addEventListener("dragend", e => this._onDragEnd(e));

    this.tiles.forEach(tile => this._makeDropTarget(tile));
    this._makeDropTarget(this.dock);
  }

  _applyInitialState() {
    if (this.gameStarted) {
      this.startBtn.disabled = true;
      this.startBtn.textContent = "Game Started!";
      this.vehicles.forEach(v => (v.draggable = false));
    }
  }

  // ---------- DRAG HANDLERS ----------
  _onDragStart(e) {
    if (this.gameStarted) return;

    const vehicle = e.target.closest(".vehicle[data-vehicle-type]");
    if (!vehicle) return;

    vehicle.classList.add("dragging");
    e.dataTransfer.setData("vehicleId", vehicle.dataset.vehicleId);
    e.dataTransfer.setData("vehicleType", vehicle.dataset.vehicleType);
  }

  _onDragEnd(e) {
    const vehicle = e.target.closest(".vehicle[data-vehicle-type]");
    if (vehicle) vehicle.classList.remove("dragging");

    this.root.querySelectorAll(".valid-drop, .invalid-drop").forEach(tile =>
      tile.classList.remove("valid-drop", "invalid-drop")
    );
  }

  // ---------- DROP TARGETS ----------
  _makeDropTarget(target) {
    target.addEventListener("dragover", e => this._onDragOver(e, target));
    target.addEventListener("dragleave", () => target.classList.remove("valid-drop", "invalid-drop"));
    target.addEventListener("drop", e => this._onDrop(e, target));
  }

  _onDragOver(e, target) {
    if (this.gameStarted) return;
    e.preventDefault();

    const vehicle = this.root.querySelector(".vehicle.dragging");
    if (!vehicle) return;

    const vehicleType = vehicle.dataset.vehicleType;
    const terrain = this._getTerrainType(target);

    const invalid = this._isInvalidPlacement(vehicleType, terrain, target);

    target.classList.toggle("valid-drop", !invalid);
    target.classList.toggle("invalid-drop", invalid);
  }

  _onDrop(e, target) {
    if (this.gameStarted) return;
    e.preventDefault();

    target.classList.remove("valid-drop", "invalid-drop");

    const vehicleId = e.dataTransfer.getData("vehicleId");
    const vehicle = this.root.querySelector(`[data-vehicle-id='${vehicleId}']`);

    if (!vehicle) return;

    // Return to dock
    if (target.id === "vehicle-dock") {
      vehicle.dataset.tileId = vehicle.dataset.dockTileId;
      target.appendChild(vehicle);
      return;
    }

    // Can't stack vehicles
    if (target.classList.contains("tile") && target.querySelector(".vehicle")) return;

    const terrain = this._getTerrainType(target);
    const vehicleType = vehicle.dataset.vehicleType;

    if (this._isInvalidPlacement(vehicleType, terrain, target)) return;

    target.appendChild(vehicle);
    vehicle.dataset.tileId = target.dataset.tileId || null;
  }

  // ---------- GAME ACTIONS ----------
  async startGame() {
    if (this.gameStarted) return;

    this.gameStarted = true;
    this.startBtn.disabled = true;
    this.startBtn.textContent = "Game Started!";

    this.vehicles.forEach(v => (v.draggable = false));

    // Save positions
    for (const v of this.vehicles) {
      const vehicleId = v.dataset.vehicleId;
      const tileId = v.dataset.tileId || v.dataset.dockTileId;

      await fetch(`${this.urls.updateVehicle}${vehicleId}/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": this._getCSRF(),
        },
        body: JSON.stringify({ tile_id: tileId }),
      });
    }

    // Mark started
    await fetch(this.urls.markStart, {
      method: "POST",
      headers: { "X-CSRFToken": this._getCSRF() },
    });

    alert("Your vehicle positions have been saved!");
  }

  async resetLevel() {
    if (!confirm("Reset all positions?")) return;

    const response = await fetch(this.urls.resetLevel, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": this._getCSRF(),
      },
    });

    const result = await response.json();

    if (result.status !== "ok") {
      alert("Error resetting level: " + result.message);
      return;
    }

    // Move every vehicle back
    this.vehicles.forEach(vehicle => {
      vehicle.draggable = true;
      const dockTile = this.root.querySelector(
        `.tile.DOCK[data-tile-id='${vehicle.dataset.dockTileId}']`
      );
      if (dockTile) {
        dockTile.appendChild(vehicle);
        vehicle.dataset.tileId = vehicle.dataset.dockTileId;
      }
    });

    this.gameStarted = false;
    this.startBtn.disabled = false;
    this.startBtn.textContent = "Start Game";

    location.reload();
  }

  // ---------- HELPERS ----------
  _getTerrainType(tile) {
    if (tile.classList.contains("WATER")) return "WATER";
    if (tile.classList.contains("LAND")) return "LAND";
    if (tile.classList.contains("DOCK")) return "DOCK";
    return "OTHER";
  }

  _isInvalidPlacement(vehicleType, terrain, tile) {
    const occupied = tile.classList.contains("tile") && tile.querySelector(".vehicle");

    if (occupied) return true;
    if (vehicleType.includes("BOAT") && !["WATER", "DOCK"].includes(terrain)) return true;
    if (vehicleType.includes("TANK") && !["LAND", "DOCK"].includes(terrain)) return true;
    return false;
  }

  _getCSRF() {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; csrftoken=`);
    if (parts.length === 2) return parts.pop().split(";").shift();
  }
}
