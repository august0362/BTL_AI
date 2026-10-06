"""Chessboard rendering with move and check highlights."""

from __future__ import annotations

import chess
import pygame

from gui import board_geometry
from gui.assets_loader import piece_image
from gui.render import Render
from gui.theme import Theme
from gui.widgets.promotion_dialog import PromotionDialog


class BoardView:
    """Draw a board position and its current input hints."""

    def __init__(self, theme: Theme, piece_set: str) -> None:
        self.theme = theme
        self.piece_set = piece_set

    def draw(
        self,
        canvas: Render,
        board: chess.Board,
        *,
        flipped: bool = False,
        selected: chess.Square | None = None,
        targets: set[chess.Square] | None = None,
        moves: tuple = (),
        dialog: PromotionDialog | None = None,
        translator=None,
    ) -> None:
        """Draw board squares, pieces, and all requested highlights."""
        last_move = chess.Move.from_uci(moves[-1].uci) if moves else None
        for square in chess.SQUARES:
            x, y = board_geometry.square_origin(square, flipped)
            rect = pygame.Rect(x, y, 80, 80)
            color = (
                self.theme.roles["board_light"]
                if (chess.square_file(square) + chess.square_rank(square)) % 2
                else self.theme.roles["board_dark"]
            )
            canvas.draw_rect(color, rect)
            if last_move and square in (last_move.from_square, last_move.to_square):
                side = round(80 * canvas.scale)
                overlay = pygame.Surface((side, side), pygame.SRCALPHA)
                overlay.fill((*pygame.Color(self.theme.roles["board_last"])[:3], 90))
                canvas.surface.blit(overlay, canvas.point((x, y)))
            if selected == square:
                side = round(80 * canvas.scale)
                overlay = pygame.Surface((side, side), pygame.SRCALPHA)
                overlay.fill((*pygame.Color(self.theme.roles["board_select"])[:3], 100))
                canvas.surface.blit(overlay, canvas.point((x, y)))
            if targets and square in targets:
                piece = board.piece_at(square)
                center = (x + 40, y + 40)
                if piece:
                    canvas.draw_circle(
                        (*pygame.Color(self.theme.roles["board_hint"])[:3], 140), center, 37, 5
                    )
                else:
                    canvas.draw_circle(
                        (*pygame.Color(self.theme.roles["board_hint"])[:3], 105), center, 12
                    )
                    canvas.draw_circle(
                        (*pygame.Color(self.theme.roles["board_light"])[:3], 165), center, 8
                    )
            if board.is_check() and board.king(board.turn) == square:
                canvas.draw_rect(self.theme.roles["danger"], rect, 5)
            piece = board.piece_at(square)
            if piece:
                name = ("w" if piece.color else "b") + piece.symbol().upper()
                canvas.surface.blit(
                    piece_image(self.piece_set, name, round(80 * canvas.scale)),
                    canvas.point((x, y)),
                )
        if dialog is not None and translator is not None:
            dialog.draw(canvas, translator)
