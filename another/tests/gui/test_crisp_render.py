"""Regression coverage for physical-resolution rendering and visible selection."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import chess
import pygame

from core.types import GameResult, Termination
from gui import render as render_module
from gui.app import App
from gui.assets_loader import get_font
from gui.replay_model import ReplayModel
from gui.theme import THEMES
from tournament.records import GameRecord


def _luminance(color: str) -> float:
    channels = [int(color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [
        value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
        for value in channels
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(first: str, second: str) -> float:
    light, dark = sorted((_luminance(first), _luminance(second)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


def test_render_frames_use_physical_viewport_without_full_surface_scaling(monkeypatch, tmp_path):
    """Every screen draws at the viewport size and fonts scale with physical pixels."""
    from core.config import load_config

    config = load_config(local_path=None)
    config["window"].update(width=1440, height=960)
    config["ui"]["show_debug_bots"] = True
    app = App(config=config, data_dir=tmp_path)
    calls: list[tuple[int, int]] = []
    presented: list[tuple[int, int]] = []

    def record_transform(original):
        def transformed(surface, size, *args, **kwargs):
            calls.append(surface.get_size())
            return original(surface, size, *args, **kwargs)

        return transformed

    original_present = app._present

    def present():
        presented.append(app.physical_canvas.get_size())
        original_present()

    monkeypatch.setattr("pygame.transform.scale", record_transform(pygame.transform.scale))
    monkeypatch.setattr(
        "pygame.transform.smoothscale",
        record_transform(pygame.transform.smoothscale),
    )
    monkeypatch.setattr(app, "_present", present)
    try:
        names = (
            "menu",
            "setup_human",
            "setup_bots",
            "history",
            "leaderboard",
            "settings",
        )
        for name in names:
            app.goto(name)
            app.render_frame()

        record = GameRecord(
            game_id="preview",
            started_at="2026-01-01T00:00:00+00:00",
            mode="human_vs_bot",
            white_id="human",
            black_id="random",
            white_name="Human",
            black_name="Random",
            opening_moves=[],
            moves=[],
            result=GameResult(None, Termination.STALEMATE),
        )
        app.replay_model = ReplayModel(record)
        app.goto("replay")
        app.render_frame()
        app.start_human_game("random", chess.WHITE)
        app.render_frame()

        assert app.canvas_size == (1440, 960)
        assert app.physical_canvas.get_size() == (app.viewport.width, app.viewport.height)
        assert presented and all(size == app.canvas_size for size in presented)
        assert all(width < 900 or height < 600 for width, height in calls)

        render_module.FONT_SCALE = 1.0
        base_height = get_font(15).get_height()
        render_module.FONT_SCALE = app.render_scale
        scaled_height = get_font(15).get_height()
        assert scaled_height >= 1.4 * base_height
    finally:
        render_module.FONT_SCALE = 1.0
        app.quit()


def test_theme_selected_button_colors_are_visibly_distinct():
    """Selected fills contrast with unselected fills across all palettes."""
    for theme in THEMES.values():
        roles = theme.roles
        assert "on_accent" in roles
        assert roles["accent"] != roles["secondary"]
        assert _contrast(roles["accent"], roles["secondary"]) >= 1.5
        assert _contrast(roles["on_accent"], roles["accent"]) >= 4.5
