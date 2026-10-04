"""Display ranking statistics and confirm resets."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from gui.assets_loader import get_font
from gui.leaderboard_view import leaderboard_rows
from gui.render import Render
from gui.screens.base import Screen
from gui.widgets.button import Button

if TYPE_CHECKING:
    from gui.app import App


class LeaderboardScreen(Screen):
    """Render the current leaderboard."""

    def __init__(self, app: App) -> None:
        super().__init__(app)
        self.confirming = False
        self.reset = Button(pygame.Rect(350, 570, 120, 38), app.translator.t("leaderboard.reset"))
        self.reset.style = "danger"
        self.back = Button(pygame.Rect(490, 570, 120, 38), app.translator.t("setup.back"))
        self.yes = Button(pygame.Rect(350, 500, 100, 38), app.translator.t("leaderboard.yes"))
        self.no = Button(pygame.Rect(470, 500, 100, 38), app.translator.t("leaderboard.no"))

    def handle_click(self, x: float, y: float) -> None:
        point = (x, y)
        if self.confirming:
            if self.yes.contains(point):
                self.app.reset_ranking()
                self.confirming = False
            elif self.no.contains(point):
                self.confirming = False
        elif self.reset.contains(point):
            self.confirming = True
        elif self.back.contains(point):
            self.app.goto("menu")

    def draw(self, canvas: Render) -> None:
        canvas.fill(self.app.theme.roles["bg"])
        canvas.blit(
            get_font(28, bold=True).render(
                self.app.translator.t("leaderboard.title"), True, self.app.theme.roles["text"]
            ),
            (80, 55),
        )
        headers = ("rank", "player", "games", "wins", "draws", "losses", "points", "elo")
        widths = (52, 235, 75, 65, 65, 65, 75, 70)
        x = 70
        font = get_font(12, bold=True)
        for key, width in zip(headers, widths, strict=True):
            canvas.blit(
                font.render(
                    self.app.translator.t(f"leaderboard.{key}"),
                    True,
                    self.app.theme.roles["accent"],
                ),
                (x, 130),
            )
            x += width
        for index, row in enumerate(leaderboard_rows(self.app.ranking, self.app.translator)[:11]):
            vals = (
                str(row.rank),
                row.name,
                str(row.games),
                str(row.wins),
                str(row.draws),
                str(row.losses),
                f"{row.points:g}",
                str(row.elo),
            )
            x = 70
            for value, width in zip(vals, widths, strict=True):
                canvas.blit(
                    font.render(value, True, self.app.theme.roles["text"]), (x, 165 + index * 31)
                )
                x += width
        self.reset.draw(canvas, get_font(13))
        self.back.draw(canvas, get_font(13))
        if self.confirming:
            canvas.draw_rect(self.app.theme.roles["surface"], (245, 450, 470, 112), radius=10)
            canvas.blit(
                get_font(16).render(
                    self.app.translator.t("leaderboard.reset_confirm"),
                    True,
                    self.app.theme.roles["text"],
                ),
                (270, 466),
            )
            self.yes.draw(canvas, get_font(13))
            self.no.draw(canvas, get_font(13))
