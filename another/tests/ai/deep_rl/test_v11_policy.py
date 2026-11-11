from pathlib import Path

import chess
import pytest

from ai.deep_rl.user import policy
from ai.deep_rl.v11.policy import V11_FORMAT, V11Policy


def _tiny_v11_file(path: Path) -> Path:
    torch = pytest.importorskip("torch")
    from ai.deep_rl.v11.model import PolicyValueNet

    torch.manual_seed(0)
    model = PolicyValueNet(channels=8, blocks=1)
    torch.save(
        {
            "format": V11_FORMAT,
            "model_config": model.config(),
            "model": {k: v.detach().cpu() for k, v in model.state_dict().items()},
            "experiment": "B_CURRICULUM",
        },
        path,
    )
    return path


def test_load_policy_reads_v11_weights_and_plays_legal_moves(tmp_path: Path) -> None:
    weights = _tiny_v11_file(tmp_path / "v11.pt")
    player = policy.load_policy(weights, simulations=8, max_think_time_s=0.0)
    assert isinstance(player, V11Policy)
    board = chess.Board()
    for _ in range(4):
        move = player.select_move(board.copy())
        assert move in board.legal_moves
        board.push(move)
    assert player.last_info["mode"] == "mcts"
    assert player.last_info["nodes"] == 7  # simulation 1 expands the root


def test_load_policy_still_rejects_unknown_format(tmp_path: Path) -> None:
    torch = pytest.importorskip("torch")
    path = tmp_path / "other.pt"
    torch.save({"format": "something-else", "model": {}}, path)
    with pytest.raises(ValueError):
        policy.load_policy(path)
