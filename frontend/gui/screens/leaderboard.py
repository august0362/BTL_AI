"""Display ranking statistics and confirm resets."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from gui.leaderboard_view import leaderboard_rows
from gui.render import Render
from gui.screens.base import Screen
from gui.widgets.button import Button
from gui.widgets.card import draw_section_title, draw_stat, draw_table, rank_color

if TYPE_CHECKING:
    from gui.app import App


class LeaderboardScreen(Screen):
    """Render the current leaderboard."""

    COLUMNS = (
        ("rank", 44),
        ("player", 96),
        ("games", 444),
        ("wins", 520),
        ("draws", 590),
        ("losses", 660),
        ("points", 734),
        ("elo", 824),
    )
    TABLE = pygame.Rect(24, 96, 912, 462)
    ROW_TOP = 140

    def __init__(self, app: App) -> None:
        super().__init__(app)
        self.confirming = False
        self.reset = Button(pygame.Rect(632, 576, 148, 40), app.translator.t("leaderboard.reset"))
        self.reset.style = "danger"
        self.back = Button(pygame.Rect(792, 576, 144, 40), app.translator.t("setup.back"))
        self.yes = Button(pygame.Rect(318, 340, 152, 42), app.translator.t("leaderboard.yes"))
        self.yes.style = "danger"
        self.no = Button(pygame.Rect(490, 340, 152, 42), app.translator.t("leaderboard.no"))

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
        roles = self.app.theme.roles
        t = self.app.translator.t
        canvas.draw_backdrop(roles)
        draw_section_title(
            canvas, roles, t("leaderboard.eyebrow"), t("leaderboard.title"), (24, 26)
        )
        # Up to 25 bots plus the human player.
        rows = leaderboard_rows(self.app.ranking, self.app.translator)[:26]
        games = sum(row.games for row in rows) // 2
        draw_stat(
            canvas, roles, pygame.Rect(632, 24, 140, 60), t("leaderboard.player"), str(len(rows))
        )
        draw_stat(canvas, roles, pygame.Rect(784, 24, 152, 60), t("leaderboard.games"), str(games))

        row_step = max(12, min(36, (self.TABLE.bottom - 8 - self.ROW_TOP) // max(1, len(rows))))
        headers = [(t(f"leaderboard.{key}"), x, key == "elo") for key, x in self.COLUMNS]
        draw_table(canvas, roles, self.TABLE, headers, len(rows), row_step, self.ROW_TOP)
        size = 14 if row_step >= 30 else 13 if row_step >= 20 else 11
        for index, row in enumerate(rows):
            top = self.ROW_TOP + index * row_step
            y = top + (row_step - round(size * 1.3)) // 2
            if row.player_id == "human":
                band = pygame.Rect(self.TABLE.left + 8, top, self.TABLE.width - 16, row_step)
                canvas.draw_glass(band, roles["accent"], alpha=55, radius=6)
            rank = f"{row.rank:02d}"
            canvas.text(size, rank, rank_color(roles, row.rank), (44, y), bold=True)
            canvas.text(size, row.name, roles["text"], (96, y), bold=row.rank <= 3, max_width=336)
            values = (
                str(row.games),
                str(row.wins),
                str(row.draws),
                str(row.losses),
                f"{row.points:g}",
            )
            for value, (_, x) in zip(values, self.COLUMNS[2:7], strict=True):
                canvas.text(size, value, roles["text_muted"], (x, y))
            canvas.text(size, str(row.elo), roles["primary"], (824, y), bold=True)

        self.reset.draw(canvas, 14)
        self.back.draw(canvas, 14)
        if self.confirming:
            canvas.draw_glass((0, 0, 960, 640), roles["bg"], alpha=170, radius=0)
            canvas.draw_glass(
                (280, 230, 400, 176),
                roles["surface"],
                alpha=240,
                radius=16,
                border=roles["rim"],
                rim=roles["glow"],
            )
            canvas.text(
                12,
                t("leaderboard.reset").upper(),
                roles["danger"],
                (0, 0),
                bold=True,
                center=(480, 262),
            )
            canvas.text(
                17,
                t("leaderboard.reset_confirm"),
                roles["text"],
                (0, 0),
                bold=True,
                max_width=360,
                center=(480, 298),
            )
            self.yes.draw(canvas, 14)
            self.no.draw(canvas, 14)
