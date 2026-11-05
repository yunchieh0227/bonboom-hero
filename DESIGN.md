# BONBOOM HERO! (formerly BONKAGEDDON) — Design & Technical Review

Labels used throughout:
**[PLATFORM]** confirmed from official CrazyGames docs (fetched 2026-11-04) ·
**[ASSUMPTION]** design assumption · **[TUNING]** proposed balance value (all live in `CONFIG` in `index.html`) ·
**[HYPOTHESIS]** unverified — needs analytics/playtest.

---

## 1. Concise GDD

| | |
|---|---|
| Pitch | Drag, aim, release a rapid volley of absurd food-hero balls through multiplier gates; ricochet them into descending "Gloomblocks"; level up, fuse heroes, survive. |
| Session | One run ≈ 6–8 min [HYPOTHESIS]; meta loop: coins → unlocks/shop → next run. |
| Arena | Portrait logical canvas **448 × 800**, 7 columns × 64 px. Rows of enemies descend from the top toward a danger line; a **gate band** sits between the danger line and the launcher, so every shot chooses a gate first. |
| Turn | Aim → volley (5+ balls, 80 ms apart) → bounces/abilities → recall → enemies descend → new row spawns → aim. |
| Fail state | Enemy crosses danger line → lose HP (boss: 3). HP 0 → optional revive (rewarded ad, once) → results. |
| Progression | In-run: XP → 3-card picks (heroes, hero levels, passives, fusions). Meta: coins → permanent upgrades + hero unlocks; codex; 3 daily missions. |
| Identity | Original cast of 8 food heroes + 4 fusions, all procedurally drawn on Canvas; armor/shield enemies make "biggest multiplier" a real trade-off. |

## 2. The 15-second core loop

| t (s) | What happens |
|---|---|
| 0–2 | Player drags. Dotted trajectory shows first bounce + reflected segment; the gate the shot will pass through lights up. |
| 2 | Release. Launcher kicks back, volley starts (5 balls × 80 ms ≈ 0.4 s). |
| 2.2–3 | Balls cross the gate band: ×N gate fans out clones; power/mutation gates tint balls. |
| 3–8 | Ricochets: hit flashes, damage numbers, explosions/lightning/splits; combo counter climbs; kills drop XP orbs that fly to the XP bar. |
| 8 | Balls return through the bottom. After 5 s the sim runs ×2; at 9 s stragglers are recalled. A **Recall** button lets the player end early. Board clear → immediate recall + "CLEAR!" bonus. |
| 8–9 | Enemies slide down one row (frozen ones don't); a new row enters; gates reshuffle. Level-up card screen if XP bar filled. |
| 9–15 | Next aim. |

## 3. First-run experience (new player, no save)

| s | Event |
|---|---|
| 0 | Page loads straight into gameplay [PLATFORM: Full Launch asks to "land players directly in gameplay"]. 2 easy rows on board, a ×2 and a ×3 gate. Animated hand drags from launcher upward, dotted line follows. No text except "DRAG & RELEASE". |
| 2–5 | First shot. Starter hero = **Bananini Boom** (explosions read instantly). Several kills on the first volley; "×2" gate pulse + clone fan. |
| 5–12 | Enemies descend, new row. Hint disappears permanently after first fire. |
| 12–35 | Turns 2–4. Combo text, XP orbs. |
| ~30–45 | **First level-up** (needs 8 XP). First-run cards are curated: Zappy Pickle / Splittini Bean / +1 Ball. |
| 45–60 | New hero in volley — visibly different (lightning or splits). Second level-up lands around 60–80 s. |
| ~2–3 min | First-run weighting pushes toward Splittini + Zappy L2 → **Thunder Pop** fusion card (gold, guaranteed slot when eligible). |
| ~2 min | First boss (wave 5) — tuned to be beatable by a basic build. |

## 4. Physics & state-machine architecture

**Loop**: `requestAnimationFrame` → real dt clamped to 0.1 s → accumulator → fixed steps of **1/120 s** (max 24 steps/frame; time scale ×2 during fast-forward just runs more steps). Rendering interpolation is unnecessary at 120 Hz sim; 60/120/144 Hz displays run identical sim steps per second. `visibilitychange` → freeze and reset clock (no catch-up burst). Per [PLATFORM], we do **not** call `gameplayStop` on tab blur.

**Collision**: circle vs AABB (closest-point; push-out along normal; reflect only if moving into the face). Substeps per ball: `ceil(speed·dt / (0.5·r))`, so max travel per substep < half radius → no tunneling even at 2× Turbo speed. Enemies live on a 7×10 grid → broad-phase = look up only the cells overlapped by the ball's AABB (≤4 cells; boss registers in all its 6 cells). Anti-stall: after every bounce, |vy| ≥ 0.22·speed enforced; per-ball lifetime 10 s.

**Modules (in one file)**: `CONFIG`, `RNG`, `Pool`, `SaveManager`, `CG` (SDK adapter), `AudioManager`, `Input`, `Board` (enemies + grid + waves), `Gates`, `Balls` (physics + abilities), `FX` (particles/text/rings/arcs/steam), `Upgrades`, `Fusion`, `Meta` (shop/unlocks/daily), `UI` (DOM screens), `Renderer`, `Game` (owns state machine).

**State machine** (single owner: `Game.setState`, transition table enforced, illegal transitions logged & ignored):

```
BOOT → MENU | AIMING(first play)
MENU → AIMING
AIMING → FIRING | PAUSED
FIRING → RESOLVING | PAUSED
RESOLVING → AIMING | UPGRADE | FUSION | GAME_OVER | PAUSED
UPGRADE → FUSION | AIMING | UPGRADE (chained level-ups) | AD_PLAYING
FUSION → AIMING | UPGRADE
PAUSED → (previous) | MENU | AIMING (restart)
GAME_OVER → AD_PLAYING (revive) | RESULTS
AD_PLAYING → (return state chosen by requester)
RESULTS → AD_PLAYING (double coins / midgame) | AIMING | MENU
```
`FIRST_PLAY` is a flag on a normal run (hint overlay) rather than a separate state, to avoid duplicating gameplay code. SDK `gameplayStart/Stop` is derived **only** from the "is gameplay" category of the current state, with an internal boolean so duplicate calls are impossible.

## 5. Multiplier-gate rules (anti-exponential)

Gate types: **Multiplier** ×2/×3/×5 (green), **Power** +DMG / +PIERCE / BIG (orange), **Mutation** ⚡/🔥/❄ (purple).

1. A gate triggers only on an **upward** crossing of the gate line, once per ball per volley.
2. **Only original volley balls can multiply.** Clones, split minis and fusion spawns can never trigger a multiplier gate → max balls from gates = volley × largest multiplier (linear, not exponential).
3. Clones inherit hero, ability level, mutations and power mods, but deal **75 %** damage [TUNING] and are drawn smaller/translucent.
4. Clones never return as volley balls; they despawn at the bottom.
5. **Physical cap: 160 active balls** [TUNING]. If spawning would exceed it, each un-spawned clone becomes **+50 % damage "Overcharge"** on the parent (visible glow + "OVERCHARGE" text) — the benefit is kept, the physics cost isn't.
6. Explosions can't trigger explosions; lightning can't trigger lightning; splits can't split. Per-volley effect budget: 220 explosions / 260 lightning arcs; beyond it effects apply plain damage with no visuals [TUNING].
7. Why ×5 isn't always best: (a) ×5 gates are narrower and only spawn near the walls (shallow, low-control angle); (b) **Tank** enemies have flat per-hit **armor**, so many weak clone hits do little while +DMG/BIG power gates or lightning (ignores armor) excel; (c) Shield enemies block hits from below, rewarding clean bank shots over spray.
8. Gate generator constraints: 2–3 non-overlapping gates, ≥1 open gap ≥ 56 px, every gate reachable inside the aim cone (min 9° elevation), at most one ×5, and the trajectory preview always shows which gate you'll pass.

## 6. Character & fusion rules

Volley composition: balls are assigned heroes **round-robin** over the roster (a fusion counts as 2 roster entries so fusing never shrinks the volley).

| Hero | Ability | L1 / L2 / L3 (visible change) |
|---|---|---|
| Sir Croissanto | Pierce | passes through 1 / 2 / 4 enemies per launch (golden lance trail) |
| Bananini Boom | Explosion on hit | radius 38 / 52 / 70, 50 % dmg (ring grows) |
| Frosty Noodle | Chill → Freeze | freeze after 3 / 2 / 2 hits; frozen enemies skip a descent; L3 frozen take +50 % |
| Zappy Pickle | Chain lightning | 2 / 3 / 5 jumps, 110 px, 40 % dmg, ignores armor |
| Splittini Bean | Split on hit | 2 / 2 / 3 minis on first 1 / 2 / 2 hits |
| Magneto Muffin | Homing | turn 2.2 / 3.4 / 5 rad/s, range 160 / 230 / 320; L3 prioritizes elites/boss |
| Turbo Turnip | Speed-up on bounce | +7 % per bounce up to 1.5× / 1.75× / 2×; dmg × speed ratio |
| Count Sipsula | Life steal | 1 HP per 260 / 200 / 150 dmg dealt, max 1 / 1 / 2 heals per turn |

**Fusion**: both ingredients at **L2+** → a gold fusion card is guaranteed in the next pick. Choosing it plays the fusion cutscene and replaces both heroes by the fusion (keeps both base abilities at the ingredients' levels + new behavior). Fusion level = clamp(lvA+lvB−3, 1, 3), upgradable to 3.

| Fusion | Recipe | New behavior (bounded) |
|---|---|---|
| Steam Supreme | Croissanto + Frosty | Hits spawn steam clouds (r 55/70/85, 2.5 s, max 6 alive): DoT + chill; balls inside bounce off the cloud rim up to 3× and regain pierce. |
| Thunder Pop | Splittini + Zappy | Split minis are electrified (2-jump lightning on hit); kills by lightning pop a spark mini (max 40 sparks/volley). |
| Ghost Magnet | Magneto + Croissanto | Phasing homing balls: pass through 6/9/12 enemies, re-target the highest-HP enemy after each pass. |
| Boomarang | Bananini + Turbo | Each bounce adds a boom stack (max 5/7/9) → explosion radius/damage scale with stacks; at max stack a big blast resets stacks. |

First discoveries persist in the save (codex). Fusion progress is run-only.

## 7. Enemy & boss progression

Wave = 3 turns (3 spawn rows). Every 5th wave = boss wave (wave holds until the boss dies).

| Enemy | From wave | HP mult | Special |
|---|---|---|---|
| Gloomlet | 1 | 1.0 | — |
| Minion | 1 | 0.5 | small, packs |
| Tank | 3 | 2.2 | flat armor `2 + 0.5·wave` per direct hit (explosions half, lightning/steam ignore) |
| Shieldy | 4 | 1.3 | bottom face blocks all damage → bank shots |
| Splitter | 7 | 1.2 | spawns 2 minions on death |
| Speedy | 9 | 0.8 | descends 2 rows |
| Elite (modifier) | 6 | ×2 | glows, 3× XP |

Formations rotate per wave: Scatter, Wall-with-gap, Fortress (tanks front), Swarm (minions), Shield line, Checker.

**Boss — "Grand Gloopmaw"** (3×2 cells): rotating shield arc covers its bottom face for 2 turns, drops for 1 turn (telegraphed by icon). Top face is a weak spot (×2 crit). Summons 2 minions per turn. Descends every 2 turns. Breach = 3 HP. Defeat: slow-mo, big blast, +1 HP, +25 coins, 20 XP, `happytime()`.

## 8. First-pass balancing table [TUNING]

| Param | Value |
|---|---|
| Sim step | 1/120 s |
| Ball speed / radius | 820 px/s / 8 px |
| Fire interval | 80 ms (−12 %/passive stack) |
| Volley size | 5 (+1 per shop level, +1 per passive) |
| Base damage | 10 |
| Turn fast-forward / recall | 5 s / 9 s after last ball fired; ball lifetime 10 s |
| Ball cap | 160 |
| Enemy HP | `round(18 · (1+0.25(w−1)) · 1.09^(w−1))` → w1 18, w5 51, w10 127, w15 270, w20 532 |
| Enemies per row | `clamp(2 + floor(w/3) ± 1, 2, 6)`, ≥1 gap until w10 |
| XP to next level | `5 + 3L + L²` → 9, 15, 23, 33… (first-run first level at 8) |
| XP per kill | 1 (tank 2, elite ×3, boss 20) |
| Gate multipliers | ×2 (common), ×3 (w2+), ×5 (w4+, edge-only, narrow) |
| Player HP | 5 (+1 per shop level, max +3) |
| Coins per run | 4·waves + kills/5 + 25·bosses |
| Shop | HP +1: 60/150/300 · Ball +1: 80/200/400 · Fire rate +10 %: 70/180/350 · Dmg +10 %: 70/180/350 · Free reroll: 100/250 |
| Unlocks | Frosty 120 · Turbo 180 · Magneto 240 · Sipsula 300 |
| Daily mission rewards | 30–70 coins |

## 9. Milestone plan

1. Core combat (canvas scaling, input, fixed-step physics, grid enemies, descent, game over, multiplier gates).
2. Game feel (procedural heroes, particles, numbers, shake, WebAudio, HUD).
3. Roguelite (XP, cards, 4 heroes, levels, 2 fusions).
4. Full content (8 heroes, 4 fusions, boss, power/mutation gates, shop, codex, daily missions).
5. CrazyGames (SDK wrapper, data module + localStorage fallback, ads, mute/pause handling).
6. Test & polish (CDP-driven headless Chrome: functional, refresh-rate, dt spikes, viewports, SDK mocks, bot balance runs).

## 10. Top five risks

1. **Fun of the core shot** — if gates feel like a no-brainer the game collapses to "aim at biggest number". Mitigation: armor/shield counters, edge-only ×5, trajectory preview. Needs real playtests.
2. **Performance in chain reactions** — mitigated by caps, pools, grid broad-phase, effect budgets; mid-range mobile not verifiable here.
3. **Balance / run length** — single-developer tuning; mitigated with a headless bot run, but bot ≠ human.
4. **SDK edge cases** (ads never calling back, data module disabled) — wrapper with watchdog timeouts and localStorage fallback; real CrazyGames environment can't be exercised from here.
5. **Readability on small landscape screens** — portrait 448×800 scaled to a 390 px tall landscape phone is small; acceptable but not ideal.

## 11. Testing strategy

Automated via Chrome DevTools Protocol (headless Chrome, Python `websocket-client`), test hooks on `window.BONK`:
- Functional: start → aim → fire (real synthesized mouse **and** touch events) → hits → descent → damage → death → results → restart ×20 (leak/freeze check).
- Physics determinism: same seed/aim simulated with frame dt 1/60, 1/120, 1/144 and 0.25 s spikes → compare ball count, damage, positions.
- Tunneling: balls at 2× speed fired at single-cell enemies; assert no ball ever inside a block.
- Caps: force ×5 gates + 14-ball volley + splits → assert ≤160 balls, particles ≤ pool size.
- SDK: page served from `localhost` (SDK `local` env = real SDK with demo ads), SDK blocked (unavailable), mocked SDK with init failure / ad error / ad never returning / data `setItem` throwing.
- Persistence: buy upgrade → reload → assert.
- Viewports: 390×844 @3x, 844×390 landscape, 1920×1080, screenshots inspected.
- Bot balance: random-aim bot plays full runs at accelerated time → wave reached / sim time.

Cannot be tested here: real CrazyGames domain, real ad fill, real devices, real 120/144 Hz panels (simulated via dt injection).

## 12. Contradictions / weaknesses in the brief

- "Do not interrupt active combat" vs "call gameplay events when an upgrade selection opens": we treat upgrade screens as breaks (gameplayStop) — consistent with docs ("at every break").
- "Pause on visibility change" vs docs: *"Do not call gameplayStop when the user switches focus"*. We freeze the sim silently without SDK calls.
- "Prefer CrazyGames data storage, fall back to localStorage" — docs say if you use the Data Module you should **fully rely on it**. We use SDK data exclusively in the `crazygames` env and localStorage only elsewhere / if the module throws.
- "Player decisions matter" vs "rapid-fire, satisfying number-go-up": tension resolved by making the *aim* the decision and everything after it spectacle.
- Daily missions + clock changes: a purely client-side reset can always be advanced by moving the clock forward; we prevent repeat claims and ignore backwards changes, but cannot prevent forward clock skipping without a server.
- Target metrics (D1 10–15 %, 80 % 60-s conversion) are goals only; nothing in the docs makes them requirements.
- "Every 5 waves a boss" + "6–8 min run" only works if a wave is several turns — hence 3 turns/wave.
- "Single file" + "testing files may exist" — the shipped artifact is `index.html` only; `tests/` is dev-only.
