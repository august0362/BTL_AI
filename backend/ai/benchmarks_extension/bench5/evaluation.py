"""Tapered evaluation shared by the Benchmark 5 bots; each profile picks its own terms.

Scores are centipawns from the side to move's view. Middlegame and endgame scores are
blended by the game phase (knight/bishop 1, rook 2, queen 4, capped at 24).
"""

from __future__ import annotations

from dataclasses import dataclass

import chess

from ai.benchmarks_extension.bench5.tables import KING_ENDGAME_TABLE, MOBILITY_WEIGHTS, PST_TABLES

MAX_PHASE = 24
PIECE_TYPES = (chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN, chess.KING)
CACHE_LIMIT = 100_000


@dataclass(frozen=True)
class MopUp:
    """Bonus for the side ahead in material that drives the enemy king to the edge."""

    min_advantage: int
    max_phase: int = MAX_PHASE  # active when phase <= max_phase ...
    enemy_without_pawns: bool = False  # ... or when the losing side has no pawns
    max_non_pawn: int = 0  # > 0: also requires total non-pawn material <= this
    enemy_center: int = 0  # x Chebyshev distance of the enemy king from the centre (0..3)
    king_manhattan: int = 0  # x (14 - Manhattan distance between the kings)
    king_chebyshev: int = 0  # x (14 - Chebyshev distance between the kings)
    own_center: int = 0  # x (4 - Chebyshev distance of the own king from the centre)
    chase_passer: int = 0  # x (7 - distance from the own king to the nearest enemy passer)
    edge_bonus: int = 0  # enemy king on its first or last rank


@dataclass(frozen=True)
class EvalConfig:
    """Weights of the evaluation terms; zero switches a term off."""

    mg_values: tuple[int, ...] = (0, 100, 320, 330, 500, 900, 0)
    eg_values: tuple[int, ...] = (0, 100, 320, 330, 500, 900, 0)
    doubled: int = 0
    isolated: int = 0
    passed: tuple[int, ...] = (0, 0, 0, 0, 0, 0, 0, 0)  # by ranks advanced from home
    islands: int = 0  # per pawn island beyond the first
    bishop_pair: int = 0
    rook_open: int = 0
    rook_semi_open: int = 0
    rook_seventh: int = 0
    knight_outpost: int = 0
    king_shield: int = 0  # middlegame, per king-zone file without a shield pawn
    king_open_file: int = 0  # middlegame, per king-zone file without any pawn
    king_semi_open_file: int = 0  # middlegame, per king-zone file without an own pawn
    mobility: bool = False  # Benchmark 4 mobility weights
    tempo: int = 0
    mopup: MopUp | None = None


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


PASSED_MASKS = [
    [
        (chess.BB_FILES[chess.square_file(sq)] | ADJACENT_FILES[chess.square_file(sq)])
        & _ahead(color, chess.square_rank(sq))
        for sq in chess.SQUARES
    ]
    for color in (chess.BLACK, chess.WHITE)
]
# Enemy pawns on these squares could one day attack a piece on the square.
OUTPOST_MASKS = [
    [
        ADJACENT_FILES[chess.square_file(sq)] & _ahead(color, chess.square_rank(sq))
        for sq in chess.SQUARES
    ]
    for color in (chess.BLACK, chess.WHITE)
]


def _center_distance(square: int) -> int:
    file, rank = chess.square_file(square), chess.square_rank(square)
    return max(abs(2 * file - 7), abs(2 * rank - 7)) // 2


def _relative_rank(color: chess.Color, square: int) -> int:
    rank = chess.square_rank(square)
    return rank if color == chess.WHITE else 7 - rank


class Evaluator5:
    """Callable evaluator with per-instance caches (no state shared between bots)."""

    def __init__(self, config: EvalConfig) -> None:
        self.config = config
        self._mg: list[list[list[int]]] = [[[]], [[]]]
        self._eg: list[list[list[int]]] = [[[]], [[]]]
        for color in (chess.BLACK, chess.WHITE):
            for piece_type in PIECE_TYPES:
                table = PST_TABLES[piece_type]
                eg_table = KING_ENDGAME_TABLE if piece_type == chess.KING else table
                index = chess.square_mirror if color == chess.WHITE else (lambda square: square)
                self._mg[color].append(
                    [config.mg_values[piece_type] + table[index(sq)] for sq in chess.SQUARES]
                )
                self._eg[color].append(
                    [config.eg_values[piece_type] + eg_table[index(sq)] for sq in chess.SQUARES]
                )
        self._pawn_cache: dict[tuple[int, int], tuple[int, int]] = {}
        self._king_cache: dict[tuple[int, int, int, int], int] = {}
        self._king_terms = bool(
            config.king_shield or config.king_open_file or config.king_semi_open_file
        )

    def clear(self) -> None:
        """Drop the pawn and king caches."""
        self._pawn_cache.clear()
        self._king_cache.clear()

    def __call__(self, board: chess.Board) -> int:
        """Return the score of ``board`` for the side to move."""
        occupied = board.occupied
        if occupied.bit_count() <= 4 and board.is_insufficient_material():
            return 0
        cfg = self.config
        black, white = board.occupied_co
        mg = eg = 0
        for piece_type, mask in (
            (chess.PAWN, board.pawns),
            (chess.KNIGHT, board.knights),
            (chess.BISHOP, board.bishops),
            (chess.ROOK, board.rooks),
            (chess.QUEEN, board.queens),
            (chess.KING, board.kings),
        ):
            mg_w, eg_w = self._mg[chess.WHITE][piece_type], self._eg[chess.WHITE][piece_type]
            bits = mask & white
            while bits:
                low = bits & -bits
                square = low.bit_length() - 1
                mg += mg_w[square]
                eg += eg_w[square]
                bits ^= low
            mg_b, eg_b = self._mg[chess.BLACK][piece_type], self._eg[chess.BLACK][piece_type]
            bits = mask & black
            while bits:
                low = bits & -bits
                square = low.bit_length() - 1
                mg -= mg_b[square]
                eg -= eg_b[square]
                bits ^= low

        white_pawns, black_pawns = board.pawns & white, board.pawns & black
        pawn_mg, pawn_eg = self._pawns(white_pawns, black_pawns)
        mg += pawn_mg
        eg += pawn_eg
        if self._king_terms:
            mg += self._kings(board, white_pawns, black_pawns)
        pieces = self._pieces(board, chess.WHITE) - self._pieces(board, chess.BLACK)
        mg += pieces
        eg += pieces

        phase = min(
            MAX_PHASE,
            (board.knights | board.bishops).bit_count()
            + 2 * board.rooks.bit_count()
            + 4 * board.queens.bit_count(),
        )
        score = int((mg * phase + eg * (MAX_PHASE - phase)) / MAX_PHASE)
        if cfg.mopup is not None:
            score += self._mopup(board, phase)
        if board.turn == chess.BLACK:
            score = -score
        return score + cfg.tempo

    def _pawns(self, white: int, black: int) -> tuple[int, int]:
        key = (white, black)
        cached = self._pawn_cache.get(key)
        if cached is not None:
            return cached
        mg_w, eg_w = self._pawn_side(white, black, chess.WHITE)
        mg_b, eg_b = self._pawn_side(black, white, chess.BLACK)
        result = (mg_w - mg_b, eg_w - eg_b)
        if len(self._pawn_cache) >= CACHE_LIMIT:
            self._pawn_cache.clear()
        self._pawn_cache[key] = result
        return result

    def _pawn_side(self, own: int, enemy: int, color: chess.Color) -> tuple[int, int]:
        cfg = self.config
        score = 0
        files = 0
        for file, file_mask in enumerate(chess.BB_FILES):
            count = (own & file_mask).bit_count()
            if count:
                files |= 1 << file
                if count > 1:
                    score -= cfg.doubled * (count - 1)
        if cfg.islands:
            islands = bin(files & ~(files << 1)).count("1")
            score -= cfg.islands * max(islands - 1, 0)
        passed_masks = PASSED_MASKS[color]
        passed = 0
        bits = own
        while bits:
            low = bits & -bits
            square = low.bit_length() - 1
            bits ^= low
            if cfg.isolated and not own & ADJACENT_FILES[square & 7]:
                score -= cfg.isolated
            if not enemy & passed_masks[square]:
                passed += cfg.passed[_relative_rank(color, square)]
        return score + passed, score + passed

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
        file, rank = chess.square_file(king), chess.square_rank(king)
        step = 1 if color == chess.WHITE else -1
        score = 0
        for f in range(max(file - 1, 0), min(file + 1, 7) + 1):
            file_mask = chess.BB_FILES[f]
            if cfg.king_shield:
                shield = 0
                for r in (rank + step, rank + 2 * step):
                    if 0 <= r <= 7:
                        shield |= chess.BB_SQUARES[chess.square(f, r)]
                if not own & shield:
                    score -= cfg.king_shield
            if not own & file_mask:
                score -= cfg.king_semi_open_file if enemy & file_mask else cfg.king_open_file
        return score

    def _pieces(self, board: chess.Board, color: chess.Color) -> int:
        cfg = self.config
        own = board.occupied_co[color]
        score = 0
        if cfg.bishop_pair and (board.bishops & own).bit_count() >= 2:
            score += cfg.bishop_pair
        own_pawns = board.pawns & own
        rooks = board.rooks & own
        while rooks:
            low = rooks & -rooks
            rooks ^= low
            square = low.bit_length() - 1
            file_mask = chess.BB_FILES[square & 7]
            if not board.pawns & file_mask:
                score += cfg.rook_open
            elif not own_pawns & file_mask:
                score += cfg.rook_semi_open
            if cfg.rook_seventh and _relative_rank(color, square) == 6:
                score += cfg.rook_seventh
        if cfg.knight_outpost:
            enemy_pawns = board.pawns & board.occupied_co[not color]
            knights = board.knights & own
            while knights:
                low = knights & -knights
                knights ^= low
                square = low.bit_length() - 1
                if (
                    3 <= _relative_rank(color, square) <= 5
                    and chess.BB_PAWN_ATTACKS[not color][square] & own_pawns
                    and not enemy_pawns & OUTPOST_MASKS[color][square]
                ):
                    score += cfg.knight_outpost
        if cfg.mobility:
            not_own = ~own
            for piece_type, weight in MOBILITY_WEIGHTS:
                bits = board.pieces_mask(piece_type, color)
                while bits:
                    low = bits & -bits
                    bits ^= low
                    score += (
                        weight * (board.attacks_mask(low.bit_length() - 1) & not_own).bit_count()
                    )
        return score

    def _mopup(self, board: chess.Board, phase: int) -> int:
        cfg = self.config
        mop = cfg.mopup
        values = cfg.mg_values
        material = [0, 0]
        non_pawn = 0
        for piece_type in (chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN):
            for color in (chess.BLACK, chess.WHITE):
                count = board.pieces_mask(piece_type, color).bit_count()
                material[color] += values[piece_type] * count
                if piece_type != chess.PAWN:
                    non_pawn += values[piece_type] * count
        diff = material[chess.WHITE] - material[chess.BLACK]
        if abs(diff) < mop.min_advantage:
            return 0
        strong = chess.WHITE if diff > 0 else chess.BLACK
        weak = not strong
        if mop.max_non_pawn and non_pawn > mop.max_non_pawn:
            return 0
        weak_pawns = board.pawns & board.occupied_co[weak]
        if phase > mop.max_phase and not (mop.enemy_without_pawns and not weak_pawns):
            return 0
        own_king, enemy_king = board.king(strong), board.king(weak)
        if own_king is None or enemy_king is None:
            return 0
        bonus = mop.enemy_center * _center_distance(enemy_king)
        bonus += mop.king_manhattan * (14 - chess.square_manhattan_distance(own_king, enemy_king))
        bonus += mop.king_chebyshev * (14 - chess.square_distance(own_king, enemy_king))
        bonus += mop.own_center * (4 - _center_distance(own_king))
        if mop.chase_passer:
            passers = [
                square
                for square in chess.SquareSet(weak_pawns)
                if not board.pawns & board.occupied_co[strong] & PASSED_MASKS[weak][square]
            ]
            if passers:
                nearest = min(chess.square_distance(own_king, square) for square in passers)
                bonus += mop.chase_passer * (7 - nearest)
        if mop.edge_bonus and chess.square_rank(enemy_king) in (0, 7):
            bonus += mop.edge_bonus
        return bonus if strong == chess.WHITE else -bonus
