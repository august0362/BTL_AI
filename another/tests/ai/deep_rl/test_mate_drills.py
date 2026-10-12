from __future__ import annotations

import csv

import chess
import numpy as np

from ai.deep_rl.user.curriculum import load_mate_puzzles, phase_for
from ai.deep_rl.user.train import (
    TrainConfig,
    _mate_success,
    _MateProgress,
    _new_mate_game,
    main,
    mate_expert_data,
    play_move,
)

MATE_ONE = ("rnbqkbnr/pppp1ppp/8/4p3/6P1/5P2/PPPPP2P/RNBQKBNR b KQkq g3 0 2", "d8h4")
MATE_TWO = (
    "r1bqkbnr/pppp1ppp/4p3/8/1n5N/N6P/PPPPPPP1/R1BQKB1R b KQkq - 0 4",
    "f8d6 f2f3 d6g3",
)
MATE_PGN = '[Result "0-1"]\n\n1. f3 e5 2. g4 Qh4# 0-1\n'


def _puzzles_csv(path, rows: list[tuple[int, str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(("level", "puzzle_id", "fen", "solution"))
        for level, fen, solution in rows:
            writer.writerow((level, f"p{level}", fen, solution))


def test_load_mate_puzzles_verifies_mate_in_one_and_two(tmp_path) -> None:
    path = tmp_path / "puzzles.csv"
    _puzzles_csv(path, [(1, MATE_ONE[0], MATE_ONE[1]), (2, MATE_TWO[0], MATE_TWO[1])])

    puzzles = load_mate_puzzles(path)

    assert [move.uci() for move in puzzles[1][0][1]] == ["d8h4"]
    assert [move.uci() for move in puzzles[2][0][1]] == ["f8d6", "f2f3", "d6g3"]
    assert puzzles[3] == [] and puzzles[4] == []


def test_mate_level_gating_and_regular_schedule_index() -> None:
    progress = _MateProgress(max_level=1, window=3, pass_rate=2 / 3, min_games=4, max_games=6)
    assert progress.record(True, 1) is None
    assert progress.record(False, 1) is None
    assert progress.record(True, 1) is None
    assert progress.record(True, 1) == (1, 4, 2 / 3)
    assert progress.level == 2
    assert progress.record(False, 1) is None
    assert progress.games_by_level[1] == 5
    assert progress.games == 0
    assert phase_for(0, TrainConfig(games=10)).name == "endgame"

    forced = _MateProgress(max_level=1, window=4, pass_rate=0.8, min_games=4, max_games=2)
    assert forced.record(False, 1) is None
    assert forced.record(False, 1) == (1, 2, 0.0)


def test_mate_one_drill_is_capped_and_mate_is_success() -> None:
    puzzle = (MATE_ONE[0], [chess.Move.from_uci(MATE_ONE[1])])
    game = _new_mate_game([puzzle], 1, np.random.default_rng(0))
    assert game.max_plies == 1
    mating_move = chess.Move.from_uci(MATE_ONE[1])

    _, finished, result = play_move(game, game.moves.index(mating_move))

    assert finished and result == "0-1"
    assert _mate_success(game)


def test_mate_expert_records_attacker_moves_and_terminal_reward() -> None:
    solution = [chess.Move.from_uci(move) for move in MATE_TWO[1].split()]
    puzzles = {
        1: [],
        2: [(MATE_TWO[0], solution)],
    }

    data = mate_expert_data(puzzles)

    assert data["actions"].shape == (2,)
    assert data["rewards"].tolist() == [0.0, 1.0]
    assert data["dones"].tolist() == [0.0, 1.0]
    assert np.unpackbits(data["next_states"][0]).any()


def test_train_smoke_with_mate_csv_and_pgn_expert(tmp_path) -> None:
    puzzle_path = tmp_path / "mate.csv"
    _puzzles_csv(puzzle_path, [(1, MATE_ONE[0], MATE_ONE[1])])
    pgn_path = tmp_path / "expert.pgn"
    pgn_path.write_text(MATE_PGN, encoding="utf-8")
    out = tmp_path / "run"

    assert (
        main(
            [
                "--out",
                str(out),
                "--games",
                "1",
                "--warmup-games",
                "0",
                "--parallel",
                "1",
                "--max-plies",
                "1",
                "--eval-every",
                "1",
                "--eval-games",
                "1",
                "--channels",
                "2",
                "--blocks",
                "0",
                "--device",
                "cpu",
                "--mate-puzzles",
                str(puzzle_path),
                "--mate-max-level",
                "1",
                "--mate-min-games",
                "1",
                "--mate-max-games",
                "1",
                "--mate-expert",
                "1",
                "--expert-pgn",
                str(pgn_path),
            ]
        )
        == 0
    )
    assert (out / "final.pt").is_file()
    with (out / "metrics.csv").open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    assert rows[0]["phase"] == "mate1"
    assert rows[-1]["phase"] == "endgame"
    assert float(rows[0]["mate_rate"]) in (0.0, 1.0)
