"""Alpha-beta (negamax) dùng mạng Q làm hàm đánh giá, cho bot khi đấu.

- Giá trị một thế cờ (theo bên sắp đi) là ``V(s) = max_{a hợp lệ} Q(s, a)``.
- Tầng cuối cùng dùng luôn Q: ở nút còn 1 nửa nước, điểm của mỗi nước ``a`` chính là
  ``Q(s, a)``, nên tìm độ sâu 3 chỉ cần chạy mạng ở các nút cách gốc 2 nửa nước. Ở các nút
  cách lá 2 nửa nước, mọi nút con được đưa vào mạng **một lần theo batch**.
- Thế cờ kết thúc tính chính xác: bị chiếu hết = ``-MATE`` (chiếu hết càng sớm càng tốt),
  hòa (hết nước, thiếu quân, lặp 3 lần, luật 50 nước) = 0.
- Iterative deepening 1 → ``depth``; hết ``max_think_time_s`` thì dùng kết quả của độ sâu
  đã xong (độ sâu 1 luôn chạy xong). ``max_think_time_s = 0`` là không giới hạn.
"""

from __future__ import annotations

import time

import chess
import numpy as np
import torch

from ai.deep_rl.user.agent import masked_q
from ai.deep_rl.user.features import action_mask, encode, legal_actions

MATE = 3.0
_PLY_PENALTY = 0.01


class _Timeout(Exception):
    pass


class AlphaBetaPolicy:
    """Chọn nước bằng alpha-beta độ sâu ``depth`` với điểm lá là max Q của mạng."""

    def __init__(
        self,
        model: torch.nn.Module,
        device: str = "cpu",
        depth: int = 3,
        max_think_time_s: float = 1.0,
        potential_scale: float = 0.0,
    ) -> None:
        if depth < 1:
            raise ValueError("depth must be >= 1")
        self.model = model
        self.device = device
        self.depth = depth
        self.max_think_time_s = max_think_time_s
        self.potential_scale = potential_scale
        self.last_info: dict = {}
        self._deadline = 0.0
        self._nodes = 0

    def select_move(self, board: chess.Board) -> chess.Move:
        """Trả về nước tốt nhất của độ sâu sâu nhất đã tìm xong."""
        started = time.perf_counter()
        limit = self.max_think_time_s
        self._deadline = started + limit if limit > 0 else float("inf")
        self._nodes = 0
        moves, q_root = self._q_values([board])[0]
        order = [moves[i] for i in np.argsort(-q_root, kind="stable")]
        best_move, best_score, depth_done = order[0], float(q_root.max()), 1
        for depth in range(2, self.depth + 1):
            try:
                scores = self._root(board, order, depth)
            except _Timeout:
                break
            order = sorted(order, key=lambda move: -scores[move])
            best_move, best_score, depth_done = order[0], scores[order[0]], depth
        self.last_info = {
            "depth": depth_done,
            "nodes": self._nodes,
            "eval": best_score,
            "time_s": time.perf_counter() - started,
        }
        return best_move

    def _q_values(self, boards: list[chess.Board]) -> list[tuple[list[chess.Move], np.ndarray]]:
        """Một lần chạy mạng cho cả batch; trả về (nước hợp lệ, Q của từng nước) mỗi thế."""
        legal = [legal_actions(board) for board in boards]
        states = torch.as_tensor(np.stack([encode(board) for board in boards]), device=self.device)
        masks = torch.as_tensor(np.stack([action_mask(actions) for _, actions in legal]))
        with torch.no_grad():
            q = masked_q(self.model(states), masks.to(self.device)).cpu().numpy()
        self._nodes += len(boards)
        from ai.deep_rl.user.potential import potential

        return [
            (moves, q[i, actions] + potential(board, self.potential_scale))
            for i, (board, (moves, actions)) in enumerate(zip(boards, legal, strict=True))
        ]

    def _check_time(self) -> None:
        if time.perf_counter() > self._deadline:
            raise _Timeout

    @staticmethod
    def _terminal(board: chess.Board, ply: int) -> float | None:
        """Điểm chính xác (theo bên sắp đi) nếu ván đã kết thúc, ngược lại None."""
        if board.is_checkmate():
            return -(MATE - _PLY_PENALTY * ply)
        if (
            board.is_stalemate()
            or board.is_insufficient_material()
            or board.halfmove_clock >= 100
            or board.is_repetition(3)
        ):
            return 0.0
        return None

    def _root(self, board: chess.Board, order: list[chess.Move], depth: int) -> dict:
        scores: dict[chess.Move, float] = {}
        if depth == 2:  # mọi nút con là lá: một batch duy nhất
            self._check_time()
            return dict(zip(order, self._leaf_scores(board, order, 0), strict=True))
        alpha = -float("inf")
        for move in order:
            board.push(move)
            try:
                score = -self._negamax(board, depth - 1, -float("inf"), -alpha, 1)
            finally:
                board.pop()
            scores[move] = score
            alpha = max(alpha, score)
        return scores

    def _negamax(
        self, board: chess.Board, depth: int, alpha: float, beta: float, ply: int
    ) -> float:
        terminal = self._terminal(board, ply)
        if terminal is not None:
            return terminal
        self._check_time()
        if depth == 1:
            return float(self._q_values([board])[0][1].max())
        if depth == 2:
            return self._frontier(board, ply)
        moves, q = self._q_values([board])[0]
        best = -float("inf")
        for index in np.argsort(-q, kind="stable"):
            board.push(moves[index])
            try:
                score = -self._negamax(board, depth - 1, -beta, -alpha, ply + 1)
            finally:
                board.pop()
            best = max(best, score)
            alpha = max(alpha, score)
            if alpha >= beta:
                break
        return best

    def _frontier(self, board: chess.Board, ply: int) -> float:
        """Nút cách lá 2 nửa nước: điểm tốt nhất trong các nút con (đánh giá theo batch)."""
        return max(self._leaf_scores(board, list(board.legal_moves), ply))

    def _leaf_scores(self, board: chess.Board, moves: list[chess.Move], ply: int) -> list[float]:
        """Điểm (theo bên đang đi ở ``board``) của từng nước, nút con chấm bằng ``-max Q``
        trong một lần chạy mạng; nút con kết thúc chấm chính xác."""
        scores: list[float] = [0.0] * len(moves)
        pending: list[tuple[int, chess.Board]] = []
        for index, move in enumerate(moves):
            child = board.copy()
            child.push(move)
            terminal = self._terminal(child, ply + 1)
            if terminal is None:
                pending.append((index, child))
            else:
                scores[index] = -terminal
        if pending:
            values = self._q_values([child for _, child in pending])
            for (index, _), (_, q) in zip(pending, values, strict=True):
                scores[index] = -float(q.max())
        return scores
