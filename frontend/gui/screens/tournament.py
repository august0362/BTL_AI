"""AI ranking screen: start a round-robin tournament and watch the standings."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from gui.assets_loader import get_font
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
from gui.widgets.progress_bar import ProgressBar

if TYPE_CHECKING:
    from gui.app import App


class TournamentScreen(Screen):
    """Show the AI ranking table with a start button and history entry."""

    COLUMNS = (
        ("tournament.rank", 70),
        ("tournament.bot", 130),
        ("tournament.games", 412),
        ("tournament.wins", 466),
        ("tournament.draws", 516),
        ("tournament.losses", 562),
        ("tournament.points", 612),
        ("tournament.time", 668),
        ("tournament.memory", 744),
        ("tournament.total", 828),
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

    def __init__(self, app: App) -> None:
        super().__init__(app)
        # More than 14 bots (19 by default) use 16 px rows and move the controls down.
        self._dense = len(app.tournament.settings.bots) > 14
        button_y = 524 if self._dense else 470
        self._status_y = 486 if self._dense else 434
        self.start = Button(
            pygame.Rect(70, button_y, 210, 44), app.translator.t("tournament.start")
        )
        self.start.style = "primary"
        self.history = Button(
            pygame.Rect(300, button_y, 180, 44), app.translator.t("tournament.history")
        )
        self.back = Button(pygame.Rect(800, button_y, 90, 44), app.translator.t("setup.back"))
        self.progress_bar = ProgressBar(pygame.Rect(70, 466 if self._dense else 410, 820, 12))
        self.sort_field = DEFAULT_SORT
        self._sorted_at = 0

    def header_rects(self) -> dict[str, pygame.Rect]:
        """Return the clickable area of every sortable column header."""
        rects = {}
        for index, (key, x) in enumerate(self.COLUMNS):
            if key in self.SORT_COLUMNS:
                right = self.COLUMNS[index + 1][1] if index + 1 < len(self.COLUMNS) else 900
                rects[self.SORT_COLUMNS[key]] = pygame.Rect(x - 4, 122, right - x, 24)
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
        translator = self.app.translator
        snapshot = self.app.tournament.snapshot()
        canvas.fill(roles["bg"])
        canvas.blit(
            get_font(28, bold=True).render(translator.t("tournament.title"), True, roles["text"]),
            (70, 46),
        )
        if snapshot.running:
            # Elapsed and estimated remaining time, right-aligned in the top-right corner.
            elapsed = format_duration(snapshot.elapsed_s)
            clock = (
                translator.t("tournament.estimating", elapsed=elapsed)
                if snapshot.eta_s is None
                else translator.t(
                    "tournament.eta", elapsed=elapsed, eta=format_duration(snapshot.eta_s)
                )
            )
            image = get_font(14).render(clock, True, roles["text_muted"])
            width = image.get_width() / max(canvas.scale, 1e-6)
            canvas.blit(image, (890 - width, 58))
        standings = self._standings(snapshot)
        canvas.blit(
            get_font(14).render(self._status(snapshot), True, roles["text_muted"]), (70, 96)
        )
        if (
            self.sort_field != DEFAULT_SORT
            and pygame.time.get_ticks() - self._sorted_at >= self.SORT_RESET_MS
        ):
            self.sort_field = DEFAULT_SORT
        header_font = get_font(12, bold=True)
        for key, x in self.COLUMNS:
            sorted_here = self.SORT_COLUMNS.get(key) == self.sort_field
            label = translator.t(key) + (" ▼" if sorted_here else "")
            color = roles["text"] if sorted_here else roles["accent"]
            canvas.blit(header_font.render(label, True, color), (x, 128))
        row_font = get_font(11 if self._dense else 12)
        playing = set(snapshot.current_pair or ()) if snapshot.running else set()
        rows = sort_rows(tournament_rows(standings, translator), self.sort_field)[:20]
        # Nine bots keep the roomy 26 px rows; up to 14 bots use 18 px rows, more use 16 px.
        row_step = 26 if len(rows) <= 9 else 18 if len(rows) <= 14 else 16
        for index, row in enumerate(rows):
            y = (150 if row_step == 16 else 154) + index * row_step
            if row.player_id in playing:
                # Highlight the two bots of the game in progress with theme colours.
                band = pygame.Rect(60, y - 2, 840, row_step)
                canvas.draw_rect(roles["surface"], band, radius=6)
                canvas.draw_rect(roles["accent"], band, width=2, radius=6)
            values = (
                str(row.rank),
                row.name,
                str(row.games),
                str(row.wins),
                str(row.draws),
                str(row.losses),
                format_points(row.points),
                format_seconds(row.think_time_s),
                format_memory(row.memory_mb),
                format_total(row.total),
            )
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
            canvas.blit(
                get_font(12).render(snapshot.error, True, roles["danger"]), (70, self._status_y)
            )
        elif snapshot.running and snapshot.current_pair is not None:
            first, second = snapshot.current_pair
            text = translator.t(
                "tournament.current_pair",
                a=translator.t(f"players.{first}"),
                b=translator.t(f"players.{second}"),
            )
            canvas.blit(get_font(12).render(text, True, roles["text_muted"]), (70, self._status_y))

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
