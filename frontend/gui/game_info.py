"""Display-independent summaries of captures and move search times."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

import chess

_INITIAL_COUNTS = (
    (chess.QUEEN, 1),
    (chess.ROOK, 2),
    (chess.BISHOP, 2),
    (chess.KNIGHT, 2),
    (chess.PAWN, 8),
)


class MoveTiming(Protocol):
    """Fields needed to include a move in the think time summary."""

    ply: int
    think_time_s: float
    is_random_opening: bool


def captured_pieces(board: chess.Board) -> dict[chess.Color, list[chess.PieceType]]:
    """List missing pieces for each color in descending piece value order."""
    captured: dict[chess.Color, list[chess.PieceType]] = {}
    for color in (chess.WHITE, chess.BLACK):
        missing: list[chess.PieceType] = []
        for piece_type, initial_count in _INITIAL_COUNTS:
            current_count = len(board.pieces(piece_type, color))
            missing.extend([piece_type] * max(0, initial_count - current_count))
        captured[color] = missing
    return captured


def think_time_summary(
    moves: Iterable[MoveTiming],
) -> dict[chess.Color, tuple[float | None, float | None]]:
    """Return each side's latest non-random move time and its average."""
    times: dict[chess.Color, list[tuple[int, float]]] = {
        chess.WHITE: [],
        chess.BLACK: [],
    }
    for move in moves:
        if move.is_random_opening:
            continue
        color = chess.WHITE if move.ply % 2 else chess.BLACK
        times[color].append((move.ply, float(move.think_time_s)))

    summary: dict[chess.Color, tuple[float | None, float | None]] = {}
    for color, color_times in times.items():
        if not color_times:
            summary[color] = (None, None)
            continue
        latest = max(color_times, key=lambda item: item[0])[1]
        average = sum(seconds for _, seconds in color_times) / len(color_times)
        summary[color] = (latest, average)
    return summary
