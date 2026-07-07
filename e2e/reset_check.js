// Regression check: Reset Game restores a battle in progress (not just a finished one) —
// clears health/positions/has_acted and recreates any destroyed vehicles.
// Prereqs: dev server running on :8000, `python setup_scenarios.py mid_battle` has been run.
const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  page.on('dialog', (d) => d.accept());

  await page.goto('http://127.0.0.1:8000/login/');
  await page.fill('input[name="username"]', 'combattest');
  await page.fill('input[name="password"]', '***REMOVED-PASSWORD***');
  await page.click('button[type="submit"]');
  await page.waitForURL('**/', { timeout: 10000 });

  await page.goto('http://127.0.0.1:8000/level/24/');
  await page.waitForSelector('#reset-btn', { timeout: 10000 });
  await page.click('#reset-btn');
  await page.waitForTimeout(1000);
  await page.waitForSelector('#start-btn:not(.hidden)');

  console.log('Start button visible again:', await page.isVisible('#start-btn'));
  console.log('Vehicles in dock:', await page.locator('#vehicle-dock .vehicle').count());
  console.log('Enemy tank on board:', await page.locator("img[data-vehicle-type='ENEMY_TANK']").count());
  console.log('Enemy plane on board:', await page.locator("img[data-vehicle-type='ENEMY_PLANE']").count());
  console.log('Enemy boat on board:', await page.locator("img[data-vehicle-type='ENEMY_BOAT']").count());

  await browser.close();
})();
