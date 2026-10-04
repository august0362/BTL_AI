"""Display-independent helpers for fitting the logical canvas to a window."""

from __future__ import annotations

from dataclasses import dataclass

LOGICAL_SIZE = (960, 640)


@dataclass(frozen=True)
class Viewport:
    """The scaled canvas rectangle inside a window."""

    scale: float
    offset_x: int
    offset_y: int
    width: int
    height: int

    @classmethod
    def fit(
        cls,
        window_w: int,
        window_h: int,
        logical: tuple[int, int] = LOGICAL_SIZE,
    ) -> Viewport:
        """Fit the logical canvas into a window while preserving its aspect ratio."""
        logical_w, logical_h = logical
        if window_w <= 0 or window_h <= 0 or logical_w <= 0 or logical_h <= 0:
            raise ValueError("window and logical dimensions must be positive")

        scale = min(window_w / logical_w, window_h / logical_h)
        width = round(logical_w * scale)
        height = round(logical_h * scale)
        return cls(
            scale=scale,
            offset_x=(window_w - width) // 2,
            offset_y=(window_h - height) // 2,
            width=width,
            height=height,
        )

    def to_logical(self, x: float, y: float) -> tuple[float, float] | None:
        """Convert a window point to logical coordinates, or return None in a border."""
        if not (
            self.offset_x <= x < self.offset_x + self.width
            and self.offset_y <= y < self.offset_y + self.height
        ):
            return None
        return (x - self.offset_x) / self.scale, (y - self.offset_y) / self.scale

    def to_window(self, x: float, y: float) -> tuple[float, float]:
        """Convert a logical point to window coordinates."""
        return self.offset_x + x * self.scale, self.offset_y + y * self.scale
