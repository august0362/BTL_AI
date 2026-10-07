"""AI ranking screen: start a round-robin tournament and watch the standings."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from gui.assets_loader import get_font
from gui.render import Render
from gui.screens.base import Screen
from gui.tournament_view import (
    format_points,
    format_seconds,
    provisional_standings,
    tournament_rows,
)
from gui.widgets.button import Button
from gui.widgets.progress_bar import ProgressBar

if TYPE_CHECKING:
    from gui.app import App


class TournamentScreen(Screen):
    """Show the AI ranking table with a start button and history entry."""

    COLUMNS = (
        ("tournament.rank", 70),
        ("tournament.bot", 130),
        ("tournament.games", 505),
        ("tournament.wins", 565),
        ("tournament.draws", 630),
        ("tournament.losses", 695),
        ("tournament.points", 755),
        ("tournament.time", 830),
    )

    def __init__(self, app: App) -> None:
        super().__init__(app)
        self.start = Button(pygame.Rect(70, 470, 210, 44), app.translator.t("tournament.start"))
        self.start.style = "primary"
        self.history = Button(
            pygame.Rect(300, 470, 180, 44), app.translator.t("tournament.history")
        )
        self.back = Button(pygame.Rect(800, 470, 90, 44), app.translator.t("setup.back"))
        self.progress_bar = ProgressBar(pygame.Rect(70, 396, 820, 14))

    def handle_click(self, x: float, y: float) -> None:
        point = (x, y)
        if self.start.contains(point):
            if self.app.tournament.snapshot().running:
                self.app.stop_tournament()
            else:
                self.app.start_tournament()
        elif self.history.contains(point):
            self.app.goto("tournament_history")
        elif self.back.contains(point):
            self.app.goto("menu")

    def draw(self, canvas: Render) -> None:
        roles = self.app.theme.roles
        translator = self.app.translator
        snapshot = self.app.tournament.snapshot()
        canvas.fill(roles["bg"])
        canvas.blit(
            get_font(28, bold=True).render(translator.t("tournament.title"), True, roles["text"]),
            (70, 46),
        )
        standings = self._standings(snapshot)
        canvas.blit(
            get_font(14).render(self._status(snapshot), True, roles["text_muted"]), (70, 96)
        )
        header_font = get_font(12, bold=True)
        for key, x in self.COLUMNS:
            canvas.blit(header_font.render(translator.t(key), True, roles["accent"]), (x, 128))
        row_font = get_font(12)
        for index, row in enumerate(tournament_rows(standings, translator)[:8]):
            values = (
                str(row.rank),
                row.name,
                str(row.games),
                str(row.wins),
                str(row.draws),
                str(row.losses),
                format_points(row.points),
                format_seconds(row.think_time_s),
            )
            y = 160 + index * 29
            for value, (_, x) in zip(values, self.COLUMNS, strict=True):
                canvas.blit(row_font.render(value, True, roles["text"]), (x, y))
        self.progress_bar.draw(canvas, self.app.theme, snapshot.progress)
        self.start.label = translator.t(
            "tournament.stop" if snapshot.running else "tournament.start"
        )
        self.start.style = "danger" if snapshot.running else "primary"
        self.start.draw(canvas, get_font(15, bold=True))
        self.history.draw(canvas, get_font(14))
        self.back.draw(canvas, get_font(14))
        if snapshot.error:
            canvas.blit(get_font(12).render(snapshot.error, True, roles["danger"]), (70, 430))
        elif snapshot.running and snapshot.current_pair is not None:
            first, second = snapshot.current_pair
            text = translator.t(
                "tournament.current_pair",
                a=translator.t(f"players.{first}"),
                b=translator.t(f"players.{second}"),
            )
            canvas.blit(get_font(12).render(text, True, roles["text_muted"]), (70, 430))

    def _standings(self, snapshot):
        if snapshot.standings:
            return snapshot.standings
        battles = self.app.tournament_history.list()
        if battles and battles[0].standings:
            return battles[0].standings
        return provisional_standings(self.app.tournament.settings.bots)

    def _status(self, snapshot) -> str:
        translator = self.app.translator
        if snapshot.running:
            return translator.t(
                "tournament.running",
                done=snapshot.games_done,
                total=snapshot.games_total,
                ply=snapshot.plies_current,
                limit=snapshot.plies_limit,
            )
        if snapshot.stopped:
            return translator.t("tournament.stopped")
        result = snapshot.result
        if result is not None and result.battle is not None:
            return translator.t(
                "tournament.finished_battle",
                index=result.battle,
                done=result.games_played,
                total=result.games_total,
            )
        battles = self.app.tournament_history.list()
        if battles and battles[0].battle is not None:
            return translator.t(
                "tournament.finished_battle",
                index=battles[0].battle,
                done=battles[0].games_played,
                total=battles[0].games_total,
            )
        return translator.t("tournament.not_started")
