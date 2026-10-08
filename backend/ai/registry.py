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
    "bench5_gpt": "ai.bench5.bot:Benchmark5GptBot",
    "bench5_gemini": "ai.bench5.bot:Benchmark5GeminiBot",
    "bench5_deepseek": "ai.bench5.bot:Benchmark5DeepSeekBot",
    "bench5_grok": "ai.bench5.bot:Benchmark5GrokBot",
    "bench5_hybrid": "ai.bench5.bot:Benchmark5HybridBot",
    "bench6_gpt": "ai.bench6.bot:Benchmark6GptBot",
    "bench6_gemini": "ai.bench6.bot:Benchmark6GeminiBot",
    "bench6_grok": "ai.bench6.bot:Benchmark6GrokBot",
    "bench6_deepseek": "ai.bench6.bot:Benchmark6DeepSeekBot",
    "bench7": "ai.bench7.bot:Benchmark7Bot",
    "bench8_luna": "ai.bench8.bot:Benchmark8LunaBot",
}
# Benchmark generation of every benchmark bot; ``[benchmarks] max_level`` hides higher ones.
BENCHMARK_LEVELS: dict[str, float] = {
    "bench_random": 1,
    "bench_alphabeta_material": 1.5,
    "bench_alphabeta3": 2,
    "bench_alphabeta_tt": 3,
    "bench_alphabeta_custom": 4,
    "bench5_gpt": 5,
    "bench5_gemini": 5,
    "bench5_deepseek": 5,
    "bench5_grok": 5,
    "bench5_hybrid": 5,
    "bench6_gpt": 6,
    "bench6_gemini": 6,
    "bench6_grok": 6,
    "bench6_deepseek": 6,
    "bench7": 7,
    "bench8_luna": 8,
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


def list_bots(
    include_debug: bool = False,
    include_baseline: bool = False,
    include_benchmarks: bool = False,
    max_benchmark_level: float | None = None,
) -> list[str]:
    """Return registered bot ids in display order (benchmarks up to ``max_benchmark_level``)."""
    bot_ids = list(BOT_REGISTRY)
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
    """Load and initialize a registered bot."""
    bot_path = (
        BOT_REGISTRY.get(bot_id)
        or DEBUG_BOTS.get(bot_id)
        or BASELINE_BOTS.get(bot_id)
        or BENCHMARK_BOTS.get(bot_id)
    )
    if bot_path is None:
        raise ValueError(f"Unknown bot id: {bot_id}")

    module_name, _, class_name = bot_path.partition(":")
    try:
        bot_class = getattr(importlib.import_module(module_name), class_name)
    except (ImportError, AttributeError) as exc:
        raise BotUnavailableError(f"Could not load bot {bot_id!r}: {exc}") from exc

    return bot_class(config)
