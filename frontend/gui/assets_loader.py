"""Load cached board artwork and choose a font for the GUI."""

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


def get_font(size: int, *, bold: bool = False) -> pygame.font.Font:
    """Pick an installed system font with broad Latin and Vietnamese coverage."""
    from gui.render import FONT_SCALE

    size = max(1, round(size * FONT_SCALE))
    for name in ("segoeui", "arial", "dejavusans"):
        path = pygame.font.match_font(name, bold=bold)
        if path:
            return pygame.font.Font(path, size)
    return pygame.font.Font(None, size)

#fit word to a given width, scaling down if necessary
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
