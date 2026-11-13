"""Static board evaluation used by the Genetic Alpha-Beta bot.

Material uses the fixed `PIECE_VALUES` shared with search; positional knowledge
comes from the evolved genome (tapered piece-square tables plus structural
terms). `game_phase` blends the midgame and endgame tables.
"""

from __future__ import annotations

import chess

from ai.genetic_alphabeta.genome import (
    PIECE_VALUES,
    PST_PIECE_TYPES,
    PST_SLOT,
    PST_SLOT_MIRROR,
    Genome,
)

# Phase weights: knight/bishop 1, rook 2, queen 4; full material = 24.
PHASE_MAX = 24

CENTER_BB = 0
for _file in range(2, 6):
    for _rank in range(2, 6):
        CENTER_BB |= chess.BB_SQUARES[chess.square(_file, _rank)]

CENTER_SQUARES = frozenset(chess.square(file, rank) for file in range(2, 6) for rank in range(2, 6))

_MATERIAL_TYPES = (chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN)

# Squares ahead of `square` for pawn-passed detection, per color.
_ADJACENT_FILES = [
    (chess.BB_FILES[f - 1] if f > 0 else 0) | (chess.BB_FILES[f + 1] if f < 7 else 0)
    for f in range(8)
]


def _ahead_mask(color: chess.Color, rank: int) -> int:
    """Bitboard of ranks in front of `rank` from `color`'s side."""
    ranks = range(rank + 1, 8) if color == chess.WHITE else range(0, rank)
    mask = 0
    for r in ranks:
        mask |= chess.BB_RANKS[r]
    return mask


_PASSED_MASKS = {
    color: [
        (chess.BB_FILES[chess.square_file(sq)] | _ADJACENT_FILES[chess.square_file(sq)])
        & _ahead_mask(color, chess.square_rank(sq))
        for sq in chess.SQUARES
    ]
    for color in (chess.WHITE, chess.BLACK)
}

_STRUCTURE_CACHE: dict[tuple[int, int], tuple[int, int, int]] = {}
STRUCTURE_CACHE_LIMIT = 32768


def center_count(board: chess.Board, color: chess.Color) -> int:
    """Count `color` pieces standing on the central 4x4 squares (c3-f6)."""
    return (board.occupied_co[color] & CENTER_BB).bit_count()


def mobility_count(board: chess.Board, color: chess.Color) -> int:
    """Count squares attacked by `color` pieces (excluding own-occupied ones).

    Uses python-chess attack tables directly, per piece type, instead of
    ``Board.attacks_mask``: the per-piece type dispatch cost dominated leaf
    evaluation. Results are identical to the bitboard version.
    """
    own = board.occupied_co[color]
    not_own = ~own
    occupied = board.occupied
    total = 0
    knights = board.knights & own
    while knights:
        square = (knights & -knights).bit_length() - 1
        knights &= knights - 1
        total += (chess.BB_KNIGHT_ATTACKS[square] & not_own).bit_count()
    bishops = board.bishops & own
    while bishops:
        square = (bishops & -bishops).bit_length() - 1
        bishops &= bishops - 1
        attacks = chess.BB_DIAG_ATTACKS[square][chess.BB_DIAG_MASKS[square] & occupied]
        total += (attacks & not_own).bit_count()
    rooks = board.rooks & own
    while rooks:
        square = (rooks & -rooks).bit_length() - 1
        rooks &= rooks - 1
        attacks = (
            chess.BB_RANK_ATTACKS[square][chess.BB_RANK_MASKS[square] & occupied]
            | chess.BB_FILE_ATTACKS[square][chess.BB_FILE_MASKS[square] & occupied]
        )
        total += (attacks & not_own).bit_count()
    queens = board.queens & own
    while queens:
        square = (queens & -queens).bit_length() - 1
        queens &= queens - 1
        attacks = chess.BB_DIAG_ATTACKS[square][chess.BB_DIAG_MASKS[square] & occupied]
        attacks |= (
            chess.BB_RANK_ATTACKS[square][chess.BB_RANK_MASKS[square] & occupied]
            | chess.BB_FILE_ATTACKS[square][chess.BB_FILE_MASKS[square] & occupied]
        )
        total += (attacks & not_own).bit_count()
    return total


def shield_count(board: chess.Board, color: chess.Color) -> int:
    """Count friendly pawns adjacent to the king (pawn shield)."""
    king = board.king(color)
    if king is None:
        return 0
    return (board.pawns & board.occupied_co[color] & chess.BB_KING_ATTACKS[king]).bit_count()


def _pawn_counts(own: int, enemy: int, color: chess.Color) -> tuple[int, int, int]:
    """Return (doubled, isolated, passed) pawn counts for one side's bitboards."""
    doubled = sum(max(0, (own & file_mask).bit_count() - 1) for file_mask in chess.BB_FILES)
    isolated = 0
    passed = 0
    masks = _PASSED_MASKS[color]
    remaining = own
    while remaining:
        low = remaining & -remaining
        square = low.bit_length() - 1
        remaining ^= low
        if not own & _ADJACENT_FILES[chess.square_file(square)]:
            isolated += 1
        if not enemy & masks[square]:
            passed += 1
    return doubled, isolated, passed


def structure_diffs(board: chess.Board) -> tuple[int, int, int]:
    """White-minus-Black (doubled, isolated, passed) diffs, cached by pawn placement."""
    white = board.pawns & board.occupied_co[chess.WHITE]
    black = board.pawns & board.occupied_co[chess.BLACK]
    key = (white, black)
    cached = _STRUCTURE_CACHE.get(key)
    if cached is not None:
        return cached
    white_counts = _pawn_counts(white, black, chess.WHITE)
    black_counts = _pawn_counts(black, white, chess.BLACK)
    diffs = (
        white_counts[0] - black_counts[0],
        white_counts[1] - black_counts[1],
        white_counts[2] - black_counts[2],
    )
    if len(_STRUCTURE_CACHE) >= STRUCTURE_CACHE_LIMIT:
        _STRUCTURE_CACHE.clear()
    _STRUCTURE_CACHE[key] = diffs
    return diffs


def doubled_count(board: chess.Board, color: chess.Color) -> int:
    """Count extra pawns stacked on the same file (beyond the first)."""
    own = board.pawns & board.occupied_co[color]
    return sum(max(0, (own & file_mask).bit_count() - 1) for file_mask in chess.BB_FILES)


def isolated_count(board: chess.Board, color: chess.Color) -> int:
    """Count pawns with no friendly pawn on an adjacent file."""
    own = board.pawns & board.occupied_co[color]
    total = 0
    remaining = own
    while remaining:
        low = remaining & -remaining
        square = low.bit_length() - 1
        remaining ^= low
        if not own & _ADJACENT_FILES[chess.square_file(square)]:
            total += 1
    return total


def passed_count(board: chess.Board, color: chess.Color) -> int:
    """Count passed pawns (no enemy pawn ahead on the same/adjacent files)."""
    own = board.pawns & board.occupied_co[color]
    enemy = board.pawns & board.occupied_co[not color]
    masks = _PASSED_MASKS[color]
    total = 0
    remaining = own
    while remaining:
        low = remaining & -remaining
        square = low.bit_length() - 1
        remaining ^= low
        if not enemy & masks[square]:
            total += 1
    return total


def has_bishop_pair(board: chess.Board, color: chess.Color) -> int:
    """1 when `color` owns both bishops, else 0."""
    return 1 if board.pieces_mask(chess.BISHOP, color).bit_count() >= 2 else 0


def rook_open_score(board: chess.Board, color: chess.Color) -> float:
    """Open-file credit for rooks: 1.0 on open files, 0.5 on semi-open files."""
    own_pawns = board.pawns & board.occupied_co[color]
    score = 0.0
    rooks = board.pieces_mask(chess.ROOK, color)
    while rooks:
        low = rooks & -rooks
        rooks ^= low
        file_mask = chess.BB_FILES[(low.bit_length() - 1) & 7]
        if not board.pawns & file_mask:
            score += 1.0
        elif not own_pawns & file_mask:
            score += 0.5
    return score


def game_phase(board: chess.Board) -> float:
    """Return 1.0 for a full midgame position and 0.0 for a bare endgame."""
    phase = (board.knights | board.bishops).bit_count()
    phase += 2 * board.rooks.bit_count()
    phase += 4 * board.queens.bit_count()
    return min(phase, PHASE_MAX) / PHASE_MAX


def _pst_score(board: chess.Board, color: chess.Color, genome: Genome, phase: float) -> float:
    """Tapered piece-square score of `color`'s pieces (White point of view slots)."""
    slots = PST_SLOT_MIRROR if color == chess.BLACK else PST_SLOT
    endgame_weight = 1.0 - phase
    total = 0.0
    for index, piece_type in enumerate(PST_PIECE_TYPES):
        squares = board.pieces_mask(piece_type, color)
        midgame_row = genome.pst_mg[index]
        endgame_row = genome.pst_eg[index]
        while squares:
            low = squares & -squares
            squares ^= low
            slot = slots[low.bit_length() - 1]
            total += midgame_row[slot] * phase + endgame_row[slot] * endgame_weight
    return total


def evaluate(board: chess.Board, genome: Genome) -> float:
    """Score the position in pawn units from White's perspective.

    The board is never mutated. Positive favors White, negative favors Black.
    Material is fixed; the genome supplies tapered piece-square tables and the
    structural terms, where doubled/isolated weights are positive magnitudes
    subtracted like penalties. Structural terms whose gene is 0.0 are skipped,
    so an untrained genome only pays for material and table lookups.
    """
    score = 0.0
    for piece_type in _MATERIAL_TYPES:
        score += PIECE_VALUES[piece_type] * (
            board.pieces_mask(piece_type, chess.WHITE).bit_count()
            - board.pieces_mask(piece_type, chess.BLACK).bit_count()
        )
    phase = game_phase(board)
    score += _pst_score(board, chess.WHITE, genome, phase)
    score -= _pst_score(board, chess.BLACK, genome, phase)
    if genome.center:
        score += genome.center * (
            (board.occupied_co[chess.WHITE] & CENTER_BB).bit_count()
            - (board.occupied_co[chess.BLACK] & CENTER_BB).bit_count()
        )
    if genome.mobility:
        score += genome.mobility * (
            mobility_count(board, chess.WHITE) - mobility_count(board, chess.BLACK)
        )
    if genome.shield:
        score += genome.shield * (
            shield_count(board, chess.WHITE) - shield_count(board, chess.BLACK)
        )
    if genome.doubled or genome.isolated or genome.passed:
        doubled, isolated, passed = structure_diffs(board)
        score -= genome.doubled * doubled
        score -= genome.isolated * isolated
        score += genome.passed * passed
    if genome.bishop_pair:
        score += genome.bishop_pair * (
            has_bishop_pair(board, chess.WHITE) - has_bishop_pair(board, chess.BLACK)
        )
    if genome.rook_open:
        score += genome.rook_open * (
            rook_open_score(board, chess.WHITE) - rook_open_score(board, chess.BLACK)
        )
    score += genome.tempo if board.turn == chess.WHITE else -genome.tempo
    return score
