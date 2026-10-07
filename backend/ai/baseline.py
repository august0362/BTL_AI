"""Alpha-Beta bot implementation replacing random move selection."""

from __future__ import annotations

import chess

from ai.base_bot import BaseBot

# Bảng giá trị cơ bản của các quân cờ (Material values)
PIECE_VALUES: dict[chess.PieceType, int] = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 20000,
}


def evaluate(board: chess.Board) -> int:
    """Đánh giá thế trận: dương ưu thế cho Trắng, âm ưu thế cho Đen."""
    if board.is_checkmate():
        # Nếu bên nào bị chiếu hết thì thua điểm cực lớn
        return -99999 if board.turn == chess.WHITE else 99999
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    score = 0
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece is not None:
            value = PIECE_VALUES[piece.piece_type]
            score += value if piece.color == chess.WHITE else -value
    return score


class RandomBaselineBot(BaseBot):
    """Select the best legal move using Alpha-Beta pruning."""

    is_baseline = False

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config)
        # Độ sâu tìm kiếm (mặc định là 3 nước nếu không cấu hình)
        self.depth: int = self.config.get("depth", 3)

    def _evaluate(self, board: chess.Board) -> int:
        """Backward-compatible wrapper around the module-level evaluation."""
        return evaluate(board)

    def _alphabeta(
        self,
        board: chess.Board,
        depth: int,
        alpha: float,
        beta: float,
        maximizing_player: bool,
    ) -> float:
        """Thuật toán Minimax kết hợp cắt tỉa Alpha-Beta."""
        if depth == 0 or board.is_game_over():
            return float(self._evaluate(board))

        if maximizing_player:
            max_eval = float("-inf")
            for move in board.legal_moves:
                board.push(move)
                eval_score = self._alphabeta(board, depth - 1, alpha, beta, False)
                board.pop()
                max_eval = max(max_eval, eval_score)
                alpha = max(alpha, eval_score)
                if beta <= alpha:
                    break  # Cắt tỉa nhánh beta
            return max_eval
        else:
            min_eval = float("inf")
            for move in board.legal_moves:
                board.push(move)
                eval_score = self._alphabeta(board, depth - 1, alpha, beta, True)
                board.pop()
                min_eval = min(min_eval, eval_score)
                beta = min(beta, eval_score)
                if beta <= alpha:
                    break  # Cắt tỉa nhánh alpha
            return min_eval

    def select_move(self, board: chess.Board) -> chess.Move:
        """Thay vì chọn ngẫu nhiên, tìm nước đi tối ưu nhất theo Alpha-Beta."""
        best_move: chess.Move | None = None
        is_white = board.turn == chess.WHITE

        if is_white:
            best_val = float("-inf")
            alpha = float("-inf")
            beta = float("inf")
            for move in board.legal_moves:
                board.push(move)
                val = self._alphabeta(board, self.depth - 1, alpha, beta, False)
                board.pop()
                if val > best_val:
                    best_val = val
                    best_move = move
                alpha = max(alpha, val)
        else:
            best_val = float("inf")
            alpha = float("-inf")
            beta = float("inf")
            for move in board.legal_moves:
                board.push(move)
                val = self._alphabeta(board, self.depth - 1, alpha, beta, True)
                board.pop()
                if val < best_val:
                    best_val = val
                    best_move = move
                beta = min(beta, val)

        self.last_search_info = {"eval": best_val, "depth": self.depth}
        # Nếu vì lý do nào đó không tìm được (chỉ còn 1 nước), bốc nước đầu tiên
        return best_move if best_move is not None else next(iter(board.legal_moves))
