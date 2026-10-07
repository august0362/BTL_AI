"""Choose both bots and the series length."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from ai import registry
from ai.base_bot import BotUnavailableError
from gui.assets_loader import get_font, render_fit
from gui.render import Render
from gui.screens.base import Screen
from gui.widgets.button import Button

if TYPE_CHECKING:
    from gui.app import App


class SetupBotsScreen(Screen):
    """Configure a bot versus bot game."""

    def __init__(self, app: App) -> None:
        super().__init__(app)
        self.bot_ids = registry.list_bots(
            include_debug=app.config.get("ui", {}).get("show_debug_bots", False),
            include_benchmarks=True,
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
        row_step = 36
        # Shift the bot columns up when more than eight bots would overlap the Swap button.
        self._top = 196 if len(self.bot_ids) <= 8 else 160
        has_unavailable = any(not available for available, _ in self.available.values())
        button_height = 23 if has_unavailable else 30
        self.buttons = [
            Button(
                pygame.Rect(220, self._top + i * row_step, 235, button_height),
                self._button_label(bot),
                enabled=self.available[bot][0],
            )
            for i, bot in enumerate(self.bot_ids)
        ]
        self.black_buttons = [
            Button(
                pygame.Rect(505, self._top + i * row_step, 235, button_height),
                self._button_label(bot),
                enabled=self.available[bot][0],
            )
            for i, bot in enumerate(self.bot_ids)
        ]
        self.format_buttons = [
            Button(
                pygame.Rect(350 + i * 135, 562 if has_unavailable else 564, 125, 32),
                app.translator.t(key),
                selected=i == self.series_index,
            )
            for i, key in enumerate(("setup.single_game", "setup.best_of_three"))
        ]
        self.swap = Button(
            pygame.Rect(424, 524 if has_unavailable else 530, 112, 30),
            app.translator.t("setup.swap"),
        )
        action_y = 602 if has_unavailable else 604
        self.start = Button(pygame.Rect(360, action_y, 110, 28), app.translator.t("setup.start"))
        self.start.style = "primary"
        self.back = Button(pygame.Rect(490, action_y, 110, 28), app.translator.t("setup.back"))
        self.error = ""

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
        canvas.fill(self.app.theme.roles["bg"])
        font = get_font(13)
        canvas.blit(
            get_font(27, bold=True).render(
                self.app.translator.t("setup.title_bots"), True, self.app.theme.roles["text"]
            ),
            (295, self._top - 84),
        )
        for x, key in ((220, "setup.white_bot"), (505, "setup.black_bot")):
            canvas.blit(
                font.render(self.app.translator.t(key), True, self.app.theme.roles["text_muted"]),
                (x, self._top - 26),
            )
        for i, button in enumerate(self.buttons):
            button.selected = i == self.white_index
            button.draw(canvas, font)
            bot_id = self.bot_ids[i]
            if not self.available[bot_id][0]:
                reason = self.app.translator.t(
                    "setup.bot_unavailable", reason=self.available[bot_id][1]
                )
                canvas.blit(
                    render_fit(get_font(9), reason, self.app.theme.roles["text_muted"], 235),
                    (220, button.rect.bottom + 1),
                )
        for i, button in enumerate(self.black_buttons):
            button.selected = i == self.black_index
            button.draw(canvas, font)
            bot_id = self.bot_ids[i]
            if not self.available[bot_id][0]:
                reason = self.app.translator.t(
                    "setup.bot_unavailable", reason=self.available[bot_id][1]
                )
                canvas.blit(
                    render_fit(get_font(9), reason, self.app.theme.roles["text_muted"], 235),
                    (505, button.rect.bottom + 1),
                )
        self.swap.draw(canvas, font)
        for button in self.format_buttons:
            button.draw(canvas, font)
        self.start.draw(canvas, font)
        self.back.draw(canvas, font)
        if self.error:
            canvas.blit(
                render_fit(get_font(10), self.error, self.app.theme.roles["text_muted"], 250),
                (620, 610),
            )

    def _button_label(self, bot_id: str) -> str:
        """Return the translated bot label."""
        return self.app._localized_bot_name(bot_id)
