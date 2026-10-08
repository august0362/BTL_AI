"""Shared interface for tournament bots."""

from abc import ABC, abstractmethod

import chess


class BotUnavailableError(Exception):
    """Raised when a bot cannot be initialized."""


class BaseBot(ABC):
    """Base class implementing the common bot state and interface."""

    bot_id: str = ""
    display_name: str = ""
    is_baseline: bool = False

    def __init__(self, config: dict | None = None) -> None:
        self.config = config or {}
        self.last_search_info: dict = {}
        name = self.config.get("display_name")
        if isinstance(name, str) and name.strip():
            self.display_name = name.strip()  # "[bots.<id>] display_name" in the config

    @abstractmethod
    def select_move(self, board: chess.Board) -> chess.Move:
        """Return a legal move for the side to move."""

    def reset(self) -> None:
        """Clear per-game search information."""
        self.last_search_info = {}
