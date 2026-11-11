"""Human versus bot setup screen."""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

import chess
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


class SetupHumanScreen(Screen):
    """Choose an available bot and the human's side."""

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
        self.selected_bot = next(
            (bot for bot in self.bot_ids if self.available[bot][0]),
            self.bot_ids[0] if self.bot_ids else "",
        )
        self.color_index = 0
        self.bot_buttons: list[Button] = []
        self.reason_positions: list[tuple[int, int, str]] = []
        # Bot tiles fill the left area (x 24..600, y 100..620): two columns, three when
        # more than 20 bots are listed. The match card sits on the right.
        columns = 3 if len(self.bot_ids) > 20 else 2
        rows = max(1, (len(self.bot_ids) + columns - 1) // columns)
        row_step = min(56, 520 // rows)
        button_height = row_step - 14
        width = (576 - (columns - 1) * 10) // columns
        self._bot_font = 14 if row_step >= 50 else 12
        for index, bot_id in enumerate(self.bot_ids):
            enabled, reason = self.available[bot_id]
            column = index % columns
            row_y = 100 + (index // columns) * row_step
            x = 24 + column * (width + 10)
            self.bot_buttons.append(
                Button(
                    pygame.Rect(x, row_y, width, button_height),
                    app._localized_bot_name(bot_id),
                    enabled=enabled,
                    selected=bot_id == self.selected_bot,
                )
            )
            if not enabled:
                self.reason_positions.append((x, row_y + button_height + 1, reason))
        self.color_buttons = [
            Button(
                pygame.Rect(636 + index * 98, 300, 90, 64),
                app.translator.t(key),
                selected=index == 0,
            )
            for index, key in enumerate(
                ("setup.color_white", "setup.color_black", "setup.color_random")
            )
        ]
        self.start_button = Button(pygame.Rect(624, 470, 312, 60), app.translator.t("setup.start"))
        self.start_button.style = "primary"
        self.back_button = Button(pygame.Rect(624, 544, 312, 40), app.translator.t("setup.back"))
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
        roles = self.app.theme.roles
        t = self.app.translator.t
        canvas.draw_backdrop(roles)
        draw_section_title(canvas, roles, t("menu.human_vs_bot"), t("setup.choose_bot"), (24, 26))
        for button, bot_id in zip(self.bot_buttons, self.bot_ids, strict=True):
            elo = round(self.app.ranking.stats(bot_id).elo)
            draw_option(canvas, roles, button, f"Elo {elo}", self._bot_font)
        for x, y, reason in self.reason_positions:
            label = t("setup.bot_unavailable", reason=reason)
            canvas.text(10, label, roles["danger"], (x + 4, y), max_width=280)

        card = pygame.Rect(616, 100, 328, 500)
        canvas.draw_glass(
            card, roles["surface"], alpha=225, border=roles["border"], rim=roles["rim"]
        )
        canvas.text(11, t("setup.match").upper(), roles["glow"], (636, 118), bold=True)
        name = self.app._localized_bot_name(self.selected_bot) if self.selected_bot else ""
        canvas.text(22, name, roles["text"], (636, 140), bold=True, max_width=288)
        if self.selected_bot:
            stats = self.app.ranking.stats(self.selected_bot)
            canvas.text(28, f"{round(stats.elo)}", roles["primary"], (636, 180), display=True)
            canvas.text(11, "ELO", roles["text_muted"], (636, 220), bold=True)
        canvas.draw_line(roles["border"], (636, 252), (924, 252), 1)
        canvas.text(11, t("setup.your_color").upper(), roles["text_muted"], (636, 274), bold=True)
        for index, button in enumerate(self.color_buttons):
            draw_option(canvas, roles, button, "", 14, center=True)
            chip = (button.rect.centerx, button.rect.top + 20)
            white, black = side_colors(self.app.theme)
            canvas.draw_circle(black if index == 1 else white, chip, 8)
            if index == 2:
                # Right half-disk, so the split chip stays round.
                half = [
                    (
                        chip[0] + 8 * math.cos(math.pi * (step / 16 - 0.5)),
                        chip[1] + 8 * math.sin(math.pi * (step / 16 - 0.5)),
                    )
                    for step in range(17)
                ]
                canvas.draw_polygon(black, half)
            canvas.draw_circle(roles["glow"], chip, 8, 1)
        self.start_button.draw(canvas, 20)
        self.back_button.draw(canvas, 15)
        if self.error:
            canvas.text(12, self.error, roles["danger"], (624, 596), max_width=312)
