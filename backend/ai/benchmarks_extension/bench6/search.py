"""Selective PVS engine behind Benchmarks 6 and 7.

A superset of the Benchmark 5 engine: incremental material/PST, a list-based bucketed
transposition table with generations, capture/continuation history, an "improving" signal,
logarithmic LMR, RFP, razoring, futility, LMP, history pruning, ProbCut, multi-cut, singular
extensions, IID/IIR, correction history, a hand-written opening book and several time
policies. Every technique is configured by :class:`SearchConfig6`; nothing is global.
"""

from __future__ import annotations

import gc
import math
import random
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import NamedTuple

import chess

from ai.benchmarks_extension.bench6.evaluation import Evaluator6

MATE = 100_000
MATE_BOUND = MATE - 1_000
INF = 1_000_000
MAX_PLY = 128
EXACT, LOWER, UPPER = 0, 1, 2
VALUES = (0, 100, 320, 330, 500, 900, 20_000)
HISTORY_MAX = 16_384
PIECE_SLOTS = 14 * 64  # (colour * 7 + piece type) * 64 + to-square
_NULL_MOVE = chess.Move.null()


class SearchTimeout(Exception):
    """Raised inside the search when the hard time limit is reached."""


class SearchResult(NamedTuple):
    """Best move, its score for the side to move, visited nodes and completed depth."""

    move: chess.Move | None
    score: int
    nodes: int
    depth: int


def _no_draw_bias(root_eval: int) -> tuple[int, int]:
    return 0, 0


@dataclass(frozen=True)
class TimeConfig6:
    """Per-move time use. All limits are fractions of ``max_think_time_s`` (never above 1)."""

    soft: float = 0.6  # default: no new iteration after this share
    hard: float = 0.92  # abort the running iteration
    policy: str = "fixed"  # "fixed" | "stability" | "panic_easy" | "complexity" | "factors"
    early: float = 0.45  # stop this early when the position is stable/easy
    late: float = 0.9  # keep going until here when the position is unstable


@dataclass(frozen=True)
class NullMove6:
    """Adaptive null move: R = base + depth // depth_div + min(cap, (eval - beta) // eval_div)."""

    min_depth: int = 3
    base: int = 2
    depth_div: int = 6
    eval_div: int = 0  # 0 = no eval term
    eval_cap: int = 0
    static_ge_beta: bool = True
    non_pv_only: bool = True
    min_pieces: int = 1
    verify_depth: int = 0  # > 0: verification search from this depth
    verify_low_material: bool = False  # always verify when the side has <= 1 piece


@dataclass(frozen=True)
class Lmr6:
    """Logarithmic late move reductions with adjustments."""

    min_depth: int = 3
    full_moves: int = 3
    base: float = 0.75
    divisor: float = 2.25
    pv_less: int = 1  # fewer plies in PV nodes
    not_improving_more: int = 1
    killer_less: int = 1  # killers and the countermove
    cut_node_more: int = 1
    history_divisor: int = 0  # subtract history // divisor (0 = off)
    captures: bool = False  # also reduce late captures (by one ply)


@dataclass(frozen=True)
class Quiescence6:
    """Leaf search; a side in check always searches every evasion (no stand-pat)."""

    max_ply: int = 10
    promotions: bool = True
    delta: int = 200  # stand_pat + victim + delta <= alpha -> skip (0 = off)
    delta_node: int = 0  # stand_pat + delta_node < alpha -> return (0 = off)
    see_prune: bool = True
    first_ply_checks: int = 0  # quiet checks searched at the first q-ply (max count)


@dataclass(frozen=True)
class SearchConfig6:
    """All switches and parameters of one Benchmark 6/7 search."""

    time: TimeConfig6 = field(default_factory=TimeConfig6)
    check_mask: int = 127  # time is checked every ``check_mask + 1`` nodes
    stop_on_mate: bool = True
    aspiration: tuple[int, ...] = (30, 100, 300)  # successive half-windows
    aspiration_grow: int = 0  # > 0: widen only the failing side by this much (Gemini)
    aspiration_min_depth: int = 4
    tt_bits: int = 18
    tt_ways: int = 2
    eval_cache_bits: int = 16
    incremental: bool = True
    killers: int = 2
    countermove: bool = True
    history_malus: bool = True
    capture_history: bool = False
    continuation: tuple[int, ...] = ()  # plies back, e.g. (1, 2)
    capture_order: str = "see"  # "mvv" | "attacked" | "see"
    null_move: NullMove6 | None = field(default_factory=NullMove6)
    reverse_futility: tuple[int, int, int] | None = None  # (max depth, margin/ply, improving)
    razoring: tuple[int, int, int] | None = None  # (max depth, base, per ply)
    futility: tuple[int, int, int] | None = None  # (max depth, base, per ply)
    futility_spares_good_quiets: bool = False  # never prune killers/countermove/good history
    late_move_pruning: tuple[int, ...] | None = None  # quiet moves allowed per depth 1..n
    lmp_improving_pct: int = 100  # threshold multiplier (percent) when improving
    history_pruning: tuple[int, int] | None = None  # (max depth, -threshold per ply)
    see_pruning: tuple[int, int, int] | None = None  # (max depth, capture, quiet per ply)
    probcut: tuple[int, int, int] | None = None  # (min depth, margin, reduction)
    multicut: tuple[int, int, int, int] | None = None  # (min depth, R, moves tried, cuts)
    iid: tuple[int, int] | None = None  # (min depth, reduction) for PV nodes without TT move
    iir_min_depth: int = 0  # > 0: reduce one ply when there is no TT move
    # (min depth, TT depth slack, fixed margin, margin per ply)
    singular: tuple[int, int, int, int] | None = None
    singular_multicut: bool = False
    lmr: Lmr6 | None = field(default_factory=Lmr6)
    check_extensions: int = 2
    capture_extension: bool = False  # SEE >= 0 captures/promotions at depth 1
    recapture_extension: bool = False
    pawn_seventh_extension: bool = False
    bad_capture_reduction: bool = False  # SEE < 0 captures searched one ply shallower
    mate_distance_pruning: bool = True
    quiescence: Quiescence6 = field(default_factory=Quiescence6)
    twofold: bool = True
    draw_scores: Callable[[int], tuple[int, int]] = _no_draw_bias
    root_repetition_filter: int | None = None
    root_repetition_penalty: int = 0
    correction: tuple[int, int] | None = None  # (table bits, clamp in centipawns)
    book: bool = False


class Engine6:
    """Iterative-deepening selective PVS search; all state lives in the instance."""

    def __init__(self, config: SearchConfig6, evaluator: Evaluator6, seed: int | None = None):
        self.config = config
        self.evaluator = evaluator
        self.pst = evaluator.pst
        self.rng = random.Random(seed)
        self.board = chess.Board()
        self.nodes = 0
        self.hard_deadline = float("inf")
        self.generation = 0
        self.repetitions: Counter[int] = Counter()
        self.rep_draw = 0
        self.final_draw = 0
        self.packed = 0
        self._tt: list | None = None
        self._tables_ready = False
        lmr = config.lmr
        self._lmr_table = (
            [
                [
                    int(lmr.base + math.log(d) * math.log(m) / lmr.divisor) if d and m else 0
                    for m in range(64)
                ]
                for d in range(MAX_PLY)
            ]
            if lmr is not None
            else None
        )
        self._book: dict[int, list[str]] | None = None

    # ------------------------------------------------------------- lifecycle
    def _ensure_tables(self) -> None:
        if self._tables_ready:
            return
        cfg = self.config
        self._tt = [None] * ((1 << cfg.tt_bits) * cfg.tt_ways)
        self._tt_mask = (1 << cfg.tt_bits) - 1
        self.eval_cache: dict[int, int] = {}
        self.history = [0] * (2 * 64 * 64)
        self.capture_hist = [0] * (PIECE_SLOTS * 7) if cfg.capture_history else None
        self.cont = {distance: [0] * (PIECE_SLOTS * PIECE_SLOTS) for distance in cfg.continuation}
        self.countermoves: list[chess.Move | None] = [None] * PIECE_SLOTS
        self.killers: list[list[chess.Move | None]] = [[None, None] for _ in range(MAX_PLY + 4)]
        self.correction_table = (
            [0] * (2 << cfg.correction[0]) if cfg.correction is not None else None
        )
        self.static_stack: list[int | None] = [None] * (MAX_PLY + 4)
        self.piece_stack: list[int] = [-1] * (MAX_PLY + 8)  # offset 4
        self._tables_ready = True

    def clear(self) -> None:
        """Forget everything learned during the previous game."""
        self._tables_ready = False
        self._tt = None
        self.evaluator.clear()

    # ----------------------------------------------------------------- driver
    def search(
        self, board: chess.Board, time_limit_s: float | None, max_depth: int
    ) -> SearchResult:
        """Search ``board`` (restored afterwards) within the time budget or ``max_depth``.

        The cyclic garbage collector is paused meanwhile: a full collection over the
        transposition table can stall for 100 ms and break the per-move time cap. The
        search creates no reference cycles, so reference counting frees everything.
        """
        enabled = gc.isenabled()
        gc.disable()
        try:
            return self._run(board, time_limit_s, max_depth)
        finally:
            if enabled:
                gc.enable()

    def _run(self, board: chess.Board, time_limit_s: float | None, max_depth: int) -> SearchResult:
        self._ensure_tables()
        cfg = self.config
        tcfg = cfg.time
        started = time.perf_counter()
        if time_limit_s is None:
            budget = None
            self.hard_deadline = float("inf")
        else:
            budget = time_limit_s
            # Keep 100 ms (or 15 %) for unwinding and the caller, so the cap is never exceeded.
            reserve = min(0.1, 0.15 * time_limit_s)
            self.hard_deadline = started + min(time_limit_s * tcfg.hard, time_limit_s - reserve)
        self.board = board
        self.nodes = 0
        self.generation = (self.generation + 1) & 0xFF
        root_length = len(board.move_stack)
        self.repetitions = self._game_keys(board)
        self.history = [value // 2 for value in self.history]
        if len(self.eval_cache) > (1 << cfg.eval_cache_bits):
            self.eval_cache.clear()
        self.packed = self.evaluator.pst_sum(board)
        self._packed_stack: list[int] = []
        previous = board.move_stack[-1] if board.move_stack else None
        self.piece_stack[3] = (
            self._piece_slot(not board.turn, board.piece_type_at(previous.to_square), previous)
            if previous
            else -1
        )
        root_eval = self.evaluator(board, self.packed)
        self.rep_draw, self.final_draw = cfg.draw_scores(root_eval)

        if cfg.book:
            book_move = self._book_move(board)
            if book_move is not None:
                return SearchResult(book_move, 0, 0, 0)

        moves = self._root_moves(board, root_eval)
        best = SearchResult(moves[0], root_eval, 0, 0)
        history: list[tuple[chess.Move, int]] = []
        legal_count = len(moves)
        last_iteration = 0.0
        for depth in range(1, max(1, max_depth) + 1):
            iteration_start = time.perf_counter()
            try:
                score, move = self._iteration(depth, moves, best.score)
            except SearchTimeout:
                while len(board.move_stack) > root_length:
                    board.pop()
                break
            best = SearchResult(move, score, self.nodes, depth)
            history.append((move, score))
            moves.remove(move)
            moves.insert(0, move)
            now = time.perf_counter()
            last_iteration = now - iteration_start
            if cfg.stop_on_mate and abs(score) >= MATE_BOUND:
                break
            if budget is not None:
                target = self._time_target(budget, history, board, legal_count)
                if now - started >= target:
                    break
                if tcfg.policy == "stability" and now + 2.0 * last_iteration > self.hard_deadline:
                    break  # the next iteration would not finish
        return SearchResult(best.move, best.score, self.nodes, best.depth)

    def _time_target(
        self,
        budget: float,
        history: list[tuple[chess.Move, int]],
        board: chess.Board,
        legal_count: int,
    ) -> float:
        tcfg = self.config.time
        policy = tcfg.policy
        soft = tcfg.soft * budget
        depth = len(history)
        best_move, score = history[-1]
        changed = depth >= 2 and history[-2][0] != best_move
        if policy == "fixed":
            return soft
        if policy == "stability":  # ChatGPT: stop early when stable, go long when unstable
            if depth >= 5:
                recent = history[-3:]
                same = all(move == best_move for move, _ in recent)
                swing = max(s for _, s in recent) - min(s for _, s in recent)
                if same and swing < 25:
                    return tcfg.early * budget
            if changed or (depth >= 2 and abs(score - history[-2][1]) > 80):
                return tcfg.late * budget
            return soft
        if policy == "panic_easy":  # Gemini: panic on a score drop, stop early on easy moves
            if depth >= 2 and history[-2][1] - score > 50:
                return tcfg.late * budget
            if depth >= 5 and all(move == best_move for move, _ in history[1:]):
                return tcfg.early * budget
            return soft
        if policy == "complexity":  # Grok: scale by mobility, checks and instability
            factor = 1.0
            if board.is_check() or changed or legal_count > 35:
                factor = 1.3
            elif legal_count < 10 and not changed:
                factor = 0.8
            return min(soft * factor, tcfg.late * budget)
        # "factors": DeepSeek multiplies stability, score stability, phase and move number
        factor = 1.0
        if depth >= 3 and all(move == best_move for move, _ in history[-3:]):
            factor *= 0.7
        if depth >= 3:
            scores = [s for _, s in history[-3:]]
            if max(scores) - min(scores) < 5:
                factor *= 0.8
        if depth >= 2 and history[-2][1] - score > 50:
            factor *= 1.5  # panic, still capped by the hard limit
        pieces = (board.occupied & ~board.pawns & ~board.kings).bit_count()
        factor *= 0.8 if pieces <= 6 else 1.0
        move_number = board.fullmove_number
        factor *= 0.5 if move_number <= 10 else 1.0 if move_number <= 30 else 0.8
        return min(soft * factor, tcfg.late * budget)

    def _game_keys(self, board: chess.Board) -> Counter[int]:
        keys = Counter([hash(board._transposition_key())])
        replay = board.copy()
        while replay.move_stack and replay.halfmove_clock > 0:
            replay.pop()
            keys[hash(replay._transposition_key())] += 1
        return keys

    def _root_moves(self, board: chess.Board, root_eval: int) -> list[chess.Move]:
        entry = self._tt_probe(hash(board._transposition_key()))
        tt_move = entry[4] if entry is not None else None
        moves = list(board.generate_legal_moves())
        moves = self._order(board, moves, 0, tt_move, None)
        cfg = self.config
        if cfg.root_repetition_filter is not None and root_eval > cfg.root_repetition_filter:
            fresh = [move for move in moves if not self._repeats_after(move)]
            if fresh:
                moves = fresh
        return moves

    def _repeats_after(self, move: chess.Move) -> bool:
        board = self.board
        board.push(move)
        repeated = self.repetitions[hash(board._transposition_key())] >= 1
        board.pop()
        return repeated

    def _iteration(
        self, depth: int, moves: list[chess.Move], previous: int
    ) -> tuple[int, chess.Move]:
        cfg = self.config
        if cfg.aspiration and depth >= cfg.aspiration_min_depth and abs(previous) < MATE_BOUND:
            if cfg.aspiration_grow:
                alpha = previous - cfg.aspiration[0]
                beta = previous + cfg.aspiration[0]
                for _ in range(6):
                    score, move = self._root(depth, alpha, beta, moves)
                    if score <= alpha:
                        alpha -= cfg.aspiration_grow
                    elif score >= beta:
                        beta += cfg.aspiration_grow
                    else:
                        return score, move
            else:
                for window in cfg.aspiration:
                    alpha, beta = previous - window, previous + window
                    score, move = self._root(depth, alpha, beta, moves)
                    if alpha < score < beta:
                        return score, move
        return self._root(depth, -INF, INF, moves)

    def _root(
        self, depth: int, alpha: int, beta: int, moves: list[chess.Move]
    ) -> tuple[int, chess.Move]:
        board = self.board
        cfg = self.config
        best_score, best_move = -INF, moves[0]
        alpha_origin = alpha
        ext = cfg.check_extensions
        for index, move in enumerate(moves):
            self._push(move, 0)
            penalty = 0
            if cfg.root_repetition_penalty and self.repetitions[hash(board._transposition_key())]:
                penalty = cfg.root_repetition_penalty
            if index == 0:
                score = -self._search(depth - 1, -beta, -alpha, 1, ext, True, False)
            else:
                score = -self._search(depth - 1, -alpha - 1, -alpha, 1, ext, False, True)
                if alpha < score < beta:
                    score = -self._search(depth - 1, -beta, -alpha, 1, ext, True, False)
            self._pop()
            score -= penalty
            if score > best_score:
                best_score, best_move = score, move
            if score > alpha:
                alpha = score
            if alpha >= beta:
                break
        flag = UPPER if best_score <= alpha_origin else LOWER if best_score >= beta else EXACT
        self._tt_store(
            hash(board._transposition_key()), depth, best_score, flag, best_move, None, 0
        )
        return best_score, best_move

    # ------------------------------------------------------------ make/unmake
    def _piece_slot(self, color: bool, piece_type: int | None, move: chess.Move) -> int:
        if piece_type is None:
            return -1
        return (int(color) * 7 + piece_type) * 64 + move.to_square

    def _push(self, move: chess.Move, ply: int) -> None:
        board = self.board
        us = board.turn
        piece = board.piece_type_at(move.from_square)
        self.piece_stack[ply + 4] = (int(us) * 7 + (piece or 1)) * 64 + move.to_square
        if self.config.incremental:
            pst = self.pst
            own = pst[us]
            frm, to = move.from_square, move.to_square
            promotion = move.promotion
            if promotion:
                delta = own[promotion][to] - own[chess.PAWN][frm]
            else:
                delta = own[piece][to] - own[piece][frm]
            captured = board.piece_type_at(to)
            if captured:
                delta += pst[not us][captured][to]
            elif piece == chess.PAWN and to == board.ep_square and (frm ^ to) & 7:
                delta += pst[not us][chess.PAWN][to - 8 if us else to + 8]
            if piece == chess.KING and abs(frm - to) == 2:
                rook_from, rook_to = (frm + 3, frm + 1) if to > frm else (frm - 4, frm - 1)
                delta += own[chess.ROOK][rook_to] - own[chess.ROOK][rook_from]
            self._packed_stack.append(self.packed)
            self.packed += delta if us else -delta
        board.push(move)

    def _pop(self) -> None:
        self.board.pop()
        if self.config.incremental:
            self.packed = self._packed_stack.pop()

    def _static_window(self, key: int, alpha: int, beta: int) -> int:
        """Static eval for stand-pat; lazy (not cached) when far outside the window."""
        cache = self.eval_cache
        value = cache.get(key)
        if value is None:
            value, exact = self.evaluator.evaluate(
                self.board, self.packed if self.config.incremental else None, alpha, beta
            )
            if exact:
                cache[key] = value
        return value

    def _static(self, key: int) -> int:
        cache = self.eval_cache
        value = cache.get(key)
        if value is None:
            board = self.board
            value = self.evaluator(board, self.packed if self.config.incremental else None)
            cache[key] = value
        return value

    # ----------------------------------------------------------------- search
    def _search(
        self,
        depth: int,
        alpha: int,
        beta: int,
        ply: int,
        extensions: int,
        pv: bool,
        cut: bool,
        null_ok: bool = True,
        excluded: chess.Move | None = None,
    ) -> int:
        cfg = self.config
        board = self.board
        self.nodes += 1
        if not self.nodes & cfg.check_mask and time.perf_counter() >= self.hard_deadline:
            raise SearchTimeout

        key = hash(board._transposition_key())
        repeated = self.repetitions[key]
        if repeated >= (1 if cfg.twofold else 2):
            return self.rep_draw if ply % 2 == 0 else -self.rep_draw
        if board.halfmove_clock >= 100:
            return self.final_draw if ply % 2 == 0 else -self.final_draw
        if ply >= MAX_PLY:
            return self._static(key)
        if cfg.mate_distance_pruning:
            alpha = max(alpha, -(MATE - ply))
            beta = min(beta, MATE - ply - 1)
            if alpha >= beta:
                return alpha

        in_check = board.is_check()
        if in_check and extensions > 0:
            depth += 1
            extensions -= 1
        if depth <= 0:
            return self._quiesce(alpha, beta, ply, 0)

        entry = None if excluded is not None else self._tt_probe(key)
        tt_move = None
        tt_depth = -1
        tt_score = 0
        tt_flag = UPPER
        if entry is not None:
            _, tt_depth, tt_score, tt_flag, tt_move, _, _ = entry
            tt_score = _from_tt(tt_score, ply)
            if (
                not pv
                and tt_depth >= depth
                and (
                    tt_flag == EXACT
                    or (tt_flag == LOWER and tt_score >= beta)
                    or (tt_flag == UPPER and tt_score <= alpha)
                )
            ):
                return tt_score

        static_stack = self.static_stack
        if in_check:
            static = None
            raw_static = None
            improving = False
            static_stack[ply] = None
        else:
            raw_static = self._static(key) if pv else self._static_window(key, alpha, beta)
            static = raw_static
            if self.correction_table is not None:
                static += self._correction(board)
            static_stack[ply] = static
            before = static_stack[ply - 2] if ply >= 2 else None
            improving = before is not None and static > before

        if not pv and not in_check and excluded is None and abs(beta) < MATE_BOUND:
            rfp = cfg.reverse_futility
            if (
                rfp is not None
                and depth <= rfp[0]
                and static - rfp[1] * depth + (rfp[2] if improving else 0) >= beta
            ):
                return static
            razor = cfg.razoring
            if (
                razor is not None
                and depth <= razor[0]
                and static + razor[1] + razor[2] * depth < alpha
            ):
                value = self._quiesce(alpha, alpha + 1, ply, 0)
                if value <= alpha:
                    return value
            null = cfg.null_move
            if (
                null is not None
                and null_ok
                and depth >= null.min_depth
                and (not null.static_ge_beta or static >= beta)
            ):
                pieces = (board.occupied_co[board.turn] & ~board.pawns & ~board.kings).bit_count()
                if pieces >= null.min_pieces:
                    reduction = null.base + (depth // null.depth_div if null.depth_div else 0)
                    if null.eval_div:
                        reduction += min(null.eval_cap, max(0, (static - beta) // null.eval_div))
                    self.piece_stack[ply + 4] = -1
                    board.push(_NULL_MOVE)
                    if cfg.incremental:
                        self._packed_stack.append(self.packed)
                    value = -self._search(
                        depth - 1 - reduction,
                        -beta,
                        -beta + 1,
                        ply + 1,
                        extensions,
                        False,
                        not cut,
                        False,
                    )
                    board.pop()
                    if cfg.incremental:
                        self.packed = self._packed_stack.pop()
                    if value >= beta:
                        verify = (null.verify_depth and depth >= null.verify_depth) or (
                            null.verify_low_material and pieces <= 1
                        )
                        if verify:
                            value = self._search(
                                depth - 1 - reduction,
                                beta - 1,
                                beta,
                                ply,
                                extensions,
                                False,
                                cut,
                                False,
                            )
                        if value >= beta:
                            return beta if value >= MATE_BOUND else value
            probcut = cfg.probcut
            if probcut is not None and depth >= probcut[0]:
                value = self._probcut(depth, beta, ply, extensions, probcut, cut)
                if value is not None:
                    return value
            multicut = cfg.multicut
            if multicut is not None and cut and depth >= multicut[0]:
                if self._multicut(depth, beta, ply, extensions, multicut):
                    return beta

        if tt_move is None and excluded is None:
            iid = cfg.iid
            if iid is not None and pv and depth >= iid[0]:
                self._search(depth - iid[1], alpha, beta, ply, extensions, pv, cut, null_ok)
                entry = self._tt_probe(key)
                if entry is not None:
                    tt_move = entry[4]
            elif cfg.iir_min_depth and depth >= cfg.iir_min_depth:
                depth -= 1

        singular_extend = 0
        singular = cfg.singular
        if (
            singular is not None
            and excluded is None
            and tt_move is not None
            and depth >= singular[0]
            and extensions > 0
            and tt_flag != UPPER
            and tt_depth >= depth - singular[1]
            and abs(tt_score) < MATE_BOUND
        ):
            singular_beta = tt_score - singular[2] - singular[3] * depth
            value = self._search(
                (depth - 1) // 2,
                singular_beta - 1,
                singular_beta,
                ply,
                extensions,
                False,
                cut,
                False,
                tt_move,
            )
            if value < singular_beta:
                singular_extend = 1
            elif cfg.singular_multicut and singular_beta >= beta:
                return singular_beta

        repetitions = self.repetitions
        repetitions[key] = repeated + 1
        try:
            best = self._moves(
                depth,
                alpha,
                beta,
                ply,
                extensions,
                pv,
                cut,
                in_check,
                key,
                tt_move,
                static,
                improving,
                excluded,
                singular_extend,
            )
        finally:
            if repeated:
                repetitions[key] = repeated
            else:
                del repetitions[key]
        if (
            self.correction_table is not None
            and raw_static is not None
            and excluded is None
            and abs(best) < MATE_BOUND
        ):
            self._update_correction(board, best - raw_static, depth, best, alpha, beta)
        return best

    def _moves(
        self,
        depth: int,
        alpha: int,
        beta: int,
        ply: int,
        extensions: int,
        pv: bool,
        cut: bool,
        in_check: bool,
        key: int,
        tt_move: chess.Move | None,
        static: int | None,
        improving: bool,
        excluded: chess.Move | None,
        singular_extend: int,
    ) -> int:
        cfg = self.config
        board = self.board
        alpha_origin = alpha
        best_score = -INF
        best_move = None
        searched = 0
        quiets_seen = 0
        tried_quiets: list[chess.Move] = []
        tried_captures: list[tuple[chess.Move, int]] = []
        killers = self.killers[ply]
        previous = board.move_stack[-1] if board.move_stack else None
        prev_slot = self.piece_stack[ply + 3]
        counter = self.countermoves[prev_slot] if cfg.countermove and prev_slot >= 0 else None
        lmr = cfg.lmr
        shallow = not pv and not in_check and static is not None
        futility = cfg.futility
        futile = (
            shallow
            and futility is not None
            and depth <= futility[0]
            and static + futility[1] + futility[2] * depth <= alpha
        )
        lmp = cfg.late_move_pruning
        lmp_limit = None
        if shallow and lmp is not None and depth <= len(lmp):
            lmp_limit = lmp[depth - 1]
            if improving:
                lmp_limit = lmp_limit * cfg.lmp_improving_pct // 100
        see_limits = (
            cfg.see_pruning
            if not in_check and cfg.see_pruning is not None and depth <= cfg.see_pruning[0]
            else None
        )
        history_prune = (
            cfg.history_pruning
            if shallow and cfg.history_pruning is not None and depth <= cfg.history_pruning[0]
            else None
        )
        any_legal = False
        prev_to = previous.to_square if previous else -1

        for move, hist in self._staged(board, ply, tt_move, excluded, counter):
            any_legal = True
            capture = board.is_capture(move)
            quiet = not capture and move.promotion is None
            if quiet:
                quiets_seen += 1
                if hist is None:
                    hist = self._quiet_score(board, move, ply)
            else:
                hist = 0
            if searched and best_score > -MATE_BOUND and not in_check:
                if quiet:
                    if lmp_limit is not None and quiets_seen > lmp_limit:
                        continue
                    if history_prune is not None and hist < -history_prune[1] * depth:
                        continue
                if see_limits is not None:
                    margin = see_limits[1] if capture else see_limits[2]
                    if margin and see(board, move) < -margin * depth:
                        continue
            special = move == tt_move or move in killers or move == counter
            self._push(move, ply)
            gives_check = board.is_check()
            if (
                futile
                and quiet
                and searched
                and not gives_check
                and not (cfg.futility_spares_good_quiets and (special or hist > 0))
            ):
                self._pop()
                continue
            new_depth = depth - 1
            child_ext = extensions
            if singular_extend and move == tt_move:
                new_depth += 1  # singular extensions share the per-branch budget
                child_ext -= 1
            elif child_ext > 0 and not gives_check:
                extended = False
                if cfg.recapture_extension and capture and move.to_square == prev_to:
                    extended = True
                elif cfg.pawn_seventh_extension and move.promotion is None:
                    piece = board.piece_type_at(move.to_square)
                    rank = move.to_square >> 3
                    if piece == chess.PAWN and rank in (1, 6):
                        extended = (rank == 6) == (not board.turn)
                elif cfg.capture_extension and depth == 1 and not quiet:
                    self._pop()
                    extended = see(board, move) >= 0
                    self._push(move, ply)
                if extended:
                    new_depth += 1
                    child_ext -= 1
            if (
                cfg.bad_capture_reduction
                and capture
                and not gives_check
                and searched
                and new_depth > 1
            ):
                self._pop()
                bad = see(board, move) < 0
                self._push(move, ply)
                if bad:
                    new_depth -= 1

            if searched == 0:
                score = -self._search(new_depth, -beta, -alpha, ply + 1, child_ext, pv, not cut)
            else:
                reduction = 0
                if (
                    lmr is not None
                    and depth >= lmr.min_depth
                    and searched >= lmr.full_moves
                    and not in_check
                    and not gives_check
                    and move != tt_move
                    and (quiet or (lmr.captures and capture))
                ):
                    if quiet:
                        reduction = self._lmr_table[min(depth, MAX_PLY - 1)][min(searched, 63)]
                        if pv:
                            reduction -= lmr.pv_less
                        if not improving:
                            reduction += lmr.not_improving_more
                        if special:
                            reduction -= lmr.killer_less
                        if cut:
                            reduction += lmr.cut_node_more
                        if lmr.history_divisor:
                            reduction -= hist // lmr.history_divisor
                    else:
                        reduction = 1
                    reduction = max(0, min(reduction, new_depth - 1))
                score = -self._search(
                    new_depth - reduction, -alpha - 1, -alpha, ply + 1, child_ext, False, True
                )
                if reduction and score > alpha:
                    score = -self._search(
                        new_depth, -alpha - 1, -alpha, ply + 1, child_ext, False, not cut
                    )
                if pv and alpha < score < beta:
                    score = -self._search(new_depth, -beta, -alpha, ply + 1, child_ext, True, False)
            self._pop()
            searched += 1

            if score > best_score:
                best_score, best_move = score, move
            if score > alpha:
                alpha = score
                if alpha >= beta:
                    self._reward(
                        board, move, quiet, depth, ply, prev_slot, tried_quiets, tried_captures
                    )
                    break
            if quiet:
                tried_quiets.append(move)
            elif capture and self.capture_hist is not None:
                tried_captures.append((move, self._capture_index(board, move)))

        if not any_legal:
            if excluded is not None:
                return alpha
            return (
                -(MATE - ply)
                if in_check
                else (self.final_draw if ply % 2 == 0 else -self.final_draw)
            )
        if best_move is None:
            return alpha
        if excluded is None:
            flag = UPPER if best_score <= alpha_origin else LOWER if best_score >= beta else EXACT
            self._tt_store(key, depth, best_score, flag, best_move, static, ply)
        return best_score

    def _probcut(
        self,
        depth: int,
        beta: int,
        ply: int,
        extensions: int,
        params: tuple[int, int, int],
        cut: bool,
    ) -> int | None:
        board = self.board
        pc_beta = beta + params[1]
        captures = sorted(board.generate_legal_captures(), key=lambda m: -_mvv_lva(board, m))
        for move in captures:
            if see(board, move) < params[1] // 2:
                continue
            self._push(move, ply)
            value = -self._quiesce(-pc_beta, -pc_beta + 1, ply + 1, 0)
            if value >= pc_beta:
                value = -self._search(
                    depth - params[2],
                    -pc_beta,
                    -pc_beta + 1,
                    ply + 1,
                    extensions,
                    False,
                    not cut,
                )
            self._pop()
            if value >= pc_beta:
                return value
        return None

    def _multicut(
        self, depth: int, beta: int, ply: int, extensions: int, params: tuple[int, int, int, int]
    ) -> bool:
        board = self.board
        moves = self._order(board, list(board.generate_legal_moves()), ply, None, None)
        cuts = 0
        for move in moves[: params[2]]:
            self._push(move, ply)
            value = -self._search(
                depth - 1 - params[1], -beta, -beta + 1, ply + 1, extensions, False, False
            )
            self._pop()
            if value >= beta:
                cuts += 1
                if cuts >= params[3]:
                    return True
        return False

    def _quiesce(self, alpha: int, beta: int, ply: int, qply: int) -> int:
        cfg = self.config
        qcfg = cfg.quiescence
        board = self.board
        self.nodes += 1
        if not self.nodes & cfg.check_mask and time.perf_counter() >= self.hard_deadline:
            raise SearchTimeout
        if ply >= MAX_PLY:
            return self.evaluator(board)

        if board.is_check():
            moves = list(board.generate_legal_moves())
            if not moves:
                return -(MATE - ply)
            if qply >= qcfg.max_ply:
                return self._static(hash(board._transposition_key()))
            moves.sort(key=lambda move: -_mvv_lva(board, move))
            stand = None
            best = -INF
        else:
            stand = self._static_window(hash(board._transposition_key()), alpha, beta)
            if stand >= beta or qply >= qcfg.max_ply:
                return stand
            if qcfg.delta_node and stand + qcfg.delta_node < alpha:
                own_pawns = board.pawns & board.occupied_co[board.turn]
                seventh = chess.BB_RANK_7 if board.turn == chess.WHITE else chess.BB_RANK_2
                if not own_pawns & seventh:
                    return stand
            best = stand
            if stand > alpha:
                alpha = stand
            moves = list(board.generate_legal_captures())
            own_pawns = board.pawns & board.occupied_co[board.turn]
            seventh = chess.BB_RANK_7 if board.turn == chess.WHITE else chess.BB_RANK_2
            if qcfg.promotions and own_pawns & seventh:
                moves.extend(
                    move
                    for move in board.generate_legal_moves(
                        own_pawns & seventh, chess.BB_ALL & ~board.occupied
                    )
                    if move.promotion == chess.QUEEN
                )
            if qcfg.first_ply_checks and qply == 0:
                moves.extend(_quiet_checks(board, qcfg.first_ply_checks))
            moves.sort(key=lambda move: -_mvv_lva(board, move))

        delta = qcfg.delta
        for move in moves:
            if stand is not None and board.is_capture(move):
                if delta and move.promotion is None:
                    victim = board.piece_type_at(move.to_square) or chess.PAWN
                    if stand + VALUES[victim] + delta <= alpha:
                        continue
                if qcfg.see_prune and see(board, move) < 0:
                    continue
            self._push(move, ply)
            score = -self._quiesce(-beta, -alpha, ply + 1, qply + 1)
            self._pop()
            if score > best:
                best = score
                if score > alpha:
                    alpha = score
                    if alpha >= beta:
                        break
        return best

    # --------------------------------------------------------------- ordering
    def _staged(
        self,
        board: chess.Board,
        ply: int,
        tt_move: chess.Move | None,
        excluded: chess.Move | None,
        counter: chess.Move | None,
    ):
        """Yield (move, quiet history or None) stage by stage.

        TT move, winning captures and queen promotions, killers and the countermove,
        quiet moves by history, then losing captures and under-promotions. Quiet moves
        are only generated when no earlier stage produced a cutoff.
        """
        if (
            tt_move is not None
            and tt_move != excluded
            and board.is_pseudo_legal(tt_move)
            and board.is_legal(tt_move)
        ):
            yield tt_move, None
        else:
            tt_move = None
        turn = board.turn
        own_pawns = board.pawns & board.occupied_co[turn]
        seventh = own_pawns & (chess.BB_RANK_7 if turn else chess.BB_RANK_2)
        empty = chess.BB_ALL & ~board.occupied
        good: list[tuple[int, chess.Move]] = []
        bad: list[tuple[int, chess.Move]] = []
        capture_score = self._capture_score
        for move in board.generate_legal_captures():
            if move == tt_move or move == excluded:
                continue
            value, losing = capture_score(board, move)
            (bad if losing else good).append((value, move))
        if seventh:
            for move in board.generate_legal_moves(seventh, empty):
                if move == tt_move or move == excluded:
                    continue
                if move.promotion == chess.QUEEN:
                    good.append((-50_000, move))
                else:
                    bad.append((-50_000, move))
        good.sort(key=_first, reverse=True)
        for _, move in good:
            yield move, None

        cfg = self.config
        tried: list[chess.Move] = []
        killers = self.killers[ply]
        for move in (killers[0], killers[1] if cfg.killers > 1 else None, counter):
            if (
                move is None
                or move == tt_move
                or move == excluded
                or move in tried
                or move.promotion
                or not board.is_legal(move)
                or board.is_capture(move)
            ):
                continue
            tried.append(move)
            yield move, None

        quiet_score = self._quiet_score
        quiets: list[tuple[int, chess.Move]] = []
        for move in board.generate_legal_moves(chess.BB_ALL, empty):
            if (
                move.promotion
                or move == tt_move
                or move == excluded
                or move in tried
                or board.is_en_passant(move)
            ):
                continue
            quiets.append((quiet_score(board, move, ply), move))
        quiets.sort(key=_first, reverse=True)
        for value, move in quiets:
            yield move, value
        bad.sort(key=_first, reverse=True)
        for _, move in bad:
            yield move, None

    def _capture_score(self, board: chess.Board, move: chess.Move) -> tuple[int, bool]:
        """MVV-LVA (+ capture history) and whether the capture loses material."""
        victim = board.piece_type_at(move.to_square)
        if victim is None:
            victim = chess.PAWN  # en passant
        attacker = board.piece_type_at(move.from_square) or chess.PAWN
        value = 10 * VALUES[victim] - VALUES[attacker]
        if move.promotion:
            value += VALUES[move.promotion]
        table = self.capture_hist
        if table is not None:
            value += (
                table[((int(board.turn) * 7 + attacker) * 64 + move.to_square) * 7 + victim] // 32
            )
        losing = False
        if VALUES[victim] < VALUES[attacker]:
            order = self.config.capture_order
            if order == "see":
                losing = see(board, move) < 0
            elif order == "attacked":
                losing = board.is_attacked_by(not board.turn, move.to_square)
        return value, losing

    def _quiet_score(self, board: chess.Board, move: chess.Move, ply: int) -> int:
        turn = board.turn
        score = self.history[(int(turn) * 64 + move.from_square) * 64 + move.to_square]
        if self.cont:
            piece = board.piece_type_at(move.from_square) or chess.PAWN
            slot = (int(turn) * 7 + piece) * 64 + move.to_square
            stack = self.piece_stack
            for distance, table in self.cont.items():
                prev = stack[ply + 4 - distance]
                if prev >= 0:
                    score += table[prev * PIECE_SLOTS + slot]
        return score

    def _capture_index(self, board: chess.Board, move: chess.Move) -> int:
        piece = board.piece_type_at(move.from_square) or chess.PAWN
        victim = board.piece_type_at(move.to_square) or chess.PAWN
        return ((int(board.turn) * 7 + piece) * 64 + move.to_square) * 7 + victim

    def _order(
        self,
        board: chess.Board,
        moves: list[chess.Move],
        ply: int,
        tt_move: chess.Move | None,
        prev_slot: int | None,
    ) -> list[chess.Move]:
        cfg = self.config
        killers = self.killers[ply] if cfg.killers else (None, None)
        first_killer = killers[0]
        second_killer = killers[1] if cfg.killers > 1 else None
        counter = None
        if cfg.countermove and prev_slot is not None and prev_slot >= 0:
            counter = self.countermoves[prev_slot]
        quiet_score = self._quiet_score

        capture_score = self._capture_score

        def score(move: chess.Move) -> int:
            if move == tt_move:
                return 30_000_000
            if board.is_capture(move):
                value, losing = capture_score(board, move)
                return (-20_000_000 if losing else 20_000_000) + value
            if move.promotion:
                return 19_000_000 + VALUES[move.promotion]
            if move == first_killer:
                return 18_000_000
            if move == second_killer:
                return 17_900_000
            if move == counter:
                return 17_000_000
            return quiet_score(board, move, ply)

        moves.sort(key=score, reverse=True)
        return moves

    def _reward(
        self,
        board: chess.Board,
        move: chess.Move,
        quiet: bool,
        depth: int,
        ply: int,
        prev_slot: int,
        tried_quiets: list[chess.Move],
        tried_captures: list[tuple[chess.Move, int]],
    ) -> None:
        cfg = self.config
        bonus = min(16 * depth * depth, 1_600)
        if quiet:
            killers = self.killers[ply]
            if cfg.killers and move != killers[0]:
                killers[1] = killers[0]
                killers[0] = move
            if cfg.countermove and prev_slot >= 0:
                self.countermoves[prev_slot] = move
            self._update_quiet(board, move, ply, bonus)
            if cfg.history_malus:
                for other in tried_quiets:
                    self._update_quiet(board, other, ply, -bonus)
        elif self.capture_hist is not None and board.is_capture(move):
            table = self.capture_hist
            index = self._capture_index(board, move)
            table[index] += bonus - table[index] * bonus // HISTORY_MAX
        if self.capture_hist is not None:
            table = self.capture_hist
            for _, index in tried_captures:
                table[index] -= bonus + table[index] * bonus // HISTORY_MAX

    def _update_quiet(self, board: chess.Board, move: chess.Move, ply: int, bonus: int) -> None:
        turn = board.turn
        magnitude = abs(bonus)
        history = self.history
        index = (int(turn) * 64 + move.from_square) * 64 + move.to_square
        history[index] += bonus - history[index] * magnitude // HISTORY_MAX
        if self.cont:
            piece = board.piece_type_at(move.from_square) or chess.PAWN
            slot = (int(turn) * 7 + piece) * 64 + move.to_square
            stack = self.piece_stack
            for distance, table in self.cont.items():
                prev = stack[ply + 4 - distance]
                if prev >= 0:
                    position = prev * PIECE_SLOTS + slot
                    table[position] += bonus - table[position] * magnitude // HISTORY_MAX

    # ------------------------------------------------------ correction history
    def _correction_index(self, board: chess.Board) -> int:
        bits = self.config.correction[0]
        pawn_key = hash(
            (board.pawns & board.occupied_co[True], board.pawns & board.occupied_co[False])
        )
        return (int(board.turn) << bits) | (pawn_key & ((1 << bits) - 1))

    def _correction(self, board: chess.Board) -> int:
        return self.correction_table[self._correction_index(board)] // 256

    def _update_correction(
        self, board: chess.Board, diff: int, depth: int, best: int, alpha: int, beta: int
    ) -> None:
        if (best >= beta and diff < 0) or (best <= alpha and diff > 0):
            return  # bounds that do not tell which way the static eval is wrong
        clamp = self.config.correction[1] * 256
        table = self.correction_table
        index = self._correction_index(board)
        weight = min(depth + 1, 16)
        value = (table[index] * (256 - weight) + diff * 256 * weight) // 256
        table[index] = max(-clamp, min(clamp, value))

    # --------------------------------------------------------------------- TT
    def _tt_probe(self, key: int) -> tuple | None:
        table = self._tt
        ways = self.config.tt_ways
        base = (key & self._tt_mask) * ways
        for slot in range(base, base + ways):
            entry = table[slot]
            if entry is not None and entry[0] == key:
                return entry
        return None

    def _tt_store(
        self,
        key: int,
        depth: int,
        score: int,
        flag: int,
        move: chess.Move | None,
        static: int | None,
        ply: int,
    ) -> None:
        table = self._tt
        ways = self.config.tt_ways
        base = (key & self._tt_mask) * ways
        generation = self.generation
        victim = base
        victim_value = INF
        for slot in range(base, base + ways):
            entry = table[slot]
            if entry is None:
                victim = slot
                break
            if entry[0] == key:
                if depth < entry[1] - 2 and flag != EXACT and entry[5] == generation:
                    return
                if move is None:
                    move = entry[4]
                victim = slot
                break
            value = entry[1] - (8 if entry[5] != generation else 0)
            if value < victim_value:
                victim_value, victim = value, slot
        else:
            if ways == 1:
                entry = table[base]
                if entry[5] == generation and entry[1] > depth and flag != EXACT:
                    return
        table[victim] = (key, depth, _to_tt(int(score), ply), flag, move, generation, static)

    # ------------------------------------------------------------------- book
    def _book_move(self, board: chess.Board) -> chess.Move | None:
        if self._book is None:
            self._book = _build_book()
        candidates = self._book.get(hash(board._transposition_key()))
        if not candidates:
            return None
        legal = [m for m in (chess.Move.from_uci(u) for u in candidates) if board.is_legal(m)]
        return self.rng.choice(legal) if legal else None


# Hand-written opening book: (moves from the start in SAN, replies in SAN).
BOOK_LINES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("", ("e4", "d4", "Nf3", "c4")),
    ("e4", ("e5", "c5", "e6", "c6")),
    ("d4", ("d5", "Nf6")),
    ("c4", ("e5", "Nf6", "c5")),
    ("Nf3", ("d5", "Nf6")),
    ("e4 e5", ("Nf3",)),
    ("e4 e5 Nf3", ("Nc6", "Nf6")),
    ("e4 e5 Nf3 Nc6", ("Bb5", "Bc4", "d4")),
    ("e4 e5 Nf3 Nc6 Bb5", ("a6", "Nf6")),
    ("e4 e5 Nf3 Nc6 Bc4", ("Bc5", "Nf6")),
    ("e4 e5 Nf3 Nf6", ("Nxe5", "d4")),
    ("e4 c5", ("Nf3", "Nc3")),
    ("e4 c5 Nf3", ("d6", "Nc6", "e6")),
    ("e4 e6", ("d4",)),
    ("e4 e6 d4", ("d5",)),
    ("e4 c6", ("d4",)),
    ("e4 c6 d4", ("d5",)),
    ("e4 d5", ("exd5",)),
    ("d4 d5", ("c4", "Nf3")),
    ("d4 d5 c4", ("e6", "c6")),
    ("d4 d5 c4 e6", ("Nc3", "Nf3")),
    ("d4 d5 Nf3", ("Nf6",)),
    ("d4 Nf6", ("c4", "Nf3")),
    ("d4 Nf6 c4", ("e6", "g6")),
    ("d4 Nf6 c4 e6", ("Nc3", "Nf3")),
    ("c4 e5", ("Nc3", "g3")),
    ("Nf3 d5", ("d4", "g3")),
    ("Nf3 Nf6", ("c4", "g3", "d4")),
)


def _build_book() -> dict[int, list[str]]:
    book: dict[int, list[str]] = {}
    for line, replies in BOOK_LINES:
        board = chess.Board()
        for san in line.split():
            board.push_san(san)
        book[hash(board._transposition_key())] = [board.parse_san(san).uci() for san in replies]
    return book


def see(board: chess.Board, move: chess.Move) -> int:
    """Static exchange evaluation of ``move`` on its target square (centipawns)."""
    to_square = move.to_square
    mover = board.piece_type_at(move.from_square)
    if mover is None:
        return 0
    occupied = board.occupied ^ chess.BB_SQUARES[move.from_square]
    if board.is_en_passant(move):
        victim = chess.PAWN
        occupied ^= chess.BB_SQUARES[to_square + (-8 if board.turn == chess.WHITE else 8)]
    else:
        victim = board.piece_type_at(to_square) or 0
    gains = [VALUES[victim]]
    current = VALUES[mover]
    if move.promotion:
        gains[0] += VALUES[move.promotion] - VALUES[chess.PAWN]
        current = VALUES[move.promotion]
    side = not board.turn
    while True:
        attackers = board.attackers_mask(side, to_square, occupied) & occupied
        if not attackers:
            break
        for piece_type in (chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN):
            candidates = attackers & board.pieces_mask(piece_type, side)
            if candidates:
                break
        else:
            piece_type = chess.KING
            candidates = attackers
            rest = occupied ^ (candidates & -candidates)
            if board.attackers_mask(not side, to_square, rest) & rest:
                break
        low = candidates & -candidates
        gains.append(current - gains[-1])
        current = VALUES[piece_type]
        occupied ^= low
        side = not side
    for index in range(len(gains) - 1, 0, -1):
        gains[index - 1] = -max(-gains[index - 1], gains[index])
    return gains[0]


def _first(item: tuple[int, chess.Move]) -> int:
    return item[0]


def _quiet_checks(board: chess.Board, limit: int) -> list[chess.Move]:
    """Up to ``limit`` quiet, non-promoting direct checks, found from the king's lines."""
    them = not board.turn
    king = board.king(them)
    if king is None:
        return []
    occupied = board.occupied
    own = board.occupied_co[board.turn]
    empty = chess.BB_ALL & ~occupied
    diagonal = chess.BB_DIAG_ATTACKS[king][chess.BB_DIAG_MASKS[king] & occupied] & empty
    straight = (
        chess.BB_FILE_ATTACKS[king][chess.BB_FILE_MASKS[king] & occupied]
        | chess.BB_RANK_ATTACKS[king][chess.BB_RANK_MASKS[king] & occupied]
    ) & empty
    checks: list[chess.Move] = []
    for from_mask, to_mask in (
        (board.knights & own, chess.BB_KNIGHT_ATTACKS[king] & empty),
        (board.bishops & own, diagonal),
        (board.rooks & own, straight),
        (board.queens & own, diagonal | straight),
        (board.pawns & own, chess.BB_PAWN_ATTACKS[them][king] & empty),
    ):
        if from_mask and to_mask:
            for move in board.generate_legal_moves(from_mask, to_mask):
                if move.promotion is None:
                    checks.append(move)
                    if len(checks) >= limit:
                        return checks
    return checks


def _to_tt(score: int, ply: int) -> int:
    if score >= MATE_BOUND:
        return score + ply
    if score <= -MATE_BOUND:
        return score - ply
    return score


def _from_tt(score: int, ply: int) -> int:
    if score >= MATE_BOUND:
        return score - ply
    if score <= -MATE_BOUND:
        return score + ply
    return score


def _mvv_lva(board: chess.Board, move: chess.Move) -> int:
    victim = board.piece_type_at(move.to_square)
    if victim is None:
        victim = chess.PAWN if board.is_en_passant(move) else 0
    attacker = board.piece_type_at(move.from_square) or chess.PAWN
    value = 10 * VALUES[victim] - VALUES[attacker] if victim else -VALUES[attacker]
    if move.promotion:
        value += VALUES[move.promotion]
    return value
