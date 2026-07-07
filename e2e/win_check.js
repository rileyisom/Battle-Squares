// Regression check: attack -> damage -> destroy -> win condition -> action lockout.
// Prereqs: dev server running on :8000, `python setup_scenarios.py tight_win` has been run.
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
  await page.fill('input[name="password"]', '***REMOVED-PASSWORD***');
  await page.click('button[type="submit"]');
  await page.waitForURL('**/', { timeout: 10000 });

  await page.goto('http://127.0.0.1:8000/level/24/');
  await page.waitForSelector('#end-turn-btn:not(.hidden)', { timeout: 10000 });

  for (let round = 1; round <= 6; round++) {
    if ((await page.locator('#game-over-banner.hidden').count()) === 0) {
      console.log(`Round ${round}: game over banner already visible, stopping.`);
      break;
    }

    const tank = page.locator("img[data-vehicle-type='TANK']");
    await tank.click();
    await page.waitForTimeout(200);

    const targetCount = await page.locator('.tile.valid-target').count();
    console.log(`Round ${round}: valid targets = ${targetCount}`);

    if (targetCount > 0) {
      const enemyTank = page.locator("img[data-vehicle-type='ENEMY_TANK']");
      const healthBefore =
        (await enemyTank.count()) > 0 ? await enemyTank.getAttribute('data-health') : 'destroyed';
      await page.locator('.tile.valid-target').first().click();
      await page.waitForTimeout(200);
      const stillThere = await enemyTank.count();
      console.log(
        `  attacked. health before=${healthBefore}, enemy tank still present after=${stillThere > 0}`
      );

      if ((await page.locator('#game-over-banner.hidden').count()) === 0) {
        console.log(`  Game over banner appeared: "${await page.textContent('#game-over-message')}"`);
        await page.screenshot({ path: 'e2e/screenshots/win_banner.png' });
        break;
      }
    }

    await page.click('#end-turn-btn');
    await page.waitForTimeout(800);
    await page.waitForSelector('#turn-indicator');
    console.log(`  after end turn: ${await page.textContent('#turn-indicator')}`);
  }

  console.log('End-turn button disabled:', (await page.getAttribute('#end-turn-btn', 'disabled')) !== null);

  console.log('--- Console/page errors ---');
  console.log(errors.length ? errors.join('\n') : '(none)');

  await browser.close();
})();
