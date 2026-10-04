"""Human versus bot setup screen."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

import chess
import pygame

from ai import registry
from ai.base_bot import BotUnavailableError
from gui.assets_loader import get_font, render_fit
from gui.render import Render
from gui.screens.base import Screen
from gui.widgets.button import Button

if TYPE_CHECKING:
    from gui.app import App


class SetupHumanScreen(Screen):
    """Choose an available bot and the human's side."""

    def __init__(self, app: App) -> None:
        super().__init__(app)
        self.bot_ids = registry.list_bots(
            include_debug=app.config.get("ui", {}).get("show_debug_bots", False)
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
        self.selected_bot = next(
            (bot for bot in self.bot_ids if self.available[bot][0]),
            self.bot_ids[0] if self.bot_ids else "",
        )
        self.color_index = 0
        self.bot_buttons: list[Button] = []
        self.reason_positions: list[tuple[int, str]] = []
        row_y = 205
        for bot_id in self.bot_ids:
            enabled, reason = self.available[bot_id]
            self.bot_buttons.append(
                Button(
                    pygame.Rect(330, row_y, 300, 34),
                    app._localized_bot_name(bot_id),
                    enabled=enabled,
                    selected=bot_id == self.selected_bot,
                )
            )
            if not enabled:
                self.reason_positions.append((row_y + 35, reason))
                row_y += 54
            else:
                row_y += 42
        color_y = max(410, row_y + 28)
        action_y = color_y + 50
        self.color_buttons = [
            Button(
                pygame.Rect(330 + index * 102, color_y, 96, 40),
                app.translator.t(key),
                selected=index == 0,
            )
            for index, key in enumerate(
                ("setup.color_white", "setup.color_black", "setup.color_random")
            )
        ]
        self.start_button = Button(
            pygame.Rect(410, action_y, 140, 42), app.translator.t("setup.start")
        )
        self.start_button.style = "primary"
        self.back_button = Button(
            pygame.Rect(410, action_y + 50, 140, 38), app.translator.t("setup.back")
        )
        self.error = ""

    def handle_click(self, x: float, y: float) -> None:
        point = (x, y)
        for index, button in enumerate(self.bot_buttons):
            if button.contains(point):
                self.selected_bot = self.bot_ids[index]
                for item, bot_id in zip(self.bot_buttons, self.bot_ids, strict=True):
                    item.selected = bot_id == self.selected_bot
                return
        for index, button in enumerate(self.color_buttons):
            if button.contains(point):
                self.color_index = index
                for item, color_index in zip(self.color_buttons, range(3), strict=True):
                    item.selected = color_index == index
                return
        if self.start_button.contains(point) and self.selected_bot:
            color = (chess.WHITE, chess.BLACK, None)[self.color_index]
            if color is None:
                color = chess.WHITE if random.choice((True, False)) else chess.BLACK
            try:
                self.app.start_human_game(self.selected_bot, color)
            except BotUnavailableError as exc:
                self.error = str(exc)
        elif self.back_button.contains(point):
            self.app.goto("menu")

    def draw(self, canvas: Render) -> None:
        canvas.fill(self.app.theme.roles["bg"])
        title = get_font(28, bold=True).render(
            self.app.translator.t("setup.title_human"), True, self.app.theme.roles["text"]
        )
        canvas.blit(title, title.get_rect(center=(480, 126)))
        canvas.blit(
            render_fit(
                get_font(16),
                self.app.translator.t("setup.choose_bot"),
                self.app.theme.roles["text_muted"],
                300,
            ),
            (330, 175),
        )
        for button in self.bot_buttons:
            button.draw(canvas, get_font(15, bold=True))
        for y, reason in self.reason_positions:
            label = self.app.translator.t("setup.bot_unavailable", reason=reason)
            text = render_fit(get_font(11), label, self.app.theme.roles["text_muted"], 300)
            canvas.blit(text, (330, y))
        canvas.blit(
            render_fit(
                get_font(16),
                self.app.translator.t("setup.your_color"),
                self.app.theme.roles["text_muted"],
                300,
            ),
            (330, self.color_buttons[0].rect.top - 28),
        )
        for button in self.color_buttons:
            button.draw(canvas, get_font(15))
        self.start_button.draw(canvas, get_font(17, bold=True))
        self.back_button.draw(canvas, get_font(16))
        if self.error:
            canvas.blit(
                render_fit(get_font(13), self.error, self.app.theme.roles["text_muted"], 394),
                (558, self.back_button.rect.top + 10),
            )
