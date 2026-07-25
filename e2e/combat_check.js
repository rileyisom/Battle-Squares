// Regression check: placement -> select -> valid moves/targets -> move -> end turn.
// Prereqs: dev server running on :8000, `python setup_scenarios.py placed` has been run.
const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(`pageerror: ${e.message}`));
  page.on('console', (msg) => {
    if (msg.type() === 'error') errors.push(`console: ${msg.text()}`);
  });

  await page.goto('http://127.0.0.1:8000/login/');
  await page.fill('input[name="username"]', 'combattest');
  await page.fill('input[name="password"]', 'combattest-e2e-local');
  await page.click('button[type="submit"]');
  await page.waitForURL('**/', { timeout: 10000 });

  await page.goto('http://127.0.0.1:8000/level/24/');
  await page.waitForSelector('#end-turn-btn:not(.hidden)', { timeout: 10000 });
  await page.screenshot({ path: 'e2e/screenshots/1_battle_start.png' });
  console.log('Turn indicator:', await page.textContent('#turn-indicator'));

  const tank = page.locator("img[data-vehicle-type='TANK']");
  await tank.click();
  await page.waitForTimeout(300);
  const validMoveCount = await page.locator('.tile.valid-move').count();
  console.log('Valid move tiles for TANK:', validMoveCount);
  await page.screenshot({ path: 'e2e/screenshots/2_tank_selected.png' });

  if (validMoveCount > 0) {
    await page.locator('.tile.valid-move').first().click();
    await page.waitForTimeout(300);
    console.log('TANK classes after move:', await tank.getAttribute('class'));
    console.log('TANK new tile-id:', await tank.getAttribute('data-tile-id'));
  }
  await page.screenshot({ path: 'e2e/screenshots/3_tank_moved.png' });

  const plane = page.locator("img[data-vehicle-type='PLANE']");
  await plane.click();
  await page.waitForTimeout(300);
  console.log('Valid move tiles for PLANE:', await page.locator('.tile.valid-move').count());
  console.log('Valid target tiles for PLANE:', await page.locator('.tile.valid-target').count());
  await page.screenshot({ path: 'e2e/screenshots/4_plane_selected.png' });

  await page.click('#end-turn-btn');
  await page.waitForTimeout(1000);
  await page.waitForSelector('#turn-indicator');
  console.log('Turn indicator after End Turn:', await page.textContent('#turn-indicator'));
  await page.screenshot({ path: 'e2e/screenshots/5_after_end_turn.png' });

  console.log('--- Console/page errors ---');
  console.log(errors.length ? errors.join('\n') : '(none)');

  await browser.close();
})();
