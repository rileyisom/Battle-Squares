# Battle Squares ⚔️

A grid-based tactical combat game where tanks, boats, and planes battle for dominance!

## Features
- Level-based grids with terrain (land, water, dock) generated per level
- Turn-based vehicle placement, movement, and attacks
- Terrain-specific vehicle rules (tanks on land, boats on water, planes anywhere)
- A simple enemy AI that attacks in range or closes distance otherwise
- Full-elimination win/loss detection
- Persistent, per-player game state between sessions

## Tech Stack
- Django (Python backend), PostgreSQL
- Tailwind CSS, vanilla JavaScript frontend

## First-time setup

Do this once, when you first clone the repo (or after pulling changes that touch
dependencies, `.env`, or migrations).

```bash
git clone https://github.com/rileyisom/Battle-Squares.git
cd Battle-Squares
```

### 1. Python environment

```bash
python -m venv .venv
```

Activate it — Windows (PowerShell): `.venv\Scripts\Activate.ps1`; macOS/Linux: `source .venv/bin/activate`.

```bash
pip install -r requirements.txt
```

### 2. Node dependencies

Used for Tailwind and Prettier:

```bash
npm install
```

### 3. Environment variables

```bash
cp .env.example .env
```

Fill in `.env` with a real `SECRET_KEY` and your local Postgres credentials.

### 4. Database

Create a Postgres database and user matching your `.env` (adjust names/password as needed):

```bash
psql -c "CREATE DATABASE battlesquares;"
psql -c "CREATE USER battlesquares WITH PASSWORD 'your-password-here';"
psql -c "GRANT ALL PRIVILEGES ON DATABASE battlesquares TO battlesquares;"
```

Then apply migrations:

```bash
python manage.py migrate
```

### 5. Tailwind CSS (optional for a quick start)

A pre-built stylesheet is already checked in at `theme/static/css/dist/styles.css`, so you can skip
this step to just get the app running. To actively develop styles:

```bash
python manage.py tailwind install
python manage.py tailwind start
```

### 6. Create an account

```bash
python manage.py createsuperuser   # for /admin/ access and logging into the game itself
```

## Running the server / testing the app

Do this every time you come back to work on the game.

### 1. Activate the virtualenv

Windows (PowerShell): `.venv\Scripts\Activate.ps1`; macOS/Linux: `source .venv/bin/activate`.

Your prompt should show a `(.venv)` prefix once it's active. If activation fails on Windows with a
"running scripts is disabled" error, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once
and try again.

### 2. Start the dev server

```bash
python manage.py runserver
```

Visit `http://127.0.0.1:8000/` — it redirects to `/login/`, since the game requires an account. Log
in with the superuser you created during setup (or any other account you've created).

### 3. Run the automated tests

Django unit tests:

```bash
python manage.py test
```

Playwright end-to-end regression checks that drive the actual grid UI in a browser (combat loop,
win/loss, reset). One-time setup, from the `e2e/` folder:

```bash
cd e2e
npm install
npx playwright install chromium
```

Then, from the project root, with the dev server running (`--noreload` avoids Windows
file-watcher issues; restart manually after backend changes):

```bash
./.venv/Scripts/python.exe manage.py runserver 127.0.0.1:8000 --noreload
```

And in another terminal, from the project root, run each check (each `setup_scenarios.py` call
resets a known DB state on a dedicated `combattest` test account before the matching script
exercises it):

```bash
./.venv/Scripts/python.exe e2e/setup_scenarios.py placed
node e2e/combat_check.js

./.venv/Scripts/python.exe e2e/setup_scenarios.py tight_win
node e2e/win_check.js

./.venv/Scripts/python.exe e2e/setup_scenarios.py mid_battle
node e2e/reset_check.js
```

See `e2e/README.md` for what each check covers.
