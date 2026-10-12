from __future__ import annotations

import csv

import chess

from ai.deep_rl.user.curriculum import load_decisive_games, phase_for, start_board
from ai.deep_rl.user.train import TrainConfig, _new_game, main, play_move


class _FixedRng:
    def __init__(self, value: int) -> None:
        self.value = value

    def randint(self, low: int, high: int) -> int:
        assert low <= self.value <= high
        return self.value


def test_load_decisive_and_start_board_preserves_history(tmp_path) -> None:
    pgn = tmp_path / "games.pgn"
    pgn.write_text(
        "1. e4 e5 2. Bc4 Nc6 3. Qh5 Nf6 4. Qxf7# 1-0\n\n1. e4 e5 1/2-1/2\n",
        encoding="utf-8",
    )
    games = load_decisive_games([pgn])
    assert len(games) == 1
    assert len(games[0]) == 7

    cycle = [chess.Move.from_uci(uci) for uci in ("g1f3", "g8f6", "f3g1", "f6g8")]
    board = start_board(cycle, 0, 0, _FixedRng(0))
    assert len(board.move_stack) == 4
    assert board.is_repetition(2)
    assert not board.is_game_over()
    ranged = start_board(games[0], 2, 4, _FixedRng(3))
    assert len(ranged.move_stack) == len(games[0]) - 3
    assert not ranged.is_game_over()


def test_phase_boundaries_and_midgame_plies_cap() -> None:
    config = TrainConfig(games=10)
    assert [phase_for(i, config).name for i in (0, 2, 3, 5, 6, 7, 9)] == [
        "endgame",
        "endgame",
        "middlegame",
        "middlegame",
        "full",
        "full150",
        "full150",
    ]
    board = chess.Board()
    for uci in ("e2e4", "e7e5", "g1f3", "b8c6", "f1c4", "g8f6"):
        board.push_uci(uci)
    game = _new_game(False, board, max_plies=1)
    _, finished, _ = play_move(game, 0)
    assert finished
    assert game.board.ply() > game.max_plies


def test_train_curriculum_smoke_and_time_limit_checkpoint(tmp_path) -> None:
    pgn = tmp_path / "tiny.pgn"
    pgn.write_text("1. e4 e5 2. Bc4 Nc6 3. Qh5 Nf6 4. Qxf7# 1-0\n", encoding="utf-8")
    out = tmp_path / "run"
    assert (
        main(
            [
                "--out",
                str(out),
                "--games",
                "20",
                "--warmup-games",
                "0",
                "--parallel",
                "1",
                "--max-plies",
                "2",
                "--eval-every",
                "20",
                "--eval-games",
                "1",
                "--channels",
                "2",
                "--blocks",
                "0",
                "--device",
                "cpu",
                "--curriculum-pgn",
                str(pgn),
                "--max-hours",
                "0.000000000001",
            ]
        )
        == 0
    )
    assert (out / "checkpoint.pt").is_file()
    assert (out / "final.pt").is_file()
    with (out / "metrics.csv").open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    assert "phase" in rows[0]
    assert int(rows[-1]["step"]) < 20
