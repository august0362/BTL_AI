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
        radius = self.rect.height // 2
        canvas.draw_rect(roles["surface_alt"], self.rect, radius=radius)
        if value > 0:
            width = max(self.rect.height, round(self.rect.width * value))
            filled = pygame.Rect(self.rect.x, self.rect.y, width, self.rect.height)
            canvas.draw_rect(roles["primary"], filled, radius=radius)
            canvas.draw_circle(roles["glow"], (filled.right - radius, filled.centery), radius + 2)
            canvas.draw_circle(roles["rim"], (filled.right - radius, filled.centery), radius - 1)
