"""Typed view of the ``[tournament]`` configuration table."""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_MATCHES_PER_PAIR = 20
DEFAULT_MAX_HISTORY = 10
DEFAULT_MAX_PLIES = 150
# 0 = không ép độ sâu: dùng cấu hình riêng của từng bot ([bots.<id>] hoặc mặc định của bot).
DEFAULT_DEPTH = 0
DEFAULT_RANDOM_OPENING_PLIES = 2
DEFAULT_SEED = -1
DEFAULT_MAX_THINK_TIME_S = 1.0


@dataclass(frozen=True)
class TournamentConfig:
    """Validated settings for one AI ranking round-robin."""

    bots: tuple[str, ...]
    matches_per_pair: int = DEFAULT_MATCHES_PER_PAIR
    max_history: int = DEFAULT_MAX_HISTORY
    max_plies: int = DEFAULT_MAX_PLIES
    depth: int = DEFAULT_DEPTH
    random_opening_plies: int = DEFAULT_RANDOM_OPENING_PLIES
    claim_draw: bool = True
    seed: int = DEFAULT_SEED
    max_think_time_s: float = DEFAULT_MAX_THINK_TIME_S
    measure_memory: bool = True  # run each bot in its own process; the OS measures its RAM
    eta_smoothing: float = 0.3  # alpha of the smoothed game times behind the time estimate

    @classmethod
    def from_config(cls, config: dict) -> TournamentConfig:
        """Build and validate the tournament settings from the loaded app config."""
        table = config.get("tournament")
        if not isinstance(table, dict):
            table = {}
        bots = table.get("bots")
        if isinstance(bots, list) and bots and all(isinstance(bot, str) for bot in bots):
            from ai import registry

            level = registry.benchmark_level(config)
            bot_ids = tuple(bot for bot in bots if registry.benchmark_allowed(bot, level))
        else:
            bot_ids = _default_bots(config)
        if len(bot_ids) < 2 or len(set(bot_ids)) != len(bot_ids):
            bot_ids = _default_bots(config)
        return cls(
            bots=bot_ids,
            matches_per_pair=max(
                1, _int_value(table, "matches_per_pair", DEFAULT_MATCHES_PER_PAIR)
            ),
            max_history=max(1, _int_value(table, "max_history", DEFAULT_MAX_HISTORY)),
            max_plies=max(1, _int_value(table, "max_plies", DEFAULT_MAX_PLIES)),
            depth=max(0, _int_value(table, "depth", DEFAULT_DEPTH)),
            random_opening_plies=max(
                0, _int_value(table, "random_opening_plies", DEFAULT_RANDOM_OPENING_PLIES)
            ),
            claim_draw=bool(table.get("claim_draw", True)),
            seed=_int_value(table, "seed", DEFAULT_SEED),
            max_think_time_s=max(
                0.0, _float_value(table, "max_think_time_s", DEFAULT_MAX_THINK_TIME_S)
            ),
            measure_memory=bool(table.get("measure_memory", True)),
            eta_smoothing=min(1.0, max(0.01, _float_value(table, "eta_smoothing", 0.3))),
        )

    def validate(self) -> None:
        """Raise ValueError when a setting cannot produce a valid tournament."""
        if len(self.bots) < 2:
            raise ValueError("tournament.bots cần ít nhất 2 bot")
        if len(set(self.bots)) != len(self.bots):
            raise ValueError("tournament.bots không được trùng nhau")
        if self.matches_per_pair < 1:
            raise ValueError("tournament.matches_per_pair phải >= 1")
        if self.max_history < 1:
            raise ValueError("tournament.max_history phải >= 1")
        if self.max_plies <= 0:
            raise ValueError("tournament.max_plies phải > 0")
        if self.depth < 0:
            raise ValueError("tournament.depth phải >= 0 (0 = không ép độ sâu)")
        if self.random_opening_plies < 0:
            raise ValueError("tournament.random_opening_plies phải >= 0")
        if self.max_think_time_s < 0:
            raise ValueError("tournament.max_think_time_s phải >= 0 (0 = không giới hạn)")


def _int_value(table: dict, key: str, default: int) -> int:
    value = table.get(key, default)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _float_value(table: dict, key: str, default: float) -> float:
    value = table.get(key, default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _default_bots(config: dict | None = None) -> tuple[str, ...]:
    from ai import registry

    return tuple(
        registry.list_bots(
            include_benchmarks=True, max_benchmark_level=registry.benchmark_level(config)
        )
    )
