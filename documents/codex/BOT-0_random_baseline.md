# Codex prompt — BOT-0: random-move baseline for not-yet-implemented bots

> Branch: `feat/random-baseline`.

---

Implement the "Baseline ngẫu nhiên" decision in `documents/CONTEXT.md` §4.2 (right after the registry code block).

## Deliverables
1. `backend/ai/baseline.py`: `RandomBaselineBot(BaseBot)` with `is_baseline = True`, its own `random.Random(self.config.get("seed"))`, and uniform choice over legal moves (moves sorted by UCI before choosing, so a seed is deterministic). Also add `is_baseline: bool = False` as a class attribute on `BaseBot`.
2. The skeletons `backend/ai/alphabeta_regression/bot.py`, `backend/ai/genetic_alphabeta/bot.py` and `backend/ai/mcts/bot.py` subclass `RandomBaselineBot`, keeping their class names, `bot_id` and `display_name`. Update their docstrings in Vietnamese: "Đang chạy baseline ngẫu nhiên. Thay toàn bộ lớp này bằng bot thật; bỏ kế thừa RandomBaselineBot."
3. `backend/ai/deep_rl/bot.py`: when `load_policy` raises `NotImplementedError`, fall back to baseline behaviour (`is_baseline = True`, random legal moves). Other failures still raise `BotUnavailableError`.
4. GUI: append `t("players.baseline_suffix")` (add `baseline_suffix = "(baseline)"` to **both** locale files) to the name of any bot instance with `is_baseline` True. This applies on the setup screens, the game panel, and anywhere the display name of a live bot is shown. History and leaderboard may show it when the info is available; do not change the `GameRecord` schema.
5. Docs: update `documents/CONTRIBUTING.md` (members replace the baseline class) and `backend/ai/deep_rl/README.md` (the bot plays random until `load_policy` is implemented) with a sentence each.

## Tests
- **Allowed exception to AGENTS.md:** the spec changed, so you may update the existing tests that asserted the old behaviour. These are the tests expecting `BotUnavailableError` for unimplemented official bots or for `deep_rl` without a policy (e.g. in `another/tests/ai/deep_rl/`). Change only those assertions, to expect baseline behaviour. Leave all other tests untouched.
- Add `another/tests/ai/test_baseline.py`: each official bot that is still a baseline has `is_baseline` True, returns legal moves, and is seed-deterministic; `ai.baseline` is importable from bot packages without breaking `lint-imports`.
- The bot contract test (`another/tests/ai/test_bot_contract.py`) must now **run and pass** for all 4 official bots instead of skipping.

## Done
Follow `AGENTS.md`. `pytest -q --basetemp=.pytest-tmp`, `ruff check .`, `ruff format --check .` and `lint-imports` must all be green.
