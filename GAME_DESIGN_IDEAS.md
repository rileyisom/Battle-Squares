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

## Combat revision (designed 2026-10-24)

### Why the current loop feels flat
Diagnosis before solutions — the problem is a lack of *decisions*, not a lack of randomness:
- Attacking is free and strictly dominant. No cost, no risk, so "is an enemy in range?" has exactly one right answer.
- Outcomes are perfectly predictable. 100hp / 25dmg = always 4 hits; the whole battle is solvable in your head on turn 1.
- Position only gates range. Manhattan distance + terrain legality are the only spatial facts — no flanking, cover, or facing, so moving is just "walk toward the enemy."
- The three vehicle types have no identity beyond four stat numbers and which tiles they can stand on.

### Luck philosophy
- Randomness goes in **magnitude, not success**. No hit/miss rolls — a whiffed turn costs the player their whole activation through no fault of their own and reads as the game cheating (the XCOM 95%-miss feeling). Variable damage always makes progress, sometimes great progress: same variance, much better feel.
- Always show the forecast *before* committing. A bad outcome the player accepted is drama; an unexplained one is noise.
- Let players buy certainty. Good positioning should narrow the spread, not just add a flat bonus — luck becomes a dial the player controls rather than a tax they pay.
- Bias toward upside. Crits feel better than misses at identical expected value.

### Aim minigame (the core idea)
Replace the single click-to-attack with a short skill check: on attack, the attacker's gun oscillates across an arc and the player presses a key to stop it. Where it stops determines damage.

The crucial relationship — **tactics set the band, execution sets the position within it**:
- Good position/matchup/terrain → tight band with a high floor (e.g. 24–30). Even a sloppy shot lands respectably.
- Bad position → wide band with a low floor (e.g. 8–30). Great timing can rescue it, but it's a gamble.
- Net effect: a perfect shot from a bad position ≈ a lazy shot from a good one. The minigame *expresses* tactical advantage instead of replacing it.

Crits live naturally here: a narrow "perfect" zone at the center of the arc, whose **width is set by tactics**. Flanking literally widens your crit window — a legible, satisfying feedback loop the player grasps immediately.

This supersedes random damage rolls. One source of variance is cleaner than two; the band concept is what we keep, because that's where the tactics live.

### Risks (in priority order)
1. **Repetition fatigue — the big one.** A tactics battle has many attacks (3 units × ~8 turns = 24+ minigames per level). If each is a 2-second ceremony, players are mashing through it resentfully by level 3. Mitigations: keep it ~1s / 2 oscillation cycles max; make it skippable (auto-resolve to the band midpoint); rely on the band being *narrow* when you're playing well, so good play barely notices it while bad shots feel appropriately dicey.
2. **Decoupling skill from tactics.** If reflexes dominate damage, positioning and matchups stop mattering and the genre inverts. The band design above is the defense; keep the band's influence dominant over the minigame's.
3. **Accessibility.** Timing challenges exclude players with motor or latency constraints. The auto-resolve path is the answer, and it doubles as the fast-forward for experienced players.
4. **Trust.** The minigame runs client-side, so the server must never accept a client-reported damage number.

### Architecture: the `accuracy` seam
Split attack resolution into two phases so the minigame is a pluggable frontend concern:
- `combat.damage_band(attacker, defender)` → `{min, max, crit_zone}`. Pure function, server-authoritative, derived from matchup/terrain/flanking/range. This is the forecast shown in the UI *and* the thing used at resolution — one source of truth.
- `combat.resolve_damage(band, accuracy)` → damage, where `accuracy` is a single normalized float in `[0, 1]`.
- `POST /attack/` carries `{target_id, accuracy}`. The server recomputes the band from scratch and clamps/validates `accuracy`; it trusts the client for *nothing else*.

Why this is expandable: `accuracy` is a **minigame-agnostic scalar**. The oscillating gun is just the first UI that produces one. Later additions — a shrinking-ring timing circle, a button-mash burst, a drag-and-release artillery arc for boats, a multi-tap volley — all reduce to the same float, and the server never changes. Frontend gets an `AimMinigame` interface (`run(vehicleType) -> Promise<accuracy>`) plus a registry keyed on vehicle type, defaulting to an instant `0.5`.

Bonus: **enemy accuracy becomes the difficulty dial.** Enemy attacks go through the identical code path with an AI-supplied accuracy (level 1 → ~0.4, late levels → ~0.75). Same mechanic, no special-casing, and it covers "difficulty scaling per level" from the build order above.

### Supporting mechanics (ranked by leverage)
- **Return fire** — attacking a survivor that has you in *its* range draws a ~50% counterpunch. Highest-leverage single change: it makes attacking a risk instead of a freebie, and it makes the existing range stats finally matter (a boat at range 2 safely shells a range-1 tank; the tank must close and eat a hit).
- **Move *and* attack with a penalty** — currently move XOR attack. Allowing both, with firing-after-moving widening the band, creates the classic tension: hold still for a strong shot or reposition for a weak one. Cheaper than full action points and gets most of the value.
- **Type matchups** — a clean triangle at 1.5×: Plane → Boat, Boat → Tank, Tank → Plane. Gives each unit identity; pairs naturally with existing terrain rules.
- **Terrain as cover** — a `_terrain_defense()` beside the existing `_terrain_allowed()`. Land gives tanks cover, open water leaves boats exposed, docks are fortified.
- **Hit feedback** — floating damage numbers, flash/shake on crit, animated health bars. Currently a hit silently decrements a number. Deliberately called out as *under-weighted*: much of "combat feels flat" is feedback, not mechanics, and this is the cheapest fix with zero balance risk.
- **Smarter enemy targeting** — the AI picks `nearest` and only ever considers attacking that unit, so it'll chip a healthy tank while a 10hp plane sits in range. Prefer kills, then lowest HP.

### Proposed build order
1. `damage_band` + `resolve_damage` + the `accuracy` wire protocol — the seam, with auto-resolve (0.5) as the only "minigame". Nothing visibly changes yet; this is pure groundwork.
2. Forecast UI — widen `vehicle_actions`' `targets` to `{id, min, max, crit_chance, lethal}` and show it on hover. Makes the band legible before any minigame exists.
3. Hit feedback (floating numbers, crit flash). Cheap, immediately improves feel, independent of everything else.
4. The oscillating-gun minigame as the first real `AimMinigame`.
5. Return fire, then type matchups, then move-and-attack. Re-balance after each — return fire alone will shift things a lot.

### Open questions
- Should enemy attacks get a *defensive* minigame (a "brace" reaction)? Leaning no — it doubles interaction count and slows enemy turns, which is exactly where repetition fatigue bites hardest.
- Does the oscillation arc read better as a spatial arc over the target, or an abstract meter? The arc is more thematic but harder to make legible on a 10×10 grid of small sprites.
- Per-vehicle minigame variety is the expandable payoff, but it also multiplies the learning curve. Maybe one shared minigame until the game is otherwise feature-complete.
- Does `has_acted` survive move-and-attack, or does it become a per-unit action budget? The latter is the real fix but a bigger refactor.

## Shop / economy (not yet designed)
- (nothing concrete yet — flesh out once combat loop exists)

## Upgrades (not yet designed)
- (nothing concrete yet)

## Open questions / parking lot
- What does "losing" a level do — retry immediately, lose currency, etc.? Partially settled: a Retry Level button now exists on the game-over banner, so retry-immediately is the default. Whether a loss should *cost* anything is still open and depends on the economy.
- Should enemy turns be scripted AI or simple heuristics (move toward nearest player unit, attack in range)? Still heuristics. See the combat revision above — enemy `accuracy` is a cheap difficulty dial that may reduce the need for smarter scripting.
