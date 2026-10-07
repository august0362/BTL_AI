"""Persist finished AI ranking tournaments as numbered battles."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import replace
from pathlib import Path

from tournament.round_robin import TournamentResult

BATTLE_PREFIX = "battle_"


class TournamentHistory:
    """Store battle results as JSON files and keep only the newest runs."""

    def __init__(self, directory: Path, max_runs: int = 10) -> None:
        if max_runs < 1:
            raise ValueError("max_runs must be >= 1")
        self.directory = Path(directory)
        self.max_runs = max_runs
        self.directory.mkdir(parents=True, exist_ok=True)

    def path_for(self, battle: int) -> Path:
        """Return the file path of one battle."""
        return self.directory / f"{BATTLE_PREFIX}{battle:04d}.json"

    def next_index(self) -> int:
        """Return the next battle number, continuing after pruned runs."""
        indices = [result.battle for result in self.list() if result.battle is not None]
        return max(indices, default=0) + 1

    def save(self, result: TournamentResult) -> TournamentResult:
        """Stamp a result with its battle number, persist it and prune old runs."""
        stamped = replace(result, battle=self.next_index())
        assert stamped.battle is not None
        path = self.path_for(stamped.battle)
        handle, temporary_name = tempfile.mkstemp(dir=self.directory, suffix=".tmp")
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as file:
                json.dump(stamped.to_json(), file, ensure_ascii=False, indent=2)
            os.replace(temporary_path, path)
        finally:
            temporary_path.unlink(missing_ok=True)
        self._prune()
        return stamped

    def list(self) -> list[TournamentResult]:
        """Return readable battles newest first, skipping invalid files."""
        results: list[TournamentResult] = []
        for path in self.directory.glob(f"{BATTLE_PREFIX}*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                results.append(TournamentResult.from_json(data))
            except (OSError, ValueError, TypeError, KeyError) as _exc:
                continue
        return sorted(results, key=lambda result: result.battle or 0, reverse=True)

    def load(self, battle: int) -> TournamentResult:
        """Load one battle by its number."""
        data = json.loads(self.path_for(battle).read_text(encoding="utf-8"))
        return TournamentResult.from_json(data)

    def clear(self) -> None:
        """Delete every stored battle."""
        for path in self.directory.glob(f"{BATTLE_PREFIX}*.json"):
            path.unlink(missing_ok=True)

    def _prune(self) -> None:
        for result in self.list()[self.max_runs :]:
            if result.battle is not None:
                self.path_for(result.battle).unlink(missing_ok=True)
