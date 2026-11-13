"""Evolvable genome: tapered piece-square tables plus structural weights.

The genome starts empty (every gene 0.0) so evolution has to discover the useful
knowledge instead of inheriting a hand-written evaluation. Piece values are
**not** part of the genome: they stay fixed in `PIECE_VALUES` because search uses
them for move ordering (MVV-LVA), delta pruning and promotions.

Piece-square tables are stored per rank and half-file:

    slot = rank * 4 + min(file, 7 - file)      # White's point of view, rank 0 = rank 1

so squares mirrored across the board share one gene and each piece keeps
8 ranks x 4 files = 32 genes per phase.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path

import chess

WEIGHTS_FILENAME = "weights.json"
CHECKPOINT_FILENAME = "evolution_checkpoint.json"
WEIGHTS_VERSION = 2

# Fixed material values used by search (MVV-LVA ordering, delta pruning) and as
# the material part of the evaluation. King scores 0.
PIECE_VALUES: dict[chess.PieceType, float] = {
    chess.PAWN: 1.0,
    chess.KNIGHT: 3.0,
    chess.BISHOP: 3.0,
    chess.ROOK: 5.0,
    chess.QUEEN: 9.0,
    chess.KING: 0.0,
}

PST_PIECES = ("pawn", "knight", "bishop", "rook", "queen", "king")
PST_PIECE_TYPES = (chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN, chess.KING)
PST_RANKS = 8
PST_HALF_FILES = 4
PST_SLOTS = PST_RANKS * PST_HALF_FILES
PST_TOTAL = len(PST_PIECES) * PST_SLOTS

STRUCTURE_FIELDS = (
    "center",
    "mobility",
    "shield",
    "doubled",
    "isolated",
    "passed",
    "bishop_pair",
    "rook_open",
    "tempo",
)

GENOME_SIZE = 2 * PST_TOTAL + len(STRUCTURE_FIELDS)

# Version 1 genomes were a flat list: pawn..queen then STRUCTURE_FIELDS.
LEGACY_FIELD_COUNT = 5 + len(STRUCTURE_FIELDS)

RANDOM_PST_SIGMA = 0.20
RANDOM_STRUCTURE_SIGMA = 0.10
PST_MUTATION_RATE = 0.05
PST_MUTATION_SCALE = 0.10
STRUCTURE_MUTATION_RATE = 0.25

PST_SLOT = tuple(
    chess.square_rank(square) * PST_HALF_FILES
    + min(chess.square_file(square), 7 - chess.square_file(square))
    for square in chess.SQUARES
)
PST_SLOT_MIRROR = tuple(PST_SLOT[chess.square_mirror(square)] for square in chess.SQUARES)


def _zero_rows() -> tuple[tuple[float, ...], ...]:
    """Return an all-zero 6 x 32 piece-square table."""
    return tuple((0.0,) * PST_SLOTS for _ in PST_PIECES)


def _reshape(flat: list[float]) -> tuple[tuple[float, ...], ...]:
    """Turn a flat 192-value PST block into 6 rows of 32 slots."""
    return tuple(
        tuple(flat[index * PST_SLOTS : (index + 1) * PST_SLOTS]) for index in range(len(PST_PIECES))
    )


def _rows_from_dict(raw: object) -> tuple[tuple[float, ...], ...]:
    """Read one 6 x 32 table from JSON; missing pieces become zero rows."""
    if raw is None:
        return _zero_rows()
    if not isinstance(raw, dict):
        raise ValueError("A piece-square table must be an object keyed by piece name")
    unknown = set(raw) - set(PST_PIECES)
    if unknown:
        raise ValueError(f"Unknown piece-square table keys: {sorted(unknown)}")
    rows = []
    for name in PST_PIECES:
        values = tuple(float(value) for value in raw.get(name, ()))
        if values and len(values) != PST_SLOTS:
            raise ValueError(f"Piece-square row {name!r} must hold {PST_SLOTS} values")
        rows.append(values or (0.0,) * PST_SLOTS)
    return tuple(rows)


@dataclass(frozen=True)
class Genome:
    """Evaluation genome in pawn units, White's point of view.

    `pst_mg` and `pst_eg` hold one 32-slot table per piece type for the midgame
    and the endgame; the evaluator blends them by game phase. The structural
    fields mirror the Benchmark 4 ideas as positive magnitudes (doubled and
    isolated pawn penalties are subtracted in the evaluator). Every default is
    0.0, which means "no knowledge yet". Frozen so bot instances can safely
    share a genome between games.
    """

    pst_mg: tuple[tuple[float, ...], ...] = field(default_factory=_zero_rows)
    pst_eg: tuple[tuple[float, ...], ...] = field(default_factory=_zero_rows)
    center: float = 0.0
    mobility: float = 0.0
    shield: float = 0.0
    doubled: float = 0.0
    isolated: float = 0.0
    passed: float = 0.0
    bishop_pair: float = 0.0
    rook_open: float = 0.0
    tempo: float = 0.0

    def __post_init__(self) -> None:
        for name in ("pst_mg", "pst_eg"):
            rows = tuple(tuple(float(value) for value in row) for row in getattr(self, name))
            if len(rows) != len(PST_PIECES) or any(len(row) != PST_SLOTS for row in rows):
                raise ValueError(f"{name} must be {len(PST_PIECES)} rows of {PST_SLOTS} values")
            object.__setattr__(self, name, rows)

    def pst_row(self, piece_type: chess.PieceType, endgame: bool = False) -> tuple[float, ...]:
        """Return the 32-slot table of `piece_type` for the midgame or endgame."""
        table = self.pst_eg if endgame else self.pst_mg
        return table[PST_PIECE_TYPES.index(piece_type)]

    def to_list(self) -> list[float]:
        """Flatten every gene: midgame tables, endgame tables, structure terms."""
        values = [value for table in (self.pst_mg, self.pst_eg) for row in table for value in row]
        values.extend(float(getattr(self, name)) for name in STRUCTURE_FIELDS)
        return values

    @classmethod
    def from_list(cls, values: list[float]) -> Genome:
        """Build a genome from `to_list` output, or migrate a legacy 14-value list."""
        flat = [float(value) for value in values]
        if len(flat) == LEGACY_FIELD_COUNT:
            return cls(**dict(zip(STRUCTURE_FIELDS, flat[5:], strict=True)))
        if len(flat) != GENOME_SIZE:
            raise ValueError(f"Expected {GENOME_SIZE} values, got {len(flat)}")
        structure = dict(zip(STRUCTURE_FIELDS, flat[2 * PST_TOTAL :], strict=True))
        return cls(
            pst_mg=_reshape(flat[:PST_TOTAL]),
            pst_eg=_reshape(flat[PST_TOTAL : 2 * PST_TOTAL]),
            **structure,
        )

    def to_dict(self) -> dict[str, object]:
        """Serialize to the versioned JSON structure written by evolution."""
        return {
            "version": WEIGHTS_VERSION,
            "pst_mg": {name: list(row) for name, row in zip(PST_PIECES, self.pst_mg, strict=True)},
            "pst_eg": {name: list(row) for name, row in zip(PST_PIECES, self.pst_eg, strict=True)},
            "structure": {name: float(getattr(self, name)) for name in STRUCTURE_FIELDS},
        }

    @classmethod
    def from_dict(cls, values: dict[str, object]) -> Genome:
        """Build a genome from a versioned dict; a legacy flat v1 dict is migrated."""
        if not {"pst_mg", "pst_eg", "structure"} & set(values):
            return cls._from_legacy(values)
        structure = values.get("structure") or {}
        if not isinstance(structure, dict):
            raise ValueError("Genome 'structure' must be an object")
        unknown = set(structure) - set(STRUCTURE_FIELDS)
        if unknown:
            raise ValueError(f"Unknown structure fields: {sorted(unknown)}")
        return cls(
            pst_mg=_rows_from_dict(values.get("pst_mg")),
            pst_eg=_rows_from_dict(values.get("pst_eg")),
            **{name: float(structure.get(name, 0.0)) for name in STRUCTURE_FIELDS},
        )

    @classmethod
    def _from_legacy(cls, values: dict[str, object]) -> Genome:
        """Migrate a v1 flat dict: piece values are dropped, structure terms carry over."""
        structure = {
            name: float(values[name])  # type: ignore[arg-type]
            for name in STRUCTURE_FIELDS
            if name in values
        }
        return cls(**structure)


DEFAULT_GENOME = Genome()


def random_genome(rng: random.Random) -> Genome:
    """Sample a genome around zero: gaussian table noise, small structural magnitudes."""
    tables = tuple(
        tuple(tuple(rng.gauss(0.0, RANDOM_PST_SIGMA) for _ in range(PST_SLOTS)) for _ in PST_PIECES)
        for _ in range(2)
    )
    structure = {name: abs(rng.gauss(0.0, RANDOM_STRUCTURE_SIGMA)) for name in STRUCTURE_FIELDS}
    return Genome(pst_mg=tables[0], pst_eg=tables[1], **structure)


def crossover(first: Genome, second: Genome, rng: random.Random) -> Genome:
    """Combine two genomes by picking each gene from either parent."""
    genes = first.to_list()
    other = second.to_list()
    return Genome.from_list(
        [left if rng.random() < 0.5 else right for left, right in zip(genes, other, strict=True)]
    )


def mutate(
    genome: Genome,
    rng: random.Random,
    rate: float = PST_MUTATION_RATE,
    scale: float = PST_MUTATION_SCALE,
) -> Genome:
    """Perturb table genes with probability `rate` and structural genes more often.

    Structural terms are penalty/bonus magnitudes, so they stay >= 0.
    """
    genes = genome.to_list()
    for index in range(2 * PST_TOTAL):
        if rng.random() < rate:
            genes[index] += rng.gauss(0.0, scale)
    for offset in range(len(STRUCTURE_FIELDS)):
        index = 2 * PST_TOTAL + offset
        if rng.random() < STRUCTURE_MUTATION_RATE:
            genes[index] = max(0.0, genes[index] + rng.gauss(0.0, scale))
    return Genome.from_list(genes)


def load_genome(path: Path) -> Genome:
    """Load a genome from JSON (versioned dict, legacy dict or flat list)."""
    try:
        raw = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"Cannot read weights file {path}: {exc}") from exc
    try:
        data = json.loads(raw)
    except ValueError as exc:
        raise ValueError(f"Invalid weights JSON in {path}: {exc}") from exc
    if isinstance(data, dict) and isinstance(data.get("genome"), (dict, list)):
        data = data["genome"]
    if isinstance(data, dict):
        return Genome.from_dict(data)
    if isinstance(data, list):
        return Genome.from_list([float(value) for value in data])
    raise ValueError(f"Unsupported weights format in {path}")


def _render(genome: Genome) -> str:
    """Render the versioned JSON with one 32-value table row per line."""
    lines = ["{", f'  "version": {WEIGHTS_VERSION},']
    for name in ("pst_mg", "pst_eg"):
        lines.append(f'  "{name}": {{')
        rows = getattr(genome, name)
        for index, piece in enumerate(PST_PIECES):
            comma = "," if index < len(PST_PIECES) - 1 else ""
            lines.append(f'    "{piece}": {json.dumps([float(v) for v in rows[index]])}{comma}')
        lines.append("  },")
    lines.append('  "structure": {')
    for index, field_name in enumerate(STRUCTURE_FIELDS):
        comma = "," if index < len(STRUCTURE_FIELDS) - 1 else ""
        value = json.dumps(float(getattr(genome, field_name)))
        lines.append(f'    "{field_name}": {value}{comma}')
    lines.append("  }")
    lines.append("}")
    return "\n".join(lines) + "\n"


def save_genome(genome: Genome, path: Path) -> Path:
    """Write a genome as versioned JSON (UTF-8, LF) to `path` and return the path."""
    target = Path(path)
    target.write_text(_render(genome), encoding="utf-8", newline="\n")
    return target
