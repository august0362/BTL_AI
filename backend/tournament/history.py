"""Store and retrieve individual tournament game records."""

from __future__ import annotations

import json
from pathlib import Path

from tournament.records import GameRecord


class History:
    """Persist game records as individual JSON files in a directory."""

    def __init__(self, directory: Path, max_games: int = 20) -> None:
        self.directory = Path(directory)
        self.max_games = max_games
        self.directory.mkdir(parents=True, exist_ok=True)

    def save(self, record: GameRecord) -> Path:
        """Save a game record and prune records older than the retention limit."""
        path = self.directory / f"{record.game_id}.json"
        path.write_text(
            json.dumps(record.to_json(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        records = self.list()
        for old_record in records[self.max_games :]:
            (self.directory / f"{old_record.game_id}.json").unlink(missing_ok=True)
        return path

    def list(self) -> list[GameRecord]:
        """Return readable records newest first, skipping invalid files."""
        records: list[GameRecord] = []
        for path in self.directory.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                records.append(GameRecord.from_json(data))
            except (OSError, ValueError, TypeError, KeyError) as _exc:
                continue
        return sorted(
            records,
            key=lambda record: (record.started_at, record.game_id),
            reverse=True,
        )

    def load(self, game_id: str) -> GameRecord:
        """Load a record by game id."""
        data = json.loads((self.directory / f"{game_id}.json").read_text(encoding="utf-8"))
        return GameRecord.from_json(data)

    def export_pgn(self, game_id: str, dest: Path) -> Path:
        """Write a game's PGN to the destination path."""
        record = self.load(game_id)
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(record.pgn, encoding="utf-8")
        return dest
