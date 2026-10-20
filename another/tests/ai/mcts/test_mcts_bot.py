"""Integration, configuration, history preservation and instance isolation."""

import json
import random

import chess
import pytest

from ai.base_bot import BaseBot
from ai.mcts.bot import MctsBot
from ai.registry import create_bot


def fixed_config(**updates) -> dict:
    return {"seed": 71, "simulations": 80, "max_think_time_s": 0, "rollout_max_plies": 2, **updates}


def test_registry_returns_a_real_mcts_implementation() -> None:
    bot = create_bot("mcts", fixed_config())
    assert isinstance(bot, BaseBot)
    assert isinstance(bot, MctsBot)
    assert not bot.is_baseline
    assert bot.bot_id == "mcts"
    bot.select_move(chess.Board())
    info = bot.last_search_info
    assert info["simulations"] == info["root_visits"] == 80
    assert info["nodes"] == 81
    assert info["depth"] >= 2
    best = max(info["root_children"], key=lambda row: (row["visits"], row["mean_reward"]))
    assert best["visits"] > 0
    assert -1 <= info["eval"] <= 1
    json.dumps(info, allow_nan=False)


def test_input_history_and_fen_survive_search() -> None:
    board = chess.Board()
    for move in ["g1f3", "g8f6", "f3g1", "f6g8"]:
        board.push_uci(move)
    before = (board.fen(en_passant="fen"), list(board.move_stack), board.root().fen())
    move = MctsBot(fixed_config()).select_move(board)
    assert move in board.legal_moves
    assert (board.fen(en_passant="fen"), board.move_stack, board.root().fen()) == before


def test_same_seed_and_fixed_simulations_reproduce_search() -> None:
    first, second = MctsBot(fixed_config()), MctsBot(fixed_config())
    board = chess.Board()
    assert first.select_move(board) == second.select_move(board)
    assert first.last_search_info["root_children"] == second.last_search_info["root_children"]


def test_other_instances_do_not_consume_our_rng_or_global_rng() -> None:
    first, reference = MctsBot(fixed_config()), MctsBot(fixed_config())
    unrelated = MctsBot(fixed_config(seed=99))
    state = random.getstate()
    unrelated.select_move(chess.Board())
    assert first.select_move(chess.Board()) == reference.select_move(chess.Board())
    assert random.getstate() == state


def test_reset_clears_diagnostics_and_search_starts_a_new_tree() -> None:
    bot = MctsBot(fixed_config())
    bot.select_move(chess.Board())
    bot.reset()
    assert bot.last_search_info == {}
    board = chess.Board()
    board.push_uci("e2e4")
    assert bot.select_move(board) in board.legal_moves
    assert bot.last_search_info["root_visits"] == 80


@pytest.mark.parametrize("black", [False, True])
def test_assisted_mate_in_one_for_both_colors(black: bool) -> None:
    board = chess.Board("7k/5Q2/6K1/8/8/8/8/8 w - - 0 1")
    if black:
        board = board.mirror()
    bot = MctsBot(fixed_config())
    move = bot.select_move(board)
    board.push(move)
    assert board.is_checkmate()
    assert bot.last_search_info["eval"] == 1.0
    assert bot.last_search_info["shortcut"] == "mate_in_one"


def test_only_move_and_finished_game_are_handled_explicitly() -> None:
    bot = MctsBot(fixed_config())
    board = chess.Board("4k3/8/8/8/8/8/4q3/4K3 w - - 0 1")
    assert bot.select_move(board).uci() == "e1e2"
    assert bot.last_search_info["shortcut"] == "only_legal_move"
    board.push_uci("e1e2")
    with pytest.raises(ValueError, match="finished game"):
        bot.select_move(board)
    assert bot.last_search_info == {}


def test_fast_mode_caps_simulations_and_time_without_weights() -> None:
    bot = MctsBot(
        {
            "fast_mode": True,
            "allow_random_init": True,
            "seed": 0,
            "simulations": 1000,
            "max_think_time_s": 10,
        }
    )
    assert bot.search_config.simulations == 32
    assert bot.search_config.max_think_time_s == 0.05
    assert bot.select_move(chess.Board()) in chess.Board().legal_moves


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("simulations", 0),
        ("simulations", True),
        ("simulations", 2.5),
        ("rollout_max_plies", -1),
        ("max_think_time_s", -1),
        ("max_think_time_s", float("nan")),
        ("max_think_time_s", "1"),
        ("exploration_constant", -1),
        ("exploration_constant", float("inf")),
        ("use_heuristics", "false"),
    ],
)
def test_invalid_search_settings_fail_clearly(key: str, value: object) -> None:
    with pytest.raises(ValueError, match="mcts:"):
        MctsBot({key: value})
