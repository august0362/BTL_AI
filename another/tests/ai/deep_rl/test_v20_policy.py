"""V20 phase history, checkpoint conversion, and bot loading contracts."""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

import chess
import pytest

from ai.deep_rl.user import policy
from ai.deep_rl.v20.policy import (
    PHASES,
    V20_FORMAT,
    V20Policy,
    load_v20_policy,
    material_phase,
    mid_probability,
    select_phase,
)

_TINY_CONFIG = {"channels": 8, "blocks": 1, "head_channels": 4}


def test_mid_probability_uses_ply_and_both_sides_material() -> None:
    board = chess.Board()
    assert material_phase(board) == 24
    assert mid_probability(board) == 0.0
    board.fullmove_number = 13
    assert board.ply() == 24
    assert mid_probability(board) == pytest.approx(0.4)
    board.fullmove_number = 16
    board.remove_piece_at(chess.D8)
    assert material_phase(board) == 20
    assert mid_probability(board) == pytest.approx(0.75)
    board.fullmove_number = 100
    assert mid_probability(board) == 1.0


def test_select_phase_start_and_quiet_midgame() -> None:
    board = chess.Board()
    assert select_phase(board) == "start"
    for san in (
        "e4 e5 Nf3 Nc6 Bc4 Bc5 d3 Nf6 O-O d6 c3 O-O Re1 a6 "
        "Bb3 Ba7 Nbd2 h6 Nf1 Re8 Ng3 Be6 Bc2 Qd7 h3 Rad8"
    ).split():
        board.push_san(san)
    original = board.copy(stack=True)
    assert board.ply() == 26
    assert material_phase(board) == 24
    assert select_phase(board) == "mid"
    assert select_phase(board, threshold=0.6) == "start"
    assert board == original and board.move_stack == original.move_stack
    assert select_phase(chess.Board()) == "start"  # No state shared between games.


def test_end_is_sticky_after_promotion_only_for_the_side_that_observed_it() -> None:
    board = chess.Board("4k2r/P7/7r/8/8/8/8/1R1RK3 w - - 0 1")
    assert board.is_valid()
    assert material_phase(board) == 8
    assert select_phase(board) == "end"
    board.push_san("a8=Q+")
    assert material_phase(board) == 12
    assert select_phase(board) == "start"  # Black never observed G <= 8 on its turn.
    board.push_san("Ke7")
    assert select_phase(board.copy(stack=True)) == "end"
    assert select_phase(board.copy(stack=False)) == "start"


def test_pack_round_trip_plays_legal_moves_and_preserves_source_hashes(tmp_path: Path) -> None:
    torch = pytest.importorskip("torch")
    from ai.deep_rl.v20.model import PolicyValueNet
    from ai.deep_rl.v20.pack import pack

    torch.manual_seed(0)
    paths = [tmp_path / f"{phase}.pt" for phase in PHASES]
    states = [PolicyValueNet(**_TINY_CONFIG).state_dict() for _ in PHASES]
    torch.save({"model": states[0], "model_config": _TINY_CONFIG}, paths[0])
    torch.save(
        {
            "model": {
                **{f"core.{key}": value for key, value in states[1].items()},
                "aux.D.2.weight": torch.zeros(1, 8),
            },
            "optimizer": {"training_path": Path("training-only")},
        },
        paths[1],
    )
    torch.save({"state_dict": states[2]}, paths[2])
    output = tmp_path / "packed" / "v20.pt"
    digest = pack(*paths, output, model_config=_TINY_CONFIG)
    assert digest == hashlib.sha256(output.read_bytes()).hexdigest()
    data = torch.load(output, weights_only=True)
    assert data["format"] == V20_FORMAT
    assert data["model_config"] == _TINY_CONFIG
    for phase, source, expected in zip(PHASES, paths, states, strict=True):
        assert data["meta"]["sources"][phase] == {
            "file": source.name,
            "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        }
        assert set(data["models"][phase]) == set(expected)
        for key, value in expected.items():
            assert torch.equal(data["models"][phase][key], value)

    player = policy.load_policy(output, simulations=8)
    assert isinstance(player, V20Policy)
    board = chess.Board()
    for _ in range(4):
        snapshot = board.copy(stack=True)
        move = player.select_move(board)
        assert board == snapshot and board.move_stack == snapshot.move_stack
        assert move in board.legal_moves
        board.push(move)
        assert player.last_info["mode"] == "mcts"
        assert player.last_info["phase"] in PHASES
        assert player.last_info["simulations"] == 8
        assert player.last_info["nodes"] == 9  # Root plus eight evaluated leaf positions.
        assert -1.0 <= player.last_info["eval"] <= 1.0


def test_file_missing_a_phase_is_rejected(tmp_path: Path) -> None:
    torch = pytest.importorskip("torch")
    path = tmp_path / "incomplete.pt"
    torch.save(
        {"format": V20_FORMAT, "model_config": _TINY_CONFIG, "models": {"start": {}, "mid": {}}},
        path,
    )
    with pytest.raises(ValueError):
        policy.load_policy(path)


@pytest.mark.parametrize("corruption", ["format", "config", "missing", "extra", "shape"])
def test_loader_strictly_validates_weights(corruption: str) -> None:
    torch = pytest.importorskip("torch")
    from ai.deep_rl.v20.model import PolicyValueNet

    state = PolicyValueNet(**_TINY_CONFIG).state_dict()
    data = {
        "format": V20_FORMAT,
        "model_config": _TINY_CONFIG,
        "models": {phase: dict(state) for phase in PHASES},
    }
    if corruption == "format":
        data["format"] = "unknown"
    elif corruption == "config":
        data["model_config"] = {"unknown": 8}
    elif corruption == "missing":
        data["models"]["end"].pop("stem.0.weight")
    elif corruption == "extra":
        data["models"]["end"]["aux.weight"] = torch.zeros(1)
    else:
        data["models"]["end"]["stem.0.weight"] = torch.zeros(1)
    with pytest.raises(ValueError):
        load_v20_policy(data)


def test_policy_import_does_not_load_torch() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import ai.deep_rl.v20.policy; assert 'torch' not in sys.modules",
        ],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "PYTHONPATH": os.pathsep.join(sys.path)},
    )
    assert result.returncode == 0, result.stderr
