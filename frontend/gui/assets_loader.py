"""Load cached board artwork and the bundled GUI fonts."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pygame

ASSET_DIR = Path(__file__).parent / "assets"


@lru_cache(maxsize=96)
def piece_image(piece_set: str, name: str, size: int) -> pygame.Surface:
    """Load and scale one piece image, caching the result by set and size."""
    path = ASSET_DIR / "pieces" / piece_set / f"{name}.png"
    image = pygame.image.load(path).convert_alpha()
    return pygame.transform.smoothscale(image, (size, size))


FONT_DIR = ASSET_DIR / "fonts"
_DISPLAY_FONT = FONT_DIR / "Syne-Bold.ttf"  # Latin only: no Vietnamese tone marks


@lru_cache(maxsize=192)
def _load_font(path: str, size: int) -> pygame.font.Font:
    return pygame.font.Font(path, size)


def clear_font_cache() -> None:
    """Drop cached fonts; they become invalid once pygame's font module restarts."""
    _load_font.cache_clear()


def get_font(size: int, *, bold: bool = False, semibold: bool = False) -> pygame.font.Font:
    """Return the bundled Inter font (full Vietnamese coverage) at the current UI scale."""
    from gui.render import FONT_SCALE

    size = max(1, round(size * FONT_SCALE))
    name = "Inter-Bold.ttf" if bold else "Inter-SemiBold.ttf" if semibold else "Inter-Regular.ttf"
    path = FONT_DIR / name
    if path.is_file():
        return _load_font(str(path), size)
    return pygame.font.Font(None, size)


def get_display_font(size: int, text: str = "") -> pygame.font.Font:
    """Return the Syne display face, or bold Inter when ``text`` needs Vietnamese marks."""
    from gui.render import FONT_SCALE

    if text.isascii() and _DISPLAY_FONT.is_file():
        return _load_font(str(_DISPLAY_FONT), max(1, round(size * FONT_SCALE)))
    return get_font(size, bold=True)


# fit word to a given width, scaling down if necessary
def render_fit(
    font: pygame.font.Font,
    text: str,
    color: tuple[int, int, int],
    max_width: int,
) -> pygame.Surface:
    """Render text scaled down as needed to stay within a horizontal bound."""
    from gui.render import FONT_SCALE

    image = font.render(text, True, color)
    max_width = max(1, round(max_width * FONT_SCALE))
    if image.get_width() > max_width:
        height = max(1, round(image.get_height() * max_width / image.get_width()))
        image = pygame.transform.smoothscale(image, (max_width, height))
    return image
