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


_PIECE_VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 0,
}
_EXACT, _LOWER, _UPPER = 0, 1, 2


class QuiescencePolicy:
    """Alpha-beta có quiescence, sắp xếp nước, bảng chuyển vị và cache kết quả mạng.

    - Điểm một thế (theo bên sắp đi) ``V(s) = max_a Q(s, a) + Φ(s)``; thế kết thúc tính chính xác.
    - Thứ tự nước: nước trong bảng chuyển vị → ăn quân (MVV-LVA) / phong cấp → còn lại theo Q.
    - Ở lá: quiescence chỉ xét nước ăn quân / phong cấp (đang bị chiếu thì xét mọi nước) tới
      ``q_depth`` nửa nước, nên không bỏ dở một chuỗi đổi quân rồi mới chấm điểm.
    - Mạng chạy theo batch cho mọi con của nút sắp xuống lá; mỗi thế chỉ chạy mạng một lần.
    - Iterative deepening 1 → ``depth`` trong ``max_think_time_s`` giây.
    """

    def __init__(
        self,
        model: torch.nn.Module,
        device: str = "cpu",
        depth: int = 3,
        max_think_time_s: float = 1.0,
        potential_scale: float = 0.0,
        q_depth: int = 4,
    ) -> None:
        if depth < 1:
            raise ValueError("depth must be >= 1")
        self.model = model
        self.device = device
        self.depth = depth
        self.max_think_time_s = max_think_time_s
        self.potential_scale = potential_scale
        self.q_depth = q_depth
        self.last_info: dict = {}
        self._deadline = 0.0
        self._nodes = 0
        self._evals: dict = {}
        self._table: dict = {}

    def select_move(self, board: chess.Board) -> chess.Move:
        """Nước tốt nhất của độ sâu sâu nhất đã tìm xong."""
        board = board.copy()
        started = time.perf_counter()
        limit = self.max_think_time_s
        self._deadline = started + limit if limit > 0 else float("inf")
        self._nodes = 0
        self._evals = {}
        _, moves, q = self._evaluate(board)
        order = self._ordered(board, moves, q, None)
        best_move, best_score, depth_done = order[0], float("nan"), 0
        for depth in range(1, self.depth + 1):
            try:
                best_score, best_move = self._root(board, order, depth)
            except _Timeout:
                break
            depth_done = depth
            order = [best_move] + [move for move in order if move != best_move]
        self.last_info = {
            "depth": depth_done,
            "nodes": self._nodes,
            "eval": best_score,
            "time_s": time.perf_counter() - started,
        }
        return best_move

    def _evaluate(self, board: chess.Board) -> tuple[float, list[chess.Move], np.ndarray]:
        key = board._transposition_key()
        cached = self._evals.get(key)
        if cached is None:
            self._evaluate_batch([board])
            cached = self._evals[key]
        return cached

    def _evaluate_batch(self, boards: list[chess.Board]) -> None:
        pending = []
        seen = set()
        for board in boards:
            key = board._transposition_key()
            if key not in self._evals and key not in seen:
                seen.add(key)
                pending.append(board)
        if not pending:
            return
        legal = [legal_actions(board) for board in pending]
        states = torch.as_tensor(np.stack([encode(board) for board in pending]), device=self.device)
        masks = torch.as_tensor(np.stack([action_mask(actions) for _, actions in legal]))
        with torch.no_grad():
            q = masked_q(self.model(states), masks.to(self.device)).cpu().numpy()
        self._nodes += len(pending)
        from ai.deep_rl.user.potential import potential

        for row, board, (moves, actions) in zip(q, pending, legal, strict=True):
            values = row[actions]
            value = float(values.max()) + potential(board, self.potential_scale) if moves else 0.0
            self._evals[board._transposition_key()] = (value, moves, values)

    def _check_time(self) -> None:
        if time.perf_counter() > self._deadline:
            raise _Timeout

    @staticmethod
    def _ordered(
        board: chess.Board, moves: list[chess.Move], q: np.ndarray, first: chess.Move | None
    ) -> list[chess.Move]:
        def key(index: int) -> tuple[int, float]:
            move = moves[index]
            if move == first:
                return (0, 0.0)
            if board.is_capture(move) or move.promotion:
                victim = board.piece_at(move.to_square)
                gain = _PIECE_VALUES[victim.piece_type] if victim else 1
                attacker = board.piece_at(move.from_square)
                cost = _PIECE_VALUES[attacker.piece_type] if attacker else 0
                promo = _PIECE_VALUES.get(move.promotion, 0) if move.promotion else 0
                return (1, -(10 * (gain + promo) - cost))
            return (2, -float(q[index]))

        return [moves[index] for index in sorted(range(len(moves)), key=key)]

    def _children(self, board: chess.Board, order: list[chess.Move]) -> list[chess.Board]:
        children = []
        for move in order:
            board.push(move)
            children.append(board.copy(stack=True))
            board.pop()
        return children

    def _root(self, board: chess.Board, order: list[chess.Move], depth: int):
        alpha, best_move = -float("inf"), order[0]
        if depth == 1:
            self._evaluate_batch(self._children(board, order))
        for move in order:
            self._check_time()
            board.push(move)
            try:
                score = -self._negamax(board, depth - 1, -float("inf"), -alpha, 1)
            finally:
                board.pop()
            if score > alpha:
                alpha, best_move = score, move
        return alpha, best_move

    def _negamax(
        self, board: chess.Board, depth: int, alpha: float, beta: float, ply: int
    ) -> float:
        terminal = AlphaBetaPolicy._terminal(board, ply)
        if terminal is not None:
            return terminal
        if depth <= 0:
            return self._quiesce(board, alpha, beta, ply, 0)
        self._check_time()
        key = board._transposition_key()
        entry = self._table.get(key)
        first = None
        original_alpha = alpha
        if entry is not None:
            entry_depth, entry_score, flag, first = entry
            if entry_depth >= depth:
                if flag == _EXACT:
                    return entry_score
                if flag == _LOWER:
                    alpha = max(alpha, entry_score)
                elif flag == _UPPER:
                    beta = min(beta, entry_score)
                if alpha >= beta:
                    return entry_score
        _, moves, q = self._evaluate(board)
        order = self._ordered(board, moves, q, first)
        if depth == 1:  # mọi con sắp vào quiescence: chạy mạng một lần cho cả nhóm
            self._evaluate_batch(self._children(board, order))
        best, best_move = -float("inf"), order[0]
        for move in order:
            board.push(move)
            try:
                score = -self._negamax(board, depth - 1, -beta, -alpha, ply + 1)
            finally:
                board.pop()
            if score > best:
                best, best_move = score, move
            alpha = max(alpha, score)
            if alpha >= beta:
                break
        flag = _UPPER if best <= original_alpha else _LOWER if best >= beta else _EXACT
        self._table[key] = (depth, best, flag, best_move)
        return best

    def _quiesce(
        self,
        board: chess.Board,
        alpha: float,
        beta: float,
        ply: int,
        qdepth: int,
        anchor: tuple[float, float] | None = None,
    ) -> float:
        """Quiescence nhanh: chạy mạng một lần ở thế đầu chuỗi (``anchor`` = (V, Φ) theo bên
        đi ở thế đó); các thế sau ước lượng bằng V đầu chuỗi + thay đổi của Φ (không chạy mạng).
        Chỉ thế đầu chuỗi mới xét nước thoát chiếu."""
        terminal = AlphaBetaPolicy._terminal(board, ply)
        if terminal is not None:
            return terminal
        from ai.deep_rl.user.potential import potential

        phi = potential(board, self.potential_scale)
        if anchor is None:
            stand = self._evaluate(board)[0]
            anchor = (stand, phi)
        else:
            # cùng bên với đầu chuỗi khi qdepth chẵn; đổi dấu khi khác bên
            base, base_phi = anchor
            same = qdepth % 2 == 0
            value = base + ((phi if same else -phi) - base_phi)
            stand = value if same else -value
        in_check = qdepth == 0 and board.is_check()
        if not in_check:
            if stand >= beta:
                return stand
            alpha = max(alpha, stand)
        if qdepth >= self.q_depth:
            return stand
        self._check_time()
        if in_check:
            moves = list(board.legal_moves)
        else:
            moves = [m for m in board.legal_moves if board.is_capture(m) or m.promotion]
        if not moves:
            return stand
        order = self._ordered(board, moves, np.zeros(len(moves)), None)
        best = stand if not in_check else -float("inf")
        for move in order:
            board.push(move)
            try:
                score = -self._quiesce(board, -beta, -alpha, ply + 1, qdepth + 1, anchor)
            finally:
                board.pop()
            best = max(best, score)
            alpha = max(alpha, score)
            if alpha >= beta:
                break
        return best
