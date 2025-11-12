const {
  gridWidth,
  levelId,
  gameStarted: initialGameStarted,
  urls,
} = window.gameConfig;

const startBtn = document.getElementById("start-btn");
const resetBtn = document.getElementById("reset-btn");
const tiles = document.querySelectorAll(".tile");
const dock = document.getElementById("vehicle-dock");
const vehicles = document.querySelectorAll(".vehicle[data-vehicle-type]:not([alt*='ENEMY'])");

// Track game state in JS memory
let gameStarted = initialGameStarted;

// ---- ASSIGN FIXED DOCK TILE ID ----
vehicles.forEach(v => {
  if (!v.dataset.dockTileId) {
    v.dataset.dockTileId = v.dataset.tileId || null;
  }
});

// ---- DRAG START / END (event delegation) ----
document.addEventListener("dragstart", e => {
  const vehicle = e.target.closest(".vehicle[data-vehicle-type]:not([alt*='ENEMY'])");
  if (!vehicle || gameStarted) return;

  vehicle.classList.add("dragging");
  e.dataTransfer.setData("vehicleId", vehicle.dataset.vehicleId);
  e.dataTransfer.setData("vehicleType", vehicle.dataset.vehicleType);
});


document.addEventListener("dragend", e => {
  const vehicle = e.target.closest(".vehicle[data-vehicle-type]:not([alt*='ENEMY'])");
  if (vehicle) vehicle.classList.remove("dragging");

  // Clear any lingering highlights
  document.querySelectorAll(".tile.valid-drop, .tile.invalid-drop, .tile.drag-over").forEach(t => {
    t.classList.remove("valid-drop", "invalid-drop", "drag-over");
  });
});

// ---- ALLOW DROP ----
function allowDropTarget(target) {
  target.addEventListener("dragover", e => {
    if (gameStarted) return;

    // Must call preventDefault() to allow dropping
    e.preventDefault();

    const vehicle = document.querySelector(".vehicle.dragging");
    if (!vehicle) return;
    const vehicleType = vehicle.dataset.vehicleType;

    // Determine terrain type
    const terrain = target.classList.contains("WATER")
      ? "WATER"
      : target.classList.contains("LAND")
      ? "LAND"
      : target.classList.contains("DOCK")
      ? "DOCK"
      : "OTHER";

    // Determine if drop is invalid
    const invalid =
      (vehicleType.includes("BOAT") && !["WATER", "DOCK"].includes(terrain)) ||
      (vehicleType.includes("TANK") && !["LAND", "DOCK"].includes(terrain)) ||
      (target.classList.contains("tile") && target.querySelector(".vehicle"));

    // Reset classes
    target.classList.remove("valid-drop", "invalid-drop");

    // Apply the right one
    if (invalid) {
      target.classList.add("invalid-drop");
    } else {
      target.classList.add("valid-drop");
    }
  });

  target.addEventListener("dragleave", e => {
    e.currentTarget.classList.remove("valid-drop", "invalid-drop");
  });

  target.addEventListener("drop", e => {
    if (gameStarted) return;
    e.preventDefault();

    const dropTarget = e.currentTarget;
    dropTarget.classList.remove("valid-drop", "invalid-drop");

    const vehicleId = e.dataTransfer.getData("vehicleId");
    const vehicleType = e.dataTransfer.getData("vehicleType");
    const vehicle = document.querySelector(`[data-vehicle-id='${vehicleId}']`);
    if (!vehicle) return;

    // Dock special case
    if (dropTarget.id === "vehicle-dock") {
      vehicle.dataset.tileId = vehicle.dataset.dockTileId;
      dropTarget.appendChild(vehicle);
      return;
    }

    // Prevent placing on occupied tile
    if (dropTarget.classList.contains("tile") && dropTarget.querySelector(".vehicle")) return;

    const terrain = dropTarget.classList.contains("WATER")
      ? "WATER"
      : dropTarget.classList.contains("LAND")
      ? "LAND"
      : dropTarget.classList.contains("DOCK")
      ? "DOCK"
      : "OTHER";

    if (
      (vehicleType.includes("BOAT") && !["WATER", "DOCK"].includes(terrain)) ||
      (vehicleType.includes("TANK") && !["LAND", "DOCK"].includes(terrain))
    ) {
      alert(`You can't place a ${vehicleType.toLowerCase()} on ${terrain.toLowerCase()}!`);
      return;
    }

    dropTarget.appendChild(vehicle);
    vehicle.dataset.tileId = dropTarget.dataset.tileId || null;
  });
}

// ---- APPLY DROP HANDLERS ----
document.querySelectorAll(".tile").forEach(allowDropTarget);
allowDropTarget(document.getElementById("vehicle-dock"));

// ---- START GAME ----
startBtn.addEventListener("click", async () => {
  if (gameStarted) return;
  gameStarted = true;
  startBtn.disabled = true;
  startBtn.textContent = "Game Started!";

  // Disable dragging for all player vehicles
  document.querySelectorAll(".vehicle[data-vehicle-type]:not([alt*='ENEMY'])").forEach(v => {
    v.draggable = false;
  });

  // Save vehicle positions
  const vehicles = document.querySelectorAll(".vehicle[data-vehicle-type]:not([alt*='ENEMY'])");
  for (const vehicle of vehicles) {
    const vehicleId = vehicle.dataset.vehicleId;
    const tileId = vehicle.dataset.tileId || vehicle.dataset.dockTileId;
    await fetch(`${urls.updateVehicle}${vehicleId}/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCookie("csrftoken"),
      },
      body: JSON.stringify({ tile_id: tileId }),
    });
  }

  // Mark the level as started for this user
  await fetch(urls.markStart, {
    method: "POST",
    headers: { "X-CSRFToken": getCookie("csrftoken") },
  });

  alert("Your vehicle positions have been saved!");
});

// ---- RESET LEVEL ----
resetBtn.addEventListener("click", async () => {
  if (!confirm("Are you sure you want to reset the level? Your player vehicle positions will go back to the dock.")) return;

  const response = await fetch(urls.resetLevel, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken"),
    },
  });

  const result = await response.json();
  if (result.status === "ok") {
    const vehicles = document.querySelectorAll(".vehicle[data-vehicle-type]:not([alt*='ENEMY'])");
    vehicles.forEach(vehicle => {
      vehicle.draggable = true;

      // Move vehicle back to its dock tile
      const dockTileId = vehicle.dataset.dockTileId;
      const dockTile = document.querySelector(`.tile.DOCK[data-tile-id='${dockTileId}']`);
      if (dockTile) {
        dockTile.appendChild(vehicle);
        vehicle.dataset.tileId = dockTileId;
      } else {
        console.warn("⚠️ Dock tile not found for vehicle:", vehicle.dataset.vehicleType);
      }
    });

    gameStarted = false;
    startBtn.disabled = false;
    startBtn.textContent = "Start Game";
    location.reload();

    // Optional: reload to refresh any backend updates
    // location.reload();
  } else {
    alert("Error resetting level: " + result.message);
  }
});

// ---- INITIAL BUTTON STATE ----
if (gameStarted) {
  startBtn.disabled = true;
  startBtn.textContent = "Game Started!";
  document.querySelectorAll(".vehicle[data-vehicle-type]:not([alt*='ENEMY'])").forEach(v => (v.draggable = false));
}

// ---- CSRF HELPER ----
function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(";").shift();
}

// ---- ASSIGN LEGACY VEHICLES TO DOCK TILES ----
/* function assignDockTiles() {
  const dockTiles = Array.from(document.querySelectorAll(".tile.DOCK"));
  
  vehicles.forEach(vehicle => {
    if (!vehicle.dataset.tileId) {
      // Find a free dock tile
      const freeTile = dockTiles.find(t => !document.querySelector(`.vehicle[data-tile-id='${t.dataset.tileId}']`));
      if (freeTile) {
        freeTile.appendChild(vehicle);
        vehicle.dataset.tileId = freeTile.dataset.tileId;
      } else {
        console.warn("⚠️ No free dock tile found for vehicle:", vehicle.dataset.vehicleType);
      }
    }
  });
}

// Call this once the page has loaded
window.addEventListener("DOMContentLoaded", () => {
  assignDockTiles();
}); */