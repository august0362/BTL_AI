"""Resolution-aware drawing primitives for logical GUI coordinates."""

from __future__ import annotations

import math
from functools import lru_cache

import pygame

FONT_SCALE = 1.0


class Render:
    """Draw logical geometry onto a physical-resolution surface."""

    def __init__(self, surface: pygame.Surface, scale: float) -> None:
        self.surface = surface
        self.scale = scale

    def fill(self, color) -> None:
        """Fill the physical target surface."""
        self.surface.fill(color)

    def get_rect(self) -> pygame.Rect:
        """Return the logical viewport bounds for layout inspection."""
        return pygame.Rect(
            0,
            0,
            round(self.surface.get_width() / self.scale),
            round(self.surface.get_height() / self.scale),
        )

    def blit(self, image: pygame.Surface, position: tuple[float, float] | pygame.Rect) -> None:
        """Blit a rendered text surface at a logical position."""
        if isinstance(position, pygame.Rect):
            self.surface.blit(image, image.get_rect(center=self.point(position.center)))
            return
        self.surface.blit(image, self.point(position))

    def blit_image(self, image: pygame.Surface, position: tuple[float, float]) -> None:
        """Scale a logical-sized image to physical pixels and blit it."""
        size = tuple(max(1, round(value * self.scale)) for value in image.get_size())
        if size != image.get_size():
            image = pygame.transform.smoothscale(image, size)
        self.surface.blit(image, self.point(position))

    def blit_center(self, image: pygame.Surface, center: tuple[float, float]) -> None:
        """Blit an image centered on a logical point."""
        size = tuple(max(1, round(value * self.scale)) for value in image.get_size())
        if size != image.get_size():
            image = pygame.transform.smoothscale(image, size)
        self.surface.blit(image, image.get_rect(center=self.point(center)))

    def render_fit(
        self, size: int | pygame.font.Font, text: str, color, max_width: int, bold: bool = False
    ):
        """Render logical-size text and fit it within a logical width."""
        font = size if isinstance(size, pygame.font.Font) else self.font(size, self.scale, bold)
        image = font.render(text, True, color)
        physical_width = max(1, round(max_width * self.scale))
        if image.get_width() > physical_width:
            height = max(1, round(image.get_height() * physical_width / image.get_width()))
            image = pygame.transform.smoothscale(image, (physical_width, height))
        return image

    def text(
        self,
        size: int | pygame.font.Font,
        text: str,
        color,
        position: tuple[float, float],
        *,
        bold: bool = False,
        max_width: int | None = None,
        center: tuple[float, float] | None = None,
        display: bool = False,
        semibold: bool = False,
    ) -> None:
        """Draw text using a font created at physical pixel size (``display``: Syne headline)."""
        if display and isinstance(size, int):
            from gui.assets_loader import get_display_font

            size = get_display_font(size, text)
        elif semibold and isinstance(size, int):
            from gui.assets_loader import get_font

            size = get_font(size, semibold=True)
        font = size if isinstance(size, pygame.font.Font) else self.font(size, self.scale, bold)
        image = font.render(text, True, color)
        # Stacked Vietnamese capitals (Ắ, Ể, Ố) make the image taller than the line box;
        # the extra rows sit on top, so anchor on the line box to keep a common baseline.
        line_height = font.get_height()
        if max_width is not None:
            limit = max(1, round(max_width * self.scale))
            if image.get_width() > limit:
                ratio = limit / image.get_width()
                line_height = max(1, round(line_height * ratio))
                image = pygame.transform.smoothscale(
                    image, (limit, max(1, round(image.get_height() * ratio)))
                )
        extra = max(0, image.get_height() - line_height)
        if center is not None:
            x, y = self.point(center)
            self.surface.blit(image, image.get_rect(centerx=x, bottom=round(y + line_height / 2)))
        else:
            x, y = self.point(position)
            self.surface.blit(image, (x, y - extra))

    def draw_polygon(self, color, points, width: int = 0) -> None:
        """Draw a polygon from logical points."""
        pygame.draw.polygon(
            self.surface, color, [self.point(point) for point in points], round(width * self.scale)
        )

    def draw_arc(self, color, rect, start: float, stop: float, width: int = 1) -> None:
        """Draw an arc inside a logical rectangle."""
        pygame.draw.arc(
            self.surface, color, self.rect(rect), start, stop, max(1, round(width * self.scale))
        )

    def point(self, value: tuple[float, float]) -> tuple[int, int]:
        return round(value[0] * self.scale), round(value[1] * self.scale)

    def rect(self, rect: pygame.Rect | tuple[int, int, int, int]) -> pygame.Rect:
        return pygame.Rect(*(round(value * self.scale) for value in rect))

    def draw_rect(self, color, rect, width: int = 0, radius: int = 0) -> None:
        pygame.draw.rect(
            self.surface,
            color,
            self.rect(rect),
            round(width * self.scale),
            border_radius=round(radius * self.scale),
        )

    def draw_line(self, color, start, end, width: int = 1) -> None:
        pygame.draw.line(
            self.surface,
            color,
            self.point(start),
            self.point(end),
            max(1, round(width * self.scale)),
        )

    def draw_circle(self, color, center, radius: int, width: int = 0) -> None:
        pygame.draw.circle(
            self.surface,
            color,
            self.point(center),
            round(radius * self.scale),
            max(0, round(width * self.scale)),
        )

    def draw_glass(
        self,
        rect,
        color,
        *,
        alpha: int = 215,
        radius: int = 12,
        border=None,
        rim=None,
    ) -> None:
        """Draw a translucent rounded panel with an optional edge and top rim light."""
        target = self.rect(rect)
        if target.width <= 0 or target.height <= 0:
            return
        corner = round(radius * self.scale)
        layer = pygame.Surface(target.size, pygame.SRCALPHA)
        pygame.draw.rect(
            layer, (*pygame.Color(color)[:3], alpha), layer.get_rect(), border_radius=corner
        )
        self.surface.blit(layer, target.topleft)
        if border is not None:
            pygame.draw.rect(
                self.surface, border, target, max(1, round(self.scale)), border_radius=corner
            )
        if rim is not None and target.width > 2 * corner:
            pygame.draw.line(
                self.surface,
                rim,
                (target.left + corner, target.top),
                (target.right - corner - 1, target.top),
                max(1, round(self.scale)),
            )

    def draw_backdrop(self, roles: dict[str, str], seconds: float | None = None) -> None:
        """Paint the gradient, two slowly drifting aurora glows and falling frost motes."""
        if seconds is None:
            seconds = pygame.time.get_ticks() / 1000
        width, height = self.surface.get_size()
        self.surface.blit(_gradient((width, height), roles["bg"], roles["secondary"]), (0, 0))
        for cx, cy, radius, color, phase in (
            (0.86, 0.10, 0.46, roles["accent"], 0.0),
            (0.08, 0.95, 0.40, roles["glow"], 2.1),
        ):
            sprite = _glow_sprite(round(radius * width), color)
            x = (cx + 0.05 * math.sin(seconds * 0.21 + phase)) * width
            y = (cy + 0.06 * math.cos(seconds * 0.17 + phase)) * height
            self.surface.blit(sprite, sprite.get_rect(center=(round(x), round(y))))
        bg = pygame.Color(roles["bg"])
        dark = bg.r + bg.g + bg.b < 384
        speck = roles["rim"] if dark else roles["glow"]
        for index in range(_MOTES):
            # Each mote falls at its own speed and sways sideways; positions wrap around.
            seed = (index * 7919) % 1000 / 1000
            speed = 6 + 14 * ((index * 104729) % 1000 / 1000)
            size = 1 + (index % 3)
            x = (seed * 960 + 14 * math.sin(seconds * 0.6 + index)) % 960
            y = ((index * 37.3) % 640 + seconds * speed) % 660 - 10
            dot = _mote(round(size * self.scale), speck, (70 if dark else 40) + 25 * (index % 3))
            self.surface.blit(dot, dot.get_rect(center=self.point((x, y))))

    @staticmethod
    @lru_cache(maxsize=96)
    def font(size: int, scale: float, bold: bool = False) -> pygame.font.Font:
        from gui.assets_loader import get_font

        return get_font(size, bold=bold)


_MOTES = 42
_GLOW_ALPHA = 46


@lru_cache(maxsize=4)
def _gradient(size: tuple[int, int], base: str, deep: str) -> pygame.Surface:
    """Build a cached vertical gradient from the background toward the deep color."""
    width, height = size
    image = pygame.Surface(size)
    top, bottom = pygame.Color(base), pygame.Color(base).lerp(pygame.Color(deep), 0.28)
    for y in range(height):
        pygame.draw.line(image, top.lerp(bottom, y / max(1, height - 1)), (0, y), (width, y))
    return image.convert() if pygame.display.get_surface() else image


@lru_cache(maxsize=8)
def _glow_sprite(radius: int, color: str) -> pygame.Surface:
    """Build a soft radial light spot with a smooth (1 - d)^2 falloff, then upscale it."""
    radius = max(1, radius)
    base = 64
    rgb = pygame.Color(color)[:3]
    image = pygame.Surface((base * 2, base * 2), pygame.SRCALPHA)
    image.fill((*rgb, 0))
    for y in range(base * 2):
        for x in range(base * 2):
            distance = math.hypot(x + 0.5 - base, y + 0.5 - base) / base
            if distance < 1:
                image.set_at((x, y), (*rgb, round(_GLOW_ALPHA * (1 - distance) ** 2)))
    return pygame.transform.smoothscale(image, (radius * 2, radius * 2))


@lru_cache(maxsize=24)
def _mote(radius: int, color: str, alpha: int) -> pygame.Surface:
    """Build one small translucent frost particle."""
    radius = max(1, radius)
    image = pygame.Surface((radius * 2 + 2, radius * 2 + 2), pygame.SRCALPHA)
    pygame.draw.circle(image, (*pygame.Color(color)[:3], alpha), (radius + 1, radius + 1), radius)
    return image
