"""Main menu screen."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import pygame

from gui.assets_loader import piece_image
from gui.render import Render
from gui.screens.base import Screen
from gui.widgets.button import Button
from gui.widgets.card import draw_card

if TYPE_CHECKING:
    from gui.app import App

# (label key, target screen, piece icon); None target quits, None icon draws a power symbol.
ENTRIES = (
    ("human_vs_bot", "setup_human", "wK"),
    ("bot_vs_bot", "setup_bots", "bN"),
    ("ai_ranking", "tournament", "wQ"),
    ("history", "history", "wR"),
    ("leaderboard", "leaderboard", "wB"),
    ("settings", "settings", "wP"),
    ("quit", None, None),
)
MEMBER_BOTS = ("alphabeta_regression", "genetic_alphabeta", "mcts", "deep_rl")


class MenuScreen(Screen):
    """Present the application's screen entry points as cards."""

    def __init__(self, app: App) -> None:
        super().__init__(app)
        rects = [pygame.Rect(56 + i * 288, 222, 272, 156) for i in range(3)]
        rects += [pygame.Rect(56 + i * 216, 398, 200, 132) for i in range(4)]
        self.buttons = [
            Button(rect, app.translator.t(f"menu.{key}"))
            for rect, (key, _, _) in zip(rects, ENTRIES, strict=True)
        ]
        self.buttons[0].style = "primary"

    def handle_click(self, x: float, y: float) -> None:
        for button, (_, target, _) in zip(self.buttons, ENTRIES, strict=True):
            if button.contains((x, y)):
                if target is None:
                    self.app.quit()
                else:
                    self.app.goto(target)
                return

    def draw(self, canvas: Render) -> None:
        roles = self.app.theme.roles
        t = self.app.translator.t
        canvas.draw_backdrop(roles)
        self._draw_emblem(canvas, roles)

        badge = t("menu.badge")
        width = round(canvas.font(12, canvas.scale, True).size(badge)[0] / canvas.scale) + 40
        canvas.draw_glass(
            (56, 56, width, 26), roles["surface"], alpha=200, radius=13, border=roles["border"]
        )
        canvas.draw_circle(roles["glow"], (70, 69), 4)
        canvas.text(12, badge, roles["primary"], (82, 61), bold=True)

        canvas.text(56, "CHESS", roles["text"], (54, 92), display=True)
        offset = 54 + round(_display_width(canvas, 56, "CHESS ") / canvas.scale)
        canvas.text(56, "AI", roles["primary"], (offset, 92), display=True)
        offset += round(_display_width(canvas, 56, "AI ") / canvas.scale)
        canvas.text(22, "TOURNAMENT", roles["text_muted"], (offset, 122), display=True)
        canvas.text(18, t("menu.tagline"), roles["text_muted"], (56, 168), max_width=600)

        for index, (button, (key, _, icon)) in enumerate(zip(self.buttons, ENTRIES, strict=True)):
            big = index < 3
            draw_card(
                canvas,
                roles,
                button.rect,
                title=button.label,
                description=t(f"menu.desc_{key}"),
                hovered=button.hovered,
                highlight=button.style == "primary",
                title_size=24 if big else 18,
                description_size=13 if big else 11,
            )
            box = 46 if big else 36
            icon_rect = pygame.Rect(button.rect.left + 18, button.rect.top + 18, box, box)
            canvas.draw_rect(
                roles["primary"] if button.style == "primary" else roles["secondary"],
                icon_rect,
                radius=10,
            )
            if icon is None:
                self._draw_power(canvas, roles, icon_rect)
            else:
                canvas.blit_image(
                    piece_image("rhosgfx", icon, box - 8),
                    (icon_rect.left + 4, icon_rect.top + 4),
                )

        canvas.draw_glass(
            (56, 550, 848, 40), roles["surface"], alpha=170, radius=12, border=roles["border"]
        )
        canvas.draw_circle(roles["glow"], (76, 570), 4)
        members = " · ".join(self.app._localized_bot_name(bot_id) for bot_id in MEMBER_BOTS)
        canvas.text(
            12,
            f"{t('menu.members')}: {members}",
            roles["text_muted"],
            (88, 562),
            semibold=True,
            max_width=800,
        )
        if self.app.notice_key:
            canvas.text(
                14,
                t(self.app.notice_key),
                roles["attention"],
                (0, 0),
                max_width=848,
                center=(480, 614),
            )

    @staticmethod
    def _draw_power(canvas: Render, roles: dict[str, str], rect: pygame.Rect) -> None:
        """Draw a power symbol inside an icon box."""
        ring = rect.inflate(-14, -14)
        canvas.draw_arc(roles["danger"], ring, math.radians(-50), math.radians(230), 2)
        canvas.draw_line(
            roles["danger"], (rect.centerx, ring.top - 2), (rect.centerx, rect.centery), 2
        )

    @staticmethod
    def _draw_emblem(canvas: Render, roles: dict[str, str]) -> None:
        """Draw the frost rings and king that decorate the header."""
        center = (800, 118)
        for radius, color in ((98, roles["border"]), (74, roles["rim"]), (50, roles["border"])):
            canvas.draw_circle(color, center, radius, 1)
        canvas.draw_circle(roles["glow"], (center[0] + 74, center[1]), 4)
        canvas.draw_circle(roles["attention"], (center[0] - 52, center[1] - 52), 3)
        king = piece_image("rhosgfx", "wK", round(80 * canvas.scale)).copy()
        king.set_alpha(220)
        canvas.surface.blit(king, king.get_rect(center=canvas.point(center)))


def _display_width(canvas: Render, size: int, text: str) -> int:
    """Return the physical width of ``text`` in the display face."""
    from gui.assets_loader import get_display_font

    return get_display_font(size, text).size(text)[0]
