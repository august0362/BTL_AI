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
    "bench_alphabeta3": "ai.benchmarks.bot:BenchmarkAlphaBetaBot",
    "bench_alphabeta_tt": "ai.benchmarks.bot:BenchmarkAlphaBetaTTBot",
    "bench_alphabeta_custom": "ai.benchmarks.bot:BenchmarkAlphaBetaCustomBot",
}


def list_bots(
    include_debug: bool = False,
    include_baseline: bool = False,
    include_benchmarks: bool = False,
) -> list[str]:
    """Return registered bot ids in display order."""
    bot_ids = list(BOT_REGISTRY)
    if include_debug:
        bot_ids.extend(DEBUG_BOTS)
    if include_baseline:
        bot_ids.extend(BASELINE_BOTS)
    if include_benchmarks:
        bot_ids.extend(BENCHMARK_BOTS)
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
