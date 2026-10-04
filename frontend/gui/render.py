"""Resolution-aware drawing primitives for logical GUI coordinates."""

from __future__ import annotations

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
    ) -> None:
        """Draw text using a font created at physical pixel size."""
        image = (
            self.render_fit(size, text, color, max_width, bold)
            if max_width is not None
            else (
                size if isinstance(size, pygame.font.Font) else self.font(size, self.scale, bold)
            ).render(text, True, color)
        )
        if center is not None:
            self.surface.blit(image, image.get_rect(center=self.point(center)))
        else:
            self.surface.blit(image, self.point(position))

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

    @staticmethod
    @lru_cache(maxsize=96)
    def font(size: int, scale: float, bold: bool = False) -> pygame.font.Font:
        from gui.assets_loader import get_font

        return get_font(size, bold=bold)
