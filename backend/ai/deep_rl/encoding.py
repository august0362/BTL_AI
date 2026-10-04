"""Chess board and action encodings for deep RL policies."""

from __future__ import annotations

import chess
import numpy as np

PLANE_COUNT = 18
ACTION_COUNT = 4096
_PIECE_TYPES = (chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN, chess.KING)


def _square(square: chess.Square, turn: chess.Color) -> tuple[int, int]:
    rank = chess.square_rank(square)
    file = chess.square_file(square)
    return (7 - rank if turn == chess.WHITE else rank), file


def encode_board(board: chess.Board) -> np.ndarray:
    """Encode a position as float32 planes from the side-to-move perspective."""
    result = np.zeros((PLANE_COUNT, 8, 8), dtype=np.float32)
    turn = board.turn
    for square, piece in board.piece_map().items():
        row, file = _square(square, turn)
        color_offset = 0 if piece.color == turn else 6
        result[color_offset + _PIECE_TYPES.index(piece.piece_type), row, file] = 1.0
    rights = (
        board.has_kingside_castling_rights(turn),
        board.has_queenside_castling_rights(turn),
        board.has_kingside_castling_rights(not turn),
        board.has_queenside_castling_rights(not turn),
    )
    result[12:16, :, :] = np.asarray(rights, dtype=np.float32)[:, None, None]
    if board.ep_square is not None:
        row, file = _square(board.ep_square, turn)
        result[16, row, file] = 1.0
    result[17, :, :] = min(board.halfmove_clock, 100) / 100.0
    return result


def encode_afterstates(board: chess.Board, moves: list[chess.Move]) -> np.ndarray:
    """Encode each resulting position from the perspective of the player who moved."""
    states = np.empty((len(moves), PLANE_COUNT, 8, 8), dtype=np.float32)
    for index, move in enumerate(moves):
        child = board.copy()
        child.push(move)
        child.turn = not child.turn
        states[index] = encode_board(child)
    return states


def move_to_action(move: chess.Move, turn: chess.Color) -> int:
    """Map a move to its from-square × to-square action (promotion type is omitted)."""
    from_row, from_file = _square(move.from_square, turn)
    to_row, to_file = _square(move.to_square, turn)
    from_index = from_row * 8 + from_file
    to_index = to_row * 8 + to_file
    return from_index * 64 + to_index


def action_to_move(index: int, board: chess.Board) -> chess.Move:
    """Decode an action to a legal move, preferring queen promotion when ambiguous."""
    if not 0 <= index < ACTION_COUNT:
        raise ValueError(f"action index out of range: {index}")
    from_index, to_index = divmod(index, 64)
    from_row, from_file = divmod(from_index, 8)
    to_row, to_file = divmod(to_index, 8)
    from_rank = 7 - from_row if board.turn == chess.WHITE else from_row
    to_rank = 7 - to_row if board.turn == chess.WHITE else to_row
    from_square = chess.square(from_file, from_rank)
    to_square = chess.square(to_file, to_rank)
    candidates = [
        move
        for move in board.legal_moves
        if move.from_square == from_square and move.to_square == to_square
    ]
    if not candidates:
        raise ValueError(f"action {index} does not represent a legal move")
    return next((move for move in candidates if move.promotion == chess.QUEEN), candidates[0])


def legal_action_mask(board: chess.Board) -> np.ndarray:
    """Return a boolean mask with true entries for legal from/to actions."""
    mask = np.zeros(ACTION_COUNT, dtype=np.bool_)
    for move in board.legal_moves:
        mask[move_to_action(move, board.turn)] = True
    return mask
