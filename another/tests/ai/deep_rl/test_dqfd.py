import io

import chess
import chess.pgn
import numpy as np
import pytest

torch = pytest.importorskip("torch")

from ai.deep_rl.user.agent import Agent, margin_loss  # noqa: E402
from ai.deep_rl.user.features import ACTIONS, action_mask, encode, legal_actions  # noqa: E402
from ai.deep_rl.user.pretrain import build_dataset, winner_transitions  # noqa: E402
from ai.deep_rl.user.replay import ReplayBuffer  # noqa: E402
from ai.deep_rl.user.train import main  # noqa: E402


def _game(pgn: str) -> chess.pgn.Game:
    game = chess.pgn.read_game(io.StringIO(pgn))
    assert game is not None
    return game


def test_winner_transitions_checkmate_resignation_and_draw() -> None:
    game = _game("1. e4 e5 2. Bc4 Nc6 3. Qh5 Nf6 4. Qxf7# 1-0")
    transitions = winner_transitions(game)
    assert len(transitions) == 4
    state, action, mask, reward, next_state, done, next_mask = transitions[-1]
    assert state.shape == (18, 8, 8) and 0 <= action < ACTIONS and mask.any()
    assert reward == 1.0 and done
    assert not next_state.any() and not next_mask.any()

    first = transitions[0]
    board = chess.Board()
    board.push_uci("e2e4")
    _, black_actions = legal_actions(board)
    assert np.array_equal(first[4], encode(board))
    assert np.array_equal(first[6], action_mask(black_actions))

    resignation = winner_transitions(_game("1. e4 e5 2. Nf3 1-0"))
    assert len(resignation) == 2
    assert resignation[-1][3] == 1.0 and resignation[-1][5]
    assert winner_transitions(_game("1. e4 e5 1/2-1/2")) == []


def test_margin_loss_uses_only_legal_actions() -> None:
    q = torch.tensor([[0.8, 0.6, 0.99], [0.4, 0.5, 0.0]])
    masks = torch.tensor([[True, True, False], [True, True, False]])
    actions = torch.tensor([0, 0])
    assert margin_loss(q[:1], masks[:1], actions[:1], 0.2).item() == 0
    assert margin_loss(q[1:], masks[1:], actions[1:], 0.2).item() == pytest.approx(0.3)
    assert margin_loss(q[:1], masks[:1], actions[:1], 0.05).item() == 0


def test_agent_expert_update_has_finite_losses_and_learns_margin() -> None:
    class TinyQ(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.values = torch.nn.Parameter(torch.zeros(ACTIONS))

        def forward(self, observations: torch.Tensor) -> torch.Tensor:
            return self.values.expand(len(observations), -1)

    agent = Agent(TinyQ(), lr=0.01, tau=0.0, margin=0.2, margin_weight=1.0)
    states = np.zeros((1, 1), dtype=np.uint8)
    masks = np.zeros((1, ACTIONS), dtype=np.bool_)
    masks[0, 1:3] = True
    expert_batch = {
        "states": states,
        "actions": np.asarray([1]),
        "masks": masks,
        "rewards": np.zeros(1, dtype=np.float32),
        "next_states": states,
        "next_masks": np.zeros_like(masks),
        "dones": np.ones(1, dtype=np.float32),
    }
    batch = {
        "states": states,
        "actions": np.asarray([0]),
        "rewards": np.zeros(1, dtype=np.float32),
        "next_states": states,
        "next_masks": np.zeros_like(masks),
        "dones": np.ones(1, dtype=np.float32),
    }
    before = margin_loss(
        agent.online(torch.as_tensor(states)),
        torch.as_tensor(masks),
        torch.as_tensor(expert_batch["actions"]),
        agent.margin,
    ).item()
    stats = agent.update(batch, expert_batch)
    assert np.isfinite(stats["td_loss"]) and np.isfinite(stats["margin_loss"])
    for _ in range(4):
        agent.update(batch, expert_batch)
    after = margin_loss(
        agent.online(torch.as_tensor(states)),
        torch.as_tensor(masks),
        torch.as_tensor(expert_batch["actions"]),
        agent.margin,
    ).item()
    assert after < before


def test_expert_replay_and_train_smoke(tmp_path) -> None:
    pgn = tmp_path / "expert.pgn"
    pgn.write_text("1. e4 e5 2. Bc4 Nc6 3. Qh5 Nf6 4. Qxf7# 1-0\n", encoding="utf-8")
    data = build_dataset([pgn], tmp_path / "built.npz")
    replay = ReplayBuffer.from_arrays(data)
    batch = replay.sample(2, np.random.default_rng(0))
    assert batch["states"].shape == (2, 18, 8, 8)
    assert batch["masks"].shape == (2, ACTIONS)

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
        "--max-plies",
        "8",
        "--batch-size",
        "2",
        "--learning-starts",
        "1",
        "--train-every",
        "1",
        "--eval-every",
        "1",
        "--eval-games",
        "1",
        "--channels",
        "8",
        "--blocks",
        "1",
        "--device",
        "cpu",
        "--expert-pgn",
        str(pgn),
        "--expert-fraction",
        "0.5",
    ]
    assert main(args) == 0
    assert (out / "expert.npz").is_file()
    header = (out / "metrics.csv").read_text(encoding="utf-8").splitlines()[0]
    assert "margin_loss" in header
