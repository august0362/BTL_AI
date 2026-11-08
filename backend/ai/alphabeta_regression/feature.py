"""Feature extraction for the alpha-beta regression evaluator."""

from __future__ import annotations

from dataclasses import dataclass

import chess

PIECE_VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
}
_PHASE_MAX = 24
_CENTER = {chess.D4, chess.E4, chess.D5, chess.E5}
_EXTENDED_CENTER = {
    chess.square(file_index, rank_index)
    for file_index in range(2, 6)
    for rank_index in range(2, 6)
}


@dataclass(frozen=True)
class BoardFeatures:
    """Immutable white-minus-black features and terminal-state metadata."""

    pawn_diff: int
    knight_diff: int
    bishop_diff: int
    rook_diff: int
    queen_diff: int
    bishop_pair_diff: int
    phase: float
    pawn_square_diff: float
    knight_square_diff: float
    bishop_square_diff: float
    rook_square_diff: float
    queen_square_diff: float
    king_square_diff: float
    center_control_diff: int
    strategic_control_diff: int
    passed_pawn_diff: int
    passed_pawn_advance_diff: int
    isolated_pawn_diff: int
    doubled_pawn_diff: int
    backward_pawn_diff: int
    protected_pawn_diff: int
    king_attackers_diff: int
    pawn_shield_diff: int
    middlegame_king_safety_diff: float
    endgame_king_activity_diff: float
    protected_piece_value_diff: int
    hanging_piece_value_diff: int
    rook_open_file_diff: int
    rook_semi_open_file_diff: int
    knight_outpost_diff: int
    mobility_diff: int
    safe_mobility_diff: int
    turn: chess.Color
    is_checkmate: bool
    is_game_over: bool


def extract_features(board: chess.Board) -> BoardFeatures:
    """Extract material, square, pawn, king, activity, and phase features."""
    phase = _game_phase(board)
    return BoardFeatures(
        pawn_diff=_piece_count_diff(board, chess.PAWN),
        knight_diff=_piece_count_diff(board, chess.KNIGHT),
        bishop_diff=_piece_count_diff(board, chess.BISHOP),
        rook_diff=_piece_count_diff(board, chess.ROOK),
        queen_diff=_piece_count_diff(board, chess.QUEEN),
        bishop_pair_diff=_bishop_pair(board, chess.WHITE) - _bishop_pair(board, chess.BLACK),
        phase=phase,
        pawn_square_diff=_piece_square_score(board, chess.PAWN),
        knight_square_diff=_piece_square_score(board, chess.KNIGHT),
        bishop_square_diff=_piece_square_score(board, chess.BISHOP),
        rook_square_diff=_piece_square_score(board, chess.ROOK),
        queen_square_diff=_piece_square_score(board, chess.QUEEN),
        king_square_diff=_piece_square_score(board, chess.KING) * phase,
        center_control_diff=_square_control(board, chess.WHITE, _CENTER)
        - _square_control(board, chess.BLACK, _CENTER),
        strategic_control_diff=_square_control(board, chess.WHITE, _EXTENDED_CENTER)
        - _square_control(board, chess.BLACK, _EXTENDED_CENTER),
        passed_pawn_diff=_passed_pawns(board, chess.WHITE)[0]
        - _passed_pawns(board, chess.BLACK)[0],
        passed_pawn_advance_diff=_passed_pawns(board, chess.WHITE)[1]
        - _passed_pawns(board, chess.BLACK)[1],
        isolated_pawn_diff=_isolated_pawns(board, chess.WHITE)
        - _isolated_pawns(board, chess.BLACK),
        doubled_pawn_diff=_doubled_pawns(board, chess.WHITE)
        - _doubled_pawns(board, chess.BLACK),
        backward_pawn_diff=_backward_pawns(board, chess.WHITE)
        - _backward_pawns(board, chess.BLACK),
        protected_pawn_diff=_protected_pawns(board, chess.WHITE)
        - _protected_pawns(board, chess.BLACK),
        king_attackers_diff=_king_attackers(board, chess.BLACK)
        - _king_attackers(board, chess.WHITE),
        pawn_shield_diff=_pawn_shield(board, chess.WHITE)
        - _pawn_shield(board, chess.BLACK),
        middlegame_king_safety_diff=(
            _king_safety(board, chess.WHITE) - _king_safety(board, chess.BLACK)
        )
        * phase,
        endgame_king_activity_diff=(
            _king_activity(board, chess.WHITE) - _king_activity(board, chess.BLACK)
        )
        * (1.0 - phase),
        protected_piece_value_diff=_protected_piece_value(board, chess.WHITE)
        - _protected_piece_value(board, chess.BLACK),
        hanging_piece_value_diff=_hanging_piece_value(board, chess.BLACK)
        - _hanging_piece_value(board, chess.WHITE),
        rook_open_file_diff=_rook_files(board, chess.WHITE, "open")
        - _rook_files(board, chess.BLACK, "open"),
        rook_semi_open_file_diff=_rook_files(board, chess.WHITE, "semi")
        - _rook_files(board, chess.BLACK, "semi"),
        knight_outpost_diff=_knight_outposts(board, chess.WHITE)
        - _knight_outposts(board, chess.BLACK),
        mobility_diff=_mobility(board, chess.WHITE) - _mobility(board, chess.BLACK),
        safe_mobility_diff=_safe_mobility(board, chess.WHITE)
        - _safe_mobility(board, chess.BLACK),
        turn=board.turn,
        is_checkmate=board.is_checkmate(),
        is_game_over=board.is_game_over(),
    )


def _piece_count_diff(board: chess.Board, piece_type: chess.PieceType) -> int:
    return len(board.pieces(piece_type, chess.WHITE)) - len(board.pieces(piece_type, chess.BLACK))


def _bishop_pair(board: chess.Board, color: chess.Color) -> int:
    return int(len(board.pieces(chess.BISHOP, color)) >= 2)


def _game_phase(board: chess.Board) -> float:
    remaining = sum(
        len(board.pieces(piece_type, color)) * value
        for piece_type, value in (
            (chess.KNIGHT, 1),
            (chess.BISHOP, 1),
            (chess.ROOK, 2),
            (chess.QUEEN, 4),
        )
        for color in chess.COLORS
    )
    return min(1.0, remaining / _PHASE_MAX)


def _piece_square_score(board: chess.Board, piece_type: chess.PieceType) -> float:
    """Return a compact color-relative piece-square score, oriented to each side."""
    score = 0.0
    for color in chess.COLORS:
        sign = 1 if color == chess.WHITE else -1
        for square in board.pieces(piece_type, color):
            file_index = chess.square_file(square)
            square_rank = chess.square_rank(square)
            rank = square_rank if color == chess.WHITE else 7 - square_rank
            rank_progress = rank if piece_type == chess.PAWN else max(0, rank - 1)
            center_distance = abs(3.5 - file_index) + abs(3.5 - rank)
            centrality = 7.0 - center_distance
            if piece_type == chess.PAWN:
                value = rank_progress + centrality * 0.1
            elif piece_type == chess.KING:
                value = -centrality
            else:
                value = centrality + rank_progress * 0.15
            score += sign * value
    return score


def _square_control(board: chess.Board, color: chess.Color, squares: set[int]) -> int:
    return sum(board.is_attacked_by(color, square) for square in squares)


def _passed_pawns(board: chess.Board, color: chess.Color) -> tuple[int, int]:
    opponent_pawns = tuple(board.pieces(chess.PAWN, not color))
    passed = [
        square
        for square in board.pieces(chess.PAWN, color)
        if not any(
            abs(chess.square_file(enemy) - chess.square_file(square)) <= 1
            and (
                chess.square_rank(enemy) > chess.square_rank(square)
                if color == chess.WHITE
                else chess.square_rank(enemy) < chess.square_rank(square)
            )
            for enemy in opponent_pawns
        )
    ]
    advance = sum(
        chess.square_rank(square) if color == chess.WHITE else 7 - chess.square_rank(square)
        for square in passed
    )
    return len(passed), advance


def _pawn_files(board: chess.Board, color: chess.Color) -> list[int]:
    files = [0] * 8
    for square in board.pieces(chess.PAWN, color):
        files[chess.square_file(square)] += 1
    return files


def _isolated_pawns(board: chess.Board, color: chess.Color) -> int:
    files = _pawn_files(board, color)
    return sum(
        files[file_index]
        for file_index in range(8)
        if files[file_index]
        and (file_index == 0 or not files[file_index - 1])
        and (file_index == 7 or not files[file_index + 1])
    )


def _doubled_pawns(board: chess.Board, color: chess.Color) -> int:
    return sum(max(0, count - 1) for count in _pawn_files(board, color))


def _backward_pawns(board: chess.Board, color: chess.Color) -> int:
    pawns = board.pieces(chess.PAWN, color)
    enemy_pawns = board.pieces(chess.PAWN, not color)
    backward = 0
    for square in pawns:
        file_index = chess.square_file(square)
        rank = chess.square_rank(square)
        support_rank = rank - 1 if color == chess.WHITE else rank + 1
        has_neighbor = any(
            abs(chess.square_file(other) - file_index) == 1
            and (
                chess.square_rank(other) >= support_rank
                if color == chess.WHITE
                else chess.square_rank(other) <= support_rank
            )
            for other in pawns
        )
        next_rank = rank + (1 if color == chess.WHITE else -1)
        if not 0 <= next_rank < 8:
            continue
        next_square = chess.square(file_index, next_rank)
        enemy_can_attack = any(
            abs(chess.square_file(enemy) - file_index) == 1
            and (
                chess.square_rank(enemy) >= rank + 1
                if color == chess.WHITE
                else chess.square_rank(enemy) <= rank - 1
            )
            for enemy in enemy_pawns
        )
        if not has_neighbor and enemy_can_attack and board.piece_at(next_square) is None:
            backward += 1
    return backward


def _protected_pawns(board: chess.Board, color: chess.Color) -> int:
    return sum(
        board.is_attacked_by(color, square)
        for square in board.pieces(chess.PAWN, color)
    )


def _king_attackers(board: chess.Board, color: chess.Color) -> int:
    king_square = board.king(color)
    if king_square is None:
        return 0
    king_zone = chess.BB_KING_ATTACKS[king_square] | chess.BB_SQUARES[king_square]
    attackers = 0
    for square in chess.scan_forward(king_zone):
        attackers += len(board.attackers(not color, square))
    return attackers


def _pawn_shield(board: chess.Board, color: chess.Color) -> int:
    king_square = board.king(color)
    if king_square is None:
        return 0
    file_index = chess.square_file(king_square)
    rank_step = 1 if color == chess.WHITE else -1
    rank = chess.square_rank(king_square) + rank_step
    return sum(
        board.piece_at(chess.square(file, rank)) == chess.Piece(chess.PAWN, color)
        for file in range(max(0, file_index - 1), min(7, file_index + 1) + 1)
        if 0 <= rank < 8
    )


def _king_safety(board: chess.Board, color: chess.Color) -> int:
    king_square = board.king(color)
    if king_square is None:
        return -8
    zone = chess.BB_KING_ATTACKS[king_square] | chess.BB_SQUARES[king_square]
    enemy_pressure = sum(
        len(board.attackers(not color, square)) for square in chess.scan_forward(zone)
    )
    queen_factor = int(
        bool(board.pieces(chess.QUEEN, chess.WHITE))
        and bool(board.pieces(chess.QUEEN, chess.BLACK))
    )
    return _pawn_shield(board, color) * 2 - enemy_pressure * queen_factor


def _king_activity(board: chess.Board, color: chess.Color) -> int:
    king_square = board.king(color)
    if king_square is None:
        return 0
    center_distance = abs(3.5 - chess.square_file(king_square)) + abs(
        3.5 - chess.square_rank(king_square)
    )
    return round(7 - center_distance)


def _protected_piece_value(board: chess.Board, color: chess.Color) -> int:
    return sum(
        PIECE_VALUES[piece_type]
        for piece_type in PIECE_VALUES
        for square in board.pieces(piece_type, color)
        if board.is_attacked_by(color, square)
    )


def _hanging_piece_value(board: chess.Board, color: chess.Color) -> int:
    return sum(
        PIECE_VALUES[piece_type]
        for piece_type in PIECE_VALUES
        for square in board.pieces(piece_type, color)
        if board.is_attacked_by(not color, square)
        and not board.is_attacked_by(color, square)
    )


def _rook_files(board: chess.Board, color: chess.Color, kind: str) -> int:
    own_pawn_files = {chess.square_file(square) for square in board.pieces(chess.PAWN, color)}
    enemy_pawn_files = {
        chess.square_file(square) for square in board.pieces(chess.PAWN, not color)
    }
    if kind == "open":
        return sum(
            chess.square_file(square) not in own_pawn_files | enemy_pawn_files
            for square in board.pieces(chess.ROOK, color)
        )
    return sum(
        chess.square_file(square) not in own_pawn_files
        and chess.square_file(square) in enemy_pawn_files
        for square in board.pieces(chess.ROOK, color)
    )


def _knight_outposts(board: chess.Board, color: chess.Color) -> int:
    enemy_pawns = board.pieces(chess.PAWN, not color)
    score = 0
    for square in board.pieces(chess.KNIGHT, color):
        rank = chess.square_rank(square)
        advanced = rank >= 3 if color == chess.WHITE else rank <= 4
        protected = board.is_attacked_by(color, square)
        pawn_challenged = any(
            abs(chess.square_file(enemy) - chess.square_file(square)) == 1
            and (
                chess.square_rank(enemy) > rank
                if color == chess.WHITE
                else chess.square_rank(enemy) < rank
            )
            for enemy in enemy_pawns
        )
        score += int(advanced and protected and not pawn_challenged)
    return score


def _mobility(board: chess.Board, color: chess.Color) -> int:
    color_board = board.copy(stack=False)
    color_board.turn = color
    return color_board.legal_moves.count()


def _safe_mobility(board: chess.Board, color: chess.Color) -> int:
    color_board = board.copy(stack=False)
    color_board.turn = color
    return sum(
        not color_board.is_attacked_by(not color, move.to_square)
        for move in color_board.legal_moves
    )
