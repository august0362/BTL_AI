"""Main menu screen."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from gui.assets_loader import get_font, piece_image, render_fit
from gui.render import Render
from gui.screens.base import Screen
from gui.widgets.button import Button

if TYPE_CHECKING:
    from gui.app import App


class MenuScreen(Screen):
    """Present the application's screen entry points."""

    def __init__(self, app: App) -> None:
        super().__init__(app)
        labels = (
            "menu.human_vs_bot",
            "menu.bot_vs_bot",
            "menu.ai_ranking",
            "menu.history",
            "menu.leaderboard",
            "menu.settings",
            "menu.quit",
        )
        self.buttons = [
            Button(pygame.Rect(340, 226 + i * 48, 280, 42), app.translator.t(key))
            for i, key in enumerate(labels)
        ]
        self.buttons[0].style = "primary"

    def handle_click(self, x: float, y: float) -> None:
        for index, button in enumerate(self.buttons):
            if button.contains((x, y)):
                if index == 0:
                    self.app.goto("setup_human")
                elif index == 1:
                    self.app.goto("setup_bots")
                elif index == 2:
                    self.app.goto("tournament")
                elif index == 3:
                    self.app.goto("history")
                elif index == 4:
                    self.app.goto("leaderboard")
                elif index == 5:
                    self.app.goto("settings")
                elif index == 6:
                    self.app.quit()
                return

    def draw(self, canvas: Render) -> None:
        canvas.fill(self.app.theme.roles["bg"])
        canvas.blit_image(piece_image("rhosgfx", "wK", 72), (444, 42))
        title = render_fit(
            get_font(37, bold=True),
            self.app.translator.t("app.title"),
            self.app.theme.roles["text"],
            900,
        )
        canvas.blit(title, title.get_rect(center=(480, 137)))
        if self.app.notice_key:
            notice = render_fit(
                get_font(17),
                self.app.translator.t(self.app.notice_key),
                self.app.theme.roles["text_muted"],
                900,
            )
            canvas.blit(notice, notice.get_rect(center=(480, 207)))
        for button in self.buttons:
            button.draw(canvas, get_font(18, bold=True))
