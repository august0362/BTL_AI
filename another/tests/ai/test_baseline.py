"""Tests for shared random baseline bots."""

import chess
import pytest

from ai import registry
from ai.baseline import RandomBaselineBot

OFFICIAL_BOT_IDS = registry.list_bots()


@pytest.mark.parametrize("bot_id", OFFICIAL_BOT_IDS)
def test_official_baselines_are_legal_and_seed_deterministic(bot_id: str) -> None:
    first = registry.create_bot(bot_id, {"seed": 17})
    second = registry.create_bot(bot_id, {"seed": 17})
    assert isinstance(first, RandomBaselineBot)
    assert first.is_baseline is True
    assert second.is_baseline is True

    first_board = chess.Board()
    second_board = chess.Board()
    first_moves: list[str] = []
    second_moves: list[str] = []
    for _ in range(12):
        first_move = first.select_move(first_board)
        second_move = second.select_move(second_board)
        assert first_move in first_board.legal_moves
        assert second_move in second_board.legal_moves
        first_moves.append(first_move.uci())
        second_moves.append(second_move.uci())
        first_board.push(first_move)
        second_board.push(second_move)

    assert first_moves == second_moves


def test_bot_packages_can_import_shared_baseline() -> None:
    from ai.alphabeta_regression.bot import AlphaBetaRegressionBot
    from ai.deep_rl.bot import DeepRLBot
    from ai.genetic_alphabeta.bot import GeneticAlphaBetaBot
    from ai.mcts.bot import MctsBot

    assert all(
        issubclass(bot_type, RandomBaselineBot)
        for bot_type in (AlphaBetaRegressionBot, GeneticAlphaBetaBot, MctsBot, DeepRLBot)
    )
