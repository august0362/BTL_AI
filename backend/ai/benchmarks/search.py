"""Negamax alpha-beta search with move ordering and an optional transposition table."""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from typing import NamedTuple

import chess
from chess.polyglot import zobrist_hash

from ai.baseline import PIECE_VALUES

Evaluator = Callable[[chess.Board], float]

EXACT = 0
LOWERBOUND = 1
UPPERBOUND = 2

DEFAULT_TT_ENTRIES = 300_000
MAX_QUIESCENCE_PLIES = 8
NULL_MOVE_REDUCTION = 2
LMR_MIN_DEPTH = 3
LMR_FIRST_MOVES = 3
MAX_CHECK_EXTENSIONS = 2
DEADLINE_CHECK_INTERVAL = 1024


class SearchTimeout(Exception):
    """Raised internally when the per-move time budget runs out mid-search."""


class SearchResult(NamedTuple):
    """Best move, its side-to-move score, visited nodes and the depth reached."""

    move: chess.Move | None
    score: float
    nodes: int
    depth: int = 0


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

    def store(
        self,
        key: int,
        depth: int,
        score: float,
        flag: int,
        move: chess.Move | None,
    ) -> None:
        """Store a result, keeping the deepest entry for a position."""
        previous = self._entries.get(key)
        if previous is not None and previous[0] > depth:
            return
        if len(self._entries) >= self.max_entries:
            self._entries.clear()
        self._entries[key] = (depth, score, flag, move)


def move_order_score(
    move: chess.Move,
    board: chess.Board,
    *,
    tt_move: chess.Move | None = None,
    killer: chess.Move | None = None,
) -> int:
    """Return a priority: TT move, captures (MVV-LVA), promotions, killers."""
    score = 0
    if tt_move is not None and move == tt_move:
        score += 1_000_000
    if board.is_capture(move):
        victim = board.piece_at(move.to_square)
        victim_value = (
            PIECE_VALUES[chess.PAWN] if victim is None else PIECE_VALUES[victim.piece_type]
        )
        attacker = board.piece_at(move.from_square)
        attacker_value = 0 if attacker is None else PIECE_VALUES[attacker.piece_type]
        score += 100_000 + victim_value * 8 - attacker_value
    if move.promotion is not None:
        score += 90_000 + PIECE_VALUES[move.promotion]
    if killer is not None and move == killer:
        score += 50_000
    return score


def order_moves(
    board: chess.Board,
    *,
    tt_move: chess.Move | None = None,
    killer: chess.Move | None = None,
) -> list[chess.Move]:
    """Return the legal moves ordered by the move-ordering heuristic."""
    return sorted(
        board.legal_moves,
        key=lambda move: -move_order_score(move, board, tt_move=tt_move, killer=killer),
    )


def alpha_beta(
    board: chess.Board,
    depth: int,
    evaluator: Evaluator,
    *,
    deadline: float | None = None,
) -> SearchResult:
    """Search without a transposition table, visiting moves in generation order."""
    return _root(board, depth, evaluator, tt=None, killers=None, deadline=deadline)


def alpha_beta_tt(
    board: chess.Board,
    depth: int,
    evaluator: Evaluator,
    *,
    tt: TranspositionTable | None = None,
    killers: dict[int, chess.Move] | None = None,
    deadline: float | None = None,
) -> SearchResult:
    """Search with move ordering, killer moves and a transposition table."""
    if tt is None:
        tt = TranspositionTable()
    if killers is None:
        killers = {}
    return _root(board, depth, evaluator, tt=tt, killers=killers, deadline=deadline)


def alpha_beta_iterative(
    board: chess.Board,
    max_depth: int,
    evaluator: Evaluator,
    *,
    tt: TranspositionTable | None = None,
    killers: dict[int, chess.Move] | None = None,
    time_limit_s: float | None = None,
    rng: random.Random | None = None,
    quiescence: bool = False,
    pruning: bool = False,
    extend_checks: bool = False,
) -> SearchResult:
    """Deepen 1..max_depth and stop early once the per-move time budget is spent.

    ``time_limit_s`` is a wall-clock budget in seconds; ``None`` (or <= 0) means
    no limit and the search always reaches ``max_depth``. When the budget runs
    out mid-iteration the partial result is discarded and the best move of the
    last completed depth is returned, so a move is always produced. With ``rng`` the
    root picks randomly among equally scored best moves (integer-valued evaluators).
    With ``quiescence`` leaf nodes keep searching captures until the position is quiet.
    With ``pruning`` interior nodes use null-move pruning and late move reductions.
    With ``extend_checks`` a side in check is searched one ply deeper (bounded).
    """
    limit = None if time_limit_s is None or time_limit_s <= 0 else float(time_limit_s)
    if board.is_game_over():
        return SearchResult(None, evaluator(board), 0, 0)
    deadline = None if limit is None else time.perf_counter() + limit

    best: SearchResult | None = None
    nodes = 0
    for depth in range(1, max(1, int(max_depth)) + 1):
        try:
            result = _root(
                board,
                depth,
                evaluator,
                tt=tt,
                killers=killers,
                deadline=deadline,
                rng=rng,
                quiescence=quiescence,
                pruning=pruning,
                extend_checks=extend_checks,
            )
        except SearchTimeout:
            break
        nodes += result.nodes
        best = SearchResult(result.move, result.score, nodes, depth)
        if deadline is not None and time.perf_counter() >= deadline:
            break
    if best is not None:
        return best
    moves = order_moves(board) if tt is not None else list(board.legal_moves)
    return SearchResult(moves[0] if moves else None, evaluator(board), nodes, 0)


def _root(
    board: chess.Board,
    depth: int,
    evaluator: Evaluator,
    *,
    tt: TranspositionTable | None,
    killers: dict[int, chess.Move] | None,
    deadline: float | None = None,
    rng: random.Random | None = None,
    quiescence: bool = False,
    pruning: bool = False,
    extend_checks: bool = False,
) -> SearchResult:
    counter = _NodeCounter()
    if board.is_game_over():
        return SearchResult(None, evaluator(board), 0, 0)

    tt_move = None
    if tt is not None:
        entry = tt.get(zobrist_hash(board))
        if entry is not None:
            tt_move = entry[3]
    killer = killers.get(board.ply()) if killers is not None else None
    moves = (
        order_moves(board, tt_move=tt_move, killer=killer)
        if tt is not None
        else list(board.legal_moves)
    )

    best_move = None
    best_score = float("-inf")
    alpha = float("-inf")
    # With rng, widen the window by 1 so moves tying the best score get exact values.
    margin = 1.0 if rng is not None else 0.0
    ties: list[chess.Move] = []
    for move in moves:
        board.push(move)
        try:
            score = -_negamax(
                board,
                depth - 1,
                float("-inf"),
                -(alpha - margin),
                evaluator,
                counter,
                tt,
                killers,
                deadline,
                quiescence,
                pruning,
                MAX_CHECK_EXTENSIONS if extend_checks else 0,
            )
        finally:
            board.pop()
        if score > best_score:
            best_move, best_score = move, score
            ties = [move]
        elif score == best_score:
            ties.append(move)
        if score > alpha:
            alpha = score
    if rng is not None and len(ties) > 1:
        best_move = rng.choice(ties)

    if tt is not None:
        tt.store(zobrist_hash(board), depth, best_score, EXACT, best_move)
    return SearchResult(best_move, best_score, counter.value, depth)


def _negamax(
    board: chess.Board,
    depth: int,
    alpha: float,
    beta: float,
    evaluator: Evaluator,
    counter: _NodeCounter,
    tt: TranspositionTable | None,
    killers: dict[int, chess.Move] | None,
    deadline: float | None = None,
    quiescence: bool = False,
    pruning: bool = False,
    extensions: int = 0,
) -> float:
    counter.value += 1
    if (
        deadline is not None
        and counter.value % DEADLINE_CHECK_INTERVAL == 0
        and time.perf_counter() >= deadline
    ):
        raise SearchTimeout
    in_check = board.is_check()
    if in_check and extensions > 0:
        # Check extension: never stop the search while the side to move is in check.
        depth += 1
        extensions -= 1
    if depth <= 0:
        if quiescence:
            return _quiesce(board, alpha, beta, evaluator, counter, deadline, 0)
        return evaluator(board)

    alpha_origin, beta_origin = alpha, beta
    key = None
    tt_move = None
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

    def child(move_depth: int, low: float, high: float) -> float:
        return -_negamax(
            board,
            move_depth,
            -high,
            -low,
            evaluator,
            counter,
            tt,
            killers,
            deadline,
            quiescence,
            pruning,
            extensions,
        )

    if pruning and depth >= LMR_MIN_DEPTH and not in_check and beta < float("inf"):
        # Null move: if passing still beats beta, a real move will too (skip with pawns only).
        own = board.occupied_co[board.turn] & ~board.pawns & ~board.kings
        if own:
            board.push(chess.Move.null())
            try:
                value = child(depth - 1 - NULL_MOVE_REDUCTION, beta - 1, beta)
            finally:
                board.pop()
            if value >= beta:
                return value

    killer = killers.get(board.ply()) if killers is not None else None
    moves = (
        order_moves(board, tt_move=tt_move, killer=killer)
        if tt is not None
        else list(board.legal_moves)
    )
    if not moves:
        return evaluator(board)  # checkmate or stalemate

    best = float("-inf")
    best_move = None
    for index, move in enumerate(moves):
        reduce = (
            pruning
            and depth >= LMR_MIN_DEPTH
            and index >= LMR_FIRST_MOVES
            and not in_check
            and move.promotion is None
            and not board.is_capture(move)
            and not board.gives_check(move)
        )
        board.push(move)
        try:
            if reduce:
                # Late quiet moves are searched one ply shallower; re-search if they surprise.
                value = child(depth - 2, alpha, alpha + 1)
                if value > alpha:
                    value = child(depth - 1, alpha, beta)
            else:
                value = child(depth - 1, alpha, beta)
        finally:
            board.pop()
        if value > best:
            best, best_move = value, move
        if value > alpha:
            alpha = value
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


def _quiesce(
    board: chess.Board,
    alpha: float,
    beta: float,
    evaluator: Evaluator,
    counter: _NodeCounter,
    deadline: float | None,
    ply: int,
) -> float:
    """Search captures only (MVV-LVA order) until the position is quiet."""
    counter.value += 1
    if (
        deadline is not None
        and counter.value % DEADLINE_CHECK_INTERVAL == 0
        and time.perf_counter() >= deadline
    ):
        raise SearchTimeout
    stand_pat = evaluator(board)
    if stand_pat >= beta or ply >= MAX_QUIESCENCE_PLIES:
        return stand_pat
    best = stand_pat
    alpha = max(alpha, stand_pat)
    captures = sorted(
        board.generate_legal_captures(), key=lambda move: -move_order_score(move, board)
    )
    for move in captures:
        board.push(move)
        try:
            score = -_quiesce(board, -beta, -alpha, evaluator, counter, deadline, ply + 1)
        finally:
            board.pop()
        if score > best:
            best = score
        if score > alpha:
            alpha = score
        if alpha >= beta:
            break
    return best


class _NodeCounter:
    """Mutable node counter shared across a recursive search."""

    __slots__ = ("value",)

    def __init__(self) -> None:
        self.value = 0
