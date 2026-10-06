"""Panel section headers and collapsible section state."""

from __future__ import annotations

import pygame
from frontend.gui.theme import THEMES

from gui.render import Render


class PanelSection:
    """Represent a panel section whose body can be collapsed."""

    def __init__(self, key: str, y: int, height: int, *, expanded: bool = True) -> None:
        self.key = key
        self.rect = pygame.Rect(656, y, 280, height)
        self.expanded = expanded

    def draw_header(self, canvas: Render, label: str, font: int, theme=None) -> None:
        """Draw the section title and disclosure marker."""
        roles = (theme or THEMES["dark_winter"]).roles
        canvas.draw_line(
            roles["border"], (self.rect.left, self.rect.top), (self.rect.right, self.rect.top)
        )
        color = roles["accent"]
        center_x = self.rect.left + 10
        center_y = self.rect.top + 14
        if self.expanded:
            points = (
                (center_x - 4, center_y - 2),
                (center_x + 4, center_y - 2),
                (center_x, center_y + 3),
            )
        else:
            points = (
                (center_x - 2, center_y - 4),
                (center_x - 2, center_y + 4),
                (center_x + 3, center_y),
            )
        canvas.draw_polygon(color, points)
        canvas.text(
            font,
            label,
            roles["text_muted"],
            (self.rect.left + 22, self.rect.top + 4),
            max_width=self.rect.width - 32,
        )

    def hit_header(self, point: tuple[float, float]) -> bool:
        """Return whether the section header was clicked."""
        return (
            self.rect.left <= point[0] <= self.rect.right
            and self.rect.top <= point[1] <= self.rect.top + 28
        )
