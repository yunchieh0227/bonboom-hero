# BONKAGEDDON

Ricochet roguelite for CrazyGames. **The shippable build is the single file `index.html`** (≈230 KB, no build step). Its only external script is the CrazyGames SDK v3.

- `DESIGN.md`: the design and technical review (GDD, core loop, rules, balance table, risks, contradictions in the spec).
- `tests/`: dev-only automated tests (Python + headless Chrome over CDP). Do not upload these.

## Run locally

```
cd game1
python -m http.server 8765 --bind 127.0.0.1
# open http://127.0.0.1:8765/index.html
```
Serve from `localhost`/`127.0.0.1`. The SDK's `local` environment (demo ads shown as overlay text) only runs on those hosts. Opening the file directly via `file://` also works; the SDK then runs `disabled` and the game plays standalone without ads.

Languages: English and Traditional Chinese (繁體中文). The game follows the browser language on first launch; the **中文 / EN** button on the main menu (or Settings → Language) switches it, and the choice is saved.

URL flags (dev): `?debug=1` shows the debug overlay (toggle with the `` ` `` key), `?seed=123` fixes the run seed, `?nosdk=1` ignores the SDK, `?sdkdata=1` uses the SDK data module outside the CrazyGames domain.

## Hero Merge Board (Phase 2)

- **Getting heroes:** every XP level-up grants Hero Summons (1 each; 2 from level 8). A boss grants 2 elite summons of the focused hero (Lv2, or Lv3 from wave 20). Later waves can also roll Lv2/Lv3 summons. The board opens between turns, and the **HEROES** button opens it any time you are aiming.
- **Merge rule:** 3 heroes of the same type **and** level that touch orthogonally (not diagonally) merge into one hero of the next level, at the cell where you completed the move. Max level is Lv4.
  - Groups larger than 3 use the drop cell plus the two matching heroes found first by a breadth-first search from it (neighbour order up, left, right, down); extras stay.
  - The new hero is re-checked at once, so chains cascade (MERGE → DOUBLE → TRIPLE → MEGA COMBO, +5 coins per extra step).
- **Controls:** drag and drop (mouse or touch), or tap a hero then tap a cell. Dropping on another hero swaps them. Tapping during an animation skips it.
- **Full board:** summons go to the 3-slot reserve. Reserve heroes don't fight. If the board and reserve are both full, the summon becomes +10 coins with an on-screen message.
- **Combat:** each board hero's share of the volley is weighted 1/3/9/27 by level, so a merge keeps exactly the same share of balls. Every level hits harder (×1.0/1.25/1.6/2.1), is bigger and has a stronger ability. Total board power adds up to 3 extra balls. The 160-ball cap is unchanged.
- **Cross-hero fusion:** when both recipe heroes are Lv2+ on the board, a **FUSE** button appears. Activating it plays the fusion cutscene and keeps the heroes: their Lv2+ units fire the fusion ball. A hero type can power only one fusion at a time.
- **Passives:** the old 3-card pick still offers passive upgrades, every 2nd level.
- **Saved permanently (save v2, migrated from v1):** highest level reached per hero, merge stats, achievements and fusions. The board itself is per run.
- All tuning values are in `CONFIG.merge` in `index.html`.

## Onboarding, unlocks and collection (Phase 3)

- **Tutorials (`Tut` in `index.html`):** one place for every lesson. Each lesson has an id, a skip rule and a completion event. Completed lessons are saved in `Save.d.tut` and never repeat. **Settings → Tutorials → REPLAY** clears them and keeps coins and unlocks. Lessons only finish on the real action; none of them fakes input.

- **Pacing (Teach → Play → Reward → Discover):** major lessons are `aim`, `gate`, `summon`, `merge`, `reserve` and `focus`.
  - After each major lesson the player gets at least 2 *meaningful turns* (`TUT_COOL`) before the next one. A meaningful turn is a real shot whose volley fully resolves; the lesson's own turn, idle time and menus don't count.
  - The counter is saved in `Save.d.tut._since`. Two major lessons never come back to back.
  - Before the merge board is unlocked, level-up summons are **banked** (kept, never lost) until their lesson is due; a "HERO SUMMON EARNED!" tip appears.
  - Safety valve: the board opens anyway after 5 banked turns.
  - Locked board rows show a "? Unlocks as you play ?" teaser.

  | Lesson | When it appears (first run) | Finishes when |
  |---|---|---|
  | `aim` | First turn: ghost hand, predicted path, DRAG TO AIM / RELEASE TO FIRE. There are no gates yet and the front line is dense, so the first shots land. | You fire a shot |
  | `gate` | After 2 more turns (4th shot): dims the screen, demo of the real ×3 rule, AIM THROUGH ×3! | A ball you fired passes the gate (gives up after 3 shots). If you pass a gate on your own first, you get a short "NICE!" tip instead. |
  | `summon` | 2 turns later, at a turn boundary with an earned summon: HERO SUMMON! portal, TAP TO SUMMON. A real new hero joins, shown on a hero card, and the game returns to combat on its own. | Your tap |
  | `boardIntro` + `merge` | 2 turns later, at the next earned summon: MERGE BOARD UNLOCKED!. One real summon is placed so a single drag completes a 3-merge; the rest is dimmed and wrong drops get a gentle retry. Afterwards EVOLVED! → YOUR HERO IS STRONGER! → back to battle. | Your merge (merging before the lesson counts as learned) |
  | `reserve` | At a board visit ≥2 turns later: RESERVE UNLOCKED!, drag a hero in, then drag it back | Store + retrieve (reward tip: 3 spare slots) |
  | `focus` | ≥2 turns later, once 3+ hero types are on the board: SUMMON FOCUS UNLOCKED!, tap a hero (2.5× chance, the real `focusMul`) | Your pick; the waiting summons then use it |
  | `merge4` / `merge5` | Only when a 4 or 5 group is one move away. Non-blocking highlight, plus 4 HEROES = BONUS CORE! or 5 HEROES = DOUBLE EVOLUTION! | That merge happens |
  | `fusion`, `boss`, `codex`, `perm` | The first time each feature appears; short non-blocking tips | Shown once |

  During board lessons there are no ads and no FIGHT button. A **SKIP TUTORIAL** button is there (the summon lesson is a single tap). If no valid lesson board exists, nothing is invented; the lesson falls back to the normal hint. Closing or reloading mid-lesson only leaves it pending. The passive card pick never appears right behind a lesson.
- **Hero discovery pacing:**
  - The first summon of the run gets the hero card.
  - Later first-of-type summons get a compact NEW HERO / NEW DISCOVERY tip; several are queued.
  - Duplicates get no extra popup.
  - The first permanent unlock gets the full reveal; later unlocks start with a shorter build-up.
- **4/5-merge (new):** 4 matching heroes give one evolution plus a **Power Core** (+5% hero damage for the run, max 5 cores; extra cores become coins). 5 matching heroes give **two** evolutions (MEGA MERGE!). The hint prefers the bigger merge.
- **Notifications (`Notify`):** one message at a time, highest priority first. Duplicates and quick repeats are dropped and the queue is capped at 4. Contextual hints: MERGE READY!, BONUS MERGE AVAILABLE!, MEGA MERGE READY!, NEW FUSION DISCOVERED!, NEW HERO AVAILABLE!
- **Hero unlock (`Reveal`):** buying a hero from the shop or a codex page plays:
  1. Coin spend and a glowing silhouette.
  2. Ring, flash and a unique entrance animation.
  3. A hero card with name, ability icon, ability and the real Lv1 text, plus an ability demo.
  4. COLLECTION UPDATED! with N / 8 heroes.

  You can skip after the first beat. The purchase is saved before the animation starts, and a drawing error closes the presentation instead of blocking.
- **Codex:** a gallery with owned heroes in colour (level pips) and locked heroes as silhouettes with cost and progress. Chips show heroes, fusions, evolutions, best level and how many heroes are ready to unlock. The first visit plays a one-time gallery intro. Hero pages show an animated portrait, the ability demo, evolution levels and fusion recipes. Locked pages show only the ability category, plus an UNLOCK button when you can afford it.
- **Coin goals:** the menu shows the next hero, `coins / cost`, a progress bar, and either "N COINS UNTIL NEXT HERO!" or "HERO READY TO UNLOCK!" (SHOP/CODEX glow). The results screen counts up coins and balance and animates the progress bar. Nothing is ever spent automatically.
- **Ability demos** are scripted replays of each hero's real Lv1 rule, drawn in their own box. They never touch the run state.
- **Save v3:** adds `tut` and the 4/5-merge stats. Migrating from v2 or v1 marks the aim and gate lessons done for returning players (and fusion/boss if already seen). It keeps the merge lesson unless they have merged before.

## Hero discovery levels and the cannon (Phase 5)

- **Hero events (`HeroEvents`):** one dispatcher with a queue, so no two full-screen presentations ever overlap.

  | Event | Presentation |
  |---|---|
  | `HERO_PERMANENTLY_UNLOCKED` | The full reveal |
  | `HERO_FIRST_RUN_SUMMON` | A short **NEW HERO JOINED!** card on the board: portrait, full name, ability and real Lv1 text, a mini demo, and "NEW DISCOVERY!" if the hero has never been seen. Auto-continues after 2.4 s or on one tap. Further summons wait behind it, and several cards play one after another. |
  | `HERO_DUPLICATE_SUMMON` | "+1 HERO" on the landing cell, no pause |
  | `HERO_LEVEL_EVOLVED` | The merge animation |
  | `HERO_FUSION_DISCOVERED` | The fusion cutscene |

  First acquisition per run is tracked in `R.runSeen` (it resets every run). Permanent discovery stays in `Save.d.seen` / `Save.d.unlocked`.
- **Permanent unlock reveal:**
  1. Anticipation, ≈0.45 s: silhouette, converging energy, rising sound.
  2. Reveal, ≈0.8 s: flash, unique entrance, NEW HERO UNLOCKED! and the full name.
  3. Hero card with a hero-coloured theme and the ability demo.
  4. Registration: the card shrinks along a curve with a glowing trail into the encyclopedia book, which opens and glows. Then ADDED TO ENCYCLOPEDIA! and "N / 8 HEROES COLLECTED", with the slot filling in.

  The unlock is saved before any of this plays. Later unlocks start with a shorter build-up.
- **Full names everywhere:** codex cards, recipes, results, banners and cards use `HEROES[id].name` (Sir Croissanto, Bananini Boom, …). Internal ids and save keys are unchanged.
- **Cannon (`Cannon`, `drawCannon`):** drawn on canvas in layers:
  - Armored base with vents and status lights.
  - Side energy tanks whose level follows the core.
  - Turret dome with a glowing energy core.
  - Barrel with reinforcement rings, charge conduits, pistons and a muzzle rim.
  - Vapor puffs during recovery.
  - Aiming reticle.

  The drawing is authored at 58 px and scaled ×1.17; balls spawn exactly at the muzzle (`MUZZLE` = 68).
- **Firing animation:**
  - **Charge** overlaps the fire interval, so there is no input delay.
  - **Fire:** flash at the spawn point, a shockwave every third ball, sparks, a layered WebAudio shot.
  - **Recoil:** an immediate kick plus a damped spring that accumulates under rapid fire up to a cap.
  - **Recovery:** the spring settles, plus vapor.

  It runs on the fixed simulation step, so it is identical at 60/144 Hz and freezes on pause.
- **Look tiers:** the cannon has 4 looks driven by permanent upgrade levels (0–2, 3–6, 7–11, 12+): extra glow lines, then armor and a bigger core, then golden fins. This is drawing only; stats do not change.

## Hero evolution Lv1–Lv8 + MAX and long-term goals (Phase 6)

Two separate tracks:

| | Resets? | What it is |
|---|---|---|
| **Combat level** Lv1…Lv8, MAX | every run | the merge board (3/4/5-merge as before). A Lv L hero = 3^(L-1) Lv1 heroes, so MAX = 6,561 Lv1. |
| **Hero Mastery** ★1…★9 | never | per hero. **+1 XP per summon** of that hero, **+new level per merge** (+1 for a 4-merge, +3 for a 5-merge), **×2 for today's featured hero**. |

- **Ranks:** thresholds 10 / 45 / 140 / 260 / 420 / 640 / 920 / 1300 XP. Each rank gives **+4% damage** to that hero, and its **summons and starters arrive at a higher level**: ★3 Lv2, ★5 Lv3, ★6 Lv4, ★7 Lv5, ★8 Lv6, ★9 Lv7. This is what makes high levels reachable.
- **Summons needed for MAX from the summon level** (3-merges only, with 5-merges in brackets):

  | Summon level | Lv1 | Lv2 | Lv4 | Lv6 | Lv7 |
  |---|---|---|---|---|---|
  | Summons for MAX | 6,561 | 2,187 | 243 | 27 (≈16) | 9 (≈6) |

  A strong late run gives about 25–40 summons.
- **Measured with the test bot** (a player who keeps one favourite hero as summon focus):
  - ★4 after 8 runs, with the pace speeding up as the summon level rises; projected ★9 after ≈25–35 focused runs.
  - With ★9 the bot reached MAX within 2 runs.
- **Hall of Legends (5×5):** a literal board of 25 MAX heroes in one run would need ≈390 Lv6 summons, which no run gives. Instead, every MAX evolution reached in any run is enshrined permanently in this hall (codex → HALL OF LEGENDS). Filling all 25 = **Pantheon**. A full in-run board of MAX heroes is still detected and celebrated (Full MAX Board).
- **Abilities:** Lv6 adds a new behaviour, Lv8 strengthens it, MAX is a signature ability.

  | Hero | Lv6 | MAX |
  |---|---|---|
  | Sir Croissanto | slash on every pierce | Royal Charge: pierces everything, every 3rd ball giant |
  | Bananini Boom | cluster bombs | Nuke Commander: 3 clusters, 90% splash |
  | Frosty Noodle | frost nova | Absolute Zero: each freeze freezes everything nearby |
  | Zappy Pickle | 55% bolts | Storm Ruler: 14 jumps, 70% bolts |
  | Splittini Bean | minis +50% | Bean Swarm: 6 minis × 5, minis ×2 |
  | Magneto Muffin | +30% vs elites/bosses | Magnetron: map-wide lock, +60% |
  | Turbo Turnip | pierce at 2× speed | Hyperdrive: 3.4× speed, pierces 3 |
  | Count Sipsula | blood bursts on heals | Blood Moon: 5 heals per turn, big bursts |

  Damage multipliers are ×1.0 … ×5.2 (Lv8) and ×6.5 (MAX). The 160-ball cap is unchanged.
- **Visuals:** every hero has its own equipment at Lv2, Lv4, Lv5, Lv6, Lv7 and Lv8 (e.g. Sir Croissanto: plume → shield → sword → gold visor → pauldrons → royal cape). Lv3 adds glowing eyes. MAX is a palette transformation plus a signature artifact and orbiting glyphs.

  Effects escalate by level:

  | Levels | Effects |
  |---|---|
  | Lv2–3 | glow |
  | Lv4–5 | dashed ring |
  | Lv6–7 | aura particles |
  | Lv8 | rays |
  | MAX | more rays and hero glyphs |
- **Evolution animations escalate:**
  - Lv2–3: minor.
  - Lv4–5: the new equipment piece flies in, plus energy rings.
  - Lv6–7: a camera push-in and an ability preview.
  - Lv5: a short full-screen SUPER EVOLUTION (1.8 s); Lv6–7: EPIC EVOLUTION.
  - Lv8: a full-screen LEGENDARY cinematic with armor assembly (2.2 s).
  - MAX: a hero-coloured ULTIMATE EVOLUTION! cinematic with the signature form name, ability and Hall of Legends entry.

  Measured full durations: 1.3 / 1.5 / 1.7 / 2.9 / 3.9 s. One tap skips.
- **Retention without pressure:**
  - Menu: the next hero (silhouette, ability, coins / cost), today's featured hero (×2 Mastery XP) and the closest mastery goal.
  - Results: Mastery XP gained, rank-ups, "N XP to ★X → summons at LvY", "+N% closer" to the next unlock, and **tomorrow's featured hero**.
  - New milestone notifications at Lv4 / Lv6 / Lv8.
  - The hero page shows the full evolution strip with the next form pulsing.
  - No streaks, timers or anything that can be lost by skipping a day.
- **Hero unlock prices** (`UNLOCK_COST`): 1,190 / 1,490 / 2,330 / 4,180 coins (9,190 in total). At roughly 100–250 coins per run that is about 6–10 runs for the first hero and several dozen for all four. Early heroes stay relevant through the fusion recipes, which all involve starter heroes.
- **Codex layout:**
  - Fusions are large showcase cards: an animated rainbow frame, the fusion portrait with both heroes, and silhouettes plus a "?" when undiscovered.
  - Achievements are a row of 10 banners on a gold rod: earned = waving gold flag, locked = dark flag with progress (e.g. 5 / 8, 2 / 25).
- **Save v4:** adds `mastery` and `legend`, plus new achievements. Older saves seed mastery from past evolutions (Lv3 → ★2, Lv4 → ★3).

## iPhone Home Screen app and saved progress

- **Install:** open the GitHub Pages URL in Safari → Share → Add to Home Screen. The icon is named **蹦蹦英雄** (`apple-touch-icon.png`, drawn from the game's own hero art). The page title is "BONBOOM HERO! 蹦蹦英雄：彈珠超進化". `apple-mobile-web-app-capable` and `manifest.webmanifest` (`display: standalone`) make it open full screen with no Safari bars. There is no service worker and no offline cache.
- **Separate saves:** iOS gives a Home Screen app its own storage, separate from Safari. Safari works as a trial with its own save. Nothing syncs the two, and neither ever deletes the other.
- **What is saved:** everything permanent (coins, heroes, upgrades, codex, achievements, mastery, Hall of Legends, missions and claimed rewards, tutorial flags, settings). It lives in `localStorage` key `bonkageddon_save`, unchanged from earlier versions. On CrazyGames the SDK data module is used instead, as before.
- **When it is saved:**
  - Purchases, unlocks and reward claims are written in the same tap and verified by reading them back.
  - Other permanent changes are written right after the current step, with several changes in one step giving one write. There is no timer.
  - `pagehide` and `visibilitychange` are extra save points only.
- **Safety:**
  - Nothing is written until the save has been loaded. A slow SDK start plus an early app switch can no longer write an empty save over real progress.
  - Every write also updates `bonkageddon_save_bak`. A corrupt main save is kept as `bonkageddon_save_corrupt` and the backup is loaded instead.
  - If storage cannot be read, the game runs but never writes over the unreadable save.
  - A save from a newer version keeps its version number and any fields this version does not know, so an old cached page cannot strip them.
  - Old saves migrate v1 → v4 as before. Write failures (quota, private mode) are caught.
  - `navigator.storage.persist()` asks the browser not to evict the data.

## Run the tests

```
python tests/run_tests.py <output_dir> [functional touch physics caps content balance restart persist save sdk realsdk merge tutorial onboard phase5 evolution i18n shots]
```
Needs Chrome at the default install path and `pip install websocket-client`. Screenshots are written to `<output_dir>/shots`.

## Dev log

- **M0 Review**: verified SDK v3 docs (init, environment, gameplayStart/Stop, requestAd callbacks and error codes, data module, muteAudio, happytime); wrote DESIGN.md.
- **M1–M4 Build**: wrote the whole game in one pass (fixed-step physics, grid broad-phase, gates, 8 heroes, 4 fusions, boss, meta progression, DOM UI, procedural art and audio).
- **Fixes from testing**:
  - Test harness raced the game's `pagehide` save, so storage is now cleared from a neutral page.
  - Upgrade randomness made fusions nearly impossible: added a fusion "pity" card (★ FUSION PATH), weighted owned-hero upgrades above passives, and flattened the XP curve. Bot runs went from 0/5 to 5/5 reaching a fusion.
  - Turbo and lifesteal were imperceptible in normal volleys, so both were buffed.
  - Boss shield was up 2 of 3 turns; it is now 1 of 3 (the spec says "occasionally"), and the label moved so it no longer hides under the HUD.
  - Banner and gate-flash timers advanced per rendered frame; they now use real dt.
  - Level-up backdrop was too transparent; made it darker.
  - Midgame-ad flow mixed state changes; rewritten.
  - Canvas font string is cached instead of re-set on every text draw.
- **Localization**: added Traditional Chinese for all UI, cards, heroes, fusions, missions and in-game canvas text; the test browser is pinned to en-US and an `i18n` group checks the toggle, persistence and leftover English.
- **M5–M6**: SDK adapter tested with mocks for every failure mode and with the real SDK in its `local` env; 120 automated checks.
- **Phase 2: 3-Merge Hero Evolution.** The previous build is kept in `archive/index_phase1.html`.
  - Replaced hero/upgrade/fusion cards with the merge board and a new `BOARD` state (gameplay stops while it is open).
  - Added Lv4 abilities, level visuals (glow, wings, crown, rays), a 4-stage merge animation and chain merges.
  - Fusion is now activated on the board; added an optional ad summon (once per wave, reward only on adFinished); save v2 with migration.
  - Rewrote the tests that depended on the roster/cards, and added a `merge` group (44 checks).
  - Balance:
    - The first economy gave Lv4 in no run (about 20 Lv1 summons cannot pay 27 per Lv4).
    - The second gave Lv4 in 4/5 runs and 11-minute snowballs.
    - The final values make Lv3 common and Lv4 a late-run event.
- **Phase 3: onboarding, hero discovery, collection.** (No separate Phase 2 backup was taken; `archive/index_phase1.html` is the only archived build.)
  - Added the tutorial manager, notification queue, merge-board unlock lesson, gate lesson, 4/5-merge with Power Cores, hero reveal with ability demos, codex gallery and detail pages, coin goals on the menu and results, Settings → REPLAY, and save v3.
  - Added a `tutorial` test group (39 checks). Codex, save and 5-merge tests were updated for the new behaviour.
  - Balance: Power Cores at +8% (max 10) pushed bot runs to 10.8 min with Lv4 in 4/5 runs. At +5% (max 5) runs are 8.6 min with Lv4 in 2/5.
