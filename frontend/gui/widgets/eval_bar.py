"""Material evaluation bar shown beside the board."""

from __future__ import annotations

import pygame
from frontend.gui.theme import THEMES

from gui.render import Render


def draw_eval_bar(canvas: Render, rect: pygame.Rect, value: float, theme=None) -> None:
    """Draw a vertical white advantage bar, where positive favors White."""
    roles = (theme or THEMES["dark_winter"]).roles
    canvas.draw_rect(roles["surface"], rect, radius=5)
    center = rect.centery
    canvas.draw_line(roles["border"], (rect.left, center), (rect.right, center), 1)
    value = max(-1.0, min(1.0, value))
    half = round(rect.height * abs(value) / 2)
    if value >= 0:
        fill = pygame.Rect(rect.left, center - half, rect.width, half)
        color = roles["text"]
    else:
        fill = pygame.Rect(rect.left, center, rect.width, half)
        color = roles["text_muted"]
    canvas.draw_rect(color, fill, radius=4)
    canvas.draw_rect(roles["border"], rect, 1, radius=5)
