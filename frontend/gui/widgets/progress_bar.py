"""Themed progress bar widget used by the AI ranking screen."""

from __future__ import annotations

from dataclasses import dataclass

import pygame

from gui.render import Render


@dataclass
class ProgressBar:
    """A rounded progress bar drawn with semantic theme colors."""

    rect: pygame.Rect

    def draw(self, canvas: Render, theme, value: float) -> None:
        """Draw the bar filled to ``value`` in the 0..1 range."""
        roles = theme.roles
        value = max(0.0, min(1.0, float(value)))
        canvas.draw_rect(roles["surface_alt"], self.rect, radius=6)
        if value > 0:
            width = max(2, round(self.rect.width * value))
            filled = pygame.Rect(self.rect.x, self.rect.y, width, self.rect.height)
            canvas.draw_rect(roles["primary"], filled, radius=6)
        canvas.draw_rect(roles["border"], self.rect, 1, radius=6)
