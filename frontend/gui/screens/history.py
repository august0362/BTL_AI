"""Browse saved games and export their PGN files."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from gui.render import Render
from gui.screens.base import Screen
from gui.widgets.button import Button
from gui.widgets.card import draw_scroll_arrow, draw_section_title, draw_stat
from tournament.records import GameRecord

if TYPE_CHECKING:
    from gui.app import App


class HistoryScreen(Screen):
    """Show recent game records."""

    VISIBLE_ROWS = 7
    ROW_TOP = 104
    ROW_STEP = 64

    def __init__(self, app: App) -> None:
        super().__init__(app)
        self.records = app.history.list()
        self.scroll_offset = 0
        self.rows = [
            Button(pygame.Rect(24, self.ROW_TOP + i * self.ROW_STEP, 860, 56), "")
            for i in range(self.VISIBLE_ROWS)
        ]
        self.scroll_up = pygame.Rect(896, 104, 40, 40)
        self.scroll_down = pygame.Rect(896, 504, 40, 40)
        self.export_button = Button(
            pygame.Rect(632, 576, 148, 40),
            app.translator.t("history.export_pgn"),
            enabled=bool(self.records),
        )
        self.export_button.style = "primary"
        self.back = Button(pygame.Rect(792, 576, 144, 40), app.translator.t("setup.back"))
        self.selected = 0
        self.notice = ""
        self._update_rows()

    def _update_rows(self) -> None:
        for row_index, button in enumerate(self.rows):
            record_index = self.scroll_offset + row_index
            button.label = (
                self._label(self.records[record_index]) if record_index < len(self.records) else ""
            )
            button.enabled = record_index < len(self.records)
            button.selected = record_index == self.selected

    def _scroll(self, amount: int) -> None:
        max_offset = max(0, len(self.records) - self.VISIBLE_ROWS)
        self.scroll_offset = max(0, min(max_offset, self.scroll_offset + amount))
        self._update_rows()

    def handle_scroll(self, dy: int) -> None:
        if dy:
            self._scroll(-dy)

    def _label(self, record: GameRecord) -> str:
        return f"{record.white_name} vs {record.black_name}"

    def _details(self, record: GameRecord) -> str:
        """Return the outcome, termination and series note of a record."""
        t = self.app.translator.t
        outcome = (
            t("game.result.draw")
            if record.result.winner is None
            else t(
                "game.result.win",
                name=record.white_name if record.result.winner else record.black_name,
            )
        )
        details = f"{outcome} · {t(f'termination.{record.result.termination.value}')}"
        if record.series_game_index:
            details += " · " + t(
                "history.series_note",
                index=record.series_game_index,
                total=3,
                series=(record.series_id or "")[:6],
            )
        return details

    def handle_click(self, x: float, y: float) -> None:
        point = (x, y)
        if self.scroll_up.collidepoint(point):
            self._scroll(-1)
            return
        if self.scroll_down.collidepoint(point):
            self._scroll(1)
            return
        for row_index, button in enumerate(self.rows):
            if button.contains(point):
                record_index = self.scroll_offset + row_index
                if record_index >= len(self.records):
                    return
                self.selected = record_index
                self._update_rows()
                self.app.open_replay(self.records[record_index].game_id)
                return
        if self.export_button.contains(point) and self.records:
            record = self.records[self.selected]
            path = self.app.history.export_pgn(
                record.game_id, self.app.data_dir / "exports" / f"{record.game_id}.pgn"
            )
            self.notice = self.app.translator.t("history.exported", path=str(path))
        elif self.back.contains(point):
            self.app.goto("menu")

    def draw(self, canvas: Render) -> None:
        roles = self.app.theme.roles
        t = self.app.translator.t
        canvas.draw_backdrop(roles)
        draw_section_title(canvas, roles, t("history.eyebrow"), t("history.title"), (24, 26))
        draw_stat(
            canvas,
            roles,
            pygame.Rect(784, 24, 152, 60),
            t("history.stat_games"),
            str(len(self.records)),
        )
        if not self.records:
            canvas.draw_glass(
                (24, 104, 912, 120), roles["surface"], alpha=205, radius=14, border=roles["border"]
            )
            canvas.text(
                16, t("history.empty"), roles["text_muted"], (0, 0), bold=True, center=(480, 164)
            )
        for row_index, button in enumerate(self.rows):
            if button.enabled:
                self._draw_row(canvas, button, self.records[self.scroll_offset + row_index])
        if len(self.records) > self.VISIBLE_ROWS:
            self._draw_scrollbar(canvas)
        if self.notice:
            canvas.text(12, self.notice, roles["glow"], (24, 590), bold=True, max_width=590)
        self.export_button.draw(canvas, 14)
        self.back.draw(canvas, 14)

    def _draw_row(self, canvas: Render, button: Button, record: GameRecord) -> None:
        roles = self.app.theme.roles
        rect = button.rect
        canvas.draw_glass(
            rect,
            roles["surface_alt"] if button.hovered else roles["surface"],
            alpha=230 if button.hovered else 210,
            radius=12,
            border=roles["glow"] if button.hovered or button.selected else roles["border"],
            rim=roles["rim"],
        )
        if button.selected:
            canvas.draw_rect(
                roles["glow"], (rect.left, rect.top + 10, 3, rect.height - 20), radius=2
            )
        winner = record.result.winner
        score = "½-½" if winner is None else "1-0" if winner else "0-1"
        badge = pygame.Rect(rect.left + 14, rect.centery - 15, 60, 30)
        canvas.draw_glass(
            badge,
            roles["accent"] if winner is not None else roles["surface_alt"],
            alpha=90 if winner is not None else 200,
            radius=15,
            border=roles["border"],
        )
        canvas.text(
            14,
            score,
            roles["primary"] if winner is not None else roles["text_muted"],
            (0, 0),
            bold=True,
            center=badge.center,
        )
        date = record.started_at[:10]
        date_width = round(canvas.font(12, canvas.scale).size(date)[0] / canvas.scale)
        canvas.text(12, date, roles["text_muted"], (rect.right - 16 - date_width, rect.top + 20))
        width = rect.width - 108 - date_width - 24
        canvas.text(
            15,
            button.label,
            roles["text"],
            (rect.left + 90, rect.top + 9),
            bold=True,
            max_width=width,
        )
        canvas.text(
            12,
            self._details(record),
            roles["text_muted"],
            (rect.left + 90, rect.top + 32),
            max_width=width,
        )

    def _draw_scrollbar(self, canvas: Render) -> None:
        roles = self.app.theme.roles
        max_offset = len(self.records) - self.VISIBLE_ROWS
        draw_scroll_arrow(canvas, roles, self.scroll_up, up=True, enabled=self.scroll_offset > 0)
        draw_scroll_arrow(
            canvas, roles, self.scroll_down, up=False, enabled=self.scroll_offset < max_offset
        )
        track = pygame.Rect(914, 152, 4, 344)
        canvas.draw_rect(roles["surface_alt"], track, radius=2)
        thumb_height = max(24, round(track.height * self.VISIBLE_ROWS / len(self.records)))
        top = track.top + round((track.height - thumb_height) * self.scroll_offset / max_offset)
        canvas.draw_rect(roles["primary"], (track.left, top, track.width, thumb_height), radius=2)
