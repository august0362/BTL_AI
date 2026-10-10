"""Mã hóa bàn cờ 18 plane và không gian 4672 nước đi, luôn nhìn từ phía bên sắp đi.

Bàn cờ được lật dọc khi Đen đi (canonical view), nên một mạng học được cho cả hai màu.

Plane (8 × 8, giá trị 0/1):
    0–5    quân mình: Tốt, Mã, Tượng, Xe, Hậu, Vua
    6–11   quân đối thủ, cùng thứ tự
    12     thế cờ hiện tại đã xuất hiện ít nhất 1 lần trước đó
    13     thế cờ hiện tại đã xuất hiện ít nhất 2 lần trước đó
    14–17  quyền nhập thành: mình cánh vua, mình cánh hậu, đối thủ cánh vua, đối thủ cánh hậu

Nước đi (kiểu AlphaZero): ``action = ô_đi × 73 + kiểu``, với 73 kiểu = 56 nước kiểu Hậu
(8 hướng × 1–7 ô, gồm cả phong Hậu) + 8 nước Mã + 9 phong cấp thấp (3 hướng × Mã/Tượng/Xe).
"""

from __future__ import annotations

import chess
import numpy as np

PLANES = 18
MOVE_TYPES = 73
ACTIONS = 64 * MOVE_TYPES  # 4672

_PIECE_TYPES = (chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN, chess.KING)
_FULL = 0xFFFF_FFFF_FFFF_FFFF
# (cột, hàng) theo góc nhìn của bên đi.
_QUEEN_DIRECTIONS = {
    (0, 1): 0,
    (1, 1): 1,
    (1, 0): 2,
    (1, -1): 3,
    (0, -1): 4,
    (-1, -1): 5,
    (-1, 0): 6,
    (-1, 1): 7,
}
_KNIGHT_JUMPS = {
    (1, 2): 0,
    (2, 1): 1,
    (2, -1): 2,
    (1, -2): 3,
    (-1, -2): 4,
    (-2, -1): 5,
    (-2, 1): 6,
    (-1, 2): 7,
}
_UNDERPROMOTIONS = {chess.KNIGHT: 0, chess.BISHOP: 1, chess.ROOK: 2}


def _sign(value: int) -> int:
    return (value > 0) - (value < 0)


def encode(board: chess.Board) -> np.ndarray:
    """Trả về mảng ``uint8 (18, 8, 8)`` của thế cờ, nhìn từ phía bên sắp đi."""
    turn = board.turn
    masks = [board.pieces_mask(piece, turn) for piece in _PIECE_TYPES]
    masks += [board.pieces_mask(piece, not turn) for piece in _PIECE_TYPES]
    if turn == chess.BLACK:
        masks = [chess.flip_vertical(mask) for mask in masks]
    flags = (
        board.is_repetition(2),
        board.is_repetition(3),
        board.has_kingside_castling_rights(turn),
        board.has_queenside_castling_rights(turn),
        board.has_kingside_castling_rights(not turn),
        board.has_queenside_castling_rights(not turn),
    )
    masks += [_FULL if flag else 0 for flag in flags]
    raw = np.array(masks, dtype="<u8").view(np.uint8)
    return np.unpackbits(raw, bitorder="little").reshape(PLANES, 8, 8)


def move_to_action(move: chess.Move, turn: chess.Color) -> int:
    """Đổi một nước đi của bên ``turn`` thành chỉ số trong ``[0, 4672)``."""
    from_square, to_square = move.from_square, move.to_square
    if turn == chess.BLACK:
        from_square, to_square = from_square ^ 56, to_square ^ 56
    dx = chess.square_file(to_square) - chess.square_file(from_square)
    dy = chess.square_rank(to_square) - chess.square_rank(from_square)
    if move.promotion is not None and move.promotion != chess.QUEEN:
        move_type = 64 + (dx + 1) * 3 + _UNDERPROMOTIONS[move.promotion]
    elif (dx, dy) in _KNIGHT_JUMPS:
        move_type = 56 + _KNIGHT_JUMPS[(dx, dy)]
    else:
        distance = max(abs(dx), abs(dy))
        move_type = _QUEEN_DIRECTIONS[(_sign(dx), _sign(dy))] * 7 + distance - 1
    return from_square * MOVE_TYPES + move_type


def legal_actions(board: chess.Board) -> tuple[list[chess.Move], np.ndarray]:
    """Trả về các nước hợp lệ và chỉ số hành động tương ứng (cùng thứ tự)."""
    moves = list(board.legal_moves)
    actions = np.fromiter(
        (move_to_action(move, board.turn) for move in moves), dtype=np.int64, count=len(moves)
    )
    return moves, actions


def action_mask(actions: np.ndarray) -> np.ndarray:
    """Mặt nạ ``bool (4672,)``: True ở các hành động hợp lệ."""
    mask = np.zeros(ACTIONS, dtype=np.bool_)
    mask[actions] = True
    return mask
