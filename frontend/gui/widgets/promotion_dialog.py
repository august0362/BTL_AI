"""Piece selection overlay for pawn promotion."""

from __future__ import annotations

import chess
import pygame

from gui.assets_loader import piece_image
from gui.i18n import Translator
from gui.render import Render
from frontend.gui.theme import THEMES, Theme


class PromotionDialog:
    """Offer the four standard promotion pieces and a cancel action."""

    PIECES = (chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT)

    def __init__(self, color: chess.Color, piece_set: str, theme: Theme | None = None) -> None:
        self.color = color
        self.piece_set = piece_set
        self.theme = theme or THEMES["dark_winter"]
        self.rect = pygame.Rect(190, 242, 380, 156)

    def draw(self, canvas: Render, translator: Translator) -> None:
        """Draw the promotion choices over the board."""
        roles = self.theme.roles
        canvas.draw_rect(roles["surface"], self.rect, radius=10)
        canvas.draw_rect(roles["border"], self.rect, 2, radius=10)
        canvas.text(20, translator.t("game.promotion_title"), roles["text"], (212, 253), bold=True)
        prefix = "w" if self.color else "b"
        for index, piece_type in enumerate(self.PIECES):
            x = 226 + index * 74
            canvas.blit_image(
                piece_image(self.piece_set, prefix + chess.piece_symbol(piece_type).upper(), 52),
                (x, 286),
            )
        canvas.text(15, translator.t("setup.back"), roles["text_muted"], (0, 0), center=(380, 373))

    def choice_at(self, point: tuple[float, float]) -> chess.PieceType | None | bool:
        """Return a promotion type, False to cancel, or None outside the dialog."""
        x, y = point
        if not self.rect.collidepoint(x, y):
            return None
        if y >= 354:
            return False
        index = int((x - 211) // 74)
        return self.PIECES[index] if 0 <= index < len(self.PIECES) else None
