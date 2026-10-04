# Codex prompt — RL-0: Deep RL infrastructure / adapter (NOT the RL algorithm)

> Runs in parallel with M4-A and OPS-1 (disjoint files). Branch: `feat/deep-rl-infra`.

---

Build the infrastructure for Option 4 exactly as specified in `documents/DEEP_RL_DESIGN.md` §1–§3. The owner will write the RL core himself, so **you must NOT implement any learning algorithm, neural network or training loop**.

## Deliverables
- `backend/ai/deep_rl/encoding.py`, `env.py`, `opponents.py`, `evaluate.py`, `metrics.py`, `weights.py`, `policy_api.py`, and `bot.py` (replace the skeleton; keep the class name `DeepRLBot` and `bot_id = "deep_rl"`), as in §2–§3.
- `backend/ai/deep_rl/user/`: skeleton files `model.py`, `agent.py`, `replay.py`, `train.py`, `policy.py`, plus `__init__.py`. Each contains a module docstring explaining in **Vietnamese** what the owner should implement, which helpers to use (`encoding`, `env`, `opponents`, `metrics`), and the expected function or class signatures. Bodies raise `NotImplementedError` (in `train.py`: a `main()` that raises). No algorithm code.
- `backend/ai/deep_rl/kaggle/train_notebook.ipynb` as in §3: valid JSON, cells compile.
- `backend/ai/deep_rl/README.md`: a short Vietnamese guide covering how to plug in, run the env, evaluate, train on Kaggle and publish weights.
- **Tests you write:** `another/tests/ai/deep_rl/`, covering
  - encoding shapes, plane semantics (start position, side-to-move flip), afterstate perspective, action mapping round trip for all legal moves in several positions (including promotion and castling), and the legal mask;
  - env reset/step/termination/rewards: win, loss, draw, material coefficient, opponent replies, truncation at `max_plies`, seeded determinism;
  - opponents return legal moves, and greedy prefers the higher-value capture;
  - `evaluate` with a random-policy stub, including colour alternation;
  - the `metrics` CSV, and that the plot writes a PNG (matplotlib optional: skip if missing);
  - `weights.py` sha256 verification with a local file (`file://` URL or a monkeypatched downloader); never use the network in tests;
  - `DeepRLBot` raises `BotUnavailableError` while `user.policy.load_policy` raises `NotImplementedError`, and plays legal moves when `load_policy` is monkeypatched with a random-policy stub.

## Constraints
- `encoding/env/opponents/evaluate/metrics/policy_api` use only stdlib, `chess`, `numpy`, and optionally `matplotlib` (import lazily, skip if absent). **No torch import outside `backend/ai/deep_rl/user/`.**
- `backend/ai/deep_rl` must not import other bot packages or `tournament`/`gui` (`lint-imports` enforces this). Use `core.GameState`/`chess` directly.
- Follow `AGENTS.md`. Touch only `backend/ai/deep_rl/**` and `another/tests/ai/deep_rl/**` (add `another/tests/ai/deep_rl/__init__.py`).

## Done
`pytest -q --basetemp=.pytest-tmp`, `ruff check .`, `ruff format --check .` and `lint-imports` must all be green. The existing bot contract test must still skip `deep_rl` (policy not implemented).
