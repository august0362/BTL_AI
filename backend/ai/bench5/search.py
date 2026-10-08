"""Configurable time-managed PVS engine behind the Benchmark 5 bots.

Every technique is switched on and tuned by a :class:`SearchConfig`, so the five Benchmark 5
profiles share one implementation and differ only in the ideas each source proposed.
"""

from __future__ import annotations

import gc
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from itertools import islice
from typing import NamedTuple

import chess

MATE = 100_000
MATE_BOUND = MATE - 1_000
INF = 1_000_000
MAX_PLY = 128
EXACT, LOWER, UPPER = 0, 1, 2
VALUES = (0, 100, 320, 330, 500, 900, 20_000)
HISTORY_LIMIT = 400_000
_NULL_MOVE = chess.Move.null()


class SearchTimeout(Exception):
    """Raised inside the search when the hard time limit is reached."""


class SearchResult(NamedTuple):
    """Best move, its score for the side to move, visited nodes and completed depth."""

    move: chess.Move | None
    score: int
    nodes: int
    depth: int


def _two(depth: int) -> int:
    return 2


def _one(depth: int, index: int) -> int:
    return 1


def _no_draw_bias(root_eval: int) -> tuple[int, int]:
    return 0, 0


@dataclass(frozen=True)
class NullMoveConfig:
    """Null-move pruning: pass, search ``depth - 1 - R`` and cut when still >= beta."""

    min_depth: int = 3
    reduction: Callable[[int], int] = _two
    non_pv_only: bool = True
    min_pieces: int = 1  # own pieces besides pawns and king (zugzwang guard)
    verify_depth: int = 0  # > 0: re-search without null move from this depth before cutting


@dataclass(frozen=True)
class LmrConfig:
    """Late move reductions for quiet moves after the first ``full_moves`` moves."""

    min_depth: int = 3
    full_moves: int = 3
    reduction: Callable[[int, int], int] = _one  # (depth, move index) -> plies
    skip_killers: bool = True


@dataclass(frozen=True)
class QuiescenceConfig:
    """Leaf search; a side in check always searches every evasion (no stand-pat)."""

    max_ply: int = 8
    promotions: bool = False  # also search quiet queen promotions
    delta_node: int = 0  # > 0: stand_pat + this < alpha -> stop (no pawn about to promote)
    delta_move: int = 0  # > 0: stand_pat + victim + this <= alpha -> skip the capture
    see_prune: bool = False  # skip captures losing material by SEE
    first_ply_checks: bool = False  # also search quiet checking moves at the first ply


@dataclass(frozen=True)
class SearchConfig:
    """All switches and parameters of one Benchmark 5 search."""

    soft_fraction: float = 0.6  # no new iteration after this share of the budget
    hard_fraction: float = 0.9  # abort the running iteration here
    check_mask: int = 127  # time is checked every ``check_mask + 1`` nodes
    stop_on_mate: bool = False
    aspiration: tuple[int, ...] = ()  # successive half-windows; empty = full window
    aspiration_min_depth: int = 4
    tt_entries: int = 300_000
    tt_two_tier: bool = False  # extra always-replace table next to the depth-preferred one
    killers: int = 2
    history_malus: bool = False  # penalise quiet moves tried before a cutoff
    history_by_piece: bool = False  # history indexed [piece][to] instead of [from][to]
    countermove: bool = False
    capture_split: str = "none"  # "none" | "attacked" | "see": losing captures after quiets
    null_move: NullMoveConfig | None = None
    reverse_futility: tuple[int, int] | None = None  # (max depth, margin per ply)
    futility: tuple[int, int] | None = None  # (max depth, margin per ply)
    late_move_pruning: tuple[int, int, int] | None = None  # (max depth, base, per ply)
    see_pruning: tuple[int, int, int] | None = None  # (max depth, capture, quiet margin/ply)
    lmr: LmrConfig | None = None
    check_extensions: int = 0  # extension budget per branch
    capture_extension: bool = False  # SEE >= 0 captures/promotions at depth 1 use the budget
    quiescence: QuiescenceConfig = field(default_factory=QuiescenceConfig)
    twofold: bool = True  # a repeated position on the path or in the game is a draw
    draw_scores: Callable[[int], tuple[int, int]] = _no_draw_bias  # root eval -> (rep, other)
    root_repetition_filter: int | None = None  # skip repeating root moves above this eval
    root_repetition_penalty: int = 0
    mate_distance_pruning: bool = False


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
                break  # the king may not capture into a defended square
        low = candidates & -candidates
        gains.append(current - gains[-1])
        current = VALUES[piece_type]
        occupied ^= low
        side = not side
    for index in range(len(gains) - 1, 0, -1):
        gains[index - 1] = -max(-gains[index - 1], gains[index])
    return gains[0]


class Engine5:
    """Iterative-deepening PVS search with its own TT, killers and history."""

    def __init__(self, config: SearchConfig, evaluate: Callable[[chess.Board], int]) -> None:
        self.config = config
        self.evaluate = evaluate
        self.tt: dict[int, tuple[int, int, int, chess.Move | None]] = {}
        self.tt2: dict[int, tuple[int, int, int, chess.Move | None]] = {}
        self.history = [0] * (2 * 7 * 64 if config.history_by_piece else 64 * 64)
        self.killers: list[list[chess.Move | None]] = [[None, None] for _ in range(MAX_PLY + 2)]
        self.countermoves: dict[int, chess.Move] = {}
        self.board = chess.Board()
        self.nodes = 0
        self.hard_deadline = float("inf")
        self.repetitions: Counter[int] = Counter()
        self.rep_draw = 0
        self.final_draw = 0

    def clear(self) -> None:
        """Forget everything learned during the previous game."""
        self.tt.clear()
        self.tt2.clear()
        self.history = [0] * len(self.history)
        self.killers = [[None, None] for _ in range(MAX_PLY + 2)]
        self.countermoves.clear()
        clear = getattr(self.evaluate, "clear", None)
        if clear is not None:
            clear()

    # ------------------------------------------------------------------ driver
    def search(
        self, board: chess.Board, time_limit_s: float | None, max_depth: int
    ) -> SearchResult:
        """Search ``board`` (restored afterwards) until the time budget or ``max_depth``.

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
        cfg = self.config
        started = time.perf_counter()
        if time_limit_s is None:
            soft = self.hard_deadline = float("inf")
        else:
            soft = started + time_limit_s * cfg.soft_fraction
            # Keep 100 ms (or 15 %) for unwinding and the caller, so the cap is never exceeded.
            reserve = min(0.1, 0.15 * time_limit_s)
            self.hard_deadline = started + min(
                time_limit_s * cfg.hard_fraction, time_limit_s - reserve
            )
        self.board = board
        self.nodes = 0
        root_length = len(board.move_stack)
        self.repetitions = self._game_keys(board)
        self.history = [value // 2 for value in self.history]
        root_eval = self.evaluate(board)
        self.rep_draw, self.final_draw = cfg.draw_scores(root_eval)

        moves = self._root_moves(board, root_eval)
        best = SearchResult(moves[0], root_eval, 0, 0)
        for depth in range(1, max(1, max_depth) + 1):
            try:
                score, move = self._iteration(depth, moves, best.score)
            except SearchTimeout:
                while len(board.move_stack) > root_length:
                    board.pop()
                break
            best = SearchResult(move, score, self.nodes, depth)
            moves.remove(move)
            moves.insert(0, move)
            if time.perf_counter() >= soft:
                break
            if cfg.stop_on_mate and abs(score) >= MATE_BOUND:
                break
        return SearchResult(best.move, best.score, self.nodes, best.depth)

    def _game_keys(self, board: chess.Board) -> Counter[int]:
        """Count the positions since the last irreversible move, including the root."""
        keys = Counter([hash(board._transposition_key())])
        replay = board.copy()
        while replay.move_stack and replay.halfmove_clock > 0:
            replay.pop()
            keys[hash(replay._transposition_key())] += 1
        return keys

    def _root_moves(self, board: chess.Board, root_eval: int) -> list[chess.Move]:
        entry = self._probe(hash(board._transposition_key()))
        moves = self._ordered(board, list(board.generate_legal_moves()), 0, entry)
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
            for window in cfg.aspiration:
                alpha, beta = previous - window, previous + window
                score, move = self._root(depth, alpha, beta, moves)
                if alpha < score < beta:
                    return score, move
        return self._root(depth, -INF, INF, moves)

    def _root(
        self, depth: int, alpha: float, beta: float, moves: list[chess.Move]
    ) -> tuple[int, chess.Move]:
        board = self.board
        cfg = self.config
        best_score, best_move = -INF, moves[0]
        alpha_origin = alpha
        for index, move in enumerate(moves):
            board.push(move)
            penalty = 0
            if cfg.root_repetition_penalty and self.repetitions[hash(board._transposition_key())]:
                penalty = cfg.root_repetition_penalty
            if index == 0:
                score = -self._search(depth - 1, -beta, -alpha, 1, cfg.check_extensions, True)
            else:
                score = -self._search(depth - 1, -alpha - 1, -alpha, 1, cfg.check_extensions, False)
                if alpha < score < beta:
                    score = -self._search(depth - 1, -beta, -alpha, 1, cfg.check_extensions, True)
            board.pop()
            score -= penalty
            if score > best_score:
                best_score, best_move = score, move
            if score > alpha:
                alpha = score
            if alpha >= beta:
                break
        flag = UPPER if best_score <= alpha_origin else LOWER if best_score >= beta else EXACT
        self._store(hash(board._transposition_key()), depth, best_score, flag, best_move, 0)
        return best_score, best_move

    # ------------------------------------------------------------------ search
    def _search(
        self,
        depth: int,
        alpha: float,
        beta: float,
        ply: int,
        extensions: int,
        pv: bool,
        null_ok: bool = True,
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
            return self.evaluate(board)
        if cfg.mate_distance_pruning:
            alpha = max(alpha, -(MATE - ply))
            beta = min(beta, MATE - ply - 1)
            if alpha >= beta:
                return int(alpha)

        in_check = board.is_check()
        if in_check and extensions > 0:
            depth += 1
            extensions -= 1
        if depth <= 0:
            return self._quiesce(alpha, beta, ply, 0)

        entry = self._probe(key)
        tt_move = None
        if entry is not None:
            entry_depth, entry_score, entry_flag, tt_move = entry
            if not pv and entry_depth >= depth:
                entry_score = _from_tt(entry_score, ply)
                if (
                    entry_flag == EXACT
                    or (entry_flag == LOWER and entry_score >= beta)
                    or (entry_flag == UPPER and entry_score <= alpha)
                ):
                    return entry_score

        static = None
        if not in_check and (cfg.reverse_futility or cfg.futility):
            static = self.evaluate(board)
            if (
                cfg.reverse_futility is not None
                and not pv
                and depth <= cfg.reverse_futility[0]
                and abs(beta) < MATE_BOUND
                and static - cfg.reverse_futility[1] * depth >= beta
            ):
                return static

        null = cfg.null_move
        if (
            null is not None
            and null_ok
            and not in_check
            and depth >= null.min_depth
            and not (pv and null.non_pv_only)
            and abs(beta) < MATE_BOUND
            and (board.occupied_co[board.turn] & ~board.pawns & ~board.kings).bit_count()
            >= null.min_pieces
        ):
            reduction = null.reduction(depth)
            board.push(_NULL_MOVE)
            value = -self._search(
                depth - 1 - reduction, -beta, -beta + 1, ply + 1, extensions, False, False
            )
            board.pop()
            if value >= beta:
                if null.verify_depth and depth >= null.verify_depth:
                    value = self._search(
                        depth - 1 - reduction, beta - 1, beta, ply, extensions, False, False
                    )
                if value >= beta:
                    return beta if value >= MATE_BOUND else value

        repetitions = self.repetitions
        repetitions[key] = repeated + 1
        try:
            return self._moves(
                depth, alpha, beta, ply, extensions, pv, in_check, key, tt_move, static
            )
        finally:
            if repeated:
                repetitions[key] = repeated
            else:
                del repetitions[key]

    def _moves(
        self,
        depth: int,
        alpha: float,
        beta: float,
        ply: int,
        extensions: int,
        pv: bool,
        in_check: bool,
        key: int,
        tt_move: chess.Move | None,
        static: int | None,
    ) -> int:
        cfg = self.config
        board = self.board
        alpha_origin = alpha
        best_score = -INF
        best_move = None
        searched = 0
        quiets_seen = 0
        tried_quiets: list[chess.Move] = []
        lmr = cfg.lmr
        killers = self.killers[ply]
        previous = board.move_stack[-1] if board.move_stack else None
        futile = (
            cfg.futility is not None
            and static is not None
            and depth <= cfg.futility[0]
            and static + cfg.futility[1] * depth <= alpha
        )
        lmp_limit = (
            cfg.late_move_pruning[1] + cfg.late_move_pruning[2] * depth
            if cfg.late_move_pruning is not None
            and not in_check
            and depth <= cfg.late_move_pruning[0]
            else None
        )
        see_limits = (
            cfg.see_pruning
            if cfg.see_pruning is not None and not in_check and depth <= cfg.see_pruning[0]
            else None
        )
        any_legal = False

        for move in self._staged(board, ply, tt_move, previous):
            any_legal = True
            capture = board.is_capture(move)
            quiet = not capture and move.promotion is None
            if quiet:
                quiets_seen += 1
            if searched and best_score > -MATE_BOUND and not in_check:
                if quiet and lmp_limit is not None and quiets_seen > lmp_limit:
                    continue
                if see_limits is not None:
                    margin = see_limits[1] if capture else see_limits[2]
                    if see(board, move) < -margin * depth:
                        continue
            board.push(move)
            gives_check = board.is_check()
            if futile and quiet and searched and not gives_check:
                board.pop()
                continue
            new_depth = depth - 1
            child_extensions = extensions
            if cfg.capture_extension and depth == 1 and extensions > 0 and not quiet:
                board.pop()
                good = see(board, move) >= 0
                board.push(move)
                if good:
                    new_depth += 1
                    child_extensions -= 1

            if searched == 0:
                score = -self._search(new_depth, -beta, -alpha, ply + 1, child_extensions, pv)
            else:
                reduction = 0
                if (
                    lmr is not None
                    and quiet
                    and depth >= lmr.min_depth
                    and searched >= lmr.full_moves
                    and not in_check
                    and not gives_check
                    and move != tt_move
                    and not (lmr.skip_killers and move in killers)
                ):
                    reduction = min(max(lmr.reduction(depth, searched), 1), new_depth - 1)
                    reduction = max(reduction, 0)
                score = -self._search(
                    new_depth - reduction, -alpha - 1, -alpha, ply + 1, child_extensions, False
                )
                if reduction and score > alpha:
                    score = -self._search(
                        new_depth, -alpha - 1, -alpha, ply + 1, child_extensions, False
                    )
                if pv and alpha < score < beta:
                    score = -self._search(new_depth, -beta, -alpha, ply + 1, child_extensions, True)
            board.pop()
            searched += 1

            if score > best_score:
                best_score, best_move = score, move
            if score > alpha:
                alpha = score
                if alpha >= beta:
                    if quiet:
                        self._reward(move, depth, ply, previous, tried_quiets)
                    break
            if quiet:
                tried_quiets.append(move)

        if not any_legal:
            return (
                -(MATE - ply)
                if in_check
                else (self.final_draw if ply % 2 == 0 else -self.final_draw)
            )
        if best_move is None:
            return int(alpha)
        flag = UPPER if best_score <= alpha_origin else LOWER if best_score >= beta else EXACT
        self._store(key, depth, best_score, flag, best_move, ply)
        return best_score

    def _quiesce(self, alpha: float, beta: float, ply: int, qply: int) -> int:
        cfg = self.config
        qcfg = cfg.quiescence
        board = self.board
        self.nodes += 1
        if not self.nodes & cfg.check_mask and time.perf_counter() >= self.hard_deadline:
            raise SearchTimeout
        if ply >= MAX_PLY:
            return self.evaluate(board)

        if board.is_check():
            moves = list(board.generate_legal_moves())
            if not moves:
                return -(MATE - ply)
            if qply >= qcfg.max_ply:
                return self.evaluate(board)
            moves.sort(key=lambda move: -_mvv_lva(board, move))
            stand = None
            best = -INF
        else:
            stand = self.evaluate(board)
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
            if qcfg.promotions:
                own_pawns = board.pawns & board.occupied_co[board.turn]
                seventh = chess.BB_RANK_7 if board.turn == chess.WHITE else chess.BB_RANK_2
                if own_pawns & seventh:
                    moves.extend(
                        move
                        for move in board.generate_legal_moves(
                            own_pawns & seventh, chess.BB_ALL & ~board.occupied
                        )
                        if move.promotion == chess.QUEEN
                    )
            if qcfg.first_ply_checks and qply == 0:
                moves.extend(
                    move
                    for move in board.generate_legal_moves()
                    if move.promotion is None
                    and not board.is_capture(move)
                    and board.gives_check(move)
                )
            moves.sort(key=lambda move: -_mvv_lva(board, move))

        for move in moves:
            if stand is not None and board.is_capture(move):
                if qcfg.delta_move and move.promotion is None:
                    victim = board.piece_type_at(move.to_square) or chess.PAWN
                    if stand + VALUES[victim] + qcfg.delta_move <= alpha:
                        continue
                if qcfg.see_prune and see(board, move) < 0:
                    continue
            board.push(move)
            score = -self._quiesce(-beta, -alpha, ply + 1, qply + 1)
            board.pop()
            if score > best:
                best = score
                if score > alpha:
                    alpha = score
                    if alpha >= beta:
                        break
        return int(best)

    # --------------------------------------------------------------- ordering
    def _staged(
        self,
        board: chess.Board,
        ply: int,
        tt_move: chess.Move | None,
        previous: chess.Move | None,
    ):
        """Yield the TT move first, then the rest of the legal moves in order."""
        if tt_move is not None and board.is_pseudo_legal(tt_move) and board.is_legal(tt_move):
            yield tt_move
        else:
            tt_move = None
        rest = [move for move in board.generate_legal_moves() if move != tt_move]
        yield from self._ordered(board, rest, ply, None, previous)

    def _ordered(
        self,
        board: chess.Board,
        moves: list[chess.Move],
        ply: int,
        entry: tuple | None,
        previous: chess.Move | None = None,
    ) -> list[chess.Move]:
        cfg = self.config
        tt_move = entry[3] if entry is not None else None
        killers = self.killers[ply] if cfg.killers else (None, None)
        first_killer = killers[0]
        second_killer = killers[1] if cfg.killers > 1 else None
        counter = None
        if cfg.countermove and previous is not None and previous:
            counter = self.countermoves.get(previous.from_square * 64 + previous.to_square)
        history = self.history
        by_piece = cfg.history_by_piece
        split = cfg.capture_split
        turn = board.turn
        piece_type_at = board.piece_type_at

        def score(move: chess.Move) -> int:
            if move == tt_move:
                return 3_000_000
            to_square = move.to_square
            victim = piece_type_at(to_square)
            if victim is None and board.is_en_passant(move):
                victim = chess.PAWN
            if victim is not None:
                attacker = piece_type_at(move.from_square) or chess.PAWN
                value = 10 * VALUES[victim] - VALUES[attacker]
                if move.promotion:
                    value += VALUES[move.promotion]
                if split == "see" and VALUES[victim] < VALUES[attacker]:
                    if see(board, move) < 0:
                        return -2_000_000 + value
                elif (
                    split == "attacked"
                    and VALUES[victim] < VALUES[attacker]
                    and board.is_attacked_by(not turn, to_square)
                ):
                    return -2_000_000 + value
                return 2_000_000 + value
            if move.promotion:
                return 1_900_000 + VALUES[move.promotion]
            if move == first_killer:
                return 1_800_000
            if move == second_killer:
                return 1_790_000
            if move == counter:
                return 1_700_000
            if by_piece:
                return history[_piece_index(board, move)]
            return history[move.from_square * 64 + to_square]

        moves.sort(key=score, reverse=True)
        return moves

    def _reward(
        self,
        move: chess.Move,
        depth: int,
        ply: int,
        previous: chess.Move | None,
        tried: list[chess.Move],
    ) -> None:
        cfg = self.config
        killers = self.killers[ply]
        if cfg.killers and move != killers[0]:
            killers[1] = killers[0]
            killers[0] = move
        bonus = depth * depth
        history = self.history
        board = self.board
        index = _piece_index(board, move) if cfg.history_by_piece else _from_to(move)
        history[index] += bonus
        if cfg.history_malus:
            for other in tried:
                other_index = (
                    _piece_index(board, other) if cfg.history_by_piece else _from_to(other)
                )
                history[other_index] -= bonus
        if history[index] > HISTORY_LIMIT:
            self.history = [value // 2 for value in history]
        if cfg.countermove and previous:
            self.countermoves[previous.from_square * 64 + previous.to_square] = move

    # --------------------------------------------------------------------- TT
    def _probe(self, key: int) -> tuple[int, int, int, chess.Move | None] | None:
        entry = self.tt.get(key)
        if entry is None and self.config.tt_two_tier:
            entry = self.tt2.get(key)
        return entry

    def _store(
        self, key: int, depth: int, score: int, flag: int, move: chess.Move | None, ply: int
    ) -> None:
        entry = (depth, _to_tt(int(score), ply), flag, move)
        table = self.tt
        previous = table.get(key)
        if previous is not None and previous[0] > depth:
            if self.config.tt_two_tier:
                _put(self.tt2, key, entry, self.config.tt_entries)
            return
        _put(table, key, entry, self.config.tt_entries)


def _put(table: dict, key: int, entry: tuple, limit: int) -> None:
    """Insert, evicting the oldest quarter of the table when it is full."""
    if key not in table and len(table) >= limit:
        for old in list(islice(table, limit // 4)):
            del table[old]
    table[key] = entry


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


def _from_to(move: chess.Move) -> int:
    return move.from_square * 64 + move.to_square


def _piece_index(board: chess.Board, move: chess.Move) -> int:
    piece = board.piece_type_at(move.from_square) or chess.PAWN
    return (int(board.turn) * 7 + piece) * 64 + move.to_square


def _mvv_lva(board: chess.Board, move: chess.Move) -> int:
    victim = board.piece_type_at(move.to_square)
    if victim is None:
        victim = chess.PAWN if board.is_en_passant(move) else 0
    attacker = board.piece_type_at(move.from_square) or chess.PAWN
    value = 10 * VALUES[victim] - VALUES[attacker] if victim else -VALUES[attacker]
    if move.promotion:
        value += VALUES[move.promotion]
    return value
