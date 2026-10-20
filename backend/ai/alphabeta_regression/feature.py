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
