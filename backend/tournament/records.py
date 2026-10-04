"""Serializable records for completed tournament games."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import chess

from core.types import GameResult, MoveRecord, Termination


@dataclass
class GameRecord:
    """Metadata and full move history for one game."""

    game_id: str
    started_at: str
    mode: str
    white_id: str
    black_id: str
    white_name: str
    black_name: str
    opening_moves: list[str]
    moves: list[MoveRecord]
    result: GameResult
    pgn: str = ""
    series_id: str | None = None
    series_game_index: int | None = None
    error: str | None = None

    def to_json(self) -> dict:
        """Return a JSON-compatible representation of this record."""
        winner = (
            "white"
            if self.result.winner == chess.WHITE
            else "black"
            if self.result.winner == chess.BLACK
            else None
        )
        return {
            "game_id": self.game_id,
            "started_at": self.started_at,
            "mode": self.mode,
            "white_id": self.white_id,
            "black_id": self.black_id,
            "white_name": self.white_name,
            "black_name": self.black_name,
            "opening_moves": list(self.opening_moves),
            "moves": [asdict(move) for move in self.moves],
            "result": {
                "winner": winner,
                "termination": self.result.termination.value,
            },
            "pgn": self.pgn,
            "series_id": self.series_id,
            "series_game_index": self.series_game_index,
            "error": self.error,
        }

    @classmethod
    def from_json(cls, d: dict) -> GameRecord:
        """Build a game record from its JSON-compatible representation."""
        winner = {"white": chess.WHITE, "black": chess.BLACK, None: None}[d["result"]["winner"]]
        result = GameResult(
            winner=winner,
            termination=Termination(d["result"]["termination"]),
        )
        return cls(
            game_id=d["game_id"],
            started_at=d["started_at"],
            mode=d["mode"],
            white_id=d["white_id"],
            black_id=d["black_id"],
            white_name=d["white_name"],
            black_name=d["black_name"],
            opening_moves=list(d["opening_moves"]),
            moves=[MoveRecord(**move) for move in d["moves"]],
            result=result,
            pgn=d.get("pgn", ""),
            series_id=d.get("series_id"),
            series_game_index=d.get("series_game_index"),
            error=d.get("error"),
        )
