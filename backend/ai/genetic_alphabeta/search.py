"""Negamax alpha-beta search over the GA-evolved evaluation."""

from __future__ import annotations

import random
import time

import chess
from chess.polyglot import zobrist_hash

from ai.genetic_alphabeta.evaluation import evaluate
from ai.genetic_alphabeta.genome import Genome

MATE_SCORE = 100000.0
TIE_EPS = 1e-9
ROOT_TIE_MARGIN = 1e-6
MAX_QUIESCENCE_PLIES = 8
MAX_CHECK_EXTENSIONS = 2
DEFAULT_TT_ENTRIES = 65536
DEADLINE_CHECK_INTERVAL = 1024

EXACT = 0
LOWERBOUND = 1
UPPERBOUND = 2


class SearchTimeout(Exception):
    """Raised internally when the per-move time budget runs out mid-search."""


class TranspositionTable:
    """Zobrist-keyed cache of alpha-beta results with bound flags."""

    def __init__(self, max_entries: int = DEFAULT_TT_ENTRIES) -> None:
        self.max_entries = max_entries
        self._entries: dict[int, tuple[int, float, int, chess.Move | None]] = {}

    def clear(self) -> None:
        """Forget every cached position."""
        self._entries.clear()

    def get(self, key: int) -> tuple[int, float, int, chess.Move | None] | None:
        """Return the cached ``(depth, score, flag, move)`` for a position."""
        return self._entries.get(key)

    def store(self, key: int, depth: int, score: float, flag: int, move: chess.Move | None) -> None:
        """Store a result, keeping the deepest entry for a position."""
        previous = self._entries.get(key)
        if previous is not None and previous[0] > depth:
            return
        if len(self._entries) >= self.max_entries:
            self._entries.clear()
        self._entries[key] = (depth, score, flag, move)


def _static(board: chess.Board, genome: Genome) -> float:
    """Static score from the side-to-move's perspective."""
    score = evaluate(board, genome)
    return score if board.turn == chess.WHITE else -score


def _check_deadline(stats: dict[str, int], deadline: float | None) -> None:
    """Raise SearchTimeout when the time budget is spent (checked periodically)."""
    if (
        deadline is not None
        and stats["nodes"] % DEADLINE_CHECK_INTERVAL == 0
        and time.perf_counter() >= deadline
    ):
        raise SearchTimeout


def _move_order_key(
    board: chess.Board,
    move: chess.Move,
    genome: Genome,
    tt_move: chess.Move | None = None,
    killer: chess.Move | None = None,
) -> tuple:
    """Order key: TT move and killers first, then captures (MVV-LVA), promotions."""
    score = 0.0
    if tt_move is not None and move == tt_move:
        score += 1_000_000.0
    if killer is not None and move == killer:
        score += 500_000.0
    if board.is_capture(move):
        if board.is_en_passant(move):
            victim = genome.pawn
        else:
            captured = board.piece_type_at(move.to_square)
            victim = genome.piece_value(captured) if captured else 0.0
        attacker = board.piece_type_at(move.from_square)
        attacker_value = genome.piece_value(attacker) if attacker else 0.0
        score += 100_000.0 + 10.0 * victim - attacker_value / 16.0
    if move.promotion:
        score += 90_000.0 + 10.0 * genome.piece_value(move.promotion)
    return (-score, move.uci())


def ordered_moves(
    board: chess.Board,
    genome: Genome,
    tt_move: chess.Move | None = None,
    killer: chess.Move | None = None,
) -> list[chess.Move]:
    """Legal moves sorted for good alpha-beta cutoffs (deterministic)."""
    return sorted(
        board.legal_moves,
        key=lambda move: _move_order_key(board, move, genome, tt_move, killer),
    )


def _quiesce(
    board: chess.Board,
    genome: Genome,
    alpha: float,
    beta: float,
    ply: int,
    stats: dict[str, int],
    deadline: float | None,
) -> float:
    """Finish captures (and all evasions while in check) past the depth limit."""
    stats["nodes"] += 1
    _check_deadline(stats, deadline)
    if board.is_check():
        evasions = list(board.legal_moves)
        if not evasions:
            return -MATE_SCORE + ply
        if ply >= MAX_QUIESCENCE_PLIES + 2:
            return _static(board, genome)
        best = -MATE_SCORE - ply
        for move in evasions:
            board.push(move)
            try:
                score = -_quiesce(board, genome, -beta, -alpha, ply + 1, stats, deadline)
            finally:
                board.pop()
            if score > best:
                best = score
            if best > alpha:
                alpha = best
            if alpha >= beta:
                break
        return best
    stand_pat = _static(board, genome)
    if ply >= MAX_QUIESCENCE_PLIES:
        if not any(board.generate_legal_moves()):
            return 0.0
        return stand_pat
    # Generate captures once; stalemate is only possible when there are none.
    captures = sorted(
        board.generate_legal_captures(),
        key=lambda move: _move_order_key(board, move, genome),
    )
    if not captures and not any(board.generate_legal_moves()):
        return 0.0
    if stand_pat >= beta:
        return stand_pat
    best = stand_pat
    if stand_pat > alpha:
        alpha = stand_pat
    for move in captures:
        # Delta pruning: a capture whose victim cannot recover alpha is hopeless.
        if move.promotion is None:
            if board.is_en_passant(move):
                victim_value = genome.pawn
            else:
                captured = board.piece_type_at(move.to_square)
                victim_value = genome.piece_value(captured) if captured else 0.0
            if stand_pat + victim_value + 1.0 <= alpha:
                continue
        board.push(move)
        try:
            score = -_quiesce(board, genome, -beta, -alpha, ply + 1, stats, deadline)
        finally:
            board.pop()
        if score > best:
            best = score
        if score > alpha:
            alpha = score
        if alpha >= beta:
            break
    return best


def _negamax(
    board: chess.Board,
    genome: Genome,
    depth: int,
    alpha: float,
    beta: float,
    ply: int,
    stats: dict[str, int],
    tt: TranspositionTable | None = None,
    killers: dict[int, chess.Move] | None = None,
    quiescence: bool = True,
    deadline: float | None = None,
    extensions: int = MAX_CHECK_EXTENSIONS,
) -> float:
    """Depth-limited negamax; always leaves `board` unchanged."""
    stats["nodes"] += 1
    _check_deadline(stats, deadline)
    if board.is_insufficient_material() or board.halfmove_clock >= 100:
        return 0.0
    if board.halfmove_clock >= 4 and board.is_repetition(3):
        return 0.0
    if board.is_check() and extensions > 0 and depth > 0:
        depth += 1
        extensions -= 1
    if depth <= 0:
        if quiescence:
            return _quiesce(board, genome, alpha, beta, ply, stats, deadline)
        if not any(board.generate_legal_moves()):
            return (-MATE_SCORE + ply) if board.is_check() else 0.0
        return _static(board, genome)

    alpha_origin, beta_origin = alpha, beta
    key: int | None = None
    tt_move: chess.Move | None = None
    if tt is not None:
        key = zobrist_hash(board)
        entry = tt.get(key)
        if entry is not None:
            entry_depth, entry_score, entry_flag, entry_move = entry
            tt_move = entry_move
            if entry_depth >= depth:
                if entry_flag == EXACT:
                    return entry_score
                if entry_flag == LOWERBOUND:
                    alpha = max(alpha, entry_score)
                else:
                    beta = min(beta, entry_score)
                if alpha >= beta:
                    return entry_score

    killer = killers.get(board.ply()) if killers is not None else None
    moves = ordered_moves(board, genome, tt_move, killer)
    if not moves:
        return (-MATE_SCORE + ply) if board.is_check() else 0.0

    best = -MATE_SCORE - ply
    best_move = None
    for move in moves:
        board.push(move)
        try:
            score = -_negamax(
                board,
                genome,
                depth - 1,
                -beta,
                -alpha,
                ply + 1,
                stats,
                tt,
                killers,
                quiescence,
                deadline,
                extensions,
            )
        finally:
            board.pop()
        if score > best:
            best = score
            best_move = move
        if best > alpha:
            alpha = best
        if alpha >= beta:
            if killers is not None and not board.is_capture(move):
                killers[board.ply()] = move
            break

    if tt is not None and key is not None:
        if best <= alpha_origin:
            flag = UPPERBOUND
        elif best >= beta_origin:
            flag = LOWERBOUND
        else:
            flag = EXACT
        tt.store(key, depth, best, flag, best_move)
    return best


def _root(
    board: chess.Board,
    genome: Genome,
    depth: int,
    rng: random.Random | None,
    stats: dict[str, int],
    tt: TranspositionTable | None = None,
    killers: dict[int, chess.Move] | None = None,
    quiescence: bool = True,
    deadline: float | None = None,
) -> tuple[chess.Move, float]:
    """Search every root move; return (best move, side-to-move score).

    The root narrows alpha as the best score improves, but keeps a tiny
    ``ROOT_TIE_MARGIN`` slack so moves tying the best still get exact scores and
    can be collected for random tie-breaking.
    """
    tt_move: chess.Move | None = None
    if tt is not None:
        entry = tt.get(zobrist_hash(board))
        if entry is not None:
            tt_move = entry[3]
    killer = killers.get(board.ply()) if killers is not None else None
    moves = ordered_moves(board, genome, tt_move, killer)
    candidates: list[chess.Move] = []
    best_score = -MATE_SCORE - 1.0
    alpha = -MATE_SCORE - 1.0
    for move in moves:
        board.push(move)
        try:
            score = -_negamax(
                board,
                genome,
                depth - 1,
                -MATE_SCORE - 1.0,
                -(alpha - ROOT_TIE_MARGIN),
                1,
                stats,
                tt,
                killers,
                quiescence,
                deadline,
                MAX_CHECK_EXTENSIONS,
            )
        finally:
            board.pop()
        if score > best_score + TIE_EPS:
            best_score = score
            candidates = [move]
        elif abs(score - best_score) <= TIE_EPS:
            candidates.append(move)
        if score > alpha:
            alpha = score
    chosen = rng.choice(candidates) if rng is not None else candidates[0]
    if tt is not None:
        tt.store(zobrist_hash(board), depth, best_score, EXACT, chosen)
    return chosen, best_score


def search_iterative(
    board: chess.Board,
    genome: Genome,
    max_depth: int,
    rng: random.Random | None = None,
    tt: TranspositionTable | None = None,
    killers: dict[int, chess.Move] | None = None,
    time_limit_s: float | None = None,
    quiescence: bool = True,
) -> tuple[chess.Move, int, float, int]:
    """Deepen 1..max_depth; on timeout keep the last completed depth.

    `time_limit_s` None (or <= 0) means no limit: the search reaches max_depth.
    Returns (move, nodes, side-to-move score, depth reached). The board is left
    unchanged.
    """
    moves = ordered_moves(board, genome)
    if not moves:
        raise ValueError("No legal moves: the position is already over")
    target = max(1, max_depth)
    limit = None if time_limit_s is None or time_limit_s <= 0 else float(time_limit_s)
    deadline = None if limit is None else time.perf_counter() + limit
    stats: dict[str, int] = {"nodes": 0}
    best_move, best_score, reached = moves[0], 0.0, 0
    try:
        for depth in range(1, target + 1):
            move, score = _root(board, genome, depth, rng, stats, tt, killers, quiescence, deadline)
            best_move, best_score, reached = move, score, depth
            if deadline is not None and time.perf_counter() >= deadline:
                break
    except SearchTimeout:
        pass
    if reached == 0:
        # Timeout struck during depth 1: finish it without a deadline instead of
        # returning an unsearched move.
        move, score = _root(board, genome, 1, rng, stats, tt, killers, quiescence, None)
        best_move, best_score, reached = move, score, 1
    return best_move, stats["nodes"], best_score, reached


def best_move(
    board: chess.Board,
    genome: Genome,
    depth: int,
    rng: random.Random | None = None,
    tt: TranspositionTable | None = None,
    killers: dict[int, chess.Move] | None = None,
    time_limit_s: float | None = None,
    quiescence: bool = True,
) -> tuple[chess.Move, int, float]:
    """Search `depth` plies; return (move, nodes, side-to-move score).

    The board is left unchanged. Equal-best moves (within TIE_EPS) are picked
    with `rng` when given, otherwise the first in ordered (UCI-stable) order.
    """
    moves = ordered_moves(board, genome)
    if not moves:
        raise ValueError("No legal moves: the position is already over")
    search_depth = max(1, depth)
    limit = None if time_limit_s is None or time_limit_s <= 0 else float(time_limit_s)
    if limit is not None:
        move, nodes, score, _ = search_iterative(
            board, genome, search_depth, rng, tt, killers, limit, quiescence
        )
        return move, nodes, score
    stats: dict[str, int] = {"nodes": 0}
    move, score = _root(board, genome, search_depth, rng, stats, tt, killers, quiescence, None)
    return move, stats["nodes"], score
