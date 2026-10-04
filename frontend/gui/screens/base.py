"""Base screen interface used by the application screen manager."""

from __future__ import annotations

from typing import TYPE_CHECKING

from gui.render import Render

if TYPE_CHECKING:
    from gui.app import App


class Screen:
    """Interface implemented by each application screen."""

    def __init__(self, app: App) -> None:
        self.app = app

    def handle_click(self, x: float, y: float) -> None:
        """Handle a logical canvas click."""

    def handle_hover(self, x: float, y: float) -> None:
        """Update button hover state from logical pointer coordinates."""
        for value in vars(self).values():
            if hasattr(value, "update_hover"):
                value.update_hover((x, y))
            elif isinstance(value, (list, tuple)):
                for item in value:
                    if hasattr(item, "update_hover"):
                        item.update_hover((x, y))

    def handle_scroll(self, dy: int) -> None:
        """Handle vertical mouse-wheel movement."""

    def update(self) -> None:
        """Update transient screen state once per frame."""

    def draw(self, canvas: Render) -> None:
        """Draw this screen onto the physical viewport through logical coordinates."""

    def on_exit(self) -> None:
        """Release resources when leaving this screen."""
