# Codex prompt — M2-3: `backend/tournament/ranking.py` + `backend/tournament/history.py`

> Wave 3 (needs M2-1 merged) · Branch: `feat/tournament-ranking` · One PR. Runs in parallel with M2-2.

---

You are implementing persistence for the "Chess AI Tournament" project (Python 3.14).

## Read first
- `documents/CONTEXT.md` §4.7 (Ranking + Elo) and §4.8 (History).
- Spec tests (**do not modify anything under `another/tests/`**): `another/tests/tournament/test_ranking.py`, `another/tests/tournament/test_history.py`.

## Create exactly these files
1. `backend/tournament/ranking.py`
   - `PlayerStats` dataclass (`wins`, `draws`, `losses`, `elo`; properties `games`, `points`), `expected_score(r_a, r_b)` and `Ranking` as in CONTEXT §4.7.
   - Elo: update both players simultaneously from **pre-game** ratings: `R' = R + K * (S - E)`.
   - `record_game` returns `False` and changes nothing for ABORTED games, mirror games (`white_id == black_id`) or games involving a `debug_ids` player. Otherwise it updates stats, saves and returns `True`.
   - Unknown ids return a fresh `PlayerStats(elo=elo_initial)`. `table()` includes every `known_ids` entry and is sorted by elo desc, then points desc, then id asc.
   - Persistence (only when `path` is not None): JSON `{"version": 1, "players": {...}}`.
     - Create parent directories.
     - Write atomically: `tempfile.mkstemp(dir=path.parent)`, then `os.replace`; leave no temp files behind.
     - On a corrupt or unreadable file, rename it to `<name>.corrupt` and start empty.
2. `backend/tournament/history.py`
   - `History(directory, max_games=20)` as in CONTEXT §4.8. Create the directory, store one `<game_id>.json` per game (UTF-8, `GameRecord.to_json()`), and prune the oldest files beyond `max_games` after each save.
   - `list()` returns newest first, ordered by `(started_at, game_id)` descending, and silently skips unreadable files.

## Constraints
- May import only stdlib, `chess`, `core` and `tournament`. Never import `ai.<bot>` packages or `gui`.
- Full type hints, short docstrings, line length 100, ruff clean. Touch only the two files above.

## Acceptance criteria
```bash
pytest another/tests/tournament/test_ranking.py another/tests/tournament/test_history.py -q   # all pass
pytest --cov -q
ruff check . && ruff format --check . && lint-imports
```
