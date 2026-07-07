# Combat loop e2e checks

Playwright scripts that drive the actual grid UI in a browser to check the
combat loop end-to-end (selection highlighting, move/attack, turn passing,
enemy AI, win/loss, reset). These aren't a full test suite — they're the
scripts used to verify the combat loop while building it, kept around so
regressions in this area are easy to re-check by hand.

## Prerequisites

From this `e2e/` folder:

```bash
npm install
npx playwright install chromium
```

Start the Django dev server (from the project root):

```bash
./.venv/Scripts/python.exe manage.py runserver 127.0.0.1:8000 --noreload
```

`--noreload` avoids Windows file-watcher issues; restart the server manually
after backend code changes.

## Running a check

Each script needs its DB scenario set up first via `setup_scenarios.py`
(uses a dedicated `combattest` user on Level 1, id 24 — safe to reset
without touching real player data):

```bash
./.venv/Scripts/python.exe e2e/setup_scenarios.py placed
node e2e/combat_check.js

./.venv/Scripts/python.exe e2e/setup_scenarios.py tight_win
node e2e/win_check.js

./.venv/Scripts/python.exe e2e/setup_scenarios.py mid_battle
node e2e/reset_check.js
```

Screenshots land in `e2e/screenshots/`. Each script also collects browser
console/page errors and prints them at the end — `(none)` is the expected
result.

## What each one covers

- **combat_check.js**: placement → select vehicle → valid move/attack
  highlighting → move → end turn → enemy AI takes its turn.
- **win_check.js**: repeated attacks → damage accumulates → target destroyed
  → full-elimination win condition fires → further board actions lock out.
- **reset_check.js**: Reset Game from a mid-battle (not yet won/lost) state
  restores vehicle positions/health and recreates any destroyed vehicles.
