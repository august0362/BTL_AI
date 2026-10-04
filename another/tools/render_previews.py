"""Render a contact sheet and theme previews without opening a visible window."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import chess
import pygame

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "frontend")]

PREVIEW_ROOT = ROOT / ".preview"
PREVIEW_DIR = PREVIEW_ROOT / "themes"
PREVIEW_DATA_DIR = PREVIEW_ROOT / "data"


def wait_for_human(app, timeout: float = 15.0) -> None:
    """Wait for a human turn in the preview game."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.render_frame()
        snapshot = app.controller.snapshot()
        if snapshot.waiting_for_human:
            return
        if snapshot.finished:
            raise RuntimeError("The sample game ended before a preview position was ready")
        time.sleep(0.02)
    raise TimeoutError("Timed out waiting for the sample game position")


def wait_for_moves(app, count: int, timeout: float = 15.0) -> None:
    """Wait until the sample controller records the requested move count."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.render_frame()
        if len(app.controller.snapshot().moves) >= count:
            return
        time.sleep(0.02)
    raise TimeoutError(f"Timed out waiting for {count} sample moves")


def click_square(app, square: chess.Square) -> None:
    """Click the center of a logical board square."""
    from gui.board_geometry import square_origin

    x, y = square_origin(square)
    app.click_logical(x + 40, y + 40)


def build_contact_sheet(game_paths: dict[str, Path], translator, themes) -> Path:
    """Create a labeled grid of all theme game screenshots."""
    columns = 4
    tile_width, tile_height = 310, 226
    rows = (len(game_paths) + columns - 1) // columns
    sheet = pygame.Surface((columns * tile_width, rows * tile_height))
    sheet.fill("#101B20")
    font = pygame.font.Font(None, 20)
    for index, (theme_id, path) in enumerate(game_paths.items()):
        x = (index % columns) * tile_width + 10
        y = (index // columns) * tile_height + 8
        theme = themes[theme_id]
        label_key = f"themes.{theme_id}"
        label = translator.t(label_key)
        if label == label_key:
            label = theme.name_en
        sheet.blit(font.render(label, True, "#F5F4EA"), (x, y))
        image = pygame.image.load(path)
        image = pygame.transform.smoothscale(image, (290, 194))
        sheet.blit(image, (x, y + 22))
    path = PREVIEW_DIR / "_all.png"
    pygame.image.save(sheet, path)
    return path


def main() -> None:
    """Save menu, game, and scrolled settings previews for every theme."""
    from core.config import load_config
    from gui.app import App
    from gui.i18n import Translator
    from gui.theme import THEME_IDS, THEMES

    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    PREVIEW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    config = load_config()
    config.setdefault("ui", {}).update(language="vi", show_debug_bots=True, bot_move_delay_ms=0)
    config.setdefault("game", {}).update(max_plies=6, random_opening_plies=0)
    config.setdefault("window", {}).update(width=1440, height=960)
    app = App(
        config=config,
        data_dir=PREVIEW_DATA_DIR / "app",
        local_config_path=PREVIEW_DATA_DIR / "local.toml",
    )
    app.resize(1440, 960)
    game_paths: dict[str, Path] = {}
    output_paths: list[Path] = []
    try:
        for theme_id in THEME_IDS:
            app.set_theme(theme_id)

            app.goto("menu")
            app.render_frame()
            menu_path = PREVIEW_DIR / f"{theme_id}_menu.png"
            pygame.image.save(app.window, menu_path)
            output_paths.append(menu_path)

            app.start_human_game("random", chess.WHITE)
            wait_for_human(app)
            first_move = next(
                move
                for move in app.controller.snapshot().board.legal_moves
                if move.promotion is None
            )
            click_square(app, first_move.from_square)
            click_square(app, first_move.to_square)
            wait_for_moves(app, 2)
            wait_for_human(app)
            hint_square = next(
                move.from_square
                for move in app.controller.snapshot().board.legal_moves
                if move.promotion is None
            )
            click_square(app, hint_square)
            app.render_frame()
            game_path = PREVIEW_DIR / f"{theme_id}_game.png"
            pygame.image.save(app.window, game_path)
            game_paths[theme_id] = game_path
            output_paths.append(game_path)

            app.goto("settings")
            app.render_frame()
            top_path = PREVIEW_DIR / f"{theme_id}_settings_top.png"
            pygame.image.save(app.window, top_path)
            output_paths.append(top_path)

            app.scroll_logical(-100)
            app.render_frame()
            bottom_path = PREVIEW_DIR / f"{theme_id}_settings_bottom.png"
            pygame.image.save(app.window, bottom_path)
            output_paths.append(bottom_path)
            app.scroll_logical(100)

        sheet_path = build_contact_sheet(game_paths, Translator("en"), THEMES)
        output_paths.append(sheet_path)
    finally:
        app.quit()

    for path in output_paths:
        print(path.relative_to(ROOT))


if __name__ == "__main__":
    main()
