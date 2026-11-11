"""Glass cards shared by the Cyber Frost screens."""

from __future__ import annotations

import pygame

from gui.render import Render


def draw_card(
    canvas: Render,
    roles: dict[str, str],
    rect: pygame.Rect,
    *,
    title: str = "",
    description: str = "",
    hovered: bool = False,
    highlight: bool = False,
    title_size: int = 20,
    description_size: int = 12,
) -> None:
    """Draw a frosted card with an optional title and description pinned to its bottom."""
    canvas.draw_glass(
        rect,
        roles["surface_alt"] if hovered else roles["surface"],
        alpha=235 if hovered else 215,
        radius=14,
        border=roles["glow"] if hovered or highlight else roles["border"],
        rim=roles["rim"],
    )
    if highlight:
        canvas.draw_rect(roles["glow"], (rect.left + 14, rect.bottom - 3, rect.width - 28, 2))
    width = rect.width - 36
    if title:
        y = rect.bottom - 18 - description_size - 8 - round(title_size * 1.25)
        canvas.text(
            title_size, title, roles["text"], (rect.left + 18, y), bold=True, max_width=width
        )
    if description:
        canvas.text(
            description_size,
            description,
            roles["text_muted"],
            (rect.left + 18, rect.bottom - 18 - round(description_size * 1.3)),
            max_width=width,
        )


def draw_section_title(
    canvas: Render, roles: dict[str, str], eyebrow: str, title: str, position: tuple[int, int]
) -> None:
    """Draw a small glowing eyebrow label above a large screen title."""
    x, y = position
    canvas.text(11, eyebrow.upper(), roles["glow"], (x, y), bold=True)
    canvas.text(26, title, roles["text"], (x, y + 16), bold=True, max_width=880)


def draw_stat(
    canvas: Render, roles: dict[str, str], rect: pygame.Rect, label: str, value: str
) -> None:
    """Draw a small glass tile with a muted label above a large display value."""
    canvas.draw_glass(rect, roles["surface"], alpha=210, radius=12, border=roles["border"])
    canvas.text(11, label.upper(), roles["text_muted"], (rect.left + 14, rect.top + 9), bold=True)
    canvas.text(
        22,
        value,
        roles["primary"],
        (rect.left + 14, rect.top + 24),
        bold=True,
        max_width=rect.width - 28,
    )


def draw_table(
    canvas: Render,
    roles: dict[str, str],
    rect: pygame.Rect,
    headers: list[tuple[str, int, bool]],
    rows: int,
    row_step: int,
    row_top: int,
) -> None:
    """Draw a glass table card: a header band with (label, x, active) columns and row stripes."""
    canvas.draw_glass(rect, roles["surface"], alpha=205, radius=14, border=roles["border"])
    header = pygame.Rect(rect.left + 8, rect.top + 8, rect.width - 16, 28)
    canvas.draw_glass(header, roles["surface_alt"], alpha=230, radius=8)
    for label, x, active in headers:
        canvas.text(
            11,
            label.upper(),
            roles["primary"] if active else roles["text_muted"],
            (x, header.top + 8),
            bold=True,
        )
    for index in range(rows):
        if index % 2:
            canvas.draw_glass(
                (rect.left + 8, row_top + index * row_step, rect.width - 16, row_step),
                roles["surface_alt"],
                alpha=110,
                radius=6,
            )


def draw_scroll_arrow(
    canvas: Render, roles: dict[str, str], rect: pygame.Rect, *, up: bool, enabled: bool
) -> None:
    """Draw a small glass scroll button with a chevron pointing up or down."""
    canvas.draw_glass(
        rect,
        roles["surface_alt"],
        alpha=230 if enabled else 120,
        radius=8,
        border=roles["glow"] if enabled else roles["border"],
    )
    x, y = rect.center
    tip, base = (y - 4, y + 3) if up else (y + 4, y - 3)
    color = roles["primary"] if enabled else roles["text_disabled"]
    canvas.draw_polygon(color, ((x, tip), (x - 6, base), (x + 6, base)))


def rank_color(roles: dict[str, str], rank: int) -> str:
    """Return the highlight color of the top three ranks."""
    return {1: roles["attention"], 2: roles["primary"], 3: roles["accent"]}.get(
        rank, roles["text_muted"]
    )


def draw_option(
    canvas: Render,
    roles: dict[str, str],
    button,
    subtitle: str,
    font_size: int,
    *,
    center: bool = False,
) -> None:
    """Draw a selectable tile: a left-aligned label with a right note, or a centered label."""
    rect = button.rect
    if not button.enabled:
        canvas.draw_glass(rect, roles["surface"], alpha=120, radius=10, border=roles["border"])
        text_color = roles["text_disabled"]
    elif button.selected:
        canvas.draw_glass(rect, roles["secondary"], alpha=235, radius=10, border=roles["glow"])
        canvas.draw_rect(roles["glow"], (rect.left, rect.top + 8, 3, rect.height - 16), radius=2)
        text_color = roles["on_secondary"]
    else:
        canvas.draw_glass(
            rect,
            roles["surface_alt"] if button.hovered else roles["surface"],
            alpha=225,
            radius=10,
            border=roles["glow"] if button.hovered else roles["border"],
            rim=roles["rim"],
        )
        text_color = roles["text"]
    if center:
        canvas.text(
            font_size,
            button.label,
            text_color,
            (0, 0),
            bold=True,
            max_width=rect.width - 12,
            center=(rect.centerx, rect.bottom - 16),
        )
        return
    note_width = 0
    if subtitle:
        note_width = round(canvas.font(11, canvas.scale, True).size(subtitle)[0] / canvas.scale)
        canvas.text(
            11,
            subtitle,
            roles["primary"] if button.enabled else roles["text_disabled"],
            (rect.right - 12 - note_width, rect.centery - 7),
            bold=True,
        )
    canvas.text(
        font_size,
        button.label,
        text_color,
        (rect.left + 14, rect.centery - round(font_size * 0.62)),
        bold=button.selected,
        max_width=rect.width - 34 - note_width,
    )
