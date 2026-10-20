"""Linear-regression evaluator for the alpha-beta bot."""

import json
from functools import lru_cache
from pathlib import Path

import chess

from ai.alphabeta_regression.feature import BoardFeatures
from ai.base_bot import BotUnavailableError

WEIGHTS_PATH = Path(__file__).with_name("weight.json")
FEATURE_NAMES = (
    "pawn_diff",
    "knight_diff",
    "bishop_diff",
    "rook_diff",
    "queen_diff",
    "mobility_diff",
    "center_control_diff",
    "pawn_advance_diff",
)


@lru_cache(maxsize=1)
def _load_weights() -> dict[str, float]:
    """Load and validate the regression feature weights."""
    try:
        with WEIGHTS_PATH.open(encoding="utf-8") as weights_file:
            raw_weights = json.load(weights_file)
    except (OSError, json.JSONDecodeError) as exc:
        raise BotUnavailableError(
            f"alphabeta_regression: cannot load weights from {WEIGHTS_PATH}: {exc}"
        ) from exc

    if not isinstance(raw_weights, dict):
        raise BotUnavailableError("alphabeta_regression: weights must be a JSON object")

    try:
        return {name: _validate_weight(raw_weights[name], name) for name in FEATURE_NAMES}
    except (KeyError, TypeError, ValueError) as exc:
        raise BotUnavailableError(
            f"alphabeta_regression: invalid weights in {WEIGHTS_PATH}: {exc}"
        ) from exc


def _validate_weight(value: object, name: str) -> float:
    """Return a finite numeric weight from the JSON value."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number")
    weight = float(value)
    if weight != weight or weight in (float("inf"), float("-inf")):
        raise ValueError(f"{name} must be finite")
    return weight


def evaluate(features: BoardFeatures, root_color: chess.Color) -> float:
    """Return the weighted feature score from the root player's point of view."""
    if features.is_checkmate:
        return float("inf") if features.turn != root_color else float("-inf")
    if features.is_game_over:
        return 0.0

    values = (
        features.pawn_diff,
        features.knight_diff,
        features.bishop_diff,
        features.rook_diff,
        features.queen_diff,
        features.mobility_diff,
        features.center_control_diff,
        features.pawn_advance_diff,
    )
    score = sum(
        weight * value for weight, value in zip(_load_weights().values(), values, strict=True)
    )
    return score if root_color == chess.WHITE else -score
