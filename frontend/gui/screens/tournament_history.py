"""Tournament history screen: past battles, standings and head-to-head scores."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from gui.assets_loader import get_font
from gui.render import Render
from gui.screens.base import Screen
from gui.tournament_view import format_matchup, format_points, format_total, tournament_rows
from gui.widgets.button import Button

if TYPE_CHECKING:
    from gui.app import App


class TournamentHistoryScreen(Screen):
    """Browse the retained battles of the AI ranking."""

    VISIBLE_BATTLES = 10
    VISIBLE_MATCHUPS = 9

    def __init__(self, app: App) -> None:
        super().__init__(app)
        self.battles = app.tournament_history.list()
        self.selected = 0
        self.matchup_offset = 0
        self.battle_buttons = [
            Button(pygame.Rect(60, 120 + index * 36, 250, 32), "")
            for index in range(self.VISIBLE_BATTLES)
        ]
        self.scroll_up = pygame.Rect(880, 378, 26, 20)
        self.scroll_down = pygame.Rect(908, 378, 26, 20)
        self.back = Button(pygame.Rect(60, 560, 120, 40), app.translator.t("setup.back"))
        self._update_buttons()

    def _update_buttons(self) -> None:
        for index, button in enumerate(self.battle_buttons):
            battle = self.battles[index] if index < len(self.battles) else None
            button.enabled = battle is not None
            button.selected = index == self.selected
            button.label = (
                ""
                if battle is None or battle.battle is None
                else self.app.translator.t("tournament.battle", index=battle.battle)
            )

    def _current(self):
        if not self.battles:
            return None
        return self.battles[min(self.selected, len(self.battles) - 1)]

    def _scroll(self, amount: int) -> None:
        result = self._current()
        if result is None:
            return
        max_offset = max(0, len(result.matchups) - self.VISIBLE_MATCHUPS)
        self.matchup_offset = max(0, min(max_offset, self.matchup_offset + amount))

    def handle_scroll(self, dy: int) -> None:
        if dy:
            self._scroll(-dy)

    def handle_click(self, x: float, y: float) -> None:
        point = (x, y)
        if self.scroll_up.collidepoint(point):
            self._scroll(-1)
            return
        if self.scroll_down.collidepoint(point):
            self._scroll(1)
            return
        for index, button in enumerate(self.battle_buttons):
            if button.contains(point):
                self.selected = index
                self.matchup_offset = 0
                self._update_buttons()
                return
        if self.back.contains(point):
            self.app.goto("menu")

    def draw(self, canvas: Render) -> None:
        roles = self.app.theme.roles
        translator = self.app.translator
        canvas.fill(roles["bg"])
        canvas.blit(
            get_font(28, bold=True).render(
                translator.t("tournament_history.title"), True, roles["text"]
            ),
            (60, 46),
        )
        if not self.battles:
            empty = get_font(16).render(
                translator.t("tournament_history.empty"), True, roles["text_muted"]
            )
            canvas.blit(
                empty,
                (60, 140),
            )
            self.back.draw(canvas, get_font(14))
            return
        for button in self.battle_buttons:
            if button.enabled:
                button.draw(canvas, get_font(13))
        result = self._current()
        if result is None:
            return
        self._draw_standings(canvas, result)
        self._draw_matchups(canvas, result)
        self.back.draw(canvas, get_font(14))

    def _draw_standings(self, canvas: Render, result) -> None:
        roles = self.app.theme.roles
        translator = self.app.translator
        for key, x in (
            ("tournament.rank", 340),
            ("tournament.bot", 390),
            ("tournament.points", 680),
            ("tournament.time", 750),
            ("tournament.total", 830),
        ):
            canvas.blit(
                get_font(12, bold=True).render(translator.t(key), True, roles["accent"]), (x, 120)
            )
        font = get_font(12)
        for index, row in enumerate(tournament_rows(result.standings, translator)[:9]):
            y = 150 + index * 22
            values = (
                str(row.rank),
                row.name,
                format_points(row.points),
                f"{row.think_time_s:.1f}s",
                format_total(row.total),
            )
            for value, x in zip(values, (340, 390, 680, 750, 830), strict=True):
                canvas.blit(font.render(value, True, roles["text"]), (x, y))
        canvas.blit(
            get_font(14, bold=True).render(
                translator.t("tournament_history.matchups"), True, roles["text"]
            ),
            (340, 350),
        )

    def _draw_matchups(self, canvas: Render, result) -> None:
        roles = self.app.theme.roles
        translator = self.app.translator
        font = get_font(12)
        visible = result.matchups[self.matchup_offset : self.matchup_offset + self.VISIBLE_MATCHUPS]
        for index, matchup in enumerate(visible):
            canvas.blit(
                font.render(format_matchup(matchup, translator), True, roles["text"]),
                (340, 400 + index * 24),
            )
        self._draw_scroll_button(canvas, self.scroll_up, up=True)
        self._draw_scroll_button(canvas, self.scroll_down, up=False)

    def _draw_scroll_button(self, canvas: Render, rect: pygame.Rect, *, up: bool) -> None:
        result = self._current()
        matchups = 0 if result is None else len(result.matchups)
        enabled = (
            self.matchup_offset > 0
            if up
            else (self.matchup_offset + self.VISIBLE_MATCHUPS < matchups)
        )
        color = self.app.theme.roles["accent"] if enabled else self.app.theme.roles["border"]
        canvas.draw_rect(self.app.theme.roles["surface"], rect, radius=4)
        center_x = rect.centerx
        if up:
            points = [
                (center_x, rect.top + 4),
                (rect.left + 5, rect.bottom - 4),
                (rect.right - 5, rect.bottom - 4),
            ]
        else:
            points = [
                (center_x, rect.bottom - 4),
                (rect.left + 5, rect.top + 4),
                (rect.right - 5, rect.top + 4),
            ]
        canvas.draw_polygon(color, points)
