"""Evolvable evaluation weights for the Genetic Alpha-Beta bot."""

from __future__ import annotations

import random
from dataclasses import asdict, dataclass
from pathlib import Path

import chess

WEIGHTS_FILENAME = "weights.json"

GENOME_FIELDS = (
    "pawn",
    "knight",
    "bishop",
    "rook",
    "queen",
    "center",
    "mobility",
    "shield",
)


@dataclass(frozen=True)
class Genome:
    """Weights of the static evaluation function (pawn units, White POV diffs).

    The first five fields are piece values. The last three scale positional
    terms: central control, move-count mobility and pawn shield around the king.
    Frozen so bot instances can safely share a genome between games.
    """

    pawn: float = 1.0
    knight: float = 3.0
    bishop: float = 3.0
    rook: float = 5.0
    queen: float = 9.0
    center: float = 0.12
    mobility: float = 0.02
    shield: float = 0.10

    def piece_value(self, piece_type: chess.PieceType) -> float:
        """Return the configured value of a piece type (king scores 0)."""
        if piece_type == chess.PAWN:
            return self.pawn
        if piece_type == chess.KNIGHT:
            return self.knight
        if piece_type == chess.BISHOP:
            return self.bishop
        if piece_type == chess.ROOK:
            return self.rook
        if piece_type == chess.QUEEN:
            return self.queen
        return 0.0

    def to_list(self) -> list[float]:
        """Serialize genome fields in GENOME_FIELDS order."""
        values = asdict(self)
        return [float(values[name]) for name in GENOME_FIELDS]

    @classmethod
    def from_list(cls, values: list[float]) -> Genome:
        """Build a genome from a GENOME_FIELDS-ordered value list."""
        if len(values) != len(GENOME_FIELDS):
            raise ValueError(f"Expected {len(GENOME_FIELDS)} values, got {len(values)}")
        return cls(**{name: float(v) for name, v in zip(GENOME_FIELDS, values, strict=True)})

    def to_dict(self) -> dict[str, float]:
        """Serialize genome fields to a plain dict."""
        return {name: float(getattr(self, name)) for name in GENOME_FIELDS}

    @classmethod
    def from_dict(cls, values: dict[str, float]) -> Genome:
        """Build a genome from a dict; missing fields fall back to defaults."""
        defaults = asdict(cls())
        unknown = set(values) - set(GENOME_FIELDS)
        if unknown:
            raise ValueError(f"Unknown genome fields: {sorted(unknown)}")
        merged = {name: float(values.get(name, defaults[name])) for name in GENOME_FIELDS}
        return cls(**merged)


DEFAULT_GENOME = Genome()


def random_genome(rng: random.Random) -> Genome:
    """Sample a genome by perturbing the defaults with the given generator."""

    def jitter(value: float, spread: float, minimum: float) -> float:
        return max(minimum, rng.uniform(value * (1.0 - spread), value * (1.0 + spread)))

    return Genome(
        pawn=jitter(1.0, 0.3, 0.1),
        knight=jitter(3.0, 0.3, 0.1),
        bishop=jitter(3.0, 0.3, 0.1),
        rook=jitter(5.0, 0.3, 0.1),
        queen=jitter(9.0, 0.3, 0.1),
        center=rng.uniform(0.0, 0.25),
        mobility=rng.uniform(0.0, 0.05),
        shield=rng.uniform(0.0, 0.25),
    )


def crossover(first: Genome, second: Genome, rng: random.Random) -> Genome:
    """Combine two genomes by picking each field from either parent."""
    picked = {
        name: getattr(first if rng.randrange(2) == 0 else second, name) for name in GENOME_FIELDS
    }
    return Genome(**picked)


def mutate(genome: Genome, rng: random.Random, rate: float = 0.3, scale: float = 0.2) -> Genome:
    """Perturb each field with probability `rate` using gaussian noise."""
    mutated = {}
    for name in GENOME_FIELDS:
        value = float(getattr(genome, name))
        if rng.random() < rate:
            value *= 1.0 + rng.gauss(0.0, scale)
        floor = 0.1 if name in ("pawn", "knight", "bishop", "rook", "queen") else 0.0
        mutated[name] = max(floor, value)
    return Genome(**mutated)


def load_genome(path: Path) -> Genome:
    """Load a genome from JSON (dict of fields or ordered list)."""
    try:
        raw = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"Cannot read weights file {path}: {exc}") from exc
    try:
        import json

        data = json.loads(raw)
    except ValueError as exc:
        raise ValueError(f"Invalid weights JSON in {path}: {exc}") from exc
    if isinstance(data, dict) and isinstance(data.get("genome"), (dict, list)):
        data = data["genome"]
    if isinstance(data, dict):
        return Genome.from_dict({k: float(v) for k, v in data.items()})
    if isinstance(data, list):
        return Genome.from_list([float(v) for v in data])
    raise ValueError(f"Unsupported weights format in {path}")


def save_genome(genome: Genome, path: Path) -> Path:
    """Write a genome as JSON dict to `path` and return the path."""
    import json

    target = Path(path)
    target.write_text(json.dumps(genome.to_dict(), indent=2) + "\n", encoding="utf-8")
    return target
