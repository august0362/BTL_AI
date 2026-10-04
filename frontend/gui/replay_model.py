"""Pygame-independent state model for stepping through a recorded game."""

from __future__ import annotations

import chess

from core.types import MoveRecord
from tournament.records import GameRecord


class ReplayModel:
    """Navigate a recorded game by rebuilding positions from its move history."""

    def __init__(self, record: GameRecord) -> None:
        self._record = record
        self._index = 0
        self._playing = False
        self._delay_ms = 500
        self._last_step_ms: float | None = None

    @property
    def index(self) -> int:
        """Return the current half-move index."""
        return self._index

    @property
    def length(self) -> int:
        """Return the number of recorded half-moves."""
        return len(self._record.moves)

    @property
    def board(self) -> chess.Board:
        """Return a new board with all moves through the current index applied."""
        board = chess.Board()
        for move_record in self._record.moves[: self._index]:
            board.push_uci(move_record.uci)
        return board

    @property
    def last_move(self) -> chess.Move | None:
        """Return the move that led to the current position, if any."""
        if self._index == 0:
            return None
        return chess.Move.from_uci(self._record.moves[self._index - 1].uci)

    @property
    def current_move(self) -> MoveRecord | None:
        """Return the record for the move that led to the current position."""
        if self._index == 0:
            return None
        return self._record.moves[self._index - 1]

    def first(self) -> None:
        """Move to the initial position and stop playback."""
        self.seek(0)
        self.pause()

    def last(self) -> None:
        """Move to the final position and stop playback."""
        self.seek(self.length)
        self.pause()

    def next(self) -> bool:
        """Advance one half-move, returning whether the position changed."""
        if self._index >= self.length:
            return False
        self._index += 1
        return True

    def prev(self) -> bool:
        """Go back one half-move, returning whether the position changed."""
        if self._index <= 0:
            return False
        self._index -= 1
        return True

    def seek(self, index: int) -> None:
        """Set the current half-move index, clamped to the recorded game."""
        self._index = max(0, min(self.length, int(index)))

    @property
    def playing(self) -> bool:
        """Return whether timed playback is active."""
        return self._playing

    def play(self, now_ms: float) -> None:
        """Start playback, restarting at the initial position when at the end."""
        if self._index >= self.length:
            self._index = 0
        self._playing = True
        self._last_step_ms = now_ms

    def pause(self) -> None:
        """Stop timed playback."""
        self._playing = False

    @property
    def delay_ms(self) -> int:
        """Return the playback delay in milliseconds."""
        return self._delay_ms

    @delay_ms.setter
    def delay_ms(self, value: int) -> None:
        """Set the playback delay, clamped to the supported interval."""
        self._delay_ms = max(100, min(5000, int(value)))

    def tick(self, now_ms: float) -> bool:
        """Advance after one delay interval and pause automatically at the end."""
        if not self._playing or self._last_step_ms is None:
            return False
        if now_ms - self._last_step_ms < self._delay_ms:
            return False
        self._last_step_ms = now_ms
        if not self.next():
            self.pause()
            return False
        if self._index >= self.length:
            self.pause()
        return True
