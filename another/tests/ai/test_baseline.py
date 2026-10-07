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

    if not first.is_baseline:
        pytest.skip(f"{bot_id} is a real implementation, not a baseline")

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
