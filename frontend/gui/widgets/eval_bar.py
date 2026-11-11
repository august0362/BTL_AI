"""Material evaluation bar."""

from __future__ import annotations

import pygame

from gui.render import Render
from gui.theme import THEMES, side_colors


def draw_eval_bar(canvas: Render, rect: pygame.Rect, value: float, theme=None) -> None:
    """Draw the White share of the bar; positive values favor White.

    A wide rectangle fills from the left, a tall one from the bottom.
    """
    theme = theme or THEMES["dark_winter"]
    roles = theme.roles
    white, black = side_colors(theme)
    value = max(-1.0, min(1.0, value))
    share = (value + 1) / 2
    canvas.draw_rect(black, rect, radius=6)
    if rect.width >= rect.height:
        filled = pygame.Rect(rect.left, rect.top, round(rect.width * share), rect.height)
        middle = ((rect.centerx, rect.top - 3), (rect.centerx, rect.bottom + 2))
    else:
        height = round(rect.height * share)
        filled = pygame.Rect(rect.left, rect.bottom - height, rect.width, height)
        middle = ((rect.left - 3, rect.centery), (rect.right + 2, rect.centery))
    if filled.width and filled.height:
        canvas.draw_rect(white, filled, radius=6)
    canvas.draw_rect(roles["rim"], rect, 1, radius=6)
    canvas.draw_line(roles["glow"], *middle, 1)
