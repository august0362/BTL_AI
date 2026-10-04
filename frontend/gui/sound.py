"""Optional, failure-tolerant sound effects for GUI events."""

from pathlib import Path
from typing import Any

import chess

SOUND_EVENTS = ("move", "capture", "check", "game_end")


def sound_for_move(board_before: chess.Board, move: chess.Move) -> str:
    """Choose a sound for a move, preferring check over capture."""
    board = board_before.copy()
    board.push(move)
    if board.is_check():
        return "check"
    if board_before.is_capture(move):
        return "capture"
    return "move"


class SoundManager:
    """Lazily play WAV effects while treating audio as an optional feature."""

    def __init__(self, sounds_dir: Path, enabled: bool = False) -> None:
        self._sounds_dir = Path(sounds_dir)
        self._enabled = bool(enabled)
        self._sounds: dict[str, object] = {}
        self._pygame: Any | None = None
        self._mixer_ready = False

    @property
    def enabled(self) -> bool:
        """Return whether playback is enabled."""
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        """Enable or disable playback."""
        self._enabled = bool(value)

    def play(self, event: str) -> None:
        """Play an event if possible; audio and file errors are ignored."""
        if not self._enabled or event not in SOUND_EVENTS:
            return
        try:
            sound_path = self._sounds_dir / f"{event}.wav"
            if not sound_path.is_file():
                return
            if self._pygame is None:
                import pygame

                self._pygame = pygame
            if not self._mixer_ready:
                if not self._pygame.mixer.get_init():
                    self._pygame.mixer.init()
                self._mixer_ready = True
            sound = self._sounds.get(event)
            if sound is None:
                sound = self._pygame.mixer.Sound(str(sound_path))
                self._sounds[event] = sound
            sound.play()
        except Exception:
            return
