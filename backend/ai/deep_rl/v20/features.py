"""19-plane board encoder from the side to move's point of view.

Planes 0-5 contain own pieces, 6-11 opponent pieces, 12-13 repetitions,
14-17 castling rights, and 18 the legal en-passant target. Black mirrors ranks.
Packed bitboards unpack to exactly the same planes; boards must retain history.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import chess
import numpy as np

if TYPE_CHECKING:
    import torch

PLANES = 19
EP_PLANE = 18
_PIECES = (chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN, chess.KING)
_FULL = 0xFFFF_FFFF_FFFF_FFFF


def encode(board: chess.Board) -> np.ndarray:
    """Return a ``uint8 (19, 8, 8)`` observation for the side to move."""
    turn = board.turn
    masks = [board.pieces_mask(piece, turn) for piece in _PIECES]
    masks += [board.pieces_mask(piece, not turn) for piece in _PIECES]
    ep = 0
    if board.ep_square is not None and board.has_legal_en_passant():
        ep = chess.BB_SQUARES[board.ep_square]
    masks.append(ep)
    if turn == chess.BLACK:
        masks = [chess.flip_vertical(mask) for mask in masks]
    ep = masks.pop()
    flags = (
        board.is_repetition(2),
        board.is_repetition(3),
        board.has_kingside_castling_rights(turn),
        board.has_queenside_castling_rights(turn),
        board.has_kingside_castling_rights(not turn),
        board.has_queenside_castling_rights(not turn),
    )
    masks += [_FULL if flag else 0 for flag in flags]
    masks.append(ep)
    raw = np.array(masks, dtype="<u8").view(np.uint8)
    return np.unpackbits(raw, bitorder="little").reshape(PLANES, 8, 8)


def encode_masks(board: chess.Board) -> tuple[int, ...]:
    """Return the 19 bitboards that ``encode`` unpacks, in the same order."""
    turn = board.turn
    masks = [board.pieces_mask(piece, turn) for piece in _PIECES]
    masks += [board.pieces_mask(piece, not turn) for piece in _PIECES]
    ep = 0
    if board.ep_square is not None and board.has_legal_en_passant():
        ep = chess.BB_SQUARES[board.ep_square]
    masks.append(ep)
    if turn == chess.BLACK:
        masks = [chess.flip_vertical(mask) for mask in masks]
    ep = masks.pop()
    flags = (
        board.is_repetition(2),
        board.is_repetition(3),
        board.has_kingside_castling_rights(turn),
        board.has_queenside_castling_rights(turn),
        board.has_kingside_castling_rights(not turn),
        board.has_queenside_castling_rights(not turn),
    )
    masks += [_FULL if flag else 0 for flag in flags]
    masks.append(ep)
    return tuple(masks)


def unpack(masks: np.ndarray) -> np.ndarray:
    """Expand ``(N, 19)`` uint64 bitboards to ``(N, 19, 8, 8)`` uint8 planes."""
    raw = np.ascontiguousarray(masks, dtype="<u8").view(np.uint8)
    return np.unpackbits(raw, axis=-1, bitorder="little").reshape(len(masks), PLANES, 8, 8)


def unpack_torch(masks: torch.Tensor) -> torch.Tensor:
    """Expand int64 bit patterns to float32 planes on the same device."""
    import torch

    shifts = torch.arange(64, dtype=torch.int64).to(masks.device)
    bits = (masks.unsqueeze(-1) >> shifts) & 1
    return bits.reshape(masks.shape[0], PLANES, 8, 8).float()
