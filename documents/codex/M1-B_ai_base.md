# Codex prompt — M1-B: `backend/ai/` base, registry, bot skeletons, random bot

> Tasks: X1-05, X1-06, X1-07 · Branch: `feat/ai-base-registry` · One PR. Can be done in parallel with M1-A.
> Copy everything below the line into Codex.

---

You are implementing the bot infrastructure of the "Chess AI Tournament" project (Python 3.14, `python-chess`).

## Read first
- `documents/CONTEXT.md` §3.1 (dependency rules), §4.1 (BaseBot contract + rules 1–8), §4.2 (registry).
- The tests are the specification. **Do not modify any file under `another/tests/`**:
  - `another/tests/ai/test_base_bot.py`
  - `another/tests/ai/test_registry.py`
  - `another/tests/ai/test_bot_contract.py`
  - `another/tests/architecture/test_config_schema.py` (checks every registered bot has a `[bots.<id>]` table, already present)

## Create exactly these files
1. `backend/ai/base_bot.py`
   - `class BotUnavailableError(Exception)`
   - `class BaseBot(ABC)`: class attrs `bot_id: str = ""`, `display_name: str = ""`; `__init__(self, config: dict | None = None)` sets `self.config = config or {}` and `self.last_search_info: dict = {}`; abstract `select_move(self, board: chess.Board) -> chess.Move`; `reset(self) -> None` clears `last_search_info`.
2. `backend/ai/registry.py`
   - `BOT_REGISTRY` (ordered exactly: `alphabeta_regression`, `genetic_alphabeta`, `mcts`, `deep_rl`) and `DEBUG_BOTS = {"random": ...}`, mapping id to `"ai.<package>.bot:<ClassName>"` as in CONTEXT §4.2.
   - `list_bots(include_debug: bool = False) -> list[str]`: official ids first, then debug ids.
   - `create_bot(bot_id: str, config: dict | None = None) -> BaseBot`: unknown id raises `ValueError`. Load the class with `importlib.import_module` + `getattr`, and wrap `ImportError`/`AttributeError` into `BotUnavailableError`. Let `BotUnavailableError` raised by the bot's `__init__` propagate unchanged.
   - **Never import bot packages statically.** `ai.registry` must only reference them as strings.
3. `backend/ai/random_bot/bot.py`: `RandomBot(BaseBot)`, `bot_id = "random"`, `display_name = "Random"`. Uses its own `random.Random(self.config.get("seed"))` instance (no global `random`) and picks uniformly from `board.legal_moves`.
4. Skeletons for the 4 official bots. Each file contains one class whose `__init__` raises `BotUnavailableError("not implemented")`:
   - `backend/ai/alphabeta_regression/bot.py` → `AlphaBetaRegressionBot`, `bot_id = "alphabeta_regression"`
   - `backend/ai/genetic_alphabeta/bot.py` → `GeneticAlphaBetaBot`, `bot_id = "genetic_alphabeta"`
   - `backend/ai/mcts/bot.py` → `MctsBot`, `bot_id = "mcts"`
   - `backend/ai/deep_rl/bot.py` → `DeepRLBot`, `bot_id = "deep_rl"`

   Add a module docstring to each skeleton: "Owner: @<github>. Replace this skeleton; keep the class name and bot_id. See documents/CONTEXT.md §4.1." Owners: alphabeta_regression = @cieldontcry, genetic_alphabeta = @khanhtaduy2k5, mcts = @quanganh167, deep_rl = @august0362.

## Constraints
- `backend/ai/base_bot.py` and `backend/ai/registry.py` may import only stdlib, `chess` and `core`.
- A bot package must never import another bot package (`lint-imports` enforces this).
- Full type hints, short docstrings, line length 100, ruff clean.
- Do not touch files outside `backend/ai/`.

## Acceptance criteria
```bash
pytest another/tests/ai another/tests/architecture -q   # random bot passes the full contract; the 4 skeletons are SKIPPED (not failed)
ruff check . && ruff format --check .
lint-imports                            # 3 contracts KEPT
```
