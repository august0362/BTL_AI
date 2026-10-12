import csv

import chess
import chess.pgn
import pytest

torch = pytest.importorskip("torch")

from ai.deep_rl.user import pretrain, train  # noqa: E402
from ai.deep_rl.user.agent import bellman_targets  # noqa: E402
from ai.deep_rl.user.features import ACTIONS  # noqa: E402
from ai.deep_rl.user.model import Model  # noqa: E402
from ai.deep_rl.user.policy import load_file, load_policy, save_weights  # noqa: E402
from ai.deep_rl.user.potential import evaluate_cp, potential  # noqa: E402
from ai.deep_rl.user.search import AlphaBetaPolicy  # noqa: E402

MATE_PGN = '[Result "0-1"]\n\n1. f3 e5 2. g4 Qh4# 0-1\n'


class _ZeroQ(torch.nn.Module):
    def forward(self, states: torch.Tensor) -> torch.Tensor:
        return torch.zeros((len(states), ACTIONS), device=states.device)


def _game(text: str) -> chess.pgn.Game:
    import io

    return chess.pgn.read_game(io.StringIO(text))


def test_potential_symmetry_bounds_and_material() -> None:
    board = chess.Board()
    assert evaluate_cp(board) == 0
    assert potential(board, 0.7) == 0
    board.set_fen("4k3/8/8/8/8/8/8/3QK3 w - - 0 1")
    assert potential(board, 0.7) > 0
    assert abs(potential(board, 0.7)) < 0.7
    assert potential(board, 0.7) == pytest.approx(potential(board.mirror(), 0.7))


def test_terminal_draw_shaping_telescopes_and_truncation_is_not_draw() -> None:
    board = chess.Board("7k/5K2/4Q3/8/8/8/8/8 w - - 0 1")
    game = train._new_game(False, board)
    move = chess.Move.from_uci("e6g6")
    index = game.moves.index(move)
    old_phi = potential(board, 0.5)
    transition, finished, result = train.play_move(
        game, index, draw_penalty=0.0, potential_scale=0.5, gamma=0.9
    )
    assert finished and result == "1/2-1/2" and game.board.is_stalemate()
    assert transition[2] == pytest.approx(-old_phi)

    penalized = train._new_game(False, chess.Board("7k/5K2/4Q3/8/8/8/8/8 w - - 0 1"))
    penalty_transition, _, _ = train.play_move(
        penalized, penalized.moves.index(move), draw_penalty=0.2
    )
    assert penalty_transition[2] == pytest.approx(-0.2)

    board = chess.Board()
    for uci in ("g1f3", "g8f6", "f3g1", "f6g8", "g1f3", "g8f6", "f3g1"):
        board.push_uci(uci)
    game = train._new_game(False, board)
    idx = game.moves.index(chess.Move.from_uci("f6g8"))
    transition, finished, _ = train.play_move(game, idx, draw_penalty=0.2)
    assert finished and transition[2] == pytest.approx(-0.2)

    truncated = train._new_game(False, chess.Board(), max_plies=1)
    transition, finished, result = train.play_move(truncated, 0, draw_penalty=0.2)
    assert finished and not transition[4] and result == "*"
    assert transition[2] == 0


def test_value_targets_have_both_signs_discount_and_potential(tmp_path) -> None:
    pgn = tmp_path / "mate.pgn"
    pgn.write_text(MATE_PGN, encoding="utf-8")
    data = pretrain.build_dataset([pgn], tmp_path / "positions.npz", potential_scale=0.0, gamma=0.9)
    assert len(data["value_actions"]) == 4
    assert data["value_targets"].tolist() == pytest.approx([-(0.9**3), 0.9**2, -0.9, 1.0])

    shaped = pretrain.build_dataset([pgn], tmp_path / "shaped.npz", potential_scale=0.5, gamma=0.9)
    board = chess.Board()
    board.push_uci("f2f3")
    assert shaped["value_targets"][1] == pytest.approx(0.9**2 - potential(board, 0.5))


def test_double_dqn_uses_online_argmax() -> None:
    rewards = torch.tensor([0.0])
    dones = torch.tensor([0.0])
    online = torch.zeros((1, ACTIONS))
    target = torch.zeros((1, ACTIONS))
    mask = torch.zeros((1, ACTIONS), dtype=torch.bool)
    mask[0, :2] = True
    online[0, 0], online[0, 1] = 1, 2
    target[0, 0], target[0, 1] = 0.8, -0.4
    value = bellman_targets(rewards, dones, target, mask, 0.9, online_q=online)
    assert value.item() == pytest.approx(0.36)


def test_weights_meta_old_files_and_search_potential(tmp_path, monkeypatch) -> None:
    model = Model(channels=2, blocks=0)
    path = tmp_path / "weights.pt"
    save_weights(model, path, {"potential_scale": 0.5})
    assert load_file(path)["meta"] == {"potential_scale": 0.5}
    assert isinstance(load_policy(path, depth=2), AlphaBetaPolicy)

    old_path = tmp_path / "old.pt"
    torch.save({"format": "deep_rl_dqn_v1", "model": {}, "config": {}}, old_path)
    assert load_file(old_path)["meta"] == {}

    board = chess.Board()
    e4 = chess.Move.from_uci("e2e4")
    module = __import__("ai.deep_rl.user.potential", fromlist=["potential"])
    monkeypatch.setattr(
        module,
        "potential",
        lambda child, scale: float(child.piece_at(chess.E4) is not None) * scale,
    )
    avoid_e4 = AlphaBetaPolicy(_ZeroQ(), depth=2, max_think_time_s=0, potential_scale=1)
    assert avoid_e4.select_move(board) != e4
    monkeypatch.setattr(
        module,
        "potential",
        lambda child, scale: -float(child.piece_at(chess.E4) is not None) * scale,
    )
    prefer_e4 = AlphaBetaPolicy(_ZeroQ(), depth=2, max_think_time_s=0, potential_scale=1)
    assert prefer_e4.select_move(board) == e4


def test_lr_warmup_and_v7_cli_smoke_runs(tmp_path) -> None:
    config = train.TrainConfig(lr=0.001, lr_warmup_games=10, lr_warmup_factor=0.1)
    assert train.learning_rate_for(0, config) == pytest.approx(0.0001)
    assert train.learning_rate_for(5, config) == pytest.approx(0.00055)
    assert train.learning_rate_for(10, config) == pytest.approx(0.001)

    pgn = tmp_path / "games.pgn"
    pgn.write_text(MATE_PGN * 2, encoding="utf-8")
    pretrain_out = tmp_path / "pretrain"
    assert (
        pretrain.main(
            [
                "--pgn",
                str(pgn),
                "--out",
                str(pretrain_out),
                "--epochs",
                "1",
                "--channels",
                "2",
                "--blocks",
                "0",
                "--batch-size",
                "2",
                "--device",
                "cpu",
                "--value-weight",
                "1.0",
                "--potential-scale",
                "0.5",
                "--gamma",
                "0.99",
            ]
        )
        == 0
    )
    weights = pretrain_out / "sl_pretrained.pt"
    assert load_file(weights)["meta"]["potential_scale"] == 0.5
    assert "val_value_loss" in next(
        csv.DictReader((pretrain_out / "pretrain_metrics.csv").open(encoding="utf-8"))
    )

    train_out = tmp_path / "selfplay"
    assert (
        train.main(
            [
                "--out",
                str(train_out),
                "--init-weights",
                str(weights),
                "--games",
                "1",
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
                "1",
                "--learning-starts",
                "1",
                "--batch-size",
                "1",
                "--eval-every",
                "1",
                "--eval-games",
                "1",
                "--potential-scale",
                "0.5",
                "--draw-penalty",
                "0.1",
                "--double-dqn",
                "1",
                "--lr-warmup-games",
                "2",
                "--lr-warmup-factor",
                "0.1",
            ]
        )
        == 0
    )
    assert (train_out / "final.pt").is_file()
