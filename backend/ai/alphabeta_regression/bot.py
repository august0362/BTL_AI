"""Alpha-beta chess bot with a material-based linear-regression evaluator."""

import chess

from ai.base_bot import BaseBot


class AlphaBetaRegressionBot(BaseBot):
    """Select moves with alpha-beta search and a material-based evaluator."""

    bot_id = "alphabeta_regression"
    display_name = "Alpha-Beta Regression"

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config)
        default_depth = 3 if self.config.get("fast_mode") else 2
        self._depth = max(1, int(self.config.get("depth", default_depth)))
        self._nodes = 0

    def select_move(self, board: chess.Board) -> chess.Move:
        """Return the legal move with the best alpha-beta score."""
        moves = sorted(board.legal_moves, key=lambda move: move.uci())
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
                self._depth - 1,
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
            "depth": self._depth,
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
        if depth == 0 or board.is_game_over():
            return self._evaluate(board, root_color)

        moves = sorted(board.legal_moves, key=lambda move: move.uci())
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

    def _evaluate(self, board: chess.Board, root_color: chess.Color) -> float:
        if board.is_checkmate():
            return float("inf") if board.turn != root_color else float("-inf")
        if board.is_game_over():
            return 0.0
        score = self.linear_regression(board)
        return score if root_color == chess.WHITE else -score

    def linear_regression(self, board: chess.Board) -> float:
        """Return the material score from White's point of view."""
        piece_values = {
            chess.PAWN: 10,
            chess.KNIGHT: 30,
            chess.BISHOP: 30,
            chess.ROOK: 50,
            chess.QUEEN: 90,
            chess.KING: 900,
        }
        score = 0
        for piece_type, value in piece_values.items():
            score += len(board.pieces(piece_type, chess.WHITE)) * value
            score -= len(board.pieces(piece_type, chess.BLACK)) * value
        return float(score)
