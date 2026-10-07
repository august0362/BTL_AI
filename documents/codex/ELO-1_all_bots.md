# Codex prompt — ELO-1: Elo + bot pickers cover all 8 bots

---

Read `documents/CONTEXT.md` §4.2 (benchmark note), §4.7, §5.2, §5.10, §5.11 first.

Today the GUI only knows the 4 member bots (+ `baseline`). The 4 benchmark bots
(`bench_random`, `bench_alphabeta3`, `bench_alphabeta_tt`, `bench_alphabeta_custom`) only appear
in the "Xếp hạng AI" tournament. Make the normal game modes and the Elo table use all 8 bots.

## What to change
1. `frontend/gui/app.py`: `Ranking(known_ids=registry.list_bots(include_benchmarks=True) + ["human"])`.
   `baseline` is no longer a known id. Elo still starts at `ranking.elo_initial` for everyone.
2. `frontend/gui/screens/setup_human.py`: bot list =
   `registry.list_bots(include_debug=show_debug_bots, include_benchmarks=True)` (8 bots, 9 with
   debug `random`).
3. `frontend/gui/screens/setup_bots.py`: same list (drop `include_baseline=True`).
4. **Layout** (both setup screens, logical canvas 960×640): 8 bots (and 9 with `random`, and when
   one or more bots are unavailable and show a reason line) must fit with no overlap and nothing
   below y=632. Suggested:
   - Người vs Bot: bot buttons in a 2-column grid (e.g. columns at x=180 and x=490, width 290,
     height 34, row step 42), then the colour row, then Start/Back side by side on one row.
     Show the unavailable reason as a small muted line under that button (shrink the row step
     only if needed).
   - Bot vs Bot: keep the White / Black columns; reduce the row step so the 8–9 rows end above
     the Swap button, and move Swap / format / Start-Back down as needed (all ≤ 632).
   - Labels like "Benchmark 4 · Alpha-Beta Custom" must fit inside their buttons in vi and en
     (shrink font to 13 if needed, no clipping).
5. The Elo table (`frontend/gui/screens/leaderboard.py`) already draws up to 11 rows; check the
   9 rows fit above the Reset/Back buttons, adjust only if they overlap.
6. Starting a game with a benchmark bot works through `registry.create_bot(bot_id, app._bot_config(bot_id))`
   as for other bots (no special case). `record_game` must count human-vs-bench and
   bot-vs-bench games.

Do not change `backend/ai/registry.py` (default `list_bots()` stays 4 bots) or the tournament.

## Tests you add (new file only; keep existing tests unchanged)
`another/tests/gui/test_all_bots.py` (headless, same fixtures/style as the other GUI smoke tests,
tmp data dir):
- `app.ranking.table()` ids == the 8 bots + `"human"` (no `baseline`), all Elo 1200.
- Setup Người vs Bot and Bot vs Bot screens list exactly the 8 bots (debug off) and 9 with
  `show_debug_bots = true`; no button rects overlap and all are inside 960×640.
- `app.ranking.record_game(...)` for a finished human vs `bench_alphabeta3` game updates both
  Elo values; a `bench_random` vs `mcts` bot game likewise.
- Clicking a benchmark bot then Start in Người vs Bot starts a game (`current_screen_name == "game"`).
A few meaningful tests are enough.

Run `another/tools/render_previews.py` for the two setup screens and the leaderboard (vi, 1440×960)
and list the PNGs.

## Done
Follow `AGENTS.md`. `pytest -q --basetemp=.pytest-tmp`, `ruff check .`, `ruff format --check .`
and `lint-imports` must all be green. Touch only `frontend/gui/app.py`,
`frontend/gui/screens/setup_human.py`, `frontend/gui/screens/setup_bots.py`,
`frontend/gui/screens/leaderboard.py` (only if needed), locales (only if needed) and the new test
file.
