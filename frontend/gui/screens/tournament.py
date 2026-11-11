"""AI ranking screen: start a round-robin tournament and watch the standings."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from gui.render import Render
from gui.screens.base import Screen
from gui.tournament_view import (
    DEFAULT_SORT,
    format_duration,
    format_memory,
    format_points,
    format_seconds,
    format_total,
    provisional_standings,
    sort_rows,
    tournament_rows,
)
from gui.widgets.button import Button
from gui.widgets.card import draw_section_title, draw_stat, draw_table, rank_color
from gui.widgets.progress_bar import ProgressBar

if TYPE_CHECKING:
    from gui.app import App


class TournamentScreen(Screen):
    """Show the AI ranking table with a start button and history entry."""

    COLUMNS = (
        ("tournament.rank", 44),
        ("tournament.bot", 96),
        ("tournament.games", 404),
        ("tournament.wins", 462),
        ("tournament.draws", 514),
        ("tournament.losses", 562),
        ("tournament.points", 614),
        ("tournament.time", 676),
        ("tournament.memory", 762),
        ("tournament.total", 848),
    )
    # Clickable headers -> row field; any other order falls back to the ranking after 5 s.
    SORT_COLUMNS = {
        "tournament.games": "games",
        "tournament.wins": "wins",
        "tournament.draws": "draws",
        "tournament.losses": "losses",
        "tournament.points": "points",
        "tournament.time": "think_time_s",
        "tournament.memory": "memory_mb",
        "tournament.total": "total",
    }
    SORT_RESET_MS = 5_000
    TABLE = pygame.Rect(24, 96, 912, 416)
    HEADER_Y = 104
    ROW_TOP = 140
    CONTROLS = pygame.Rect(24, 522, 912, 106)

    def __init__(self, app: App) -> None:
        super().__init__(app)
        self.start = Button(pygame.Rect(40, 580, 200, 38), app.translator.t("tournament.start"))
        self.start.style = "primary"
        self.history = Button(
            pygame.Rect(252, 580, 168, 38), app.translator.t("tournament.history")
        )
        self.back = Button(pygame.Rect(792, 580, 128, 38), app.translator.t("setup.back"))
        self.progress_bar = ProgressBar(pygame.Rect(40, 558, 880, 8))
        self.sort_field = DEFAULT_SORT
        self._sorted_at = 0

    def header_rects(self) -> dict[str, pygame.Rect]:
        """Return the clickable area of every sortable column header."""
        rects = {}
        for index, (key, x) in enumerate(self.COLUMNS):
            if key in self.SORT_COLUMNS:
                right = self.COLUMNS[index + 1][1] if index + 1 < len(self.COLUMNS) else 928
                rects[self.SORT_COLUMNS[key]] = pygame.Rect(x - 4, self.HEADER_Y, right - x, 28)
        return rects

    def sort_by(self, field: str) -> None:
        """Sort the table by ``field`` (highest first); the ranking order returns after 5 s."""
        self.sort_field = field
        self._sorted_at = pygame.time.get_ticks()

    def handle_click(self, x: float, y: float) -> None:
        point = (x, y)
        for field, rect in self.header_rects().items():
            if rect.collidepoint(point):
                self.sort_by(field)
                return
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
        t = self.app.translator.t
        snapshot = self.app.tournament.snapshot()
        canvas.draw_backdrop(roles)
        draw_section_title(canvas, roles, t("tournament.eyebrow"), t("tournament.title"), (24, 26))
        bots = str(len(self.app.tournament.settings.bots))
        draw_stat(canvas, roles, pygame.Rect(632, 24, 140, 60), t("tournament.stat_bots"), bots)
        draw_stat(
            canvas,
            roles,
            pygame.Rect(784, 24, 152, 60),
            t("tournament.stat_games"),
            self._games_label(snapshot),
        )

        if (
            self.sort_field != DEFAULT_SORT
            and pygame.time.get_ticks() - self._sorted_at >= self.SORT_RESET_MS
        ):
            self.sort_field = DEFAULT_SORT
        rows = sort_rows(
            tournament_rows(self._standings(snapshot), self.app.translator), self.sort_field
        )
        row_step = max(12, min(36, (self.TABLE.bottom - 8 - self.ROW_TOP) // max(1, len(rows))))
        headers = [
            (
                t(key) + (" \u25bc" if self.SORT_COLUMNS.get(key) == self.sort_field else ""),
                x,
                self.SORT_COLUMNS.get(key) == self.sort_field,
            )
            for key, x in self.COLUMNS
        ]
        draw_table(canvas, roles, self.TABLE, headers, len(rows), row_step, self.ROW_TOP)
        size = 14 if row_step >= 30 else 13 if row_step >= 20 else 11
        playing = set(snapshot.current_pair or ()) if snapshot.running else set()
        for index, row in enumerate(rows):
            top = self.ROW_TOP + index * row_step
            y = top + (row_step - round(size * 1.3)) // 2
            if row.player_id in playing:
                # Highlight the two bots of the game in progress.
                band = pygame.Rect(self.TABLE.left + 8, top, self.TABLE.width - 16, row_step)
                canvas.draw_glass(band, roles["accent"], alpha=70, radius=6, border=roles["glow"])
                canvas.draw_rect(roles["glow"], (band.left, top + 3, 3, row_step - 6), radius=2)
            rank = f"{row.rank:02d}"
            canvas.text(size, rank, rank_color(roles, row.rank), (44, y), bold=True)
            canvas.text(size, row.name, roles["text"], (96, y), bold=row.rank <= 3, max_width=296)
            values = (
                str(row.games),
                str(row.wins),
                str(row.draws),
                str(row.losses),
                format_points(row.points),
                format_seconds(row.think_time_s),
                format_memory(row.memory_mb),
            )
            for value, (_, x) in zip(values, self.COLUMNS[2:9], strict=True):
                canvas.text(size, value, roles["text_muted"], (x, y))
            canvas.text(size, format_total(row.total), roles["primary"], (848, y), bold=True)

        canvas.draw_glass(
            self.CONTROLS,
            roles["surface"],
            alpha=205,
            radius=14,
            border=roles["border"],
            rim=roles["rim"],
        )
        dot = roles["glow"] if snapshot.running else roles["text_disabled"]
        canvas.draw_circle(dot, (46, 541), 4)
        canvas.text(13, self._status(snapshot), roles["text"], (58, 532), bold=True, max_width=520)
        if snapshot.running:
            # Elapsed and estimated remaining time, right-aligned on the status line.
            elapsed = format_duration(snapshot.elapsed_s)
            clock = (
                t("tournament.estimating", elapsed=elapsed)
                if snapshot.eta_s is None
                else t("tournament.eta", elapsed=elapsed, eta=format_duration(snapshot.eta_s))
            )
            width = round(canvas.font(12, canvas.scale).size(clock)[0] / canvas.scale)
            canvas.text(12, clock, roles["text_muted"], (920 - width, 533))
        self.progress_bar.draw(canvas, self.app.theme, snapshot.progress)
        self.start.label = t("tournament.stop" if snapshot.running else "tournament.start")
        self.start.style = "danger" if snapshot.running else "primary"
        self.start.draw(canvas, 15)
        self.history.draw(canvas, 14)
        self.back.draw(canvas, 14)
        if snapshot.error:
            canvas.text(12, snapshot.error, roles["danger"], (436, 590), max_width=340)
        elif snapshot.running and snapshot.current_pair is not None:
            first, second = snapshot.current_pair
            text = t("tournament.current_pair", a=t(f"players.{first}"), b=t(f"players.{second}"))
            canvas.text(12, text, roles["glow"], (436, 590), bold=True, max_width=340)

    def _games_label(self, snapshot) -> str:
        if snapshot.running and snapshot.games_total:
            return f"{snapshot.games_done}/{snapshot.games_total}"
        battles = self.app.tournament_history.list()
        if battles:
            return f"{battles[0].games_played}/{battles[0].games_total}"
        return "0"

    def _standings(self, snapshot):
        if snapshot.standings:
            return snapshot.standings
        battles = self.app.tournament_history.list()
        bots = self.app.tournament.settings.bots
        # Show the last battle only while its line-up matches the configured bots.
        if battles and battles[0].standings and set(battles[0].participants) == set(bots):
            return battles[0].standings
        return provisional_standings(bots)

    def _status(self, snapshot) -> str:
        translator = self.app.translator
        if snapshot.running:
            running = translator.t(
                "tournament.running",
                done=snapshot.games_done,
                total=snapshot.games_total,
                ply=snapshot.plies_current,
                limit=snapshot.plies_limit,
            )
            return f"{running} · {translator.t('tournament.provisional')}"
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
