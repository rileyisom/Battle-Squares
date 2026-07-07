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

## Setup

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

### 6. Run it

```bash
python manage.py createsuperuser   # optional, for /admin/
python manage.py runserver
```

Visit `http://127.0.0.1:8000/`.
