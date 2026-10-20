"""Train a regression evaluator from the JSONL position dataset."""

import argparse
import json
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Allow ``python backend\ai\alphabeta_regression\train.py`` from the repository root.
if __package__ in {None, ""}:
    backend_path = Path(__file__).resolve().parents[2]
    if str(backend_path) not in sys.path:
        sys.path.insert(0, str(backend_path))

from ai.alphabeta_regression.evaluate import FEATURE_NAMES


@dataclass(frozen=True)
class Position:
    """One labeled chess position from the JSONL dataset."""

    game_id: str
    values: tuple[float, ...]
    target: float


@dataclass(frozen=True)
class TrainingResult:
    """Fitted model and validation metadata."""

    model: dict[str, Any]
    validation_mse: float
    train_games: int
    validation_games: int


def train(
    dataset_path: Path,
    model_path: Path,
    *,
    weight_path: Path | None = None,
    model_type: str = "ridge",
    alpha: float = 1.0,
    validation_fraction: float = 0.2,
    seed: int = 0,
    standardize: bool = True,
) -> TrainingResult:
    """Fit a grouped regression model and export model and runtime weights."""
    if model_type not in {"linear", "ridge"}:
        raise ValueError("model_type must be 'linear' or 'ridge'")
    if alpha < 0:
        raise ValueError("alpha must be non-negative")
    if not 0 < validation_fraction < 1:
        raise ValueError("validation_fraction must be between 0 and 1")

    positions = _read_positions(dataset_path)
    train_positions, validation_positions = _split_by_game(positions, validation_fraction, seed)
    means, scales = _normalization(train_positions, standardize)
    train_matrix = [_transform(position.values, means, scales) for position in train_positions]
    validation_matrix = [
        _transform(position.values, means, scales) for position in validation_positions
    ]
    coefficients, intercept = _fit_regression(
        train_matrix,
        [position.target for position in train_positions],
        alpha if model_type == "ridge" else 0.0,
    )
    validation_predictions = [
        _predict(values, coefficients, intercept) for values in validation_matrix
    ]
    validation_mse = _mean_squared_error(
        [position.target for position in validation_positions],
        validation_predictions,
    )
    model = {
        "model_type": model_type,
        "feature_names": list(FEATURE_NAMES),
        "coefficients": coefficients,
        "intercept": intercept,
        "normalization": {
            "enabled": standardize,
            "mean": means,
            "scale": scales,
        },
        "alpha": alpha if model_type == "ridge" else 0.0,
        "train_games": len({position.game_id for position in train_positions}),
        "validation_games": len({position.game_id for position in validation_positions}),
        "validation_mse": validation_mse,
    }
    model_path.parent.mkdir(parents=True, exist_ok=True)
    model_path.write_text(
        json.dumps(model, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    if weight_path is None:
        weight_path = Path(__file__).with_name("weight.json")
    _write_runtime_weights(model, weight_path)
    return TrainingResult(
        model=model,
        validation_mse=validation_mse,
        train_games=model["train_games"],
        validation_games=model["validation_games"],
    )


def _write_runtime_weights(model: dict[str, Any], weight_path: Path) -> None:
    """Export fitted coefficients in the raw-feature format used by the bot."""
    normalization = model["normalization"]
    coefficients = model["coefficients"]
    scales = normalization["scale"]
    raw_coefficients = [
        coefficient / scale for coefficient, scale in zip(coefficients, scales, strict=True)
    ]
    weight_path.parent.mkdir(parents=True, exist_ok=True)
    weight_path.write_text(
        json.dumps(
            dict(zip(FEATURE_NAMES, raw_coefficients, strict=True)),
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )


def _read_positions(dataset_path: Path) -> list[Position]:
    """Read and validate labeled positions from JSONL."""
    positions: list[Position] = []
    with dataset_path.open(encoding="utf-8") as dataset_file:
        for line_number, line in enumerate(dataset_file, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                game_id = row["game_id"]
                features = row["features"]
                target = row["target"]
                values = tuple(float(features[name]) for name in FEATURE_NAMES)
                target_value = float(target)
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                raise ValueError(f"Invalid dataset row at line {line_number}") from exc
            if not isinstance(game_id, str) or not game_id:
                raise ValueError(f"Invalid game_id at line {line_number}")
            positions.append(Position(game_id, values, target_value))

    if not positions:
        raise ValueError(f"Dataset is empty: {dataset_path}")
    return positions


def _split_by_game(
    positions: list[Position],
    validation_fraction: float,
    seed: int,
) -> tuple[list[Position], list[Position]]:
    """Split positions without putting positions from one game in both sets."""
    game_ids = sorted({position.game_id for position in positions})
    if len(game_ids) < 2:
        raise ValueError("Dataset must contain at least two distinct game_id values")

    random.Random(seed).shuffle(game_ids)
    validation_count = max(1, round(len(game_ids) * validation_fraction))
    validation_count = min(validation_count, len(game_ids) - 1)
    validation_ids = set(game_ids[:validation_count])
    train_positions = [position for position in positions if position.game_id not in validation_ids]
    validation_positions = [
        position for position in positions if position.game_id in validation_ids
    ]
    return train_positions, validation_positions


def _normalization(
    positions: list[Position],
    enabled: bool,
) -> tuple[list[float], list[float]]:
    """Calculate feature means and scales using only training positions."""
    feature_count = len(FEATURE_NAMES)
    if not enabled:
        return [0.0] * feature_count, [1.0] * feature_count
    means = [
        sum(position.values[index] for position in positions) / len(positions)
        for index in range(feature_count)
    ]
    scales = []
    for index, mean in enumerate(means):
        variance = sum((position.values[index] - mean) ** 2 for position in positions) / len(
            positions
        )
        scales.append(variance**0.5 or 1.0)
    return means, scales


def _transform(values: tuple[float, ...], means: list[float], scales: list[float]) -> list[float]:
    """Apply saved feature normalization."""
    return [
        (value - mean) / scale for value, mean, scale in zip(values, means, scales, strict=True)
    ]


def _fit_regression(
    matrix: list[list[float]],
    targets: list[float],
    alpha: float,
) -> tuple[list[float], float]:
    """Fit linear or Ridge regression by solving its normal equations."""
    feature_count = len(FEATURE_NAMES)
    augmented = [[1.0, *row] for row in matrix]
    gram = [
        [sum(row[i] * row[j] for row in augmented) for j in range(feature_count + 1)]
        for i in range(feature_count + 1)
    ]
    rhs = [
        sum(row[i] * target for row, target in zip(augmented, targets, strict=True))
        for i in range(feature_count + 1)
    ]
    for index in range(1, feature_count + 1):
        gram[index][index] += alpha
    solution = _solve(gram, rhs)
    return solution[1:], solution[0]


def _solve(matrix: list[list[float]], vector: list[float]) -> list[float]:
    """Solve a positive-definite linear system with Gaussian elimination."""
    size = len(vector)
    augmented = [row[:] + [vector[index]] for index, row in enumerate(matrix)]
    for column in range(size):
        pivot = max(range(column, size), key=lambda row: abs(augmented[row][column]))
        if abs(augmented[pivot][column]) < 1e-12:
            raise ValueError("Regression features are singular; use Ridge with alpha > 0")
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        pivot_value = augmented[column][column]
        augmented[column] = [value / pivot_value for value in augmented[column]]
        for row in range(size):
            if row == column:
                continue
            factor = augmented[row][column]
            augmented[row] = [
                value - factor * pivot_value_value
                for value, pivot_value_value in zip(augmented[row], augmented[column], strict=True)
            ]
    return [row[-1] for row in augmented]


def _predict(values: list[float], coefficients: list[float], intercept: float) -> float:
    """Predict a target for normalized feature values."""
    return intercept + sum(
        coefficient * value for coefficient, value in zip(coefficients, values, strict=True)
    )


def _mean_squared_error(targets: list[float], predictions: list[float]) -> float:
    """Return mean squared error for validation predictions."""
    if not targets:
        raise ValueError("Validation split is empty")
    return sum(
        (target - prediction) ** 2 for target, prediction in zip(targets, predictions, strict=True)
    ) / len(targets)


def main() -> None:
    """Run regression training from the command line."""
    parser = argparse.ArgumentParser(description="Train the alpha-beta regression evaluator.")
    parser.add_argument("dataset_path", type=Path, help="Input positions.jsonl")
    parser.add_argument(
        "model_path",
        type=Path,
        nargs="?",
        default=Path("model.json"),
        help="Output model.json (default: model.json)",
    )
    parser.add_argument(
        "--weight-path",
        type=Path,
        default=Path(__file__).with_name("weight.json"),
        help="Runtime weights path (default: package weight.json)",
    )
    parser.add_argument("--model", choices=("ridge", "linear"), default="ridge")
    parser.add_argument("--alpha", type=float, default=1.0)
    parser.add_argument("--validation-fraction", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--no-standardize", action="store_true")
    args = parser.parse_args()
    result = train(
        args.dataset_path,
        args.model_path,
        weight_path=args.weight_path,
        model_type=args.model,
        alpha=args.alpha,
        validation_fraction=args.validation_fraction,
        seed=args.seed,
        standardize=not args.no_standardize,
    )
    print(f"Train games: {result.train_games}")
    print(f"Validation games: {result.validation_games}")
    print(f"Validation MSE: {result.validation_mse:.6f}")
    print(f"Wrote model to {args.model_path}")


if __name__ == "__main__":
    main()
