import random

import chess
import numpy as np
import pytest

from ai.deep_rl.user.features import (
    ACTIONS,
    action_mask,
    encode,
    legal_actions,
    move_to_action,
)
from ai.deep_rl.user.replay import ReplayBuffer

torch = pytest.importorskip("torch")

from ai.deep_rl.user.agent import MASK_VALUE, Agent, bellman_targets  # noqa: E402
from ai.deep_rl.user.model import Model  # noqa: E402
from ai.deep_rl.user.policy import load_policy, save_weights  # noqa: E402
from ai.deep_rl.user.train import format_duration, main, smooth  # noqa: E402


def _random_boards(count: int, seed: int = 0) -> list[chess.Board]:
    rng = random.Random(seed)
    boards = []
    board = chess.Board()
    while len(boards) < count:
        if board.is_game_over():
            board = chess.Board()
        board.push(rng.choice(list(board.legal_moves)))
        boards.append(board.copy())
    return boards


def _mirror_move(move: chess.Move) -> chess.Move:
    return chess.Move(
        chess.square_mirror(move.from_square),
        chess.square_mirror(move.to_square),
        move.promotion,
    )


def test_encode_start_position_planes() -> None:
    planes = encode(chess.Board())
    assert planes.shape == (18, 8, 8) and planes.dtype == np.uint8
    assert planes[0].sum() == 8 and planes[0, 1].all()  # my pawns on rank 2
    assert planes[6].sum() == 8 and planes[6, 6].all()  # opponent pawns on rank 7
    assert planes[5, 0, 4] == 1 and planes[11, 7, 4] == 1  # kings on e1 / e8
    assert not planes[12:14].any()
    assert planes[14:18].all()


def test_encode_is_canonical_for_both_colors() -> None:
    for board in _random_boards(60):
        assert np.array_equal(encode(board), encode(board.mirror()))


def test_castling_and_repetition_planes() -> None:
    board = chess.Board("r3k2r/8/8/8/8/8/8/R3K2R w Kq - 0 1")
    planes = encode(board)
    assert planes[14].all() and not planes[15].any()  # white: kingside only
    assert not planes[16].any() and planes[17].all()  # black: queenside only
    board = chess.Board()
    for uci in ("g1f3", "g8f6", "f3g1", "f6g8"):
        board.push_uci(uci)
    assert encode(board)[12].all() and not encode(board)[13].any()


def test_actions_are_unique_and_mirror_symmetric() -> None:
    for board in _random_boards(80, seed=1):
        moves, actions = legal_actions(board)
        assert len(set(actions.tolist())) == len(moves)
        assert ((actions >= 0) & (actions < ACTIONS)).all()
        mirrored = board.mirror()
        for move, action in zip(moves, actions, strict=True):
            assert move_to_action(_mirror_move(move), mirrored.turn) == action


def test_underpromotions_get_distinct_actions() -> None:
    board = chess.Board("8/P6k/8/8/8/8/6Kp/8 w - - 0 1")
    moves, actions = legal_actions(board)
    promotions = {
        move.promotion: action
        for move, action in zip(moves, actions, strict=True)
        if move.promotion
    }
    assert set(promotions) == {chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT}
    assert len(set(promotions.values())) == 4


def test_replay_buffer_roundtrip_and_overwrite() -> None:
    buffer = ReplayBuffer(capacity=3)
    board = chess.Board()
    state = encode(board)
    _, actions = legal_actions(board)
    mask = action_mask(actions)
    for step in range(5):
        buffer.add(state, step, 1.0, state, step % 2 == 0, mask)
    assert len(buffer) == 3
    batch = buffer.sample(16, np.random.default_rng(0))
    assert np.array_equal(batch["states"][0], state)
    assert np.array_equal(batch["next_masks"][0], mask)
    assert set(batch["actions"].tolist()) <= {2, 3, 4}


def test_model_output_shape_and_range() -> None:
    model = Model(channels=8, blocks=1)
    with torch.no_grad():
        q = model(torch.as_tensor(np.stack([encode(chess.Board())] * 2)))
    assert q.shape == (2, ACTIONS)
    assert float(q.abs().max()) <= 1.0


def test_bellman_target_negamax_and_masking() -> None:
    next_q = torch.zeros(3, ACTIONS)
    next_q[:, 0] = 0.5
    next_q[:, 1] = 0.9  # illegal below, must be ignored
    next_mask = torch.zeros(3, ACTIONS, dtype=torch.bool)
    next_mask[:, 0] = True
    rewards = torch.tensor([0.0, 1.0, 0.0])
    dones = torch.tensor([0.0, 1.0, 1.0])
    targets = bellman_targets(rewards, dones, next_q, next_mask, gamma=0.9)
    assert torch.allclose(targets, torch.tensor([-0.45, 1.0, 0.0]))
    empty = torch.zeros(1, ACTIONS, dtype=torch.bool)
    terminal = bellman_targets(torch.zeros(1), torch.ones(1), next_q[:1], empty, 0.9)
    assert torch.isfinite(terminal).all() and MASK_VALUE < -1e8


def test_agent_acts_legally_and_updates() -> None:
    torch.manual_seed(0)
    agent = Agent(Model(channels=8, blocks=1), tau=0.5)
    boards = _random_boards(8, seed=2)
    states = np.stack([encode(board) for board in boards])
    legal = [legal_actions(board)[1] for board in boards]
    masks = np.stack([action_mask(actions) for actions in legal])
    for temperature in (None, 1.0, 0.1):
        picked = agent.act(states, masks, temperature)
        assert all(action in actions for action, actions in zip(picked, legal, strict=True))
    assert agent.select_action(boards[0]) in boards[0].legal_moves

    buffer = ReplayBuffer(capacity=16)
    for state, mask, actions in zip(states, masks, legal, strict=True):
        buffer.add(state, int(actions[0]), 0.0, state, False, mask)
    before = [p.clone() for p in agent.target.parameters()]
    stats = agent.update(buffer.sample(8, np.random.default_rng(0)))
    assert np.isfinite(stats["loss"])
    online = list(agent.online.parameters())
    for old, new, current in zip(before, agent.target.parameters(), online, strict=True):
        assert torch.allclose(new, old.lerp(current, 0.5))


def test_policy_roundtrip(tmp_path) -> None:
    model = Model(channels=8, blocks=1)
    save_weights(model, tmp_path / "w.pt")
    policy = load_policy(tmp_path / "w.pt")
    for board in _random_boards(5, seed=3):
        assert policy.select_move(board.copy()) in board.legal_moves


def test_train_smoke(tmp_path) -> None:
    out = tmp_path / "run"
    args = ["--out", str(out), "--games", "6", "--warmup-games", "2", "--parallel", "3"]
    args += ["--max-plies", "16", "--batch-size", "8", "--learning-starts", "8"]
    args += ["--eval-every", "3", "--eval-games", "2", "--channels", "8", "--blocks", "1"]
    args += ["--device", "cpu"]
    assert main(args) == 0
    assert (out / "best.pt").is_file() and (out / "final.pt").is_file()
    rows = (out / "metrics.csv").read_text(encoding="utf-8").splitlines()
    assert rows[0].startswith("step,loss") and len(rows) == 3
    assert main([*args, "--games", "9", "--resume", str(out / "checkpoint.pt")]) == 0


def test_eta_smoothing_and_format() -> None:
    assert smooth(None, 10.0, 0.3) == 10.0
    assert smooth(10.0, 20.0, 0.3) == pytest.approx(13.0)
    assert format_duration(3725.4) == "1:02:05"
    assert format_duration(float("nan")) == "?"
