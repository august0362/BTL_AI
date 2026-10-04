"""Browse saved games and export their PGN files."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from gui.assets_loader import get_font, render_fit
from gui.render import Render
from gui.screens.base import Screen
from gui.widgets.button import Button
from tournament.records import GameRecord

if TYPE_CHECKING:
    from gui.app import App


class HistoryScreen(Screen):
    """Show recent game records."""

    VISIBLE_ROWS = 7

    def __init__(self, app: App) -> None:
        super().__init__(app)
        self.records = app.history.list()
        self.scroll_offset = 0
        self.rows = [
            Button(pygame.Rect(80, 155 + i * 58, 800, 48), "") for i in range(self.VISIBLE_ROWS)
        ]
        self.scroll_up = pygame.Rect(884, 155, 28, 22)
        self.scroll_down = pygame.Rect(916, 155, 28, 22)
        self.export_button = Button(
            pygame.Rect(365, 570, 135, 38),
            app.translator.t("history.export_pgn"),
            enabled=bool(self.records),
        )
        self.back = Button(pygame.Rect(515, 570, 120, 38), app.translator.t("setup.back"))
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
        outcome = (
            self.app.translator.t("game.result.draw")
            if record.result.winner is None
            else self.app.translator.t(
                "game.result.win",
                name=record.white_name if record.result.winner else record.black_name,
            )
        )
        termination = self.app.translator.t(f"termination.{record.result.termination.value}")
        suffix = f"  •  {record.started_at[:10]}"
        if record.series_game_index:
            suffix += "  •  " + self.app.translator.t(
                "history.series_note",
                index=record.series_game_index,
                total=3,
                series=(record.series_id or "")[:6],
            )
        return f"{record.white_name} vs {record.black_name} — {outcome} — {termination}{suffix}"

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
        canvas.fill(self.app.theme.roles["bg"])
        canvas.blit(
            get_font(28, bold=True).render(
                self.app.translator.t("history.title"), True, self.app.theme.roles["text"]
            ),
            (80, 82),
        )
        if not self.records:
            canvas.blit(
                get_font(18).render(
                    self.app.translator.t("history.empty"), True, self.app.theme.roles["text_muted"]
                ),
                (80, 160),
            )
        for button in self.rows:
            if button.enabled:
                button.draw(canvas, get_font(12))
        self._draw_scroll_button(canvas, self.scroll_up, up=True)
        self._draw_scroll_button(canvas, self.scroll_down, up=False)
        self.export_button.draw(canvas, get_font(13))
        self.back.draw(canvas, get_font(13))
        if self.notice:
            canvas.blit(
                render_fit(get_font(12), self.notice, self.app.theme.roles["accent"], 900),
                (80, 620),
            )

    def _draw_scroll_button(self, canvas: Render, rect: pygame.Rect, *, up: bool) -> None:
        enabled = (
            self.scroll_offset > 0
            if up
            else (self.scroll_offset + self.VISIBLE_ROWS < len(self.records))
        )
        color = self.app.theme.roles["accent"] if enabled else self.app.theme.roles["border"]
        canvas.draw_rect(self.app.theme.roles["surface"], rect, radius=4)
        center_x = rect.centerx
        if up:
            points = [
                (center_x, rect.top + 5),
                (rect.left + 6, rect.bottom - 5),
                (rect.right - 6, rect.bottom - 5),
            ]
        else:
            points = [
                (center_x, rect.bottom - 5),
                (rect.left + 6, rect.top + 5),
                (rect.right - 6, rect.top + 5),
            ]
        canvas.draw_polygon(color, points)
