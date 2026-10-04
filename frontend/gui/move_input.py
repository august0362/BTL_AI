"""Display-independent click-to-move state for a chess board."""

from __future__ import annotations

from dataclasses import dataclass

import chess


@dataclass(frozen=True)
class InputResult:
    """Describe the action produced by a board click."""

    kind: str
    square: chess.Square | None = None
    move: chess.Move | None = None
    promotion_moves: tuple[chess.Move, ...] = ()


class MoveInput:
    """Track a selected piece and resolve clicks into legal moves."""

    def __init__(self) -> None:
        self.selected: chess.Square | None = None
        self._promotion_moves: tuple[chess.Move, ...] = ()

    def click(
        self,
        board: chess.Board,
        square: chess.Square | None,
        player_color: chess.Color,
    ) -> InputResult:
        """Apply one click according to the current turn and selection."""
        if board.turn != player_color:
            return InputResult("none")
        if self._promotion_moves:
            return InputResult("none")
        if square is not None and not 0 <= square < 64:
            square = None
        if square is None:
            if self.selected is not None:
                self.selected = None
                return InputResult("deselect")
            return InputResult("none")

        piece = board.piece_at(square)
        if self.selected is None:
            if (
                piece is not None
                and piece.color == player_color
                and self._moves_from(board, square)
            ):
                self.selected = square
                return InputResult("select", square=square)
            return InputResult("none")

        if square == self.selected:
            self.selected = None
            return InputResult("deselect")
        if piece is not None and piece.color == player_color and self._moves_from(board, square):
            self.selected = square
            return InputResult("select", square=square)

        candidates = tuple(
            move
            for move in board.legal_moves
            if move.from_square == self.selected and move.to_square == square
        )
        if candidates:
            if any(move.promotion is not None for move in candidates):
                self._promotion_moves = candidates
                return InputResult("promotion", square=square, promotion_moves=candidates)
            self.selected = None
            return InputResult("move", move=candidates[0])

        self.selected = None
        return InputResult("deselect")

    def choose_promotion(self, piece_type: chess.PieceType) -> chess.Move:
        """Return the pending promotion move for a piece type."""
        if not self._promotion_moves:
            raise ValueError("no promotion is pending")
        for move in self._promotion_moves:
            if move.promotion == piece_type:
                self._promotion_moves = ()
                self.selected = None
                return move
        raise ValueError("the selected piece type is not a legal promotion")

    def legal_targets(self, board: chess.Board) -> set[chess.Square]:
        """Return legal destination squares for the selected piece."""
        if self.selected is None:
            return set()
        return {move.to_square for move in board.legal_moves if move.from_square == self.selected}

    def clear(self) -> None:
        """Clear the selected piece and any pending promotion."""
        self.selected = None
        self._promotion_moves = ()

    @staticmethod
    def _moves_from(board: chess.Board, square: chess.Square) -> bool:
        return any(move.from_square == square for move in board.legal_moves)
