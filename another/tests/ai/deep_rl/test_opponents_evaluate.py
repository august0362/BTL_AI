import chess

from ai.deep_rl.evaluate import EvalResult, evaluate
from ai.deep_rl.opponents import GreedyCaptureOpponent, MixedOpponent, RandomOpponent


def test_opponents_choose_legal_moves_and_greedy_takes_queen() -> None:
    board = chess.Board("4k3/8/8/3q4/8/8/8/3RK2R w - - 0 1")
    rng = __import__("random").Random(3)
    for opponent in (
        RandomOpponent(),
        GreedyCaptureOpponent(),
        MixedOpponent([(RandomOpponent(), 1)]),
    ):
        assert opponent.select_move(board, rng) in board.legal_moves
    move = GreedyCaptureOpponent().select_move(board, rng)
    assert board.piece_at(move.to_square).piece_type == chess.QUEEN


class RandomPolicy:
    def __init__(self):
        self.colors = []

    def select_move(self, board):
        self.colors.append(board.turn)
        return next(iter(board.legal_moves))


def test_evaluate_counts_games_and_alternates_policy_color() -> None:
    policy = RandomPolicy()
    result = evaluate(policy, RandomOpponent(), n_games=2, seed=4, max_plies=2)
    assert isinstance(result, EvalResult)
    assert result.wins + result.draws + result.losses == 2
    assert result.avg_plies == 2
    assert policy.colors[0] is chess.WHITE
    assert policy.colors[1] is chess.BLACK
