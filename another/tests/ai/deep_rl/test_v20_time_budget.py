"""Regression checks for the ramp policy's per-move search deadline."""

from __future__ import annotations

from pathlib import Path

import chess
import numpy as np
import pytest

torch = pytest.importorskip("torch")

from ai.deep_rl.bot import DeepRLBot  # noqa: E402
from ai.deep_rl.v20 import batched  # noqa: E402
from ai.deep_rl.v20.model import PolicyValueNet  # noqa: E402
from ai.deep_rl.v20.moves import ACTIONS, move_to_action  # noqa: E402
from ai.deep_rl.v20.policy import PHASES, V20_FORMAT, V20RampPolicy  # noqa: E402


class _Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def _fake_inference(
    monkeypatch: pytest.MonkeyPatch,
    clock: _Clock,
    cost_s: float,
    preferred: chess.Move | None = None,
) -> None:
    def infer(
        model: PolicyValueNet, planes: list[np.ndarray], device: str | torch.device
    ) -> tuple[np.ndarray, np.ndarray]:
        clock.now += cost_s
        logits = np.zeros((len(planes), ACTIONS), dtype=np.float32)
        if preferred is not None:
            logits[:, move_to_action(preferred, chess.WHITE)] = 10.0
        return logits, np.zeros(len(planes), dtype=np.float32)

    monkeypatch.setattr(batched.time, "perf_counter", clock)
    monkeypatch.setattr(batched, "_infer_batch", infer)


@pytest.fixture
def weights(tmp_path: Path) -> Path:
    """Create a small packed checkpoint for the real bot loading path."""
    config = {"channels": 8, "blocks": 1, "head_channels": 4}
    state = PolicyValueNet(**config).state_dict()
    path = tmp_path / "weights.pt"
    torch.save(
        {
            "format": V20_FORMAT,
            "model_config": config,
            "models": {phase: state for phase in PHASES},
        },
        path,
    )
    return path


def test_bot_honors_one_second_budget_and_resets_it_each_move(
    weights: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("ai.deep_rl.bot.resolve_weights", lambda url, sha: weights)
    bot = DeepRLBot(
        {"search": "ramp", "simulations": 200, "batch_size": 1, "max_think_time_s": 1.0}
    )
    assert isinstance(bot.policy, V20RampPolicy)
    clock = _Clock()
    _fake_inference(monkeypatch, clock, cost_s=0.25)
    board = chess.Board()

    for _ in range(2):
        original = board.copy(stack=True)
        started = clock.now
        move = bot.select_move(board)
        assert move in board.legal_moves
        assert board == original and board.move_stack == original.move_stack
        assert clock.now - started == pytest.approx(1.0)
        assert bot.last_search_info["new_simulations"] == 3
        assert bot.last_search_info["early_stop_reason"] == "time_limit"
        assert bot.policy.tree.root is not None
        root = bot.policy.tree.root
        assert root.visits is not None and root.moves[int(root.visits.argmax())] == move
        board.push(move)


def test_expired_root_inference_returns_highest_policy_legal_move(
    weights: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("ai.deep_rl.bot.resolve_weights", lambda url, sha: weights)
    bot = DeepRLBot({"search": "ramp", "simulations": 200, "max_think_time_s": 1.0})
    clock = _Clock()
    preferred = chess.Move.from_uci("e2e4")
    _fake_inference(monkeypatch, clock, cost_s=2.0, preferred=preferred)

    assert bot.select_move(chess.Board()) == preferred
    assert bot.last_search_info["new_simulations"] == 0
    assert bot.last_search_info["avg_leaf_depth"] == 0.0
    assert bot.last_search_info["early_stop_reason"] == "time_limit"


def test_zero_time_limit_completes_the_simulation_budget(
    weights: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("ai.deep_rl.bot.resolve_weights", lambda url, sha: weights)
    bot = DeepRLBot({"search": "ramp", "simulations": 16, "batch_size": 1, "max_think_time_s": 0.0})
    clock = _Clock()
    _fake_inference(monkeypatch, clock, cost_s=0.25)

    assert bot.select_move(chess.Board()) in chess.Board().legal_moves
    assert clock.now > 1.0
    assert bot.last_search_info["new_simulations"] == 16
    assert bot.last_search_info["early_stop_reason"] is None
