"""Modular evaluation functions for the benchmark alpha-beta bots.

Every evaluator returns a score from the perspective of the side to move, so the
search can use plain negamax. Benchmark 2 reuses ``ai.baseline.evaluate`` through
``material_evaluator``; Benchmark 4 can swap in any function registered here.
"""

from __future__ import annotations

from collections.abc import Callable

import chess

from ai.baseline import PIECE_VALUES, evaluate

MATE_SCORE = 99999

CENTRAL_SQUARES = frozenset({chess.D4, chess.E4, chess.D5, chess.E5})
DEVELOPMENT_SQUARES = frozenset(
    {chess.C3, chess.D3, chess.E3, chess.F3, chess.C6, chess.D6, chess.E6, chess.F6}
)
CENTRAL_BONUS = 20
DEVELOPMENT_BONUS = 8

# Piece-square tables ("Simplified Evaluation Function", Tomasz Michniewski) from White's
# view: index 0 is a8, index 63 is h1. White looks up square_mirror(square), Black the square.
# fmt: off
PST_TABLES: dict[chess.PieceType, tuple[int, ...]] = {
    chess.PAWN: (
        0, 0, 0, 0, 0, 0, 0, 0,
        50, 50, 50, 50, 50, 50, 50, 50,
        10, 10, 20, 30, 30, 20, 10, 10,
        5, 5, 10, 25, 25, 10, 5, 5,
        0, 0, 0, 20, 20, 0, 0, 0,
        5, -5, -10, 0, 0, -10, -5, 5,
        5, 10, 10, -20, -20, 10, 10, 5,
        0, 0, 0, 0, 0, 0, 0, 0,
    ),
    chess.KNIGHT: (
        -50, -40, -30, -30, -30, -30, -40, -50,
        -40, -20, 0, 0, 0, 0, -20, -40,
        -30, 0, 10, 15, 15, 10, 0, -30,
        -30, 5, 15, 20, 20, 15, 5, -30,
        -30, 0, 15, 20, 20, 15, 0, -30,
        -30, 5, 10, 15, 15, 10, 5, -30,
        -40, -20, 0, 5, 5, 0, -20, -40,
        -50, -40, -30, -30, -30, -30, -40, -50,
    ),
    chess.BISHOP: (
        -20, -10, -10, -10, -10, -10, -10, -20,
        -10, 0, 0, 0, 0, 0, 0, -10,
        -10, 0, 5, 10, 10, 5, 0, -10,
        -10, 5, 5, 10, 10, 5, 5, -10,
        -10, 0, 10, 10, 10, 10, 0, -10,
        -10, 10, 10, 10, 10, 10, 10, -10,
        -10, 5, 0, 0, 0, 0, 5, -10,
        -20, -10, -10, -10, -10, -10, -10, -20,
    ),
    chess.ROOK: (
        0, 0, 0, 0, 0, 0, 0, 0,
        5, 10, 10, 10, 10, 10, 10, 5,
        -5, 0, 0, 0, 0, 0, 0, -5,
        -5, 0, 0, 0, 0, 0, 0, -5,
        -5, 0, 0, 0, 0, 0, 0, -5,
        -5, 0, 0, 0, 0, 0, 0, -5,
        -5, 0, 0, 0, 0, 0, 0, -5,
        0, 0, 0, 5, 5, 0, 0, 0,
    ),
    chess.QUEEN: (
        -20, -10, -10, -5, -5, -10, -10, -20,
        -10, 0, 0, 0, 0, 0, 0, -10,
        -10, 0, 5, 5, 5, 5, 0, -10,
        -5, 0, 5, 5, 5, 5, 0, -5,
        0, 0, 5, 5, 5, 5, 0, -5,
        -10, 5, 5, 5, 5, 5, 0, -10,
        -10, 0, 5, 0, 0, 0, 0, -10,
        -20, -10, -10, -5, -5, -10, -10, -20,
    ),
    chess.KING: (
        -30, -40, -40, -50, -50, -40, -40, -30,
        -30, -40, -40, -50, -50, -40, -40, -30,
        -30, -40, -40, -50, -50, -40, -40, -30,
        -30, -40, -40, -50, -50, -40, -40, -30,
        -20, -30, -30, -40, -40, -30, -30, -20,
        -10, -20, -20, -20, -20, -20, -20, -10,
        20, 20, 0, 0, 0, 0, 20, 20,
        20, 30, 10, 0, 0, 10, 30, 20,
    ),
}
KING_ENDGAME_TABLE: tuple[int, ...] = (
    -50, -40, -30, -20, -20, -30, -40, -50,
    -30, -20, -10, 0, 0, -10, -20, -30,
    -30, -10, 20, 30, 30, 20, -10, -30,
    -30, -10, 30, 40, 40, 30, -10, -30,
    -30, -10, 30, 40, 40, 30, -10, -30,
    -30, -10, 20, 30, 30, 20, -10, -30,
    -30, -30, 0, 0, 0, 0, -30, -30,
    -50, -30, -30, -30, -30, -30, -30, -50,
)
# fmt: on


def material_evaluator(board: chess.Board) -> float:
    """Return the baseline material evaluation from the side to move's view."""
    return _from_white(float(evaluate(board)), board)


def positional_evaluator(board: chess.Board) -> float:
    """Return a modular heuristic: material, central control and development."""
    if board.is_checkmate():
        return _from_white(float(-MATE_SCORE if board.turn == chess.WHITE else MATE_SCORE), board)
    if board.is_stalemate() or board.is_insufficient_material():
        return 0.0
    score = _piece_score(board, chess.WHITE) - _piece_score(board, chess.BLACK)
    return _from_white(score, board)


def is_endgame(board: chess.Board) -> bool:
    """True when no queens remain or each side has at most one piece besides pawns."""
    if not board.queens:
        return True
    for color in (chess.WHITE, chess.BLACK):
        pieces = board.occupied_co[color] & ~board.pawns & ~board.kings
        if pieces.bit_count() > 1:
            return False
    return True


def _terminal_score(board: chess.Board) -> float | None:
    """Mate (faster is better) or draw score for the side to move, else ``None``."""
    if not any(board.generate_legal_moves()):
        return float(-(MATE_SCORE - board.ply())) if board.is_check() else 0.0
    if (
        board.is_insufficient_material()
        or board.halfmove_clock >= 100
        or (board.halfmove_clock >= 4 and board.is_repetition(3))
    ):
        return 0.0
    return None


def _square_values(table: tuple[int, ...], value: int) -> tuple[list[int], list[int]]:
    """Material plus table bonus for every square, for White and for Black."""
    white = [value + table[chess.square_mirror(square)] for square in chess.SQUARES]
    black = [value + table[square] for square in chess.SQUARES]
    return white, black


_PST_VALUES = {
    piece_type: _square_values(table, PIECE_VALUES[piece_type])
    for piece_type, table in PST_TABLES.items()
}
_KING_ENDGAME_VALUES = _square_values(KING_ENDGAME_TABLE, PIECE_VALUES[chess.KING])


def _pst_score(board: chess.Board, endgame: bool) -> int:
    """Material plus piece-square bonuses from White's view."""
    score = 0
    for piece_type, (white_values, black_values) in _PST_VALUES.items():
        if endgame and piece_type == chess.KING:
            white_values, black_values = _KING_ENDGAME_VALUES
        mask = board.pieces_mask(piece_type, chess.WHITE)
        while mask:
            low = mask & -mask
            score += white_values[low.bit_length() - 1]
            mask ^= low
        mask = board.pieces_mask(piece_type, chess.BLACK)
        while mask:
            low = mask & -mask
            score -= black_values[low.bit_length() - 1]
            mask ^= low
    return score


def pst_evaluator(board: chess.Board) -> float:
    """Benchmark 2: material plus piece-square tables; faster mates score higher."""
    terminal = _terminal_score(board)
    if terminal is not None:
        return terminal
    return _from_white(float(_pst_score(board, is_endgame(board))), board)


DOUBLED_PAWN_PENALTY = 15
ISOLATED_PAWN_PENALTY = 15
PASSED_PAWN_BONUS = (0, 5, 10, 20, 35, 60, 100, 0)  # by ranks advanced from home
MISSING_SHIELD_PENALTY = 15
OPEN_KING_FILE_PENALTY = 20
BISHOP_PAIR_BONUS = 30
ROOK_OPEN_FILE_BONUS = 20
ROOK_SEMI_OPEN_FILE_BONUS = 10
# Points per square a piece attacks that is not occupied by its own side.
MOBILITY_WEIGHTS = ((chess.KNIGHT, 4), (chess.BISHOP, 4), (chess.ROOK, 2), (chess.QUEEN, 1))
STRUCTURE_CACHE_LIMIT = 200_000

_ADJACENT_FILES = [
    (chess.BB_FILES[f - 1] if f > 0 else 0) | (chess.BB_FILES[f + 1] if f < 7 else 0)
    for f in range(8)
]


def _ahead_mask(color: chess.Color, rank: int) -> int:
    """All squares on the ranks in front of ``rank`` from ``color``'s side."""
    ranks = range(rank + 1, 8) if color == chess.WHITE else range(0, rank)
    mask = 0
    for r in ranks:
        mask |= chess.BB_RANKS[r]
    return mask


# Enemy pawns on these squares stop a pawn from being passed.
_PASSED_MASKS = {
    color: [
        (chess.BB_FILES[chess.square_file(sq)] | _ADJACENT_FILES[chess.square_file(sq)])
        & _ahead_mask(color, chess.square_rank(sq))
        for sq in chess.SQUARES
    ]
    for color in (chess.WHITE, chess.BLACK)
}


def _shield_files(color: chess.Color, king: int) -> tuple[tuple[int, int], ...]:
    """Shield-square and whole-file masks for the king file and its neighbours."""
    file, rank = chess.square_file(king), chess.square_rank(king)
    step = 1 if color == chess.WHITE else -1
    result = []
    for f in range(max(file - 1, 0), min(file + 1, 7) + 1):
        shield = 0
        for r in (rank + step, rank + 2 * step):
            if 0 <= r <= 7:
                shield |= chess.BB_SQUARES[chess.square(f, r)]
        result.append((shield, chess.BB_FILES[f]))
    return tuple(result)


_SHIELD_MASKS = {
    color: [_shield_files(color, sq) for sq in chess.SQUARES]
    for color in (chess.WHITE, chess.BLACK)
}
_structure_cache: dict[tuple[int, int, int, int, bool], int] = {}


def _pawn_structure(own: int, enemy: int, color: chess.Color) -> int:
    """Doubled and isolated pawn penalties plus passed pawn bonuses (pawn bitboards)."""
    score = 0
    for file_mask in chess.BB_FILES:
        count = (own & file_mask).bit_count()
        if count > 1:
            score -= DOUBLED_PAWN_PENALTY * (count - 1)
    passed = _PASSED_MASKS[color]
    mask = own
    while mask:
        low = mask & -mask
        square = low.bit_length() - 1
        mask ^= low
        if not own & _ADJACENT_FILES[square & 7]:
            score -= ISOLATED_PAWN_PENALTY
        if not enemy & passed[square]:
            rank = square >> 3
            score += PASSED_PAWN_BONUS[rank if color == chess.WHITE else 7 - rank]
    return score


def _king_safety(own: int, king: int | None, color: chess.Color) -> int:
    """Penalise missing shield pawns and open files around the king (middlegame only)."""
    if king is None:
        return 0
    score = 0
    for shield, file_mask in _SHIELD_MASKS[color][king]:
        if not own & shield:
            score -= MISSING_SHIELD_PENALTY
        if not own & file_mask:
            score -= OPEN_KING_FILE_PENALTY
    return score


def _structure_score(board: chess.Board, endgame: bool) -> int:
    """Pawn structure and king safety from White's view, cached by pawn/king placement."""
    white = board.pawns & board.occupied_co[chess.WHITE]
    black = board.pawns & board.occupied_co[chess.BLACK]
    white_king, black_king = board.king(chess.WHITE), board.king(chess.BLACK)
    key = (
        white,
        black,
        -1 if white_king is None else white_king,
        -1 if black_king is None else black_king,
        endgame,
    )
    cached = _structure_cache.get(key)
    if cached is not None:
        return cached
    score = _pawn_structure(white, black, chess.WHITE) - _pawn_structure(black, white, chess.BLACK)
    if not endgame:
        score += _king_safety(white, white_king, chess.WHITE)
        score -= _king_safety(black, black_king, chess.BLACK)
    if len(_structure_cache) >= STRUCTURE_CACHE_LIMIT:
        _structure_cache.clear()
    _structure_cache[key] = score
    return score


def _piece_bonus(board: chess.Board, color: chess.Color) -> int:
    """Mobility, bishop pair and rooks on open or semi-open files for ``color``."""
    score = BISHOP_PAIR_BONUS if board.pieces_mask(chess.BISHOP, color).bit_count() >= 2 else 0
    not_own = ~board.occupied_co[color]
    for piece_type, weight in MOBILITY_WEIGHTS:
        mask = board.pieces_mask(piece_type, color)
        while mask:
            low = mask & -mask
            mask ^= low
            score += weight * (board.attacks_mask(low.bit_length() - 1) & not_own).bit_count()
    own_pawns = board.pawns & board.occupied_co[color]
    rooks = board.pieces_mask(chess.ROOK, color)
    while rooks:
        low = rooks & -rooks
        rooks ^= low
        file_mask = chess.BB_FILES[(low.bit_length() - 1) & 7]
        if not board.pawns & file_mask:
            score += ROOK_OPEN_FILE_BONUS
        elif not own_pawns & file_mask:
            score += ROOK_SEMI_OPEN_FILE_BONUS
    return score


def advanced_evaluator(board: chess.Board) -> float:
    """Benchmark 4: ``pst`` + pawn structure, king safety, mobility, bishop pair, rook files."""
    terminal = _terminal_score(board)
    if terminal is not None:
        return terminal
    endgame = is_endgame(board)
    score = _pst_score(board, endgame) + _structure_score(board, endgame)
    score += _piece_bonus(board, chess.WHITE) - _piece_bonus(board, chess.BLACK)
    return _from_white(float(score), board)


def register_evaluator(name: str, evaluator: Callable[[chess.Board], float]) -> None:
    """Add or replace a named evaluator used by the custom benchmark bot."""
    EVALUATORS[name] = evaluator


def build_evaluator(name: str = "positional") -> Callable[[chess.Board], float]:
    """Return a named side-to-move evaluator, raising ValueError if unknown."""
    try:
        return EVALUATORS[name]
    except KeyError:
        raise ValueError(f"unknown evaluator: {name!r}") from None


def _piece_score(board: chess.Board, color: chess.Color) -> float:
    score = 0.0
    for square, piece in board.piece_map().items():
        if piece.color != color:
            continue
        score += PIECE_VALUES[piece.piece_type]
        if piece.piece_type in (chess.PAWN, chess.KNIGHT, chess.BISHOP):
            if square in CENTRAL_SQUARES:
                score += CENTRAL_BONUS
            elif square in DEVELOPMENT_SQUARES:
                score += DEVELOPMENT_BONUS
    return score


def _from_white(score: float, board: chess.Board) -> float:
    """Flip a White-perspective score when Black is to move."""
    return score if board.turn == chess.WHITE else -score


EVALUATORS: dict[str, Callable[[chess.Board], float]] = {
    "material": material_evaluator,
    "positional": positional_evaluator,
    "pst": pst_evaluator,
    "advanced": advanced_evaluator,
}
