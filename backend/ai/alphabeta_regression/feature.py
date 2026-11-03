"""Feature extraction for the alpha-beta regression evaluator."""

from dataclasses import dataclass

import chess


@dataclass(frozen=True)
class BoardFeatures:
    """Immutable white-minus-black features for a chess position."""

    pawn_diff: int
    knight_diff: int
    bishop_diff: int
    rook_diff: int
    queen_diff: int
    mobility_diff: int
    center_control_diff: int
    pawn_advance_diff: int
    minor_development_diff: int
    early_queen_development_diff: int
    center_occupancy_diff: int
    castled_diff: int
    turn: chess.Color
    is_checkmate: bool
    is_game_over: bool


def extract_features(board: chess.Board) -> BoardFeatures:
    """Extract material, positional, and terminal-state features from a board."""
    return BoardFeatures(
        pawn_diff=_piece_count_diff(board, chess.PAWN),
        knight_diff=_piece_count_diff(board, chess.KNIGHT),
        bishop_diff=_piece_count_diff(board, chess.BISHOP),
        rook_diff=_piece_count_diff(board, chess.ROOK),
        queen_diff=_piece_count_diff(board, chess.QUEEN),
        mobility_diff=_mobility(board, chess.WHITE) - _mobility(board, chess.BLACK),
        center_control_diff=(
            _center_control(board, chess.WHITE) - _center_control(board, chess.BLACK)
        ),
        pawn_advance_diff=(_pawn_advance(board, chess.WHITE) - _pawn_advance(board, chess.BLACK)),
        minor_development_diff=(
            _minor_development(board, chess.WHITE) - _minor_development(board, chess.BLACK)
        ),
        early_queen_development_diff=(
            _early_queen_development(board, chess.WHITE)
            - _early_queen_development(board, chess.BLACK)
        ),
        center_occupancy_diff=(
            _center_occupancy(board, chess.WHITE) - _center_occupancy(board, chess.BLACK)
        ),
        castled_diff=int(_has_castled(board, chess.WHITE)) - int(_has_castled(board, chess.BLACK)),
        turn=board.turn,
        is_checkmate=board.is_checkmate(),
        is_game_over=board.is_game_over(),
    )


def _piece_count_diff(board: chess.Board, piece_type: chess.PieceType) -> int:
    """Return the white-minus-black count for a piece type."""
    return len(board.pieces(piece_type, chess.WHITE)) - len(board.pieces(piece_type, chess.BLACK))


def _mobility(board: chess.Board, color: chess.Color) -> int:
    """Return the number of legal moves available to a color."""
    if board.turn == color:
        return board.legal_moves.count()
    color_board = board.copy(stack=False)
    color_board.turn = color
    return color_board.legal_moves.count()


def _center_control(board: chess.Board, color: chess.Color) -> int:
    """Return the number of central squares attacked by a color."""
    center_squares = (chess.D4, chess.E4, chess.D5, chess.E5)
    return sum(board.is_attacked_by(color, square) for square in center_squares)


def _pawn_advance(board: chess.Board, color: chess.Color) -> int:
    """Return total pawn distance advanced from each side's starting rank."""
    advance = 0
    for square in board.pieces(chess.PAWN, color):
        rank = chess.square_rank(square)
        advance += rank - 1 if color == chess.WHITE else 6 - rank
    return advance


def _minor_development(board: chess.Board, color: chess.Color) -> int:
    """Count knights and bishops that have left their original squares."""
    home_squares = (
        (chess.B1, chess.G1, chess.C1, chess.F1)
        if color == chess.WHITE
        else (chess.B8, chess.G8, chess.C8, chess.F8)
    )
    home = set(home_squares)
    developed = 0
    for piece_type in (chess.KNIGHT, chess.BISHOP):
        developed += sum(square not in home for square in board.pieces(piece_type, color))
    return developed


def _early_queen_development(board: chess.Board, color: chess.Color) -> int:
    """Count queens developed before two minor pieces during the first ten moves."""
    if board.fullmove_number > 10 or _minor_development(board, color) >= 2:
        return 0
    home_square = chess.D1 if color == chess.WHITE else chess.D8
    return sum(square != home_square for square in board.pieces(chess.QUEEN, color))


def _center_occupancy(board: chess.Board, color: chess.Color) -> int:
    """Count a side's pieces occupying the four central squares."""
    center_squares = (chess.D4, chess.E4, chess.D5, chess.E5)
    return sum(
        (piece := board.piece_at(square)) is not None and piece.color == color
        for square in center_squares
    )


def _has_castled(board: chess.Board, color: chess.Color) -> bool:
    """Return whether the king occupies a normal castled square."""
    king_square = board.king(color)
    if king_square is None:
        return False
    rank = 0 if color == chess.WHITE else 7
    return king_square in (chess.square(2, rank), chess.square(6, rank))
