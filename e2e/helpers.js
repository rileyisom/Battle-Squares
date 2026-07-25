const path = require('path');

function loadEnv() {
  if (typeof process.loadEnvFile === 'function' && !process.env.CLAUDE_TEST_USERNAME) {
    process.loadEnvFile(path.join(__dirname, '..', '.env'));
  }
}

async function loginAsClaude(page, baseUrl = 'http://127.0.0.1:8000') {
  loadEnv();
  const username = process.env.CLAUDE_TEST_USERNAME;
  const password = process.env.CLAUDE_TEST_PASSWORD;
  if (!username || !password) {
    throw new Error('CLAUDE_TEST_USERNAME/CLAUDE_TEST_PASSWORD not set in .env');
  }
  await page.goto(`${baseUrl}/login/`);
  await page.fill('input[name="username"]', username);
  await page.fill('input[name="password"]', password);
  await page.click('button[type="submit"]');
  await page.waitForURL('**/', { timeout: 10000 });
}

module.exports = { loginAsClaude };
