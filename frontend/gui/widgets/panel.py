"""Panel cards with a clickable header that collapses their body."""

from __future__ import annotations

import pygame

from gui.render import Render
from gui.theme import THEMES


class PanelSection:
    """A glass card in the side panel whose body can be collapsed from its header."""

    HEADER = 28

    def __init__(self, key: str, y: int, height: int, *, expanded: bool = True) -> None:
        self.key = key
        self.rect = pygame.Rect(652, y, 296, height)
        self.expanded = expanded

    def draw_header(self, canvas: Render, label: str, font: int, theme=None) -> None:
        """Draw the card background, its small-caps title and the disclosure chevron."""
        roles = (theme or THEMES["dark_winter"]).roles
        canvas.draw_glass(
            self.rect, roles["surface"], alpha=225, border=roles["border"], rim=roles["rim"]
        )
        canvas.draw_circle(roles["glow"], (self.rect.left + 13, self.rect.top + 14), 3)
        canvas.text(
            11,
            label.upper(),
            roles["text_muted"],
            (self.rect.left + 23, self.rect.top + 7),
            bold=True,
            max_width=self.rect.width - 52,
        )
        x = self.rect.right - 16
        y = self.rect.top + 14
        points = (
            ((x - 4, y - 2), (x + 4, y - 2), (x, y + 3))
            if self.expanded
            else ((x - 2, y - 4), (x - 2, y + 4), (x + 3, y))
        )
        canvas.draw_polygon(roles["text_muted"], points)

    def hit_header(self, point: tuple[float, float]) -> bool:
        """Return whether the section header was clicked."""
        return (
            self.rect.left <= point[0] <= self.rect.right
            and self.rect.top <= point[1] <= self.rect.top + self.HEADER
        )
