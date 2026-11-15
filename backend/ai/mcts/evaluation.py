"""Small, self-contained heuristics; disabled entirely in Pure MCTS mode."""

from __future__ import annotations

import math

import chess

# Immutable constants, not mutable state shared by bot instances.
PIECE_VALUES = (0, 100, 320, 330, 500, 900, 0)


def _bonus(kind: int, square: int, endgame: bool) -> int:
    file, rank = chess.square_file(square), chess.square_rank(square)
    center = 7 - abs(2 * file - 7) - abs(2 * rank - 7)
    if kind == chess.PAWN:
        return (12 if endgame else 4) * rank + 3 * max(0, center)
    if kind == chess.KNIGHT:
        return 8 * center
    if kind == chess.BISHOP:
        return 4 * center
    if kind == chess.ROOK:
        return 2 * rank
    if kind == chess.QUEEN:
        return center
    return 10 * center if endgame else -20 * rank - 8 * center


_MIDDLE = tuple(
    tuple(PIECE_VALUES[kind] + _bonus(kind, square, False) for square in chess.SQUARES)
    for kind in range(7)
)
_ENDING = tuple(
    tuple(PIECE_VALUES[kind] + _bonus(kind, square, True) for square in chess.SQUARES)
    for kind in range(7)
)


def positional_score(board: chess.Board) -> float:
    """Return a white-relative material/position score in centipawns."""
    middle = ending = phase = 0
    material = [0, 0]
    for color in (chess.BLACK, chess.WHITE):
        sign = 1 if color else -1
        for kind in range(chess.PAWN, chess.KING + 1):
            mask = board.pieces_mask(kind, color)
            value = PIECE_VALUES[kind] * mask.bit_count()
            material[color] += value
            phase += (0, 0, 1, 1, 2, 4, 0)[kind] * mask.bit_count()
            while mask:
                low = mask & -mask
                square = low.bit_length() - 1
                index = square if color else square ^ 56
                middle += sign * _MIDDLE[kind][index]
                ending += sign * _ENDING[kind][index]
                mask ^= low
    phase = min(24, phase)
    score = (middle * phase + ending * (24 - phase)) / 24
    # Encourage mating a bare king. This is an estimate, never a declared win.
    for color in (chess.BLACK, chess.WHITE):
        if material[color] >= 500 and material[not color] == 0:
            ours, theirs = board.king(color), board.king(not color)
            if ours is not None and theirs is not None:
                file, rank = chess.square_file(theirs), chess.square_rank(theirs)
                edge = 3 - min(file, 7 - file, rank, 7 - rank)
                bonus = 30 * edge + 20 * (7 - chess.square_distance(ours, theirs))
                score += bonus if color else -bonus
    return score


def estimated_white_reward(board: chess.Board) -> float:
    """Map a nonterminal estimate to (0.05, 0.95), reserving 0/1 for real outcomes."""
    return 0.5 + 0.45 * math.tanh(positional_score(board) / 1200.0)


def score_to_reward(score: float) -> float:
    """Convert a leaf estimate to a reward; reserve exact 0/1 for real outcomes."""
    return 0.5 + 0.45 * score / (400 + abs(score))


def move_priority(board: chess.Board, move: chess.Move) -> float:
    """Prioritize promotions, captures and central development in assisted rollouts."""
    priority = 0.0
    attacker = board.piece_type_at(move.from_square) or chess.PAWN
    victim = board.piece_type_at(move.to_square)
    if board.is_en_passant(move):
        victim = chess.PAWN
    if victim is not None:
        priority += 10 * PIECE_VALUES[victim] - PIECE_VALUES[attacker]
    if move.promotion:
        priority += 10 * (PIECE_VALUES[move.promotion] - PIECE_VALUES[chess.PAWN])
    file, rank = chess.square_file(move.to_square), chess.square_rank(move.to_square)
    priority += 7 - abs(2 * file - 7) - abs(2 * rank - 7)
    return priority
