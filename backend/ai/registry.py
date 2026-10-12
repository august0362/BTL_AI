"""Registry and lazy loader for tournament bots."""

import importlib

from ai.base_bot import BaseBot, BotUnavailableError

BOT_REGISTRY: dict[str, str] = {
    "alphabeta_regression": "ai.alphabeta_regression.bot:AlphaBetaRegressionBot",
    "genetic_alphabeta": "ai.genetic_alphabeta.bot:GeneticAlphaBetaBot",
    "mcts": "ai.mcts.bot:MctsBot",
    "deep_rl": "ai.deep_rl.bot:DeepRLBot",
}
DEBUG_BOTS: dict[str, str] = {"random": "ai.random_bot.bot:RandomBot"}
BASELINE_BOTS: dict[str, str] = {"baseline": "ai.random_bot.bot:BaselineBot"}
BENCHMARK_BOTS: dict[str, str] = {
    "bench_random": "ai.benchmarks.bot:BenchmarkRandomBot",
    "bench_alphabeta_material": "ai.benchmarks.bot:BenchmarkMaterialBot",
    "bench_alphabeta3": "ai.benchmarks.bot:BenchmarkAlphaBetaBot",
    "bench_alphabeta_tt": "ai.benchmarks.bot:BenchmarkAlphaBetaTTBot",
    "bench_alphabeta_custom": "ai.benchmarks.bot:BenchmarkAlphaBetaCustomBot",
    # Each later generation is its own package, plugged in only here.
    "bench5_gpt": "ai.benchmarks_extension.bench5.bot:Benchmark5GptBot",
    "bench5_deepseek": "ai.benchmarks_extension.bench5.bot:Benchmark5DeepSeekBot",
    "bench5_hybrid": "ai.benchmarks_extension.bench5.bot:Benchmark5HybridBot",
    "bench6_gpt": "ai.benchmarks_extension.bench6.bot:Benchmark6GptBot",
    "bench6_gemini": "ai.benchmarks_extension.bench6.bot:Benchmark6GeminiBot",
    "bench6_deepseek": "ai.benchmarks_extension.bench6.bot:Benchmark6DeepSeekBot",
    "bench7": "ai.benchmarks_extension.bench7.bot:Benchmark7Bot",
    "bench8_luna": "ai.benchmarks_extension.bench8.bot:Benchmark8LunaBot",
    "bench_super_alphabeta_nnue": "ai.benchmarks_extension.bench9.bot:SuperAlphaBetaNNUEBot",
}
# Benchmark generation of every benchmark bot; ``[benchmarks] max_level`` hides higher ones.
BENCHMARK_LEVELS: dict[str, float] = {
    "bench_random": 1,
    "bench_alphabeta_material": 1.5,
    "bench_alphabeta3": 2,
    "bench_alphabeta_tt": 3,
    "bench_alphabeta_custom": 4,
    "bench5_gpt": 5,
    "bench5_deepseek": 5,
    "bench5_hybrid": 5,
    "bench6_gpt": 6,
    "bench6_gemini": 6,
    "bench6_deepseek": 6,
    "bench7": 7,
    "bench8_luna": 8,
    "bench_super_alphabeta_nnue": 9,
}


def benchmark_level(config: dict | None) -> float | None:
    """Read ``[benchmarks] max_level`` (None = no limit; invalid values = no limit)."""
    table = (config or {}).get("benchmarks", {})
    value = table.get("max_level") if isinstance(table, dict) else None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def benchmark_allowed(bot_id: str, max_level: float | None) -> bool:
    """True unless ``bot_id`` is a benchmark above ``max_level``."""
    level = BENCHMARK_LEVELS.get(bot_id)
    return level is None or max_level is None or level <= max_level


def config_bots(config: dict | None) -> list[str]:
    """Bots declared only in config (``[bots.<id>] class = "module:Class"``), unless disabled.

    Lets an owner add a bot in ``local.toml`` (e.g. a second Deep RL weights file) without code;
    ``enabled = false`` hides it again.
    """
    tables = (config or {}).get("bots", {})
    if not isinstance(tables, dict):
        return []
    known = set(BOT_REGISTRY) | set(DEBUG_BOTS) | set(BASELINE_BOTS) | set(BENCHMARK_BOTS)
    return [
        bot_id
        for bot_id, table in tables.items()
        if bot_id not in known
        and isinstance(table, dict)
        and isinstance(table.get("class"), str)
        and ":" in table["class"]
        and table.get("enabled") is not False
    ]


def list_bots(
    include_debug: bool = False,
    include_baseline: bool = False,
    include_benchmarks: bool = False,
    max_benchmark_level: float | None = None,
    config: dict | None = None,
) -> list[str]:
    """Return bot ids in display order: official bots, ``config`` bots, then the rest
    (benchmarks up to ``max_benchmark_level``)."""
    bot_ids = list(BOT_REGISTRY)
    bot_ids.extend(config_bots(config))
    if include_debug:
        bot_ids.extend(DEBUG_BOTS)
    if include_baseline:
        bot_ids.extend(BASELINE_BOTS)
    if include_benchmarks:
        bot_ids.extend(
            bot_id for bot_id in BENCHMARK_BOTS if benchmark_allowed(bot_id, max_benchmark_level)
        )
    return bot_ids


def create_bot(bot_id: str, config: dict | None = None) -> BaseBot:
    """Load and initialize a registered or config-declared bot."""
    bot_path = (
        BOT_REGISTRY.get(bot_id)
        or DEBUG_BOTS.get(bot_id)
        or BASELINE_BOTS.get(bot_id)
        or BENCHMARK_BOTS.get(bot_id)
    )
    if bot_path is None:
        class_path = (config or {}).get("class")
        if isinstance(class_path, str) and ":" in class_path:
            bot_path = class_path
    if bot_path is None:
        raise ValueError(f"Unknown bot id: {bot_id}")

    module_name, _, class_name = bot_path.partition(":")
    try:
        bot_class = getattr(importlib.import_module(module_name), class_name)
    except (ImportError, AttributeError) as exc:
        raise BotUnavailableError(f"Could not load bot {bot_id!r}: {exc}") from exc

    bot = bot_class(config)
    bot.bot_id = bot_id
    return bot
