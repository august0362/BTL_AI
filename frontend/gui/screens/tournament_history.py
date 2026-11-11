"""Tournament history screen: past battles, standings and head-to-head scores."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from gui.render import Render
from gui.screens.base import Screen
from gui.tournament_view import format_matchup, format_points, format_total, tournament_rows
from gui.widgets.button import Button
from gui.widgets.card import (
    draw_option,
    draw_scroll_arrow,
    draw_section_title,
    draw_stat,
    draw_table,
    rank_color,
)

if TYPE_CHECKING:
    from gui.app import App


class TournamentHistoryScreen(Screen):
    """Browse the retained battles of the AI ranking."""

    VISIBLE_BATTLES = 10
    BATTLES = pygame.Rect(24, 96, 252, 470)
    COLUMNS = (
        ("tournament.rank", 312),
        ("tournament.bot", 360),
        ("tournament.points", 660),
        ("tournament.time", 750),
        ("tournament.total", 850),
    )
    TABLE_TOP = 96
    ROW_TOP = 140
    BOTTOM = 566
    MATCHUP_STEP = 24

    def __init__(self, app: App) -> None:
        super().__init__(app)
        self.battles = app.tournament_history.list()
        self.selected = 0
        self.matchup_offset = 0
        self.battle_offset = 0
        self.visible_matchups = 4
        self._pointer = (0.0, 0.0)
        self.battle_buttons = [
            Button(pygame.Rect(36, 136 + index * 42, 228, 36), "")
            for index in range(self.VISIBLE_BATTLES)
        ]
        self.battle_up = pygame.Rect(196, 106, 34, 24)
        self.battle_down = pygame.Rect(234, 106, 34, 24)
        self.scroll_up = pygame.Rect(852, 0, 34, 24)
        self.scroll_down = pygame.Rect(890, 0, 34, 24)
        self.back = Button(pygame.Rect(792, 576, 144, 40), app.translator.t("setup.back"))
        self._update_buttons()

    def _update_buttons(self) -> None:
        for row, button in enumerate(self.battle_buttons):
            index = self.battle_offset + row
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
        max_offset = max(0, len(result.matchups) - self.visible_matchups)
        self.matchup_offset = max(0, min(max_offset, self.matchup_offset + amount))

    def _scroll_battles(self, amount: int) -> None:
        max_offset = max(0, len(self.battles) - self.VISIBLE_BATTLES)
        self.battle_offset = max(0, min(max_offset, self.battle_offset + amount))
        self._update_buttons()

    def handle_hover(self, x: float, y: float) -> None:
        self._pointer = (x, y)
        super().handle_hover(x, y)

    def handle_scroll(self, dy: int) -> None:
        if not dy:
            return
        if self.BATTLES.collidepoint(self._pointer):
            self._scroll_battles(-dy)
        else:
            self._scroll(-dy)

    def handle_click(self, x: float, y: float) -> None:
        point = (x, y)
        if len(self.battles) > self.VISIBLE_BATTLES:
            if self.battle_up.collidepoint(point):
                self._scroll_battles(-1)
                return
            if self.battle_down.collidepoint(point):
                self._scroll_battles(1)
                return
        if self.scroll_up.collidepoint(point):
            self._scroll(-1)
            return
        if self.scroll_down.collidepoint(point):
            self._scroll(1)
            return
        for row, button in enumerate(self.battle_buttons):
            if button.contains(point) and button.enabled:
                self.selected = self.battle_offset + row
                self.matchup_offset = 0
                self._update_buttons()
                return
        if self.back.contains(point):
            self.app.goto("menu")

    def draw(self, canvas: Render) -> None:
        roles = self.app.theme.roles
        t = self.app.translator.t
        canvas.draw_backdrop(roles)
        draw_section_title(
            canvas, roles, t("tournament_history.eyebrow"), t("tournament_history.title"), (24, 26)
        )
        result = self._current()
        games = "0" if result is None else f"{result.games_played}/{result.games_total}"
        draw_stat(
            canvas,
            roles,
            pygame.Rect(632, 24, 140, 60),
            t("tournament_history.stat_battles"),
            str(len(self.battles)),
        )
        draw_stat(canvas, roles, pygame.Rect(784, 24, 152, 60), t("tournament.stat_games"), games)
        self.back.draw(canvas, 14)
        if result is None:
            canvas.draw_glass(
                (24, 96, 912, 120), roles["surface"], alpha=205, radius=14, border=roles["border"]
            )
            canvas.text(
                16,
                t("tournament_history.empty"),
                roles["text_muted"],
                (0, 0),
                bold=True,
                center=(480, 156),
            )
            return
        canvas.draw_glass(
            self.BATTLES, roles["surface"], alpha=205, radius=14, border=roles["border"]
        )
        canvas.text(
            11,
            t("tournament_history.battles").upper(),
            roles["text_muted"],
            (self.BATTLES.left + 14, self.BATTLES.top + 14),
            bold=True,
        )
        for button in self.battle_buttons:
            if button.enabled:
                draw_option(canvas, roles, button, "", 13)
        if len(self.battles) > self.VISIBLE_BATTLES:
            max_offset = len(self.battles) - self.VISIBLE_BATTLES
            draw_scroll_arrow(
                canvas, roles, self.battle_up, up=True, enabled=self.battle_offset > 0
            )
            draw_scroll_arrow(
                canvas,
                roles,
                self.battle_down,
                up=False,
                enabled=self.battle_offset < max_offset,
            )
        table = self._draw_standings(canvas, result)
        self._draw_matchups(canvas, result, table.bottom + 10)

    def _draw_standings(self, canvas: Render, result) -> pygame.Rect:
        roles = self.app.theme.roles
        translator = self.app.translator
        rows = tournament_rows(result.standings, translator)[:25]
        # Up to 25 bots: rows shrink so at least four head-to-head lines stay visible.
        available = self.BOTTOM - 150 - self.ROW_TOP - 8
        step = max(11, min(28, available // max(1, len(rows))))
        table = pygame.Rect(292, self.TABLE_TOP, 644, self.ROW_TOP - self.TABLE_TOP + 8)
        table.height += step * len(rows)
        headers = [(translator.t(key), x, key == "tournament.total") for key, x in self.COLUMNS]
        draw_table(canvas, roles, table, headers, len(rows), step, self.ROW_TOP)
        size = 13 if step >= 22 else 11 if step >= 14 else 10
        for index, row in enumerate(rows):
            y = self.ROW_TOP + index * step + (step - round(size * 1.3)) // 2
            canvas.text(size, f"{row.rank:02d}", rank_color(roles, row.rank), (312, y), bold=True)
            canvas.text(size, row.name, roles["text"], (360, y), bold=row.rank <= 3, max_width=290)
            canvas.text(size, format_points(row.points), roles["text_muted"], (660, y))
            canvas.text(size, f"{row.think_time_s:.1f}s", roles["text_muted"], (750, y))
            canvas.text(size, format_total(row.total), roles["primary"], (850, y), bold=True)
        return table

    def _draw_matchups(self, canvas: Render, result, top: int) -> None:
        roles = self.app.theme.roles
        translator = self.app.translator
        card = pygame.Rect(292, top, 644, self.BOTTOM - top)
        canvas.draw_glass(card, roles["surface"], alpha=205, radius=14, border=roles["border"])
        canvas.text(
            11,
            translator.t("tournament_history.matchups").upper(),
            roles["text_muted"],
            (card.left + 16, card.top + 13),
            bold=True,
        )
        self.visible_matchups = max(1, (card.height - 46) // self.MATCHUP_STEP)
        self._scroll(0)
        visible = result.matchups[self.matchup_offset : self.matchup_offset + self.visible_matchups]
        for index, matchup in enumerate(visible):
            y = card.top + 38 + index * self.MATCHUP_STEP
            if index % 2:
                canvas.draw_glass(
                    (card.left + 8, y, card.width - 16, self.MATCHUP_STEP),
                    roles["surface_alt"],
                    alpha=110,
                    radius=6,
                )
            canvas.text(
                12,
                format_matchup(matchup, translator),
                roles["text"],
                (card.left + 18, y + 5),
                max_width=card.width - 36,
            )
        self.scroll_up.y = self.scroll_down.y = card.top + 8
        if len(result.matchups) > self.visible_matchups:
            max_offset = len(result.matchups) - self.visible_matchups
            draw_scroll_arrow(
                canvas, roles, self.scroll_up, up=True, enabled=self.matchup_offset > 0
            )
            draw_scroll_arrow(
                canvas,
                roles,
                self.scroll_down,
                up=False,
                enabled=self.matchup_offset < max_offset,
            )
