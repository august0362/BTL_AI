"""SAN move table that keeps the latest moves in view."""

from __future__ import annotations

import pygame

from gui.render import Render
from gui.theme import THEMES


def draw_move_list(
    canvas: Render,
    rect: pygame.Rect,
    moves: tuple,
    font: int,
    theme=None,
) -> None:
    """Draw moves as numbered White / Black rows, highlighting the latest one."""
    roles = (theme or THEMES["dark_winter"]).roles
    line_height = 24
    visible = max(1, rect.height // line_height)
    rows = [
        (moves[index].san, moves[index + 1].san if index + 1 < len(moves) else "")
        for index in range(0, len(moves), 2)
    ]
    first = max(0, len(rows) - visible)
    column = (rect.width - 44) // 2
    for row_index, (white, black) in enumerate(rows[first:]):
        y = rect.top + row_index * line_height
        number = first + row_index + 1
        if number % 2 == 0:
            canvas.draw_rect(roles["surface_alt"], (rect.left, y, rect.width, 22), radius=6)
        latest_x = None
        if first + row_index == len(rows) - 1:
            latest_x = rect.left + 40 + (column if black else 0)
            canvas.draw_glass(
                (latest_x - 4, y + 1, column - 4, 20), roles["accent"], alpha=70, radius=5
            )
            canvas.draw_rect(roles["glow"], (latest_x - 4, y + 3, 2, 16))
        canvas.text(font, f"{number}", roles["text_muted"], (0, 0), center=(rect.left + 18, y + 11))
        canvas.text(font, white, roles["text"], (rect.left + 40, y + 2), max_width=column - 8)
        canvas.text(
            font, black, roles["text"], (rect.left + 40 + column, y + 2), max_width=column - 8
        )
