"""Build a JSONL feature dataset from completed PGN games."""

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TextIO

import chess.pgn

from ai.alphabeta_regression.feature import extract_features


@dataclass
class DatasetStats:
    """Counts collected while building a position dataset."""

    valid_games: int = 0
    skipped_games: int = 0
    positions: int = 0


def build_dataset(input_dir: Path, output_path: Path) -> int:
    """Extract post-move features from completed PGN games.

    Return the number of positions written to ``output_path``.
    """
    if not input_dir.is_dir():
        raise NotADirectoryError(f"PGN input directory does not exist: {input_dir}")

    pgn_paths = sorted(input_dir.glob("*.pgn"))
    output_path.parent.mkdir(parents=True, exist_ok=True)

    stats = _build_dataset(output_path, pgn_paths)
    return stats.positions


def _build_dataset(
    output_path: Path,
    pgn_paths: list[Path],
) -> DatasetStats:
    """Write all valid games in an input directory and return its statistics."""
    stats = DatasetStats()
    with output_path.open("w", encoding="utf-8", newline="\n") as output_file:
        for pgn_path in pgn_paths:
            _write_file_dataset(pgn_path, output_file, stats)
    return stats


def _write_file_dataset(
    pgn_path: Path,
    output_file: TextIO,
    stats: DatasetStats,
) -> None:
    """Write valid games from one PGN file and update dataset statistics."""
    with pgn_path.open(encoding="utf-8") as pgn_file:
        game_index = 0
        while (game := chess.pgn.read_game(pgn_file)) is not None:
            game_id = f"{pgn_path.stem}:{game_index}"
            game_index += 1
            target = _result_target(game.headers.get("Result"))
            if target is None or game.errors:
                stats.skipped_games += 1
                continue

            stats.valid_games += 1
            board = game.board()
            for move in game.mainline_moves():
                board.push(move)
                row = {
                    "game_id": game_id,
                    "features": asdict(extract_features(board)),
                    "target": target,
                }
                output_file.write(json.dumps(row, separators=(",", ":")) + "\n")
                stats.positions += 1


def _result_target(result: str | None) -> int | None:
    """Convert a completed PGN result to a white-perspective regression target."""
    return {"1-0": 1, "1/2-1/2": 0, "0-1": -1}.get(result)


def main() -> None:
    """Run the PGN-to-JSONL dataset generator from the command line."""
    parser = argparse.ArgumentParser(
        description="Extract alpha-beta regression features from completed PGN games."
    )
    parser.add_argument("input_dir", type=Path, help="Directory containing .pgn files")
    parser.add_argument("output_path", type=Path, help="Destination JSONL file")
    args = parser.parse_args()
    if not args.input_dir.is_dir():
        raise NotADirectoryError(f"PGN input directory does not exist: {args.input_dir}")
    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    stats = _build_dataset(args.output_path, sorted(args.input_dir.glob("*.pgn")))

    print(f"Valid games: {stats.valid_games}")
    print(f"Skipped games: {stats.skipped_games}")
    print(f"Extracted positions: {stats.positions}")
    print(f"Wrote dataset to {args.output_path}")


if __name__ == "__main__":
    main()
