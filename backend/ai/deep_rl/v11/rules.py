"""V11 player-specific utility (draw = -0.1 for both sides); outcomes come from ``v20.rules``."""

from __future__ import annotations

import chess


def utility(winner: chess.Color | None, player: chess.Color) -> float:
    """Return +1 for a win, -1 for a loss, and -0.1 for either player's draw."""
    if winner is None:
        return -0.1
    return 1.0 if winner == player else -1.0
