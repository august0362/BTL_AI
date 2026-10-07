"""Full round-robin tournament between registered bots."""

from __future__ import annotations

import random
import threading
import time
import uuid
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from itertools import combinations

import chess

from core.types import Termination
from tournament.match_runner import MatchRunner
from tournament.records import GameRecord

POINTS_WIN = 1.0
POINTS_DRAW = 0.5

ProgressCallback = Callable[[int, int, tuple[str, str] | None], None]
PlyCallback = Callable[[int], None]


@dataclass
class Matchup:
    """Head-to-head totals for one unordered pair of bots."""

    bot_a: str
    bot_b: str
    games: int = 0
    wins_a: int = 0
    wins_b: int = 0
    draws: int = 0
    score_a: float = 0.0
    score_b: float = 0.0

    def add(self, winner: chess.Color | None, a_is_white: bool) -> None:
        """Record one finished game from bot A's perspective."""
        self.games += 1
        if winner is None:
            self.draws += 1
            self.score_a += POINTS_DRAW
            self.score_b += POINTS_DRAW
        elif (winner == chess.WHITE) == a_is_white:
            self.wins_a += 1
            self.score_a += POINTS_WIN
        else:
            self.wins_b += 1
            self.score_b += POINTS_WIN

    @property
    def key(self) -> tuple[str, str]:
        """Return the unordered pair identity."""
        return (self.bot_a, self.bot_b)

    def to_json(self) -> dict:
        """Return a JSON-compatible representation."""
        return {
            "bot_a": self.bot_a,
            "bot_b": self.bot_b,
            "games": self.games,
            "wins_a": self.wins_a,
            "wins_b": self.wins_b,
            "draws": self.draws,
            "score_a": self.score_a,
            "score_b": self.score_b,
        }

    @classmethod
    def from_json(cls, data: dict) -> Matchup:
        """Rebuild a matchup from its JSON representation."""
        return cls(
            bot_a=data["bot_a"],
            bot_b=data["bot_b"],
            games=int(data["games"]),
            wins_a=int(data["wins_a"]),
            wins_b=int(data["wins_b"]),
            draws=int(data["draws"]),
            score_a=float(data["score_a"]),
            score_b=float(data["score_b"]),
        )


@dataclass(frozen=True)
class StandingRow:
    """One row of the final (or live) tournament table."""

    bot_id: str
    rank: int
    points: float
    games: int
    wins: int
    draws: int
    losses: int
    think_time_s: float
    score_pct: float

    def to_json(self) -> dict:
        """Return a JSON-compatible representation."""
        return {
            "bot_id": self.bot_id,
            "rank": self.rank,
            "points": self.points,
            "games": self.games,
            "wins": self.wins,
            "draws": self.draws,
            "losses": self.losses,
            "think_time_s": self.think_time_s,
            "score_pct": self.score_pct,
        }

    @classmethod
    def from_json(cls, data: dict) -> StandingRow:
        """Rebuild a standing row from its JSON representation."""
        return cls(
            bot_id=data["bot_id"],
            rank=int(data["rank"]),
            points=float(data["points"]),
            games=int(data["games"]),
            wins=int(data["wins"]),
            draws=int(data["draws"]),
            losses=int(data["losses"]),
            think_time_s=float(data["think_time_s"]),
            score_pct=float(data["score_pct"]),
        )


@dataclass
class TournamentResult:
    """A complete round-robin run: standings plus head-to-head breakdowns."""

    tournament_id: str
    created_at: str
    participants: tuple[str, ...]
    matches_per_pair: int
    completed: bool
    games_played: int
    games_total: int
    standings: tuple[StandingRow, ...]
    matchups: tuple[Matchup, ...]
    battle: int | None = None
    errors: tuple[str, ...] = field(default_factory=tuple)

    @property
    def title_key(self) -> str:
        """Return the translation key of the battle title."""
        return "tournament.battle"

    def to_json(self) -> dict:
        """Return a JSON-compatible representation."""
        return {
            "version": 1,
            "battle": self.battle,
            "tournament_id": self.tournament_id,
            "created_at": self.created_at,
            "participants": list(self.participants),
            "matches_per_pair": self.matches_per_pair,
            "completed": self.completed,
            "games_played": self.games_played,
            "games_total": self.games_total,
            "standings": [row.to_json() for row in self.standings],
            "matchups": [matchup.to_json() for matchup in self.matchups],
        }

    @classmethod
    def from_json(cls, data: dict) -> TournamentResult:
        """Rebuild a tournament result from its JSON representation."""
        if data.get("version") != 1:
            raise ValueError("unsupported tournament data")
        battle = data.get("battle")
        return cls(
            tournament_id=data["tournament_id"],
            created_at=data["created_at"],
            participants=tuple(data["participants"]),
            matches_per_pair=int(data["matches_per_pair"]),
            completed=bool(data["completed"]),
            games_played=int(data["games_played"]),
            games_total=int(data["games_total"]),
            standings=tuple(StandingRow.from_json(row) for row in data["standings"]),
            matchups=tuple(Matchup.from_json(item) for item in data["matchups"]),
            battle=None if battle is None else int(battle),
        )


def compute_standings(
    participants: Sequence[str],
    matchups: Iterable[Matchup],
    think_times: Mapping[str, float] | None = None,
) -> tuple[StandingRow, ...]:
    """Rank bots by points, breaking ties with the lower total thinking time."""
    wins = {bot_id: 0 for bot_id in participants}
    draws = {bot_id: 0 for bot_id in participants}
    losses = {bot_id: 0 for bot_id in participants}
    games = {bot_id: 0 for bot_id in participants}
    points = {bot_id: 0.0 for bot_id in participants}

    for matchup in matchups:
        for bot_id, own_wins, own_losses, own_draws, score in (
            (matchup.bot_a, matchup.wins_a, matchup.wins_b, matchup.draws, matchup.score_a),
            (matchup.bot_b, matchup.wins_b, matchup.wins_a, matchup.draws, matchup.score_b),
        ):
            if bot_id not in points:
                continue
            wins[bot_id] += own_wins
            losses[bot_id] += own_losses
            draws[bot_id] += own_draws
            games[bot_id] += own_wins + own_losses + own_draws
            points[bot_id] += score

    times = dict(think_times or {})

    def strength(bot_id: str) -> tuple[float, float]:
        """Smaller is better: more points first, then less total thinking time."""
        return (-points[bot_id], times.get(bot_id, 0.0))

    ordered = sorted(participants, key=lambda bot_id: (strength(bot_id), bot_id))

    rows: list[StandingRow] = []
    for bot_id in ordered:
        rank = 1 + sum(
            1
            for other_id in participants
            if other_id != bot_id and strength(other_id) < strength(bot_id)
        )
        played = games[bot_id]
        rows.append(
            StandingRow(
                bot_id=bot_id,
                rank=rank,
                points=points[bot_id],
                games=played,
                wins=wins[bot_id],
                draws=draws[bot_id],
                losses=losses[bot_id],
                think_time_s=times.get(bot_id, 0.0),
                score_pct=(points[bot_id] / played) if played else 0.0,
            )
        )
    return tuple(rows)


class RoundRobinRunner:
    """Play every unordered pair of bots, balancing colors as evenly as possible."""

    def __init__(
        self,
        participant_ids: Sequence[str],
        *,
        matches_per_pair: int = 20,
        max_plies: int = 150,
        claim_draw: bool = True,
        random_opening_plies: int = 2,
        depth: int | None = None,
        max_think_time_s: float | None = None,
        eval_scale: float = 8.0,
        bot_configs: Mapping[str, Mapping[str, object]] | None = None,
        seed: int | None = None,
        on_progress: ProgressCallback | None = None,
        on_ply: PlyCallback | None = None,
        on_game_end: Callable[[GameRecord], None] | None = None,
        clock: Callable[[], float] = time.perf_counter,
        create_bot: Callable[..., object] | None = None,
    ) -> None:
        participants = tuple(participant_ids)
        if len(participants) < 2:
            raise ValueError("round robin needs at least two participants")
        if len(set(participants)) != len(participants):
            raise ValueError("participants must be unique")
        if matches_per_pair < 1:
            raise ValueError("matches_per_pair must be >= 1")
        self.participants = participants
        self.matches_per_pair = matches_per_pair
        self.max_plies = max_plies
        self.claim_draw = claim_draw
        self.random_opening_plies = random_opening_plies
        self.depth = depth
        self.max_think_time_s = max_think_time_s
        self.eval_scale = eval_scale
        self.pairs: tuple[tuple[str, str], ...] = tuple(combinations(participants, 2))
        self.games_total = len(self.pairs) * matches_per_pair
        self._bot_configs = {key: dict(value) for key, value in (bot_configs or {}).items()}
        self._rng = random.Random(seed)
        self._on_progress = on_progress
        self._on_ply = on_ply
        self._on_game_end = on_game_end
        self._clock = clock
        self._create_bot = create_bot or _registry_create_bot
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._current_runner: MatchRunner | None = None
        self._current_pair: tuple[str, str] | None = None
        self._played = 0
        self._matchups: dict[tuple[str, str], Matchup] = {
            pair: Matchup(pair[0], pair[1]) for pair in self.pairs
        }
        self._think: dict[str, float] = {bot_id: 0.0 for bot_id in participants}
        self._errors: list[str] = []

    @property
    def played(self) -> int:
        """Return the number of games finished so far."""
        with self._lock:
            return self._played

    @property
    def current_pair(self) -> tuple[str, str] | None:
        """Return the pairing currently being played, if any."""
        with self._lock:
            return self._current_pair

    @property
    def errors(self) -> tuple[str, ...]:
        """Return messages collected from aborted games."""
        with self._lock:
            return tuple(self._errors)

    def standings(self) -> tuple[StandingRow, ...]:
        """Return live standings computed from the games finished so far."""
        with self._lock:
            return compute_standings(
                self.participants, list(self._matchups.values()), dict(self._think)
            )

    def request_stop(self) -> None:
        """Stop after the current game, aborting a game already in progress."""
        self._stop.set()
        with self._lock:
            runner = self._current_runner
        if runner is not None:
            runner.request_stop()

    def play(self) -> TournamentResult:
        """Play the whole schedule and return the final standings."""
        created_at = datetime.now(UTC).isoformat()
        completed = True
        for pair_index, pair in enumerate(self.pairs):
            if self._stop.is_set():
                completed = False
                break
            for a_is_white in self._colors(pair_index):
                if self._stop.is_set():
                    completed = False
                    break
                with self._lock:
                    self._current_pair = pair
                self._play_game(pair, a_is_white)
                with self._lock:
                    self._played += 1
                if self._on_progress is not None:
                    self._on_progress(self.played, self.games_total, pair)
            if not completed:
                break
        with self._lock:
            self._current_pair = None
            matchups = tuple(self._matchups.values())
            played = self._played
            standings = compute_standings(self.participants, matchups, dict(self._think))
            errors = tuple(self._errors)
        return TournamentResult(
            tournament_id=uuid.uuid4().hex,
            created_at=created_at,
            participants=self.participants,
            matches_per_pair=self.matches_per_pair,
            completed=completed,
            games_played=played,
            games_total=self.games_total,
            standings=standings,
            matchups=matchups,
            errors=errors,
        )

    def _colors(self, pair_index: int) -> list[bool]:
        """Return whether bot A has White in each game of the pair."""
        colors = [True, False] * (self.matches_per_pair // 2)
        if self.matches_per_pair % 2:
            colors.append(pair_index % 2 == 0)
        return colors

    def _bot_config(self, bot_id: str) -> dict:
        config = dict(self._bot_configs.get(bot_id, {}))
        if self.depth:
            config["depth"] = self.depth
        if self.max_think_time_s is not None:
            config["max_think_time_s"] = self.max_think_time_s
        return config

    def _handle_move(self, _record: object, state: object) -> None:
        """Forward the in-game half-move count so the GUI can show live progress."""
        if self._on_ply is not None:
            self._on_ply(int(getattr(state, "ply_count", 0)))

    def _play_game(self, pair: tuple[str, str], a_is_white: bool) -> None:
        bot_a, bot_b = pair
        white_id, black_id = (bot_a, bot_b) if a_is_white else (bot_b, bot_a)
        try:
            white = self._create_bot(white_id, self._bot_config(white_id))
            black = self._create_bot(black_id, self._bot_config(black_id))
        except Exception as exc:  # noqa: BLE001 - one broken bot must not stop the tournament
            with self._lock:
                self._errors.append(f"{white_id} vs {black_id}: {exc}")
            return
        runner = MatchRunner(
            white,
            black,
            mode="bot_vs_bot",
            random_opening_plies=self.random_opening_plies,
            max_plies=self.max_plies,
            claim_draw=self.claim_draw,
            eval_scale=self.eval_scale,
            rng=self._rng,
            on_move=self._handle_move if self._on_ply is not None else None,
        )
        with self._lock:
            self._current_runner = runner
            if self._stop.is_set():
                runner.request_stop()
        record = runner.play()
        with self._lock:
            self._current_runner = None
            if record.result.termination is not Termination.ABORTED:
                self._matchups[pair].add(record.result.winner, a_is_white)
                self._add_think_time(record)
            elif record.error:
                self._errors.append(record.error)
        if self._on_game_end is not None:
            self._on_game_end(record)

    def _add_think_time(self, record: GameRecord) -> None:
        """Add each side's measured thinking time to its tournament total."""
        for move in record.moves:
            if move.is_random_opening:
                continue
            bot_id = record.white_id if move.ply % 2 == 1 else record.black_id
            self._think[bot_id] = self._think.get(bot_id, 0.0) + move.think_time_s


def _registry_create_bot(bot_id: str, config: dict | None = None):
    from ai import registry

    return registry.create_bot(bot_id, config)
