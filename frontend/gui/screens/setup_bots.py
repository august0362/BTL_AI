"""Choose both bots and the series length."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from ai import registry
from ai.base_bot import BotUnavailableError
from gui.render import Render
from gui.screens.base import Screen
from gui.theme import side_colors
from gui.widgets.button import Button
from gui.widgets.card import draw_option, draw_section_title

if TYPE_CHECKING:
    from gui.app import App


class SetupBotsScreen(Screen):
    """Configure a bot versus bot game."""

    def __init__(self, app: App) -> None:
        super().__init__(app)
        self.bot_ids = registry.list_bots(
            include_debug=app.config.get("ui", {}).get("show_debug_bots", False),
            include_benchmarks=True,
            max_benchmark_level=registry.benchmark_level(app.config),
            config=app.config,
        )
        self.available: dict[str, tuple[bool, str]] = {}
        for bot_id in self.bot_ids:
            try:
                bot = registry.create_bot(bot_id, app._bot_config(bot_id))
                if bot.is_baseline:
                    app._baseline_bot_ids.add(bot_id)
                else:
                    app._baseline_bot_ids.discard(bot_id)
                self.available[bot_id] = (True, "")
            except BotUnavailableError as exc:
                self.available[bot_id] = (False, str(exc))
        usable = [bot for bot in self.bot_ids if self.available[bot][0]]
        white = (
            app.white_bot_id if app.white_bot_id in self.bot_ids else (usable[0] if usable else "")
        )
        black = (
            app.black_bot_id
            if app.black_bot_id in self.bot_ids
            else (usable[1] if len(usable) > 1 else white)
        )
        self.white_index = self.bot_ids.index(white) if white else 0
        self.black_index = self.bot_ids.index(black) if black else 0
        self.series_index = 0 if app.n_games == 1 else 1
        has_unavailable = any(not available for available, _ in self.available.values())
        # Shift the bot columns up when more bots would overlap the Swap button; 14-15 bots
        # use compact 30 px rows and move Swap next to the series buttons.
        self._compact = len(self.bot_ids) > 9
        # 19-20 bots: each side shows two sub-columns of ten rows (filled top to bottom).
        self._split = len(self.bot_ids) > 15
        self._per_column = (len(self.bot_ids) + 1) // 2 if self._split else len(self.bot_ids)
        if self._split:
            row_step = 30
            self._top = 96
            button_height = 17 if has_unavailable else 24
        elif self._compact:
            row_step = 30
            self._top = 96
            button_height = 17 if has_unavailable else 24
        else:
            row_step = 36
            self._top = 196 if len(self.bot_ids) <= 8 else 160
            button_height = 23 if has_unavailable else 30
        self._column_x = ((30, 245), (500, 715)) if self._split else ((220,), (505,))
        self._column_width = 205 if self._split else 235
        self.buttons = [
            Button(
                self._bot_rect(0, i, row_step, button_height),
                self._button_label(bot),
                enabled=self.available[bot][0],
            )
            for i, bot in enumerate(self.bot_ids)
        ]
        self.black_buttons = [
            Button(
                self._bot_rect(1, i, row_step, button_height),
                self._button_label(bot),
                enabled=self.available[bot][0],
            )
            for i, bot in enumerate(self.bot_ids)
        ]
        self.format_buttons = [
            Button(
                pygame.Rect(156 + i * 128, 584, 120, 40),
                app.translator.t(key),
                selected=i == self.series_index,
            )
            for i, key in enumerate(("setup.single_game", "setup.best_of_three"))
        ]
        # One action row under both lists: series format, swap, start and back.
        swap_rect = pygame.Rect(412, 584, 110, 40)
        self.swap = Button(swap_rect, app.translator.t("setup.swap"))
        self.start = Button(pygame.Rect(546, 584, 140, 40), app.translator.t("setup.start"))
        self.start.style = "primary"
        self.back = Button(pygame.Rect(694, 584, 110, 40), app.translator.t("setup.back"))
        self.error = ""

    def _bot_rect(self, side: int, index: int, row_step: int, height: int) -> pygame.Rect:
        """Rectangle of bot ``index`` in the White (0) or Black (1) list."""
        column, row = divmod(index, self._per_column)
        x = self._column_x[side][column]
        return pygame.Rect(x, self._top + row * row_step, self._column_width, height)

    def handle_click(self, x: float, y: float) -> None:
        point = (x, y)
        for i, button in enumerate(self.buttons):
            if button.contains(point):
                self.white_index = i
                for j, item in enumerate(self.buttons):
                    item.selected = j == i
                return
        for i, button in enumerate(self.black_buttons):
            if button.contains(point):
                self.black_index = i
                for j, item in enumerate(self.black_buttons):
                    item.selected = j == i
                return
        for i, button in enumerate(self.format_buttons):
            if button.contains(point):
                self.series_index = i
                for j, item in enumerate(self.format_buttons):
                    item.selected = i == j
                return
        if self.swap.contains(point):
            self.white_index, self.black_index = self.black_index, self.white_index
        elif self.start.contains(point) and self.bot_ids:
            try:
                self.app.start_bot_game(
                    self.bot_ids[self.white_index],
                    self.bot_ids[self.black_index],
                    (1, 3)[self.series_index],
                )
            except BotUnavailableError as exc:
                self.error = str(exc)
        elif self.back.contains(point):
            self.app.goto("menu")

    def draw(self, canvas: Render) -> None:
        roles = self.app.theme.roles
        t = self.app.translator.t
        canvas.draw_backdrop(roles)
        size = 11 if self._split else 12 if self._compact else 13
        draw_section_title(
            canvas, roles, t("menu.bot_vs_bot"), t("setup.title_bots"), (24, self._top - 92)
        )
        for side, (columns, key) in enumerate(
            zip(self._column_x, ("setup.white_bot", "setup.black_bot"), strict=True)
        ):
            buttons = self.black_buttons if side else self.buttons
            area = buttons[0].rect.unionall([button.rect for button in buttons]).inflate(16, 16)
            area = pygame.Rect(area.left, area.top - 22, area.width, area.height + 22)
            canvas.draw_glass(area, roles["surface"], alpha=150, radius=14, border=roles["border"])
            chip = side_colors(self.app.theme)[side]
            canvas.draw_circle(chip, (columns[0] + 5, self._top - 18), 5)
            canvas.draw_circle(roles["glow"], (columns[0] + 5, self._top - 18), 5, 1)
            canvas.text(
                11,
                t(key).upper(),
                roles["text_muted"],
                (columns[0] + 16, self._top - 25),
                bold=True,
            )
        for selected, buttons in (
            (self.white_index, self.buttons),
            (self.black_index, self.black_buttons),
        ):
            for i, button in enumerate(buttons):
                button.selected = i == selected
                draw_option(canvas, roles, button, "", size)
                bot_id = self.bot_ids[i]
                if not self.available[bot_id][0]:
                    reason = t("setup.bot_unavailable", reason=self.available[bot_id][1])
                    canvas.text(
                        9,
                        reason,
                        roles["danger"],
                        (button.rect.left, button.rect.bottom + 1),
                        max_width=button.rect.width,
                    )
        self.swap.draw(canvas, size)
        for button in self.format_buttons:
            button.draw(canvas, size)
        self.start.draw(canvas, size + 1)
        self.back.draw(canvas, size)
        if self.error:
            canvas.text(10, self.error, roles["danger"], (156, 628), max_width=648)

    def _button_label(self, bot_id: str) -> str:
        """Return the translated bot label."""
        return self.app._localized_bot_name(bot_id)
