"""Hand-crafted evaluation of Benchmark 7 (own copy, free to diverge from Benchmark 6).

Material and piece-square values are packed into one integer (middlegame << 20 + endgame)
so the search can update them incrementally on every move. Every other knowledge term is
switched on and weighted by an :class:`EvalConfig6`. Scores are centipawns for the side to
move; the evaluation is colour-symmetric.
"""

from __future__ import annotations

from dataclasses import dataclass

import chess

from ai.bench7.tables import KING_ENDGAME_TABLE, PST_TABLES

SHIFT = 20
HALF = 1 << (SHIFT - 1)
LOW_MASK = (1 << SHIFT) - 1
MAX_PHASE = 24
CACHE_LIMIT = 100_000
PIECE_TYPES = (chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN, chess.KING)
PHASE_WEIGHT = (0, 0, 1, 1, 2, 4, 0)
MATERIAL = (0, 100, 320, 330, 500, 900, 0)
NOT_A = ~chess.BB_FILE_A & chess.BB_ALL
NOT_H = ~chess.BB_FILE_H & chess.BB_ALL
LIGHT_SQUARES = chess.BB_LIGHT_SQUARES
KNIGHT_ATTACKS = chess.BB_KNIGHT_ATTACKS
DIAG_ATTACKS, DIAG_MASKS = chess.BB_DIAG_ATTACKS, chess.BB_DIAG_MASKS
FILE_ATTACKS, FILE_MASKS = chess.BB_FILE_ATTACKS, chess.BB_FILE_MASKS
RANK_ATTACKS, RANK_MASKS = chess.BB_RANK_ATTACKS, chess.BB_RANK_MASKS
DARK_SQUARES = chess.BB_DARK_SQUARES


def pack(mg: int, eg: int) -> int:
    """Pack a middlegame and an endgame score into one integer."""
    return (mg << SHIFT) + eg


def unpack(packed: int) -> tuple[int, int]:
    """Split a packed score into (middlegame, endgame)."""
    eg = ((packed + HALF) & LOW_MASK) - HALF
    return (packed - eg) >> SHIFT, eg


# PeSTO tables (Rofchade), a8 first from White's view; values P N B R Q.
# fmt: off
PESTO_MG_VALUES = (0, 82, 337, 365, 477, 1025, 0)
PESTO_EG_VALUES = (0, 94, 281, 297, 512, 936, 0)
PESTO_MG = {
    chess.PAWN: (
        0, 0, 0, 0, 0, 0, 0, 0,
        98, 134, 61, 95, 68, 126, 34, -11,
        -6, 7, 26, 31, 65, 56, 25, -20,
        -14, 13, 6, 21, 23, 12, 17, -23,
        -27, -2, -5, 12, 17, 6, 10, -25,
        -26, -4, -4, -10, 3, 3, 33, -12,
        -35, -1, -20, -23, -15, 24, 38, -22,
        0, 0, 0, 0, 0, 0, 0, 0,
    ),
    chess.KNIGHT: (
        -167, -89, -34, -49, 61, -97, -15, -107,
        -73, -41, 72, 36, 23, 62, 7, -17,
        -47, 60, 37, 65, 84, 129, 73, 44,
        -9, 17, 19, 53, 37, 69, 18, 22,
        -13, 4, 16, 13, 28, 19, 21, -8,
        -23, -9, 12, 10, 19, 17, 25, -16,
        -29, -53, -12, -3, -1, 18, -14, -19,
        -105, -21, -58, -33, -17, -28, -19, -23,
    ),
    chess.BISHOP: (
        -29, 4, -82, -37, -25, -42, 7, -8,
        -26, 16, -18, -13, 30, 59, 18, -47,
        -16, 37, 43, 40, 35, 50, 37, -2,
        -4, 5, 19, 50, 37, 37, 7, -2,
        -6, 13, 13, 26, 34, 12, 10, 4,
        0, 15, 15, 15, 14, 27, 18, 10,
        4, 15, 16, 0, 7, 21, 33, 1,
        -33, -3, -14, -21, -13, -12, -39, -21,
    ),
    chess.ROOK: (
        32, 42, 32, 51, 63, 9, 31, 43,
        27, 32, 58, 62, 80, 67, 26, 44,
        -5, 19, 26, 36, 17, 45, 61, 16,
        -24, -11, 7, 26, 24, 35, -8, -20,
        -36, -26, -12, -1, 9, -7, 6, -23,
        -45, -25, -16, -17, 3, 0, -5, -33,
        -44, -16, -20, -9, -1, 11, -6, -71,
        -19, -13, 1, 17, 16, 7, -37, -26,
    ),
    chess.QUEEN: (
        -28, 0, 29, 12, 59, 44, 43, 45,
        -24, -39, -5, 1, -16, 57, 28, 54,
        -13, -17, 7, 8, 29, 56, 47, 57,
        -27, -27, -16, -16, -1, 17, -2, 1,
        -9, -26, -9, -10, -2, -4, 3, -3,
        -14, 2, -11, -2, -5, 2, 14, 5,
        -35, -8, 11, 2, 8, 15, -3, 1,
        -1, -18, -9, 10, -15, -25, -31, -50,
    ),
    chess.KING: (
        -65, 23, 16, -15, -56, -34, 2, 13,
        29, -1, -20, -7, -8, -4, -38, -29,
        -9, 24, 2, -16, -20, 6, 22, -22,
        -17, -20, -12, -27, -30, -25, -14, -36,
        -49, -1, -27, -39, -46, -44, -33, -51,
        -14, -14, -22, -46, -44, -30, -15, -27,
        1, 7, -8, -64, -43, -16, 9, 8,
        -15, 36, 12, -54, 8, -28, 24, 14,
    ),
}
PESTO_EG = {
    chess.PAWN: (
        0, 0, 0, 0, 0, 0, 0, 0,
        178, 173, 158, 134, 147, 132, 165, 187,
        94, 100, 85, 67, 56, 53, 82, 84,
        32, 24, 13, 5, -2, 4, 17, 17,
        13, 9, -3, -7, -7, -8, 3, -1,
        4, 7, -6, 1, 0, -5, -1, -8,
        13, 8, 8, 10, 13, 0, 2, -7,
        0, 0, 0, 0, 0, 0, 0, 0,
    ),
    chess.KNIGHT: (
        -58, -38, -13, -28, -31, -27, -63, -99,
        -25, -8, -25, -2, -9, -25, -24, -52,
        -24, -20, 10, 9, -1, -9, -19, -41,
        -17, 3, 22, 22, 22, 11, 8, -18,
        -18, -6, 16, 25, 16, 17, 4, -18,
        -23, -3, -1, 15, 10, -3, -20, -22,
        -42, -20, -10, -5, -2, -20, -23, -44,
        -29, -51, -23, -15, -22, -18, -50, -64,
    ),
    chess.BISHOP: (
        -14, -21, -11, -8, -7, -9, -17, -24,
        -8, -4, 7, -12, -3, -13, -4, -14,
        2, -8, 0, -1, -2, 6, 0, 4,
        -3, 9, 12, 9, 14, 10, 3, 2,
        -6, 3, 13, 19, 7, 10, -3, -9,
        -12, -3, 8, 10, 13, 3, -7, -15,
        -14, -18, -7, -1, 4, -9, -15, -27,
        -23, -9, -23, -5, -9, -16, -5, -17,
    ),
    chess.ROOK: (
        13, 10, 18, 15, 12, 12, 8, 5,
        11, 13, 13, 11, -3, 3, 8, 3,
        7, 7, 7, 5, 4, -3, -5, -3,
        4, 3, 13, 1, 2, 1, -1, 2,
        3, 5, 8, 4, -5, -6, -8, -11,
        -4, 0, -5, -1, -7, -12, -8, -16,
        -6, -6, 0, 2, -9, -9, -11, -3,
        -9, 2, 3, -1, -5, -13, 4, -20,
    ),
    chess.QUEEN: (
        -9, 22, 22, 27, 27, 19, 10, 20,
        -17, 20, 32, 41, 58, 25, 30, 0,
        -20, 6, 9, 49, 47, 35, 19, 9,
        3, 22, 24, 45, 57, 40, 57, 36,
        -18, 28, 19, 47, 31, 34, 39, 23,
        -16, -27, 15, 6, 9, 17, 10, 5,
        -22, -23, -30, -16, -16, -23, -36, -32,
        -33, -28, -22, -43, -5, -32, -20, -41,
    ),
    chess.KING: (
        -74, -35, -18, -18, -11, 15, 4, -17,
        -12, 17, 14, 17, 17, 38, 23, 11,
        10, 17, 23, 15, 20, 45, 44, 13,
        -8, 22, 24, 27, 26, 33, 26, 3,
        -18, -4, 21, 24, 27, 23, 9, -11,
        -19, -3, 11, 21, 23, 16, 7, -9,
        -27, -11, 4, 13, 14, 4, -5, -17,
        -53, -34, -21, -11, -28, -14, -24, -43,
    ),
}
# fmt: on


@dataclass(frozen=True)
class MopUp6:
    """Drive the bare (or nearly bare) king to the edge, or to the right corner for KBNK."""

    min_advantage: int = 300
    max_phase: int = 6
    enemy_without_pawns: bool = True
    enemy_center: int = 10  # x Chebyshev distance of the weak king from the centre
    king_manhattan: int = 4  # x (14 - Manhattan distance between the kings)
    edge_bonus: int = 20
    kbnk_corner: bool = False  # KBN vs K: push to a corner of the bishop's colour


@dataclass(frozen=True)
class EvalConfig6:
    """Weights of the Benchmark 6/7 evaluation; zero/False switches a term off."""

    tables: str = "michniewski"  # "michniewski" | "pesto"
    mg_values: tuple[int, ...] = MATERIAL
    eg_values: tuple[int, ...] = MATERIAL
    # pawn structure (cached by pawn placement)
    doubled: int = 15
    isolated: int = 15
    backward: int = 0
    islands: int = 0
    phalanx: int = 0  # pawn with a friendly pawn beside it
    supported: int = 0  # pawn defended by a friendly pawn
    passed: tuple[int, ...] = (0, 5, 10, 20, 40, 70, 120, 0)
    candidate: int = 0  # half-open-file pawn with enough support to become passed
    # passed pawn dynamics
    passer_protected: int = 0
    passer_connected: int = 0
    passer_blocked_pct: int = 0  # bonus kept when the stop square is occupied (0 = off)
    passer_king_distance: int = 0  # endgame weight of king proximity to the queening square
    rook_behind_passer: int = 0
    unstoppable_passer: int = 0  # pawn endgames: rule of the square
    # pieces
    bishop_pair: int = 30
    rook_open: int = 20
    rook_semi_open: int = 10
    rook_seventh: int = 0
    rooks_connected: int = 0
    knight_outpost: int = 0
    bishop_outpost: int = 0
    mobility: tuple[int, int, int, int] | None = None  # safe squares x (N, B, R, Q)
    # king
    king_shield: int = 0
    king_open_file: int = 0
    king_semi_open_file: int = 0
    king_storm: int = 0
    king_danger: int = 0  # 0 = off, else divisor of units^2 (attack units N/B 2, R 3, Q 5)
    # tactics
    threat_pawn: int = 0  # piece attacked by an enemy pawn
    threat_minor: int = 0  # rook/queen attacked by a minor, queen attacked by a rook
    hanging: int = 0  # piece attacked and undefended
    # phases and knowledge
    development: int = 0  # opening-phase term (3-phase evaluation)
    tempo: int = 0
    mopup: MopUp6 | None = None
    scaling: bool = False  # opposite bishops, pawnless small edges, KNN vs K, rook-pawn KPK
    fifty_move_scaling: bool = False
    lazy_margin: int = 0  # > 0: skip activity/passer terms far outside the window


def _pawn_attacks(pawns: int, color: chess.Color) -> int:
    if color == chess.WHITE:
        return (((pawns & NOT_A) << 7) | ((pawns & NOT_H) << 9)) & chess.BB_ALL
    return ((pawns & NOT_A) >> 9) | ((pawns & NOT_H) >> 7)


def _adjacent(file: int) -> int:
    return (chess.BB_FILES[file - 1] if file > 0 else 0) | (
        chess.BB_FILES[file + 1] if file < 7 else 0
    )


ADJACENT_FILES = [_adjacent(file) for file in range(8)]


def _ahead(color: chess.Color, rank: int) -> int:
    ranks = range(rank + 1, 8) if color == chess.WHITE else range(rank)
    mask = 0
    for r in ranks:
        mask |= chess.BB_RANKS[r]
    return mask


def _relative_rank(color: chess.Color, square: int) -> int:
    rank = square >> 3
    return rank if color == chess.WHITE else 7 - rank


FRONT_SPAN = [
    [chess.BB_FILES[sq & 7] & _ahead(color, sq >> 3) for sq in chess.SQUARES]
    for color in (chess.BLACK, chess.WHITE)
]
PASSED_MASKS = [
    [(chess.BB_FILES[sq & 7] | ADJACENT_FILES[sq & 7]) & _ahead(c, sq >> 3) for sq in chess.SQUARES]
    for c in (chess.BLACK, chess.WHITE)
]
ATTACK_SPAN = [
    [ADJACENT_FILES[sq & 7] & _ahead(c, sq >> 3) for sq in chess.SQUARES]
    for c in (chess.BLACK, chess.WHITE)
]
# Own pawns on these squares (adjacent files, same rank or behind) can still support the pawn.
SUPPORT_SPAN = [
    [ADJACENT_FILES[sq & 7] & ~_ahead(c, sq >> 3) & chess.BB_ALL for sq in chess.SQUARES]
    for c in (chess.BLACK, chess.WHITE)
]
KING_ZONE = [
    [
        chess.BB_KING_ATTACKS[sq]
        | chess.BB_SQUARES[sq]
        | (
            (
                (chess.BB_KING_ATTACKS[sq] << 8)
                if c == chess.WHITE
                else (chess.BB_KING_ATTACKS[sq] >> 8)
            )
            & chess.BB_ALL
        )
        for sq in chess.SQUARES
    ]
    for c in (chess.BLACK, chess.WHITE)
]
KING_DANGER_UNITS = (0, 0, 2, 2, 3, 5, 0)


def _center_distance(square: int) -> int:
    file, rank = square & 7, square >> 3
    return max(abs(2 * file - 7), abs(2 * rank - 7)) // 2


def build_pst(config: EvalConfig6) -> list[list[list[int]]]:
    """Packed material + PST value per [colour][piece type][square], owner's perspective."""
    pst: list[list[list[int]]] = [[[0] * 64 for _ in range(7)] for _ in range(2)]
    pesto = config.tables == "pesto"
    for piece_type in PIECE_TYPES:
        if pesto:
            mg_table, eg_table = PESTO_MG[piece_type], PESTO_EG[piece_type]
            mg_value, eg_value = PESTO_MG_VALUES[piece_type], PESTO_EG_VALUES[piece_type]
        else:
            mg_table = PST_TABLES[piece_type]
            eg_table = KING_ENDGAME_TABLE if piece_type == chess.KING else mg_table
            mg_value, eg_value = config.mg_values[piece_type], config.eg_values[piece_type]
        for square in chess.SQUARES:
            white_index = chess.square_mirror(square)
            pst[chess.WHITE][piece_type][square] = pack(
                mg_value + mg_table[white_index], eg_value + eg_table[white_index]
            )
            pst[chess.BLACK][piece_type][square] = pack(
                mg_value + mg_table[square], eg_value + eg_table[square]
            )
    return pst


class Evaluator6:
    """Callable evaluator with per-instance caches (no state shared between bots)."""

    def __init__(self, config: EvalConfig6) -> None:
        self.config = config
        self.pst = build_pst(config)
        self._pawn_cache: dict[tuple[int, int], tuple[int, int, int, int]] = {}
        self._king_cache: dict[tuple[int, int, int, int], int] = {}
        cfg = config
        self._king_terms = bool(
            cfg.king_shield or cfg.king_open_file or cfg.king_semi_open_file or cfg.king_storm
        )
        self._activity = bool(
            cfg.mobility or cfg.king_danger or cfg.threat_pawn or cfg.threat_minor or cfg.hanging
        )
        self._passer_terms = bool(
            cfg.passer_protected
            or cfg.passer_connected
            or cfg.passer_blocked_pct
            or cfg.passer_king_distance
            or cfg.rook_behind_passer
            or cfg.unstoppable_passer
        )

    def clear(self) -> None:
        """Drop the pawn and king caches."""
        self._pawn_cache.clear()
        self._king_cache.clear()

    def pst_sum(self, board: chess.Board) -> int:
        """Packed material + PST total from White's view (the incremental baseline)."""
        black, white = board.occupied_co
        total = 0
        pst_white, pst_black = self.pst[chess.WHITE], self.pst[chess.BLACK]
        for piece_type, mask in (
            (chess.PAWN, board.pawns),
            (chess.KNIGHT, board.knights),
            (chess.BISHOP, board.bishops),
            (chess.ROOK, board.rooks),
            (chess.QUEEN, board.queens),
            (chess.KING, board.kings),
        ):
            table = pst_white[piece_type]
            bits = mask & white
            while bits:
                low = bits & -bits
                total += table[low.bit_length() - 1]
                bits ^= low
            table = pst_black[piece_type]
            bits = mask & black
            while bits:
                low = bits & -bits
                total -= table[low.bit_length() - 1]
                bits ^= low
        return total

    def __call__(self, board: chess.Board, packed: int | None = None) -> int:
        """Return the score for the side to move; ``packed`` is the incremental PST sum."""
        return self.evaluate(board, packed)[0]

    def evaluate(
        self,
        board: chess.Board,
        packed: int | None = None,
        alpha: int | None = None,
        beta: int | None = None,
    ) -> tuple[int, bool]:
        """Return (score, exact) for the side to move.

        With a window and ``lazy_margin`` the expensive terms are skipped when the cheap
        score is already far outside the window; ``exact`` is then False.
        """
        occupied = board.occupied
        if occupied.bit_count() <= 4 and board.is_insufficient_material():
            return 0, True
        cfg = self.config
        if packed is None:
            packed = self.pst_sum(board)
        mg, eg = unpack(packed)
        black, white = board.occupied_co
        pawns = board.pawns
        white_pawns, black_pawns = pawns & white, pawns & black

        pawn_mg, pawn_eg, white_passers, black_passers = self._pawns(white_pawns, black_pawns)
        mg += pawn_mg
        eg += pawn_eg
        if self._king_terms:
            mg += self._kings(board, white_pawns, black_pawns)

        knights, bishops, rooks, queens = board.knights, board.bishops, board.rooks, board.queens
        phase = min(
            MAX_PHASE,
            (knights | bishops).bit_count() + 2 * rooks.bit_count() + 4 * queens.bit_count(),
        )
        piece_mg, piece_eg = self._pieces(board, white, black, white_pawns, black_pawns)
        mg += piece_mg
        eg += piece_eg
        if cfg.development and phase >= 18:
            mg += self._development(board, white, black)
        expensive = self._activity or ((white_passers or black_passers) and self._passer_terms)
        if expensive and cfg.lazy_margin and alpha is not None:
            cheap = self._finish(board, mg, eg, phase, white, black)
            if cheap - cfg.lazy_margin >= beta or cheap + cfg.lazy_margin <= alpha:
                return cheap, False
        if self._activity:
            act_mg, act_eg = self._activity_terms(board, white, black, white_pawns, black_pawns)
            mg += act_mg
            eg += act_eg
        if (white_passers or black_passers) and self._passer_terms:
            pas_mg, pas_eg = self._passer_dynamics(board, white_passers, black_passers, phase)
            mg += pas_mg
            eg += pas_eg
        return self._finish(board, mg, eg, phase, white, black), True

    def _finish(
        self, board: chess.Board, mg: int, eg: int, phase: int, white: int, black: int
    ) -> int:
        """Blend the phases, apply endgame knowledge and return the side-to-move score."""
        cfg = self.config
        score = int((mg * phase + eg * (MAX_PHASE - phase)) / MAX_PHASE)
        if cfg.mopup is not None and phase <= max(cfg.mopup.max_phase, 8):
            score += self._mopup(board, phase)
        if cfg.scaling and phase <= 10:
            score = self._scale(board, score, white, black)
        if cfg.fifty_move_scaling and board.halfmove_clock > 20:
            score = score * max(0, 100 - board.halfmove_clock) // 80
        if board.turn == chess.BLACK:
            score = -score
        return score + cfg.tempo

    # ------------------------------------------------------------------ pawns
    def _pawns(self, white: int, black: int) -> tuple[int, int, int, int]:
        key = (white, black)
        cached = self._pawn_cache.get(key)
        if cached is not None:
            return cached
        w_mg, w_eg, w_passers = self._pawn_side(white, black, chess.WHITE)
        b_mg, b_eg, b_passers = self._pawn_side(black, white, chess.BLACK)
        result = (w_mg - b_mg, w_eg - b_eg, w_passers, b_passers)
        if len(self._pawn_cache) >= CACHE_LIMIT:
            self._pawn_cache.clear()
        self._pawn_cache[key] = result
        return result

    def _pawn_side(self, own: int, enemy: int, color: chess.Color) -> tuple[int, int, int]:
        cfg = self.config
        mg = eg = 0
        files = 0
        for file, file_mask in enumerate(chess.BB_FILES):
            count = (own & file_mask).bit_count()
            if count:
                files |= 1 << file
                if count > 1:
                    mg -= cfg.doubled * (count - 1)
                    eg -= cfg.doubled * (count - 1)
        if cfg.islands:
            islands = bin(files & ~(files << 1)).count("1")
            mg -= cfg.islands * max(islands - 1, 0)
            eg -= cfg.islands * max(islands - 1, 0)
        own_attacks = _pawn_attacks(own, color)
        enemy_attacks = _pawn_attacks(enemy, not color)
        passed_masks = PASSED_MASKS[color]
        passers = 0
        bits = own
        while bits:
            low = bits & -bits
            square = low.bit_length() - 1
            bits ^= low
            file = square & 7
            rel = _relative_rank(color, square)
            isolated = not own & ADJACENT_FILES[file]
            if isolated:
                mg -= cfg.isolated
                eg -= cfg.isolated
            if cfg.phalanx and own & ADJACENT_FILES[file] & chess.BB_RANKS[square >> 3]:
                mg += cfg.phalanx
                eg += cfg.phalanx
            if cfg.supported and low & own_attacks:
                mg += cfg.supported
                eg += cfg.supported
            if not enemy & passed_masks[square]:
                passers |= low
                mg += cfg.passed[rel]
                eg += cfg.passed[rel]
                continue
            if cfg.backward and not isolated:
                stop = square + 8 if color == chess.WHITE else square - 8
                if (
                    0 <= stop < 64
                    and not own & SUPPORT_SPAN[color][square]
                    and chess.BB_SQUARES[stop] & enemy_attacks
                ):
                    mg -= cfg.backward
                    eg -= cfg.backward
            if cfg.candidate and not enemy & FRONT_SPAN[color][square]:
                sentries = (enemy & ATTACK_SPAN[color][square]).bit_count()
                helpers = (own & SUPPORT_SPAN[color][square]).bit_count()
                if helpers >= sentries:
                    mg += cfg.candidate * rel // 2
                    eg += cfg.candidate * rel
        return mg, eg, passers

    def _kings(self, board: chess.Board, white_pawns: int, black_pawns: int) -> int:
        white_king, black_king = board.king(chess.WHITE), board.king(chess.BLACK)
        if white_king is None or black_king is None:
            return 0
        key = (white_pawns, black_pawns, white_king, black_king)
        cached = self._king_cache.get(key)
        if cached is not None:
            return cached
        score = self._king_side(white_pawns, black_pawns, white_king, chess.WHITE)
        score -= self._king_side(black_pawns, white_pawns, black_king, chess.BLACK)
        if len(self._king_cache) >= CACHE_LIMIT:
            self._king_cache.clear()
        self._king_cache[key] = score
        return score

    def _king_side(self, own: int, enemy: int, king: int, color: chess.Color) -> int:
        cfg = self.config
        file, rank = king & 7, king >> 3
        step = 1 if color == chess.WHITE else -1
        score = 0
        for f in range(max(file - 1, 0), min(file + 1, 7) + 1):
            file_mask = chess.BB_FILES[f]
            if cfg.king_shield:
                shield = 0
                for r in (rank + step, rank + 2 * step):
                    if 0 <= r <= 7:
                        shield |= chess.BB_SQUARES[r * 8 + f]
                if not own & shield:
                    score -= cfg.king_shield
            if not own & file_mask:
                score -= cfg.king_semi_open_file if enemy & file_mask else cfg.king_open_file
            if cfg.king_storm:
                storm = 0
                for r in (rank + step, rank + 2 * step, rank + 3 * step):
                    if 0 <= r <= 7:
                        storm |= chess.BB_SQUARES[r * 8 + f]
                if enemy & storm:
                    score -= cfg.king_storm
        return score

    # ----------------------------------------------------------------- pieces
    def _pieces(
        self, board: chess.Board, white: int, black: int, white_pawns: int, black_pawns: int
    ) -> tuple[int, int]:
        cfg = self.config
        mg = eg = 0
        bishops, rooks, knights = board.bishops, board.rooks, board.knights
        pawns = board.pawns
        for color, own, own_pawns, enemy_pawns, sign in (
            (chess.WHITE, white, white_pawns, black_pawns, 1),
            (chess.BLACK, black, black_pawns, white_pawns, -1),
        ):
            score = 0
            if cfg.bishop_pair and (bishops & own).bit_count() >= 2:
                score += cfg.bishop_pair
            own_rooks = rooks & own
            bits = own_rooks
            while bits:
                low = bits & -bits
                bits ^= low
                square = low.bit_length() - 1
                file_mask = chess.BB_FILES[square & 7]
                if not pawns & file_mask:
                    score += cfg.rook_open
                elif not own_pawns & file_mask:
                    score += cfg.rook_semi_open
                if cfg.rook_seventh and _relative_rank(color, square) == 6:
                    score += cfg.rook_seventh
            if cfg.rooks_connected and own_rooks.bit_count() == 2:
                first = own_rooks & -own_rooks
                if board.attacks_mask(first.bit_length() - 1) & (own_rooks ^ first):
                    score += cfg.rooks_connected
            if cfg.knight_outpost or cfg.bishop_outpost:
                own_attacks = _pawn_attacks(own_pawns, color)
                outposts = own_attacks & (
                    chess.BB_RANK_4 | chess.BB_RANK_5 | chess.BB_RANK_6
                    if color == chess.WHITE
                    else chess.BB_RANK_3 | chess.BB_RANK_4 | chess.BB_RANK_5
                )
                for value, mask in (
                    (cfg.knight_outpost, knights & own & outposts),
                    (cfg.bishop_outpost, bishops & own & outposts),
                ):
                    while value and mask:
                        low = mask & -mask
                        mask ^= low
                        if not enemy_pawns & ATTACK_SPAN[color][low.bit_length() - 1]:
                            score += value
            mg += sign * score
            eg += sign * score
        return mg, eg

    def _activity_terms(
        self, board: chess.Board, white: int, black: int, white_pawns: int, black_pawns: int
    ) -> tuple[int, int]:
        """Mobility, king danger and threats from one pass over the piece attacks."""
        cfg = self.config
        weights = cfg.mobility
        occupied = board.occupied
        knights, bishops, rooks, queens, kings = (
            board.knights,
            board.bishops,
            board.rooks,
            board.queens,
            board.kings,
        )
        pawn_attacks = (_pawn_attacks(black_pawns, chess.BLACK), _pawn_attacks(white_pawns, True))
        attacked = [pawn_attacks[0], pawn_attacks[1]]
        minor_attacks = [0, 0]
        rook_attacks = [0, 0]
        mobility = [0, 0]
        danger = [0, 0]
        w_knight, w_bishop, w_rook, w_queen = weights if weights is not None else (0, 0, 0, 0)
        for color, own in ((chess.WHITE, white), (chess.BLACK, black)):
            enemy_king = kings & (black if color else white)
            zone = KING_ZONE[not color][enemy_king.bit_length() - 1] if enemy_king else 0
            safe = ~own & ~pawn_attacks[not color]
            units = attackers = mob = 0
            queen_attacks = minors = heavy = 0
            bits = knights & own
            while bits:
                low = bits & -bits
                bits ^= low
                attacks = KNIGHT_ATTACKS[low.bit_length() - 1]
                minors |= attacks
                mob += w_knight * (attacks & safe).bit_count()
                if attacks & zone:
                    attackers += 1
                    units += 2 * (attacks & zone).bit_count()
            bits = bishops & own
            while bits:
                low = bits & -bits
                bits ^= low
                square = low.bit_length() - 1
                attacks = DIAG_ATTACKS[square][DIAG_MASKS[square] & occupied]
                minors |= attacks
                mob += w_bishop * (attacks & safe).bit_count()
                if attacks & zone:
                    attackers += 1
                    units += 2 * (attacks & zone).bit_count()
            bits = rooks & own
            while bits:
                low = bits & -bits
                bits ^= low
                square = low.bit_length() - 1
                attacks = (
                    FILE_ATTACKS[square][FILE_MASKS[square] & occupied]
                    | RANK_ATTACKS[square][RANK_MASKS[square] & occupied]
                )
                heavy |= attacks
                mob += w_rook * (attacks & safe).bit_count()
                if attacks & zone:
                    attackers += 1
                    units += 3 * (attacks & zone).bit_count()
            bits = queens & own
            while bits:
                low = bits & -bits
                bits ^= low
                square = low.bit_length() - 1
                attacks = (
                    DIAG_ATTACKS[square][DIAG_MASKS[square] & occupied]
                    | FILE_ATTACKS[square][FILE_MASKS[square] & occupied]
                    | RANK_ATTACKS[square][RANK_MASKS[square] & occupied]
                )
                queen_attacks |= attacks
                mob += w_queen * (attacks & safe).bit_count()
                if attacks & zone:
                    attackers += 1
                    units += 5 * (attacks & zone).bit_count()
            attacked[color] |= queen_attacks | minors | heavy
            minor_attacks[color] = minors
            rook_attacks[color] = heavy
            mobility[color] = mob
            if cfg.king_danger and queens & own and attackers >= 2:
                danger[color] = min(units * units // cfg.king_danger, 600)

        mg = mobility[chess.WHITE] - mobility[chess.BLACK]
        eg = mg
        mg += danger[chess.WHITE] - danger[chess.BLACK]
        threat_score = 0
        if cfg.threat_pawn or cfg.threat_minor or cfg.hanging:
            for color, own in ((chess.WHITE, white), (chess.BLACK, black)):
                king = kings & own
                if king:
                    attacked[color] |= chess.BB_KING_ATTACKS[king.bit_length() - 1]
            for color, own, sign in ((chess.WHITE, white, 1), (chess.BLACK, black, -1)):
                enemy = not color
                pieces = own & ~board.pawns & ~kings
                score = 0
                if cfg.threat_pawn:
                    score -= cfg.threat_pawn * (pieces & pawn_attacks[enemy]).bit_count()
                if cfg.threat_minor:
                    score -= cfg.threat_minor * (
                        (own & (rooks | queens) & minor_attacks[enemy]).bit_count()
                        + (own & queens & rook_attacks[enemy]).bit_count()
                    )
                if cfg.hanging:
                    loose = pieces & attacked[enemy] & ~attacked[color]
                    score -= cfg.hanging * loose.bit_count()
                threat_score += sign * score
        return mg + threat_score, eg + threat_score

    def _passer_dynamics(
        self, board: chess.Board, white_passers: int, black_passers: int, phase: int
    ) -> tuple[int, int]:
        cfg = self.config
        mg = eg = 0
        occupied = board.occupied
        pawn_only = not (board.occupied & ~board.pawns & ~board.kings)
        for color, passers, sign in (
            (chess.WHITE, white_passers, 1),
            (chess.BLACK, black_passers, -1),
        ):
            own = board.occupied_co[color]
            own_pawns = board.pawns & own
            own_king = board.king(color)
            enemy_king = board.king(not color)
            support = _pawn_attacks(own_pawns, color)
            bits = passers
            while bits:
                low = bits & -bits
                bits ^= low
                square = low.bit_length() - 1
                rel = _relative_rank(color, square)
                base = cfg.passed[rel]
                s_mg = s_eg = 0
                if cfg.passer_protected and low & support:
                    s_mg += cfg.passer_protected // 2
                    s_eg += cfg.passer_protected
                if cfg.passer_connected and passers & ADJACENT_FILES[square & 7]:
                    s_mg += cfg.passer_connected // 2
                    s_eg += cfg.passer_connected
                stop = square + 8 if color == chess.WHITE else square - 8
                if cfg.passer_blocked_pct and 0 <= stop < 64 and occupied & chess.BB_SQUARES[stop]:
                    s_eg -= base * (100 - cfg.passer_blocked_pct) // 100
                promotion = (square & 7) + (56 if color == chess.WHITE else 0)
                if cfg.passer_king_distance and rel >= 3 and own_king is not None:
                    if enemy_king is not None:
                        weight = cfg.passer_king_distance * (rel - 2)
                        s_eg += weight * (
                            chess.square_distance(enemy_king, promotion)
                            - chess.square_distance(own_king, promotion) // 2
                        )
                if cfg.rook_behind_passer:
                    behind = FRONT_SPAN[not color][square]
                    if board.rooks & own & behind:
                        s_eg += cfg.rook_behind_passer
                if cfg.unstoppable_passer and pawn_only and enemy_king is not None:
                    distance = 7 - rel
                    if board.turn != color:
                        distance += 1
                    if chess.square_distance(enemy_king, promotion) > distance:
                        s_eg += cfg.unstoppable_passer
                mg += sign * s_mg
                eg += sign * s_eg
        return mg, eg

    def _development(self, board: chess.Board, white: int, black: int) -> int:
        """Opening phase: undeveloped minors, early queen trips and uncastled kings."""
        cfg = self.config
        score = 0
        for own, home, queen_home, castled, sign in (
            (
                white,
                chess.BB_B1 | chess.BB_C1 | chess.BB_F1 | chess.BB_G1,
                chess.BB_D1,
                chess.BB_G1 | chess.BB_C1 | chess.BB_B1 | chess.BB_H1,
                1,
            ),
            (
                black,
                chess.BB_B8 | chess.BB_C8 | chess.BB_F8 | chess.BB_G8,
                chess.BB_D8,
                chess.BB_G8 | chess.BB_C8 | chess.BB_B8 | chess.BB_H8,
                -1,
            ),
        ):
            minors = own & (board.knights | board.bishops)
            undeveloped = (minors & home).bit_count()
            value = -cfg.development * undeveloped
            queen = board.queens & own
            if queen and not queen & queen_home and undeveloped >= 2:
                value -= cfg.development
            if board.kings & own & castled:
                value += cfg.development
            score += sign * value
        return score

    # -------------------------------------------------------------- endgames
    def _mopup(self, board: chess.Board, phase: int) -> int:
        mop = self.config.mopup
        pawns = board.pawns
        black, white = board.occupied_co
        material_white = 0
        material_black = 0
        for piece_type, mask in (
            (chess.PAWN, pawns),
            (chess.KNIGHT, board.knights),
            (chess.BISHOP, board.bishops),
            (chess.ROOK, board.rooks),
            (chess.QUEEN, board.queens),
        ):
            material_white += MATERIAL[piece_type] * (mask & white).bit_count()
            material_black += MATERIAL[piece_type] * (mask & black).bit_count()
        diff = material_white - material_black
        if abs(diff) < mop.min_advantage:
            return 0
        strong = chess.WHITE if diff > 0 else chess.BLACK
        weak_pawns = pawns & (black if strong == chess.WHITE else white)
        if phase > mop.max_phase and not (mop.enemy_without_pawns and not weak_pawns):
            return 0
        own_king, enemy_king = board.king(strong), board.king(not strong)
        if own_king is None or enemy_king is None:
            return 0
        bonus = mop.enemy_center * _center_distance(enemy_king)
        bonus += mop.king_manhattan * (14 - chess.square_manhattan_distance(own_king, enemy_king))
        if mop.edge_bonus and ((enemy_king >> 3) in (0, 7) or (enemy_king & 7) in (0, 7)):
            bonus += mop.edge_bonus
        if mop.kbnk_corner:
            own = white if strong == chess.WHITE else black
            if (
                not pawns
                and (board.knights & own).bit_count() == 1
                and (board.bishops & own).bit_count() == 1
                and not board.rooks
                and not board.queens
            ):
                light = bool(board.bishops & own & LIGHT_SQUARES)
                corners = (chess.H1, chess.A8) if light else (chess.A1, chess.H8)
                nearest = min(chess.square_distance(enemy_king, corner) for corner in corners)
                bonus += 25 * (7 - nearest)
        return bonus if strong == chess.WHITE else -bonus

    def _scale(self, board: chess.Board, score: int, white: int, black: int) -> int:
        """Shrink scores of drawish endgames towards zero."""
        if score == 0:
            return 0
        strong_white = score > 0
        strong = white if strong_white else black
        weak = black if strong_white else white
        pawns = board.pawns
        bishops = board.bishops
        others = board.knights | board.rooks | board.queens
        if (
            not others
            and (bishops & white).bit_count() == 1
            and (bishops & black).bit_count() == 1
            and bool(bishops & white & LIGHT_SQUARES) != bool(bishops & black & LIGHT_SQUARES)
        ):
            return score // 2
        strong_pawns = pawns & strong
        if not strong_pawns:
            strong_material = sum(
                MATERIAL[pt] * (board.pieces_mask(pt, True if strong_white else False)).bit_count()
                for pt in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN)
            )
            weak_material = sum(
                MATERIAL[pt] * (board.pieces_mask(pt, False if strong_white else True)).bit_count()
                for pt in (chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN)
            )
            if strong_material - weak_material < 400:
                return score // 8
            if (board.knights & strong).bit_count() == 2 and not (
                (board.bishops | board.rooks | board.queens) & strong
            ):
                return score // 10
        if (
            strong_pawns.bit_count() == 1
            and not (board.occupied & ~pawns & ~board.kings)
            and not pawns & weak
            and strong_pawns & (chess.BB_FILE_A | chess.BB_FILE_H)
        ):
            weak_king = board.king(not strong_white)
            pawn_square = strong_pawns.bit_length() - 1
            corner = (pawn_square & 7) + (56 if strong_white else 0)
            if weak_king is not None and chess.square_distance(weak_king, corner) <= 1:
                return score // 10
        return score
