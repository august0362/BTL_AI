"""Small, self-contained heuristics; disabled entirely in Pure MCTS mode."""

from __future__ import annotations

import math

import chess

# Immutable constants, not mutable state shared by bot instances.
PIECE_VALUES = (0, 100, 320, 330, 500, 900, 0)


def positional_score(board: chess.Board) -> float:
    """Return a white-relative material/position score in centipawns."""
    score = 0.0
    material = [0, 0]
    for color in (chess.BLACK, chess.WHITE):
        sign = 1 if color else -1
        for kind in range(chess.PAWN, chess.KING):
            squares = board.pieces(kind, color)
            value = PIECE_VALUES[kind] * len(squares)
            material[color] += value
            score += sign * value
            for square in squares:
                file = chess.square_file(square)
                rank = chess.square_rank(square) if color else 7 - chess.square_rank(square)
                center = 7 - abs(2 * file - 7) - abs(2 * rank - 7)
                if kind == chess.PAWN:
                    bonus = 7 * rank + max(0, center) * 3
                elif kind == chess.KNIGHT:
                    bonus = center * 8
                elif kind == chess.BISHOP:
                    bonus = center * 4
                elif kind == chess.ROOK:
                    bonus = rank * 2
                else:
                    bonus = center
                score += sign * bonus
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
