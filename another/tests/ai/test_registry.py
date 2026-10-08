"""Đặc tả backend/ai/registry.py — documents/CONTEXT.md §4.2."""

import pytest

from tests._helpers import PROJECT_ROOT, require_module

registry = require_module("ai.registry")
base = require_module("ai.base_bot")

OFFICIAL = ["alphabeta_regression", "genetic_alphabeta", "mcts", "deep_rl"]
BENCHMARKS = [
    "bench_random",
    "bench_alphabeta_material",
    "bench_alphabeta3",
    "bench_alphabeta_tt",
    "bench_alphabeta_custom",
    "bench5_gpt",
    "bench5_gemini",
    "bench5_deepseek",
    "bench5_grok",
    "bench5_hybrid",
    "bench6_gpt",
    "bench6_gemini",
    "bench6_grok",
    "bench6_deepseek",
    "bench7",
    "bench8_luna",
]


def test_official_bots_in_order():
    assert list(registry.BOT_REGISTRY) == OFFICIAL
    assert registry.list_bots() == OFFICIAL


def test_debug_bots_hidden_by_default():
    assert "random" in registry.DEBUG_BOTS
    assert "random" not in registry.list_bots()
    assert registry.list_bots(include_debug=True) == OFFICIAL + ["random"]


def test_benchmark_bots_are_opt_in():
    assert list(registry.BENCHMARK_BOTS) == BENCHMARKS
    assert "bench_random" not in registry.list_bots(include_debug=True)
    assert registry.list_bots(include_benchmarks=True) == OFFICIAL + BENCHMARKS
    assert registry.list_bots(include_debug=True, include_benchmarks=True) == (
        OFFICIAL + ["random"] + BENCHMARKS
    )


def test_create_benchmark_bot():
    bot = registry.create_bot("bench_random", {"seed": 1})
    assert isinstance(bot, base.BaseBot)
    assert bot.bot_id == "bench_random"
    assert bot.config == {"seed": 1}


def test_paths_follow_convention():
    all_bots = {**registry.BOT_REGISTRY, **registry.DEBUG_BOTS, **registry.BENCHMARK_BOTS}
    for bot_id, path in all_bots.items():
        module, _, cls = path.partition(":")
        assert cls, f"{bot_id}: thiếu ':Class' trong {path!r}"
        assert module.startswith("ai.") and module.endswith(".bot"), path


def test_every_bot_package_is_registered():
    # Tạo thư mục bot mới trong backend/ai/ mà quên đăng ký => CI đỏ.
    packages = {p.parent.name for p in (PROJECT_ROOT / "backend" / "ai").glob("*/__init__.py")}
    all_bots = {**registry.BOT_REGISTRY, **registry.DEBUG_BOTS, **registry.BENCHMARK_BOTS}
    registered = {path.split(".")[1] for path in all_bots.values()}
    assert packages == registered


def test_create_random_bot():
    bot = registry.create_bot("random", {"seed": 1})
    assert isinstance(bot, base.BaseBot)
    assert bot.bot_id == "random"
    assert bot.config == {"seed": 1}


def test_unknown_bot_raises_value_error():
    with pytest.raises(ValueError):
        registry.create_bot("does_not_exist")


def test_benchmark_level_filters_generations():
    assert registry.benchmark_level({"benchmarks": {"max_level": 4}}) == 4.0
    assert registry.benchmark_level({}) is None
    assert registry.benchmark_level({"benchmarks": {"max_level": "x"}}) is None
    upto4 = registry.list_bots(include_benchmarks=True, max_benchmark_level=4)
    assert upto4 == OFFICIAL + BENCHMARKS[:5]
    upto5 = registry.list_bots(include_benchmarks=True, max_benchmark_level=5)
    assert upto5 == OFFICIAL + [
        b for b in BENCHMARKS if not b.startswith(("bench6", "bench7", "bench8"))
    ]
    assert registry.list_bots(include_benchmarks=True, max_benchmark_level=1) == OFFICIAL + [
        "bench_random"
    ]
    for bot_id in registry.BENCHMARK_BOTS:
        assert bot_id in registry.BENCHMARK_LEVELS
