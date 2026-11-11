"""Change language, sound, replay speed, and the active color theme."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from gui.render import Render
from gui.screens.base import Screen
from gui.theme import THEMES, Theme
from gui.weights_info import WeightsRow, weights_rows
from gui.widgets.button import Button
from gui.widgets.card import draw_scroll_arrow, draw_section_title

if TYPE_CHECKING:
    from gui.app import App


class SettingsScreen(Screen):
    """Edit interface preferences and preview the available themes."""

    THEME_AREA = pygame.Rect(24, 196, 912, 344)
    CARD_WIDTH = 206
    CARD_HEIGHT = 74
    COLUMN_STEP = 216
    ROW_STEP = 84

    def __init__(self, app: App) -> None:
        super().__init__(app)
        self.theme_area = pygame.Rect(self.THEME_AREA)
        self.vi = Button(
            pygame.Rect(168, 104, 128, 38),
            app.translator.t("settings.language_vi"),
            selected=app.translator.language == "vi",
        )
        self.en = Button(
            pygame.Rect(306, 104, 128, 38),
            app.translator.t("settings.language_en"),
            selected=app.translator.language == "en",
        )
        self.weights = Button(pygame.Rect(652, 104, 268, 38), self._weights_label())
        self.sound = Button(pygame.Rect(24, 578, 232, 40), self._sound_label())
        self.speed = Button(pygame.Rect(268, 578, 360, 40), self._speed_label())
        self.back = Button(pygame.Rect(792, 578, 144, 40), app.translator.t("setup.back"))
        self.theme_rects: dict[str, pygame.Rect] = {}
        self.group_positions: list[tuple[str, int]] = []
        self.scroll_up = pygame.Rect(900, 0, 28, 24)
        self.scroll_down = pygame.Rect(900, 0, 28, 24)
        self.scroll_offset = 0
        self.preview_theme_id: str | None = None
        self.content_height = 0
        self._update_layout()

    @property
    def preview_theme(self) -> Theme:
        """Return the hovered theme, or the app's selected theme."""
        return THEMES.get(self.preview_theme_id, self.app.theme)

    def _sound_label(self) -> str:
        sound_key = "settings.sound_on" if self.app.sound_enabled else "settings.sound_off"
        return f"{self.app.translator.t('settings.sound')}: {self.app.translator.t(sound_key)}"

    def _speed_label(self) -> str:
        delay = self.app.config.get("ui", {}).get("replay_delay_ms", 800)
        return f"{self.app.translator.t('settings.replay_speed')}: {delay} ms"

    def _weights_label(self) -> str:
        key = (
            "settings.sound_on"
            if self.app.config.get("ui", {}).get("show_weights_info", False)
            else "settings.sound_off"
        )
        return f"{self.app.translator.t('settings.weights')}: {self.app.translator.t(key)}"

    def _update_layout(self) -> None:
        shown = self.app.config.get("ui", {}).get("show_weights_info", False)
        # The weights panel takes the space under the language row; the themes card shrinks.
        self.theme_area = pygame.Rect(24, 304, 912, 236) if shown else pygame.Rect(self.THEME_AREA)
        self.scroll_up.y = self.theme_area.top - 32
        self.scroll_down.y = self.theme_area.bottom - 24
        self._layout_theme_rects()

    @staticmethod
    def _theme_groups() -> tuple[tuple[str, list[str]], ...]:
        dark = [theme_id for theme_id, theme in THEMES.items() if theme.is_dark]
        light = [theme_id for theme_id, theme in THEMES.items() if not theme.is_dark]
        return (("settings.dark", dark), ("settings.light", light))

    def _layout_theme_rects(self) -> None:
        self.theme_rects.clear()
        self.group_positions.clear()
        y = 0
        for group_key, theme_ids in self._theme_groups():
            self.group_positions.append((group_key, y))
            y += 26
            for index, theme_id in enumerate(theme_ids):
                row, column = divmod(index, 4)
                self.theme_rects[theme_id] = pygame.Rect(
                    40 + column * self.COLUMN_STEP,
                    self.theme_area.y + y + row * self.ROW_STEP - self.scroll_offset,
                    self.CARD_WIDTH,
                    self.CARD_HEIGHT,
                )
            y += ((len(theme_ids) + 3) // 4) * self.ROW_STEP + 10
        self.content_height = max(0, y - 10)

    def _max_scroll(self) -> int:
        return max(0, self.content_height - self.theme_area.height)

    def _scroll(self, amount: int) -> None:
        self.scroll_offset = max(0, min(self._max_scroll(), self.scroll_offset + amount))
        self.preview_theme_id = None
        self._layout_theme_rects()

    def handle_scroll(self, dy: int) -> None:
        if dy:
            self._scroll(-dy * 52)

    def handle_hover(self, x: float, y: float) -> None:
        super().handle_hover(x, y)
        point = (x, y)
        self.preview_theme_id = None
        if self.theme_area.collidepoint(point):
            for theme_id, rect in self.theme_rects.items():
                if rect.collidepoint(point):
                    self.preview_theme_id = theme_id
                    break
        try:
            pygame.mouse.set_cursor(
                pygame.SYSTEM_CURSOR_HAND
                if self.preview_theme_id is not None
                or self.scroll_up.collidepoint(point)
                or self.scroll_down.collidepoint(point)
                or self.vi.contains(point)
                or self.en.contains(point)
                or self.weights.contains(point)
                or self.sound.contains(point)
                or self.speed.contains(point)
                or self.back.contains(point)
                else pygame.SYSTEM_CURSOR_ARROW
            )
        except pygame.error:
            pass

    def handle_click(self, x: float, y: float) -> None:
        point = (x, y)
        if self.scroll_up.collidepoint(point):
            self._scroll(-self.ROW_STEP)
        elif self.scroll_down.collidepoint(point):
            self._scroll(self.ROW_STEP)
        elif self.vi.contains(point):
            self.app.set_language("vi")
        elif self.en.contains(point):
            self.app.set_language("en")
        elif self.weights.contains(point):
            self.app._save_ui(
                "show_weights_info",
                not self.app.config.get("ui", {}).get("show_weights_info", False),
            )
            self.weights.label = self._weights_label()
            self._update_layout()
        elif self.sound.contains(point):
            self.app.set_sound_enabled(not self.app.sound_enabled)
            self.sound.label = self._sound_label()
        elif self.speed.contains(point):
            current = self.app.config.get("ui", {}).get("replay_delay_ms", 800)
            self.app.set_replay_delay(500 if current >= 1000 else current + 500)
            self.speed.label = self._speed_label()
        elif self.back.contains(point):
            self.app.goto("menu")
        elif self.theme_area.collidepoint(point):
            for theme_id, rect in self.theme_rects.items():
                if rect.collidepoint(point):
                    self.app.set_theme(theme_id)
                    return

    def draw(self, canvas: Render) -> None:
        theme = self.preview_theme
        roles = theme.roles
        t = self.app.translator.t
        canvas.draw_backdrop(roles)
        draw_section_title(canvas, roles, t("settings.eyebrow"), t("settings.title"), (24, 26))

        canvas.draw_glass(
            (24, 96, 912, 54), roles["surface"], alpha=210, radius=14, border=roles["border"]
        )
        canvas.text(11, t("settings.language").upper(), roles["text_muted"], (42, 116), bold=True)
        self.vi.selected = self.app.translator.language == "vi"
        self.en.selected = self.app.translator.language == "en"
        self.vi.draw(canvas, 14, theme)
        self.en.draw(canvas, 14, theme)
        self.weights.draw(canvas, 13, theme)
        if self.app.config.get("ui", {}).get("show_weights_info", False):
            self._draw_weights(canvas, roles)

        card = pygame.Rect(24, self.theme_area.top - 40, 912, self.theme_area.height + 52)
        canvas.draw_glass(card, roles["surface"], alpha=205, radius=14, border=roles["border"])
        canvas.text(11, t("settings.themes").upper(), roles["glow"], (40, card.top + 14), bold=True)
        previous_clip = canvas.surface.get_clip()
        canvas.surface.set_clip(canvas.rect(self.theme_area))
        for group_key, y in self.group_positions:
            group_y = self.theme_area.y + y - self.scroll_offset
            canvas.text(12, t(group_key), roles["text_muted"], (40, group_y + 4), bold=True)
        for theme_id, rect in self.theme_rects.items():
            if rect.colliderect(self.theme_area):
                self._draw_theme_card(canvas, roles, theme_id, rect)
        canvas.surface.set_clip(previous_clip)
        if self._max_scroll():
            draw_scroll_arrow(
                canvas, roles, self.scroll_up, up=True, enabled=self.scroll_offset > 0
            )
            draw_scroll_arrow(
                canvas,
                roles,
                self.scroll_down,
                up=False,
                enabled=self.scroll_offset < self._max_scroll(),
            )
        self.sound.draw(canvas, 13, theme)
        self.speed.draw(canvas, 13, theme)
        self.back.draw(canvas, 14, theme)

    def _draw_weights(self, canvas: Render, roles: dict[str, str]) -> None:
        """List the Deep RL weight files in use under the language row."""
        rows = weights_rows(self.app.config, self.app.translator)
        canvas.draw_glass(
            (24, 158, 912, 96), roles["surface"], alpha=210, radius=14, border=roles["border"]
        )
        canvas.text(
            11,
            self.app.translator.t("settings.weights_details").upper(),
            roles["text_muted"],
            (40, 168),
            bold=True,
        )
        font = canvas.font(12, canvas.scale)
        for index, row in enumerate(rows[:3]):
            file_name = row.file
            details = self._weights_detail(row, file_name)
            while font.size(details)[0] > round(872 * canvas.scale) and file_name:
                file_name = file_name[:-1] + "…" if len(file_name) > 1 else "…"
                details = self._weights_detail(row, file_name)
            canvas.text(12, details, roles["text"], (40, 188 + index * 20))

    def _draw_theme_card(
        self, canvas: Render, roles: dict[str, str], theme_id: str, rect: pygame.Rect
    ) -> None:
        """Draw one theme tile: its palette strip, its name and a check when selected."""
        palette_theme = THEMES[theme_id]
        selected = theme_id == self.app.theme.id
        hovered = theme_id == self.preview_theme_id
        canvas.draw_glass(
            rect,
            roles["surface_alt"] if hovered or selected else roles["surface"],
            alpha=235,
            radius=12,
            border=roles["glow"] if selected else roles["primary"] if hovered else roles["border"],
            rim=roles["rim"],
        )
        if selected:
            canvas.draw_rect(roles["glow"], rect, 2, radius=12)
        colors = palette_theme.palette
        strip = pygame.Rect(rect.x + 10, rect.y + 10, rect.width - 20, 24)
        width = strip.width / max(1, len(colors))
        for index, color in enumerate(colors):
            left = strip.left + round(index * width)
            right = strip.left + round((index + 1) * width)
            canvas.draw_rect(color, (left, strip.top, right - left, strip.height))
        canvas.draw_rect(roles["rim"], strip, 1)
        translation_key = f"themes.{theme_id}"
        name = self.app.translator.t(translation_key)
        if name == translation_key:
            name = (
                palette_theme.name_vi
                if self.app.translator.language == "vi"
                else palette_theme.name_en
            )
        canvas.text(
            13,
            name,
            roles["primary"] if selected else roles["text"],
            (rect.x + 12, rect.y + 44),
            bold=selected,
            max_width=rect.width - 48,
        )
        if selected:
            center = (rect.right - 20, rect.y + 53)
            canvas.draw_circle(roles["accent"], center, 9)
            x, y = center
            canvas.draw_line(roles["on_accent"], (x - 4, y), (x - 1, y + 3), 2)
            canvas.draw_line(roles["on_accent"], (x - 1, y + 3), (x + 4, y - 3), 2)

    @staticmethod
    def _weights_detail(row: WeightsRow, file_name: str) -> str:
        return f"{row.name} — {file_name} ({row.source}) · sha {row.sha256} · depth {row.depth}"
