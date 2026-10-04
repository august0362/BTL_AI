"""Change language, sound, replay speed, and the active color theme."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from gui.render import Render
from gui.screens.base import Screen
from gui.theme import THEMES, Theme
from gui.widgets.button import Button

if TYPE_CHECKING:
    from gui.app import App


class SettingsScreen(Screen):
    """Edit interface preferences and preview the available themes."""

    THEME_AREA = pygame.Rect(80, 184, 800, 306)
    CARD_WIDTH = 188
    CARD_HEIGHT = 62
    COLUMN_STEP = 200
    ROW_STEP = 70

    def __init__(self, app: App) -> None:
        super().__init__(app)
        self.vi = Button(
            pygame.Rect(360, 96, 112, 38),
            app.translator.t("settings.language_vi"),
            selected=app.translator.language == "vi",
        )
        self.en = Button(
            pygame.Rect(488, 96, 112, 38),
            app.translator.t("settings.language_en"),
            selected=app.translator.language == "en",
        )
        self.sound = Button(pygame.Rect(92, 518, 238, 38), self._sound_label())
        self.speed = Button(pygame.Rect(344, 518, 360, 38), self._speed_label())
        self.back = Button(pygame.Rect(720, 518, 160, 38), app.translator.t("setup.back"))
        self.theme_rects: dict[str, pygame.Rect] = {}
        self.group_positions: list[tuple[str, int]] = []
        self.scroll_up = pygame.Rect(892, 185, 28, 24)
        self.scroll_down = pygame.Rect(892, 465, 28, 24)
        self.scroll_offset = 0
        self.preview_theme_id: str | None = None
        self.content_height = 0
        self._layout_theme_rects()

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
                    80 + column * self.COLUMN_STEP,
                    self.THEME_AREA.y + y + row * self.ROW_STEP - self.scroll_offset,
                    self.CARD_WIDTH,
                    self.CARD_HEIGHT,
                )
            y += ((len(theme_ids) + 3) // 4) * self.ROW_STEP + 10
        self.content_height = max(0, y - 10)

    def _max_scroll(self) -> int:
        return max(0, self.content_height - self.THEME_AREA.height)

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
        if self.THEME_AREA.collidepoint(point):
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
        elif self.sound.contains(point):
            self.app.set_sound_enabled(not self.app.sound_enabled)
            self.sound.label = self._sound_label()
        elif self.speed.contains(point):
            current = self.app.config.get("ui", {}).get("replay_delay_ms", 800)
            self.app.set_replay_delay(500 if current >= 1000 else current + 500)
            self.speed.label = self._speed_label()
        elif self.back.contains(point):
            self.app.goto("menu")
        elif self.THEME_AREA.collidepoint(point):
            for theme_id, rect in self.theme_rects.items():
                if rect.collidepoint(point):
                    self.app.set_theme(theme_id)
                    return

    def draw(self, canvas: Render) -> None:
        theme = self.preview_theme
        roles = theme.roles
        canvas.fill(roles["bg"])
        canvas.text(
            28,
            self.app.translator.t("settings.title"),
            roles["text"],
            (80, 38),
            bold=True,
        )
        canvas.text(
            15,
            self.app.translator.t("settings.language"),
            roles["text_muted"],
            (200, 108),
        )
        self.vi.selected = self.app.translator.language == "vi"
        self.en.selected = self.app.translator.language == "en"
        self.vi.draw(canvas, 14, theme)
        self.en.draw(canvas, 14, theme)
        canvas.text(
            18,
            self.app.translator.t("settings.themes"),
            roles["text"],
            (80, 155),
            bold=True,
        )
        canvas.draw_rect(roles["surface"], self.THEME_AREA, radius=10)
        previous_clip = canvas.surface.get_clip()
        canvas.surface.set_clip(canvas.rect(self.THEME_AREA))
        for group_key, y in self.group_positions:
            group_y = self.THEME_AREA.y + y - self.scroll_offset
            canvas.text(
                13,
                self.app.translator.t(group_key),
                roles["text_muted"],
                (92, group_y + 4),
                bold=True,
            )
        for theme_id, rect in self.theme_rects.items():
            if not rect.colliderect(self.THEME_AREA):
                continue
            palette_theme = THEMES[theme_id]
            selected = theme_id == self.app.theme.id
            hovered = theme_id == self.preview_theme_id
            fill = (
                roles["accent"]
                if selected
                else roles["surface_alt"]
                if hovered
                else roles["surface"]
            )
            canvas.draw_rect(fill, rect, radius=8)
            border = (
                roles["accent"] if selected else roles["primary"] if hovered else roles["border"]
            )
            canvas.draw_rect(border, rect, 2 if selected else 1, radius=8)
            for index, color in enumerate(palette_theme.palette):
                canvas.draw_rect(
                    color,
                    (rect.x + 8 + index * 38, rect.y + 7, 30, 18),
                    radius=4,
                )
            translation_key = f"themes.{theme_id}"
            name = self.app.translator.t(translation_key)
            if name == translation_key:
                name = (
                    palette_theme.name_vi
                    if self.app.translator.language == "vi"
                    else palette_theme.name_en
                )
            text_color = roles["on_accent"] if selected else roles["text"]
            canvas.text(
                12,
                name,
                text_color,
                (rect.x + 8, rect.y + 35),
                max_width=rect.width - 16,
            )
        canvas.surface.set_clip(previous_clip)
        self._draw_scroll_control(canvas, self.scroll_up, up=True, roles=roles)
        self._draw_scroll_control(canvas, self.scroll_down, up=False, roles=roles)
        self.sound.draw(canvas, 13, theme)
        self.speed.draw(canvas, 13, theme)
        self.back.draw(canvas, 14, theme)

    def _draw_scroll_control(self, canvas: Render, rect: pygame.Rect, *, up: bool, roles) -> None:
        enabled = self.scroll_offset > 0 if up else self.scroll_offset < self._max_scroll()
        color = roles["accent"] if enabled else roles["border"]
        canvas.draw_rect(roles["surface"], rect, radius=6)
        canvas.draw_rect(roles["border"], rect, 1, radius=6)
        center_x, center_y = rect.center
        if up:
            points = (
                (center_x, center_y - 5),
                (center_x - 6, center_y + 4),
                (center_x + 6, center_y + 4),
            )
        else:
            points = (
                (center_x, center_y + 5),
                (center_x - 6, center_y - 4),
                (center_x + 6, center_y - 4),
            )
        canvas.draw_polygon(color, points)
