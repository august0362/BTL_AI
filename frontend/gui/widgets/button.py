"""Small reusable button drawing and hit testing."""

from __future__ import annotations

from dataclasses import dataclass

import pygame

from gui.render import Render


@dataclass
class Button:
    """A rounded clickable rectangle with a label."""

    current_theme = None

    rect: pygame.Rect
    label: str
    enabled: bool = True
    selected: bool = False
    hovered: bool = False
    pressed: bool = False
    style: str = "secondary"

    def draw(self, canvas: Render, font: pygame.font.Font | int, theme=None) -> None:
        """Draw the button and its centered label."""
        from gui.theme import THEMES

        roles = (theme or self.current_theme or THEMES["dark_winter"]).roles
        color = roles["text_disabled"] if not self.enabled else roles[self.style]
        if self.selected:
            color = roles["accent"]
        elif self.pressed:
            color = roles["primary"]
        elif self.hovered:
            if self.style == "primary":
                color = roles["primary_hover"]
            elif self.style != "danger":
                color = roles["secondary_hover"]
        quiet = (
            self.enabled
            and self.style == "secondary"
            and not (self.selected or self.pressed or self.hovered)
        )
        if quiet:
            canvas.draw_glass(
                self.rect,
                roles["surface_alt"],
                alpha=225,
                radius=10,
                border=roles["border"],
                rim=roles["rim"],
            )
        else:
            canvas.draw_rect(color, self.rect, radius=10)
            edge = (
                roles["primary"]
                if self.selected
                else roles["glow"]
                if self.hovered
                else roles["border"]
            )
            canvas.draw_rect(edge, self.rect, 2 if self.selected else 1, radius=10)
        text_color = roles["text_disabled"]
        if self.enabled:
            if self.selected:
                text_color = roles["on_accent"]
            elif self.pressed:
                text_color = roles["on_primary"]
            elif self.hovered and self.style == "primary":
                text_color = roles.get("on_primary_hover", roles["on_primary"])
            elif self.hovered and self.style == "secondary":
                text_color = roles.get("on_secondary_hover", roles["on_secondary"])
            elif self.style == "danger":
                text_color = roles.get("on_danger", roles["on_primary"])
            elif self.style == "primary":
                text_color = roles["on_primary"]
            elif quiet:
                text_color = roles["text"]
            else:
                text_color = roles["on_secondary"]
        font_size = (
            font if isinstance(font, int) else max(1, round(font.get_height() / canvas.scale))
        )
        text = canvas.render_fit(
            font_size,
            self.label,
            text_color,
            max(1, self.rect.width - 16),
            bold=True,
        )
        canvas.surface.blit(text, text.get_rect(center=canvas.point(self.rect.center)))

    def contains(self, point: tuple[float, float]) -> bool:
        """Return whether a point falls inside an enabled button."""
        return self.enabled and self.rect.collidepoint(point)

    def update_hover(self, point: tuple[float, float]) -> None:
        """Update hover and pressed states, ignoring disabled buttons."""
        self.hovered = self.contains(point)
        self.pressed = False
        try:
            pygame.mouse.set_cursor(
                pygame.SYSTEM_CURSOR_HAND if self.hovered else pygame.SYSTEM_CURSOR_ARROW
            )
        except pygame.error:
            pass
