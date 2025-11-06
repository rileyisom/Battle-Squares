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

// Assign each vehicle its fixed dock tile ID
vehicles.forEach(v => {
  if (!v.dataset.dockTileId) {
    v.dataset.dockTileId = v.dataset.tileId; // assign the original dock tile ID
  }
});

// ---- DRAG START / END ----
vehicles.forEach(vehicle => {
  vehicle.addEventListener("dragstart", e => {
    if (gameStarted) return;
    vehicle.classList.add("dragging");
    e.dataTransfer.setData("vehicleId", vehicle.dataset.vehicleId);
    e.dataTransfer.setData("vehicleType", vehicle.dataset.vehicleType);
  });

  vehicle.addEventListener("dragend", () => {
    vehicle.classList.remove("dragging");
  });
});

// ---- ALLOW DROP ----
function allowDropTarget(target) {
  target.addEventListener("dragover", e => {
    if (gameStarted) return;
    e.preventDefault();
  });

  target.addEventListener("drop", e => {
    if (gameStarted) return;
    e.preventDefault();

    const vehicleId = e.dataTransfer.getData("vehicleId");
    const vehicleType = e.dataTransfer.getData("vehicleType");
    const vehicle = document.querySelector(`[data-vehicle-id='${vehicleId}']`);
    if (!vehicle) return;

    // Special case: dropping on the dock
    if (target.id === "vehicle-dock") {
      // Always assign the original dock tile ID
      vehicle.dataset.tileId = vehicle.dataset.dockTileId;

      // Append vehicle back to dock container
      target.appendChild(vehicle);
      return; // stop further processing
    }

    // Prevent placing on occupied tile
    if (target.classList.contains("tile") && target.querySelector(".vehicle")) return;

    // Determine terrain
    const terrain = target.classList.contains("WATER")
      ? "WATER"
      : target.classList.contains("LAND")
      ? "LAND"
      : target.classList.contains("DOCK")
      ? "DOCK"
      : "OTHER";

    // Validate placement
    if (
      (vehicleType.includes("BOAT") && !["WATER", "DOCK"].includes(terrain)) ||
      (vehicleType.includes("TANK") && !["LAND", "DOCK"].includes(terrain))
    ) {
      alert(`You can't place a ${vehicleType.toLowerCase()} on ${terrain.toLowerCase()}!`);
      return;
    }

    // Move vehicle to target tile
    vehicle.parentElement?.removeChild(vehicle);
    target.appendChild(vehicle);
    vehicle.dataset.tileId = target.dataset.tileId || null;
  });
}

// Apply to grid tiles and dock
tiles.forEach(allowDropTarget);
allowDropTarget(dock);

// ---- START GAME ----
startBtn.addEventListener("click", async () => {
  if (gameStarted) return;
  gameStarted = true;
  startBtn.disabled = true;
  startBtn.textContent = "Game Started!";

  vehicles.forEach(v => (v.draggable = false));

  // Save vehicle positions
  for (const vehicle of vehicles) {
    const vehicleId = vehicle.dataset.vehicleId;
    const tileId = vehicle.dataset.tileId || vehicle.dataset.dockTileId; // use fixed dock tile if on dock

    await fetch(`${urls.updateVehicle}${vehicleId}/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCookie("csrftoken"),
      },
      body: JSON.stringify({ tile_id: tileId }),
    });
  }

  // Update level's "game started" flag in backend
  await fetch(urls.markStart, {
    method: "POST",
    headers: {
      "X-CSRFToken": getCookie("csrftoken"),
    },
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
    // Reset front-end
    vehicles.forEach(vehicle => {
      vehicle.draggable = true;

      // Move vehicle back to its fixed dock tile
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

    // Reload the page to reflect new vehicle positions
    location.reload();
  } else {
    alert("Error resetting level: " + result.message);
  }
});

// ---- DISABLE BUTTON IF GAME STARTED ----
if (gameStarted) {
  startBtn.disabled = true;
  startBtn.textContent = "Game Started!";
  vehicles.forEach(v => (v.draggable = false));
}

// ---- CSRF helper ----
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