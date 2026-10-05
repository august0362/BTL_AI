"""Negamax alpha-beta search over the GA-evolved evaluation."""

from __future__ import annotations

import random

import chess

from ai.genetic_alphabeta.evaluation import evaluate
from ai.genetic_alphabeta.genome import Genome

MATE_SCORE = 100000.0
TIE_EPS = 1e-9


def _static(board: chess.Board, genome: Genome) -> float:
    """Static score from the side-to-move's perspective."""
    score = evaluate(board, genome)
    return score if board.turn == chess.WHITE else -score


def _terminal(board: chess.Board, ply: int) -> float | None:
    """Terminal score from the side-to-move's view, or None if not terminal."""
    if board.is_checkmate():
        return -MATE_SCORE + ply
    if (
        board.is_stalemate()
        or board.is_insufficient_material()
        or board.is_seventyfive_moves()
        or board.is_fivefold_repetition()
        or board.can_claim_draw()
    ):
        return 0.0
    return None


def _move_order_key(board: chess.Board, move: chess.Move, genome: Genome) -> tuple:
    """Order key: captures (MVV-LVA) and promotions first, then stable UCI."""
    score = 0.0
    if board.is_capture(move):
        if board.is_en_passant(move):
            victim = genome.pawn
        else:
            captured = board.piece_at(move.to_square)
            victim = genome.piece_value(captured.piece_type) if captured else 0.0
        attacker = board.piece_at(move.from_square)
        attacker_value = genome.piece_value(attacker.piece_type) if attacker else 0.0
        score += 10.0 * victim - attacker_value / 16.0
    if move.promotion:
        score += 10.0 * genome.piece_value(move.promotion)
    return (-score, move.uci())


def ordered_moves(board: chess.Board, genome: Genome) -> list[chess.Move]:
    """Legal moves sorted for good alpha-beta cutoffs (deterministic)."""
    return sorted(board.legal_moves, key=lambda move: _move_order_key(board, move, genome))


def _negamax(
    board: chess.Board,
    genome: Genome,
    depth: int,
    alpha: float,
    beta: float,
    ply: int,
    stats: dict[str, int],
) -> float:
    """Depth-limited negamax; always leaves `board` unchanged."""
    stats["nodes"] += 1
    terminal = _terminal(board, ply)
    if terminal is not None:
        return terminal
    if depth <= 0:
        return _static(board, genome)
    best = -MATE_SCORE - ply
    for move in ordered_moves(board, genome):
        board.push(move)
        try:
            score = -_negamax(board, genome, depth - 1, -beta, -alpha, ply + 1, stats)
        finally:
            board.pop()
        if score > best:
            best = score
        if best > alpha:
            alpha = best
        if alpha >= beta:
            break
    return best


def best_move(
    board: chess.Board,
    genome: Genome,
    depth: int,
    rng: random.Random | None = None,
) -> tuple[chess.Move, int, float]:
    """Search `depth` plies; return (move, nodes, side-to-move score).

    The board is left unchanged. Equal-best moves (within TIE_EPS) are picked
    with `rng` when given, otherwise the first in ordered (UCI-stable) order.
    """
    moves = ordered_moves(board, genome)
    if not moves:
        raise ValueError("No legal moves: the position is already over")
    search_depth = max(1, depth)
    stats: dict[str, int] = {"nodes": 0}
    candidates: list[chess.Move] = []
    best_score = -MATE_SCORE - 1.0
    for move in moves:
        board.push(move)
        try:
            score = -_negamax(
                board, genome, search_depth - 1, -MATE_SCORE - 1.0, MATE_SCORE + 1.0, 1, stats
            )
        finally:
            board.pop()
        if score > best_score + TIE_EPS:
            best_score = score
            candidates = [move]
        elif abs(score - best_score) <= TIE_EPS:
            candidates.append(move)
    chosen = rng.choice(candidates) if rng is not None else candidates[0]
    return chosen, stats["nodes"], best_score
