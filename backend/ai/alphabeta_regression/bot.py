"""Alpha-beta chess bot with a material-based linear-regression evaluator."""

import time

import chess

from ai.alphabeta_regression.evaluate import evaluate
from ai.alphabeta_regression.feature import extract_features
from ai.base_bot import BaseBot


class _OutOfTime(Exception):
    """Raised inside the search when the per-move time budget runs out."""


class AlphaBetaRegressionBot(BaseBot):
    """Select moves with alpha-beta search and a material-based evaluator."""

    bot_id = "alphabeta_regression"
    display_name = "Alpha-Beta Regression"
    _MIN_DEPTH = 1
    _MAX_DEPTH = 6

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config)
        default_depth = 1 if self.config.get("fast_mode") else 3
        try:
            configured_depth = int(self.config.get("depth", default_depth))
        except (TypeError, ValueError):
            configured_depth = default_depth
        self._depth = max(self._MIN_DEPTH, min(self._MAX_DEPTH, configured_depth))
        self._nodes = 0
        try:
            seconds = float(self.config.get("max_think_time_s", 0))
        except (TypeError, ValueError):
            seconds = 0.0
        self._time_limit_s = seconds if seconds > 0 else None
        self._deadline: float | None = None

    def select_move(self, board: chess.Board) -> chess.Move:
        """Return the legal move with the best alpha-beta score.

        With ``max_think_time_s`` > 0: iterative deepening 1 -> depth, keeping the deepest
        search that finished in time (depth 1 always finishes).
        """
        if self._time_limit_s is None:
            return self._search(board, self._depth)
        started = time.perf_counter()
        best = self._search(board, 1)
        info = dict(self.last_search_info)
        self._deadline = started + self._time_limit_s * 0.9
        try:
            for depth in range(2, self._depth + 1):
                if time.perf_counter() >= self._deadline:
                    break
                best = self._search(board.copy(), depth)
                info = dict(self.last_search_info)
        except _OutOfTime:
            pass
        finally:
            self._deadline = None
        self.last_search_info = info
        return best

    def _search(self, board: chess.Board, search_depth: int) -> chess.Move:
        """Full-width alpha-beta at ``search_depth`` plies."""
        moves = self._ordered_moves(board)
        if not moves:
            raise ValueError("Cannot select a move from a board without legal moves")

        root_color = board.turn
        best_move = moves[0]
        best_score = float("-inf")
        alpha = float("-inf")
        beta = float("inf")
        self._nodes = 0

        for move in moves:
            board.push(move)
            score = self._alpha_beta(
                board,
                search_depth - 1,
                alpha,
                beta,
                root_color,
            )
            board.pop()

            if score > best_score:
                best_score = score
                best_move = move
            alpha = max(alpha, best_score)

        self.last_search_info = {
            "depth": search_depth,
            "nodes": self._nodes,
            "eval": max(-1.0, min(1.0, best_score)),
        }
        return best_move

    def _alpha_beta(
        self,
        board: chess.Board,
        depth: int,
        alpha: float,
        beta: float,
        root_color: chess.Color,
    ) -> float:
        self._nodes += 1
        if self._deadline is not None and self._nodes % 32 == 0:
            if time.perf_counter() > self._deadline:
                raise _OutOfTime
        if depth == 0 or board.is_game_over():
            return evaluate(extract_features(board), root_color)

        moves = self._ordered_moves(board)
        maximizing = board.turn == root_color

        if maximizing:
            value = float("-inf")
            for move in moves:
                board.push(move)
                value = max(
                    value,
                    self._alpha_beta(board, depth - 1, alpha, beta, root_color),
                )
                board.pop()
                alpha = max(alpha, value)
                if alpha >= beta:
                    break
            return value

        value = float("inf")
        for move in moves:
            board.push(move)
            value = min(
                value,
                self._alpha_beta(board, depth - 1, alpha, beta, root_color),
            )
            board.pop()
            beta = min(beta, value)
            if alpha >= beta:
                break
        return value

    def _ordered_moves(self, board: chess.Board) -> list[chess.Move]:
        """Order forcing moves first so alpha-beta can prune more branches."""
        return sorted(
            board.legal_moves,
            key=lambda move: (
                -self._move_order_score(board, move),
                move.uci(),
            ),
        )

    @staticmethod
    def _move_order_score(board: chess.Board, move: chess.Move) -> int:
        """Score captures, promotions, and checks for search ordering."""
        score = 0
        if board.is_capture(move):
            victim = board.piece_at(move.to_square)
            if victim is None and board.is_en_passant(move):
                victim_value = 1
            else:
                victim_value = 0 if victim is None else victim.piece_type
            attacker = board.piece_at(move.from_square)
            attacker_value = 0 if attacker is None else attacker.piece_type
            score += 100 * victim_value - attacker_value
        if move.promotion is not None:
            score += 90
        if board.gives_check(move):
            score += 80
        return score
