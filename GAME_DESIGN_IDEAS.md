# Game Design Ideas Ledger

Running log of gameplay/design ideas discussed for this project. Newest entries at the bottom of each section. This is a brainstorming ledger, not a spec — implementation status belongs in code/commits, not here.

## Core direction
- Level-based progression: each `Level` is a discrete map with its own difficulty.
- As players advance through levels: grids get bigger, more vehicles (player and enemy), better upgrades unlock.
- A shop for spending earned currency on upgrades between levels.

## Combat loop (built 2026-07-06)
- Decisions: alternating turns (player acts with any/all units, then End Turn hands the phase to enemy AI), simple fixed damage per vehicle type (no matchup multipliers yet), full-elimination win/loss.
- Placeholder balance numbers (tune later): TANK 100hp/move2/range1/dmg25, BOAT 100hp/move3/range2/dmg20, PLANE 75hp/move4/range2/dmg30.
- Movement/targeting use Manhattan distance with no pathfinding/obstruction — a tile in range is reachable if it's empty and legal terrain. Fine for now; revisit if it hurts the feel once islands get more maze-like.
- Enemy AI is a simple greedy heuristic: attack the nearest player unit if in range, else step toward it. No target prioritization (e.g. lowest-health, highest-threat) yet — worth revisiting once there's more than one enemy type interacting per level.
- e2e regression scripts for this loop live in `e2e/` (Playwright) — see `e2e/README.md`.
- Proposed next build order:
  1. ~~Turn-based movement + attack resolution + win/loss condition~~ — done.
  2. Level progression gating: unlock level N+1 once level N is won.
  3. Difficulty scaling per level: bigger `width`/`height`, more `StartingVehicle` entries — mostly free since the admin generator already parameterizes on these.
  4. Currency + shop + upgrades: needs new concept — persistent player profile/currency across levels, an upgrade/ownership model, coins awarded on level win.

## Shop / economy (not yet designed)
- (nothing concrete yet — flesh out once combat loop exists)

## Upgrades (not yet designed)
- (nothing concrete yet)

## Open questions / parking lot
- What does "losing" a level do — retry immediately, lose currency, etc.?
- Should enemy turns be scripted AI or simple heuristics (move toward nearest player unit, attack in range)?
