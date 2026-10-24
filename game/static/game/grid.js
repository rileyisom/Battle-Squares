import { runAim } from './aim.js';

export class GameGrid {
  constructor(rootEl, config) {
    this.root = rootEl;
    this.gridWidth = config.gridWidth;
    this.gridHeight = config.gridHeight;
    this.levelId = config.levelId;
    this.urls = config.urls;
    this.gameStarted = config.gameStarted;
    this.currentPhase = config.currentPhase || 'PLAYER';
    this.gameStatus = config.gameStatus || 'IN_PROGRESS';
    this.turnNumber = config.turnNumber || 1;
    this.selectedVehicleEl = null;
    this.selectedInfo = null;
    this.selectedTargetCount = 0;
    // Shot forecasts for the selected vehicle, keyed by target id.
    this.forecasts = new Map();

    // Bottom 40% starts at this row index (matches admin.py: height - int(height * 0.4))
    this.bottomZoneStart = this.gridHeight - Math.floor(this.gridHeight * 0.4);

    this.startBtn = document.getElementById('start-btn');
    this.resetBtn = document.getElementById('reset-btn');
    this.endTurnBtn = document.getElementById('end-turn-btn');
    this.turnIndicator = document.getElementById('turn-indicator');
    this.gameOverBanner = document.getElementById('game-over-banner');
    this.gameOverMessage = document.getElementById('game-over-message');
    this.retryBtn = document.getElementById('retry-btn');
    this.infoPanel = document.getElementById('info-panel');
    this.gridEl = document.getElementById('grid');
    this.tiles = this.root.querySelectorAll('.tile');
    this.dock = document.getElementById('vehicle-dock');

    this.vehicles = this.root.querySelectorAll(".vehicle[data-vehicle-type]:not([alt*='ENEMY'])");

    this._assignDockTileIds();
    this._markPlayerZone();
    this._bindUI();
    this._bindDragDrop();
    this._applyInitialState();
    this._updateStartButtonVisibility();
  }

  // ---------- INITIALIZE ----------
  _markPlayerZone() {
    this.tiles.forEach((tile) => {
      const tileY = parseInt(tile.dataset.tileY, 10);
      if (tileY >= this.bottomZoneStart) {
        tile.classList.add('player-zone');
      }
      if (tileY === this.bottomZoneStart) {
        tile.classList.add('player-zone-boundary');
      }
    });
  }

  _assignDockTileIds() {
    this.vehicles.forEach((v) => {
      if (!v.dataset.dockTileId) {
        v.dataset.dockTileId = v.dataset.tileId || null;
      }
    });
  }

  _bindUI() {
    this.startBtn.addEventListener('click', () => this.startGame());
    this.resetBtn.addEventListener('click', () => this.resetLevel());
    this.endTurnBtn.addEventListener('click', () => this.endTurn());
    this.retryBtn.addEventListener('click', () => this.resetLevel());
  }

  _bindDragDrop() {
    // Use event delegation instead of binding to every tile
    document.addEventListener('dragstart', (e) => this._onDragStart(e));
    document.addEventListener('dragend', (e) => this._onDragEnd(e));

    this.tiles.forEach((tile) => this._makeDropTarget(tile));
    this._makeDropTarget(this.dock);
  }

  _applyInitialState() {
    if (this.gameStarted) {
      this.startBtn.disabled = true;
      this.startBtn.textContent = 'Game Started!';
      this.startBtn.classList.add('hidden');
      this.vehicles.forEach((v) => (v.draggable = false));
      this._enterBattleMode();
    }
  }

  _updateStartButtonVisibility() {
    if (this.gameStarted) return;
    const allPlaced = this.dock.querySelectorAll('.vehicle[data-vehicle-type]').length === 0;
    this.startBtn.classList.toggle('hidden', !allPlaced);
  }

  // ---------- BATTLE MODE ----------
  _enterBattleMode() {
    this.endTurnBtn.classList.remove('hidden');
    this.turnIndicator.classList.remove('hidden');
    this._updateTurnIndicator();
    document.addEventListener('click', (e) => this._onBoardClick(e));
    document.addEventListener('mouseover', (e) => this._onBoardHover(e));

    if (this.gameStatus !== 'IN_PROGRESS') {
      this._showGameOver(this.gameStatus);
    }
  }

  _updateTurnIndicator() {
    this.turnIndicator.textContent = `Turn ${this.turnNumber} — ${
      this.currentPhase === 'PLAYER' ? 'Your turn' : "Enemy's turn"
    }`;
  }

  _showGameOver(status) {
    this.gameOverMessage.textContent = status === 'WON' ? 'Victory!' : 'Defeat!';
    this.gameOverBanner.classList.remove('hidden');
    this.endTurnBtn.disabled = true;
  }

  _onBoardClick(e) {
    if (this.gameStatus !== 'IN_PROGRESS' || this.currentPhase !== 'PLAYER') return;

    const vehicleEl = e.target.closest('.vehicle[data-vehicle-id]');
    const tileEl = e.target.closest('.tile[data-tile-id]');

    if (vehicleEl && vehicleEl.dataset.isEnemy === 'true' && this.selectedVehicleEl) {
      const parentTile = vehicleEl.closest('.tile');
      if (parentTile && parentTile.classList.contains('valid-target')) {
        this._attack(vehicleEl);
        return;
      }
      // Clicked an enemy that can't be reached — say so instead of just
      // dropping the selection, which reads as the click being ignored.
      this._showPanelMessage('Out of attack range. Shaded tiles show this unit’s reach.');
      return;
    }

    if (vehicleEl && vehicleEl.dataset.isEnemy === 'false') {
      if (vehicleEl.classList.contains('acted')) {
        this._clearSelection();
        this._showPanelMessage('That vehicle has already acted this turn.');
        return;
      }
      this._selectVehicle(vehicleEl);
      return;
    }

    if (tileEl && tileEl.classList.contains('valid-move') && this.selectedVehicleEl) {
      this._move(tileEl);
      return;
    }

    this._clearSelection();
  }

  async _selectVehicle(vehicleEl) {
    const vehicleId = vehicleEl.dataset.vehicleId;
    const response = await fetch(`${this.urls.vehicleActions}${vehicleId}/`);
    const result = await response.json();

    this._clearSelection();
    if (result.status !== 'ok') {
      // Surface the reason rather than appearing inert.
      this._showPanelMessage(result.message || 'That vehicle cannot act right now.');
      return;
    }

    this.selectedVehicleEl = vehicleEl;
    vehicleEl.classList.add('selected');

    result.moves.forEach((tileId) => {
      const tile = this.root.querySelector(`.tile[data-tile-id='${tileId}']`);
      if (tile) tile.classList.add('valid-move');
    });

    (result.attack_tiles || []).forEach((tileId) => {
      const tile = this.root.querySelector(`.tile[data-tile-id='${tileId}']`);
      if (tile) tile.classList.add('in-attack-range');
    });

    this.selectedInfo = result.vehicle || null;
    this.selectedTargetCount = result.targets.length;
    this._renderVehicleInfo();

    result.targets.forEach((forecast) => {
      this.forecasts.set(String(forecast.target_id), forecast);
      const targetVehicle = this.root.querySelector(
        `.vehicle[data-vehicle-id='${forecast.target_id}']`
      );
      const tile = targetVehicle ? targetVehicle.closest('.tile') : null;
      if (tile) tile.classList.add('valid-target');
    });
  }

  _clearSelection() {
    if (this.selectedVehicleEl) this.selectedVehicleEl.classList.remove('selected');
    this.selectedVehicleEl = null;
    this.selectedInfo = null;
    this.selectedTargetCount = 0;
    this.forecasts.clear();
    this._renderForecast(null);
    this.root
      .querySelectorAll('.valid-move, .valid-target, .in-attack-range')
      .forEach((t) => t.classList.remove('valid-move', 'valid-target', 'in-attack-range'));
  }

  _showPanelMessage(text) {
    if (!this.infoPanel) return;
    this.infoPanel.innerHTML = `<div class="panel-message"></div>`;
    this.infoPanel.firstChild.textContent = text;
  }

  // ---------- SHOT FORECAST ----------
  _onBoardHover(e) {
    if (!this.selectedVehicleEl) return;
    const vehicleEl = e.target.closest('.vehicle[data-vehicle-id]');
    const id =
      vehicleEl && vehicleEl.dataset.isEnemy === 'true' ? vehicleEl.dataset.vehicleId : null;
    const forecast = id ? this.forecasts.get(id) : null;
    // Fall back to the selected unit's own card rather than blanking, so the
    // panel always explains what the highlights on the board mean.
    if (forecast) this._renderForecast(forecast);
    else this._renderVehicleInfo();
  }

  _renderVehicleInfo() {
    if (!this.infoPanel) return;
    const info = this.selectedInfo;
    if (!info) {
      this.infoPanel.innerHTML = '';
      return;
    }

    // Spelled out because move and attack range differ for some types (the
    // plane can fly a ring further than it can shoot), which otherwise reads
    // as the game refusing to target a perfectly reachable enemy.
    const splitRange =
      info.move_range !== info.attack_range
        ? `<div class="unit-hint">Moves ${info.move_range}, shoots ${info.attack_range} — only the shaded tiles are in firing range.</div>`
        : '';
    const noTargets =
      this.selectedTargetCount === 0 ? `<div class="unit-hint">No targets in range.</div>` : '';

    this.infoPanel.innerHTML = `
      <div class="forecast">
        <div class="unit-name">${info.type.replace('_', ' ')}</div>
        <div class="forecast-row">
          <span>HP</span><strong>${info.health}/${info.max_health}</strong>
        </div>
        <div class="forecast-row">
          <span>Move</span><strong>${info.move_range}</strong>
        </div>
        <div class="forecast-row">
          <span>Shoot</span><strong>${info.attack_range}</strong>
        </div>
        ${splitRange}${noTargets}
      </div>
    `;
  }

  _renderForecast(forecast) {
    if (!this.infoPanel) return;

    if (!forecast) {
      this.infoPanel.innerHTML = '';
      return;
    }

    // Quality is what the aim minigame will key off: a high-quality shot has a
    // tight band and a wide crit window, so it is forgiving to aim.
    const quality = Math.round(forecast.quality * 100);
    const qualityClass = quality >= 70 ? 'q-high' : quality >= 45 ? 'q-mid' : 'q-low';
    const critWindow = Math.round(forecast.crit_window * 100);
    const lethality = {
      certain: ['Lethal', 'text-green-400'],
      likely: ['Can finish', 'text-yellow-300'],
      crit_only: ['Lethal on crit', 'text-orange-300'],
      no: ['Not lethal', 'text-gray-400'],
    }[forecast.lethality] || ['', 'text-gray-400'];

    this.infoPanel.innerHTML = `
      <div class="forecast">
        <div class="forecast-row">
          <span>Damage</span><strong>${forecast.min}–${forecast.max}</strong>
        </div>
        <div class="forecast-row">
          <span>Crit</span><strong>${forecast.crit_damage}</strong>
        </div>
        <div class="forecast-row">
          <span>Crit window</span><strong>${critWindow}%</strong>
        </div>
        <div class="forecast-row">
          <span>Target HP</span><strong>${forecast.target_health}</strong>
        </div>
        <div class="forecast-quality">
          <div class="forecast-quality-fill ${qualityClass}" style="width: ${quality}%"></div>
        </div>
        <div class="forecast-quality-label">Shot quality ${quality}%</div>
        <div class="forecast-lethality ${lethality[1]}">${lethality[0]}</div>
      </div>
    `;
  }

  async _move(tileEl) {
    const vehicleEl = this.selectedVehicleEl;
    const vehicleId = vehicleEl.dataset.vehicleId;
    const tileId = tileEl.dataset.tileId;

    const response = await fetch(`${this.urls.moveVehicle}${vehicleId}/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this._getCSRF() },
      body: JSON.stringify({ tile_id: tileId }),
    });
    const result = await response.json();
    if (result.status !== 'ok') {
      alert(result.message);
      return;
    }

    const healthBar = vehicleEl.parentElement.querySelector(`[data-health-bar-for='${vehicleId}']`);
    tileEl.appendChild(vehicleEl);
    if (healthBar) tileEl.appendChild(healthBar);
    vehicleEl.dataset.tileId = tileId;
    vehicleEl.classList.add('acted');

    this._clearSelection();
  }

  async _attack(targetVehicleEl) {
    const attackerEl = this.selectedVehicleEl;
    const attackerId = attackerEl.dataset.vehicleId;
    const targetId = targetVehicleEl.dataset.vehicleId;

    // Only the accuracy crosses the wire; the server recomputes the damage
    // band itself, so a tampered value can shift a shot within its band but
    // never beyond it.
    const accuracy = await runAim(attackerEl.dataset.vehicleType, {
      attackerEl,
      targetEl: targetVehicleEl,
    });

    const response = await fetch(`${this.urls.attack}${attackerId}/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this._getCSRF() },
      body: JSON.stringify({ target_id: targetId, accuracy }),
    });
    const result = await response.json();
    if (result.status !== 'ok') {
      alert(result.message);
      return;
    }

    if (result.target_destroyed) {
      const tile = targetVehicleEl.closest('.tile');
      const healthBar = tile ? tile.querySelector(`[data-health-bar-for='${targetId}']`) : null;
      targetVehicleEl.remove();
      if (healthBar) healthBar.remove();
    } else {
      this._setHealth(targetId, result.target_health);
    }

    attackerEl.classList.add('acted');
    this._clearSelection();

    if (result.game_status !== 'IN_PROGRESS') {
      this.gameStatus = result.game_status;
      this._showGameOver(result.game_status);
    }
  }

  _setHealth(vehicleId, health) {
    const vehicleEl = this.root.querySelector(`.vehicle[data-vehicle-id='${vehicleId}']`);
    if (!vehicleEl) return;

    const maxHealth = parseInt(vehicleEl.dataset.maxHealth, 10) || 100;
    const pct = Math.max(0, Math.min(100, Math.round((health / maxHealth) * 100)));
    const tile = vehicleEl.closest('.tile');
    const fill = tile
      ? tile.querySelector(`[data-health-bar-for='${vehicleId}'] .health-bar-fill`)
      : null;
    if (fill) fill.style.width = `${pct}%`;
    vehicleEl.dataset.health = health;
  }

  async endTurn() {
    if (this.gameStatus !== 'IN_PROGRESS' || this.currentPhase !== 'PLAYER') return;

    const response = await fetch(this.urls.endTurn, {
      method: 'POST',
      headers: { 'X-CSRFToken': this._getCSRF() },
    });
    const result = await response.json();
    if (result.status !== 'ok') {
      alert(result.message);
      return;
    }

    location.reload();
  }

  // ---------- DRAG HANDLERS ----------
  _onDragStart(e) {
    if (this.gameStarted) return;

    const vehicle = e.target.closest('.vehicle[data-vehicle-type]');
    if (!vehicle) return;

    vehicle.classList.add('dragging');
    e.dataTransfer.setData('vehicleId', vehicle.dataset.vehicleId);
    e.dataTransfer.setData('vehicleType', vehicle.dataset.vehicleType);
    this.gridEl.classList.add('placement-active');
  }

  _onDragEnd(e) {
    const vehicle = e.target.closest('.vehicle[data-vehicle-type]');
    if (vehicle) vehicle.classList.remove('dragging');

    this.root
      .querySelectorAll('.valid-drop, .invalid-drop')
      .forEach((tile) => tile.classList.remove('valid-drop', 'invalid-drop'));

    this.gridEl.classList.remove('placement-active');
  }

  // ---------- DROP TARGETS ----------
  _makeDropTarget(target) {
    target.addEventListener('dragover', (e) => this._onDragOver(e, target));
    target.addEventListener('dragleave', () =>
      target.classList.remove('valid-drop', 'invalid-drop')
    );
    target.addEventListener('drop', (e) => this._onDrop(e, target));
  }

  _onDragOver(e, target) {
    if (this.gameStarted) return;
    e.preventDefault();

    const vehicle = this.root.querySelector('.vehicle.dragging');
    if (!vehicle) return;

    const vehicleType = vehicle.dataset.vehicleType;
    const terrain = this._getTerrainType(target);

    const invalid = this._isInvalidPlacement(vehicleType, terrain, target);

    target.classList.toggle('valid-drop', !invalid);
    target.classList.toggle('invalid-drop', invalid);
  }

  _onDrop(e, target) {
    if (this.gameStarted) return;
    e.preventDefault();

    target.classList.remove('valid-drop', 'invalid-drop');

    const vehicleId = e.dataTransfer.getData('vehicleId');
    const vehicle = this.root.querySelector(`[data-vehicle-id='${vehicleId}']`);

    if (!vehicle) return;

    // Return to dock
    if (target.id === 'vehicle-dock') {
      vehicle.dataset.tileId = vehicle.dataset.dockTileId;
      target.appendChild(vehicle);
      this._updateStartButtonVisibility();
      return;
    }

    // Can't stack vehicles
    if (target.classList.contains('tile') && target.querySelector('.vehicle')) return;

    const terrain = this._getTerrainType(target);
    const vehicleType = vehicle.dataset.vehicleType;

    if (this._isInvalidPlacement(vehicleType, terrain, target)) return;

    target.appendChild(vehicle);
    vehicle.dataset.tileId = target.dataset.tileId || null;
    this._updateStartButtonVisibility();
  }

  // ---------- GAME ACTIONS ----------
  async startGame() {
    if (this.gameStarted) return;

    this.gameStarted = true;
    this.startBtn.disabled = true;
    this.startBtn.textContent = 'Game Started!';

    this.vehicles.forEach((v) => (v.draggable = false));

    // Save positions
    for (const v of this.vehicles) {
      const vehicleId = v.dataset.vehicleId;
      const tileId = v.dataset.tileId || v.dataset.dockTileId;

      await fetch(`${this.urls.updateVehicle}${vehicleId}/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': this._getCSRF(),
        },
        body: JSON.stringify({ tile_id: tileId }),
      });
    }

    // Mark started
    await fetch(this.urls.markStart, {
      method: 'POST',
      headers: { 'X-CSRFToken': this._getCSRF() },
    });

    location.reload();
  }

  async resetLevel() {
    if (!confirm('Reset all positions?')) return;

    const response = await fetch(this.urls.resetLevel, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': this._getCSRF(),
      },
    });

    const result = await response.json();

    if (result.status !== 'ok') {
      alert('Error resetting level: ' + result.message);
      return;
    }

    // Move every vehicle back
    this.vehicles.forEach((vehicle) => {
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
    this.startBtn.textContent = 'Start Game';

    location.reload();
  }

  // ---------- HELPERS ----------
  _getTerrainType(tile) {
    if (tile.classList.contains('WATER')) return 'WATER';
    if (tile.classList.contains('LAND')) return 'LAND';
    if (tile.classList.contains('DOCK')) return 'DOCK';
    return 'OTHER';
  }

  _isInvalidPlacement(vehicleType, terrain, tile) {
    const occupied = tile.classList.contains('tile') && tile.querySelector('.vehicle');

    if (occupied) return true;
    if (vehicleType.includes('BOAT') && !['WATER', 'DOCK'].includes(terrain)) return true;
    if (vehicleType.includes('TANK') && !['LAND', 'DOCK'].includes(terrain)) return true;

    // Non-dock tiles must be in the player zone (bottom 40%)
    if (terrain !== 'DOCK' && !tile.classList.contains('player-zone')) return true;

    return false;
  }

  _getCSRF() {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; csrftoken=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
  }
}
