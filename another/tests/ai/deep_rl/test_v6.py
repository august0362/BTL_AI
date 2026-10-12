import csv

import chess
import numpy as np
import pytest

torch = pytest.importorskip("torch")

from ai.deep_rl.user.agent import Agent, bellman_targets  # noqa: E402
from ai.deep_rl.user.features import ACTIONS, action_mask, encode, legal_actions  # noqa: E402
from ai.deep_rl.user.replay import ReplayBuffer  # noqa: E402
from ai.deep_rl.user.train import (  # noqa: E402
    TrainConfig,
    _copy_decisive,
    _new_game,
    _sample_batches,
    _store_ready,
    main,
    temperature_for,
)


class _FixedQ(torch.nn.Module):
    def __init__(self, values: list[float]) -> None:
        super().__init__()
        self.values = torch.nn.Parameter(torch.tensor(values))

    def forward(self, states: torch.Tensor) -> torch.Tensor:
        return self.values.expand(len(states), -1)


def test_act_temperature_zero_argmax_and_normalized_softmax(monkeypatch) -> None:
    values = [0.0] * ACTIONS
    values[:3] = [0.0, 0.05, -0.1]
    agent = Agent(_FixedQ(values))
    states = np.zeros((1, 1), dtype=np.uint8)
    masks = np.zeros((1, ACTIONS), dtype=np.bool_)
    masks[0, :2] = True
    assert agent.act(states, masks, 0)[0] == 1

    captured: list[torch.Tensor] = []

    def take_sample(probabilities: torch.Tensor, count: int) -> torch.Tensor:
        captured.append(probabilities)
        return probabilities.argmax(dim=1, keepdim=True)

    monkeypatch.setattr(torch, "multinomial", take_sample)
    picked = agent.act(states, masks, 0.3)
    probs = captured[0][0]
    raw = torch.softmax(torch.tensor([0.0, 0.05]) / 0.3, dim=0)
    assert probs[1] > raw[1]
    assert picked[0] in (0, 1)
    assert probs[2:].sum() == 0


def test_temperature_schedule_ramps_and_holds() -> None:
    config = TrainConfig(games=100, temp_start=0.0, temperature=0.3, temp_ramp_fraction=0.3)
    assert temperature_for(0, config) == 0.0
    assert temperature_for(15, config) == pytest.approx(0.15)
    assert temperature_for(30, config) == pytest.approx(0.3)
    assert temperature_for(99, config) == pytest.approx(0.3)


def test_n_step_mate_returns_and_truncated_bootstrap() -> None:
    game = _new_game(False)
    state = encode(chess.Board())
    _, actions = legal_actions(chess.Board())
    mask = action_mask(actions)
    game.pending.extend(
        [
            (state, i, reward, state, done, mask)
            for i, (reward, done) in enumerate(((0.0, False), (0.0, False), (1.0, True)))
        ]
    )
    replay = ReplayBuffer(8)
    _store_ready(game, replay, n_step=5, gamma=0.9, finished=True, terminal=True)
    assert replay.rewards[:3].tolist() == pytest.approx([0.9**2, -0.9, 1.0])
    assert replay.steps[:3].tolist() == [3, 2, 1]
    assert replay.dones[:3].tolist() == [1.0, 1.0, 1.0]

    next_q = torch.zeros(1, ACTIONS)
    next_q[0, 0] = 0.5
    mask_tensor = torch.zeros(1, ACTIONS, dtype=torch.bool)
    mask_tensor[0, 0] = True
    target = bellman_targets(
        torch.tensor([0.2]),
        torch.tensor([0.0]),
        next_q,
        mask_tensor,
        0.9,
        steps=torch.tensor([3]),
    )
    assert target.item() == pytest.approx(0.2 - 0.9**3 * 0.5)

    truncated = _new_game(False)
    truncated.pending.extend(
        [(state, i, reward, state, False, mask) for i, reward in enumerate((0.25, 0.5))]
    )
    truncated_replay = ReplayBuffer(4)
    _store_ready(truncated, truncated_replay, 5, 0.9, finished=True, terminal=False)
    assert truncated_replay.rewards[0] == pytest.approx(0.25 - 0.9 * 0.5)
    assert truncated_replay.steps[0] == 2
    assert truncated_replay.dones[0] == 0
    trunc_target = bellman_targets(
        torch.tensor([truncated_replay.rewards[0]]),
        torch.tensor([truncated_replay.dones[0]]),
        next_q,
        mask_tensor,
        0.9,
        torch.tensor([truncated_replay.steps[0]]),
    )
    assert trunc_target.item() == pytest.approx(0.25 - 0.9 * 0.5 + 0.9**2 * 0.5)


def test_decisive_buffer_and_mixed_batch_fallback() -> None:
    board = chess.Board()
    for move in ("f2f3", "e7e5", "g2g4", "d8h4"):
        board.push_uci(move)
    mate_game = _new_game(False, board)
    state = encode(chess.Board())
    _, actions = legal_actions(chess.Board())
    mask = action_mask(actions)
    transition = (state, 2, 1.0, state, True, mask, 1)
    mate_game.transitions.extend([transition, transition])
    decisive = ReplayBuffer(16)
    _copy_decisive(mate_game, decisive)
    assert len(decisive) == 2

    draw_game = _new_game(False, chess.Board("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1"))
    draw_game.transitions.append(transition)
    _copy_decisive(draw_game, decisive)
    assert len(decisive) == 2

    main_buffer, expert = ReplayBuffer(8), ReplayBuffer(8)
    for sample_buffer, action in ((main_buffer, 1), (decisive, 2), (expert, 3)):
        for _ in range(len(sample_buffer), 8 if sample_buffer is not decisive else 2):
            sample_buffer.add(state, action, 0.0, state, False, mask)
    batch, expert_batch = _sample_batches(
        main_buffer, decisive, expert, 8, 0.25, 0.25, np.random.default_rng(0)
    )
    assert len(batch["actions"]) == 6
    assert np.count_nonzero(batch["actions"] == 2) == 2
    assert len(expert_batch["actions"]) == 2

    small_decisive = ReplayBuffer(1)
    small_decisive.add(state, 2, 0.0, state, False, mask)
    fallback, _ = _sample_batches(
        main_buffer,
        small_decisive,
        expert,
        8,
        0.25,
        0.25,
        np.random.default_rng(1),
    )
    assert len(fallback["actions"]) == 6
    assert np.count_nonzero(fallback["actions"] == 1) == 5


def test_train_main_smoke_with_v6_options(tmp_path) -> None:
    pgn = tmp_path / "mate.pgn"
    pgn.write_text("1. f3 e5 2. g4 Qh4# 0-1\n", encoding="utf-8")
    out = tmp_path / "run"
    args = [
        "--out",
        str(out),
        "--games",
        "2",
        "--warmup-games",
        "0",
        "--parallel",
        "1",
        "--channels",
        "2",
        "--blocks",
        "0",
        "--device",
        "cpu",
        "--max-plies",
        "8",
        "--curriculum-pgn",
        str(pgn),
        "--endgame-max-plies",
        "4",
        "--n-step",
        "3",
        "--decisive-fraction",
        "0.25",
        "--decisive-buffer-size",
        "16",
        "--temp-start",
        "0",
    ]
    assert main(args) == 0
    with (out / "metrics.csv").open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    assert "decisive_buffer" in rows[0]
    assert (out / "final.pt").is_file()
