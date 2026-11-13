"""Piece selection overlay for pawn promotion."""

from __future__ import annotations

import chess
import pygame

from gui.assets_loader import piece_image
from gui.i18n import Translator
from gui.render import Render
from gui.theme import THEMES, Theme


class PromotionDialog:
    """Offer the four standard promotion pieces and a cancel action."""

    PIECES = (chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT)
    TILE = 84
    TILE_STEP = 96
    TILES_LEFT = 134
    TILES_TOP = 274
    CANCEL_TOP = 368

    def __init__(self, color: chess.Color, piece_set: str, theme: Theme | None = None) -> None:
        self.color = color
        self.piece_set = piece_set
        self.theme = theme or THEMES["dark_winter"]
        self.rect = pygame.Rect(114, 228, 412, 184)

    def draw(self, canvas: Render, translator: Translator) -> None:
        """Dim the board and draw the promotion choices on a glass card."""
        roles = self.theme.roles
        canvas.draw_glass((0, 0, 640, 640), roles["bg"], alpha=150, radius=0)
        canvas.draw_glass(
            self.rect,
            roles["surface"],
            alpha=240,
            radius=16,
            border=roles["rim"],
            rim=roles["glow"],
        )
        canvas.text(
            12,
            translator.t("game.promotion_title").upper(),
            roles["glow"],
            (0, 0),
            bold=True,
            center=(self.rect.centerx, self.rect.top + 24),
        )
        prefix = "w" if self.color else "b"
        for index, piece_type in enumerate(self.PIECES):
            tile = pygame.Rect(
                self.TILES_LEFT + index * self.TILE_STEP, self.TILES_TOP, self.TILE, self.TILE
            )
            canvas.draw_glass(
                tile, roles["surface_alt"], alpha=230, radius=12, border=roles["border"]
            )
            # Load at physical size so the piece is resampled once and stays sharp.
            image = piece_image(
                self.piece_set,
                prefix + chess.piece_symbol(piece_type).upper(),
                round(70 * canvas.scale),
            )
            canvas.surface.blit(image, image.get_rect(center=canvas.point(tile.center)))
        cancel = pygame.Rect(0, self.CANCEL_TOP + 6, 140, 32)
        cancel.centerx = self.rect.centerx
        canvas.draw_glass(
            cancel, roles["surface_alt"], alpha=220, radius=16, border=roles["border"]
        )
        canvas.text(
            13,
            translator.t("setup.back"),
            roles["text_muted"],
            (0, 0),
            bold=True,
            center=(self.rect.centerx, self.CANCEL_TOP + 22),
        )

    def choice_at(self, point: tuple[float, float]) -> chess.PieceType | None | bool:
        """Return a promotion type, False to cancel, or None outside the dialog."""
        x, y = point
        if not self.rect.collidepoint(x, y):
            return None
        if y >= self.CANCEL_TOP:
            return False
        index = int((x - self.TILES_LEFT) // self.TILE_STEP)
        return self.PIECES[index] if 0 <= index < len(self.PIECES) else None
