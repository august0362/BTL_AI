"""Scrollable SAN move list."""

from __future__ import annotations

import pygame
from frontend.gui.theme import THEMES

from gui.render import Render


def draw_move_list(
    canvas: Render,
    rect: pygame.Rect,
    moves: tuple,
    font: int,
    theme=None,
) -> None:
    """Draw moves in two-column chess notation, keeping the latest in view."""
    roles = (theme or THEMES["dark_winter"]).roles
    canvas.draw_rect(roles["surface"], rect, radius=10)
    line_height = 25
    visible = max(1, rect.height // line_height)
    rows = [
        (moves[index].san, moves[index + 1].san if index + 1 < len(moves) else "")
        for index in range(0, len(moves), 2)
    ]
    rows = rows[-visible:]
    for row_index, (white, black) in enumerate(rows):
        y = rect.top + 5 + row_index * line_height
        if row_index == len(rows) - 1:
            canvas.draw_rect(
                roles["surface_alt"],
                (rect.left + 3, y - 2, rect.width - 6, 23),
                radius=8,
            )
        label = f"{len(moves) // 2 - len(rows) + row_index + 1:>2}."
        canvas.text(font, label, roles["text_muted"], (rect.left + 8, y))
        canvas.text(font, white, roles["text"], (rect.left + 39, y))
        canvas.text(font, black, roles["text"], (rect.left + 103, y))
