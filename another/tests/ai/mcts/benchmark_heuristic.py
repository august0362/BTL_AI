"""Paired-color matches against the unchanged Benchmark 2, with complete PGN evidence."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import random
import statistics
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from ai.registry import create_bot
from tournament.match_runner import MatchRunner, generate_random_opening
from tournament.process_player import ProcessPlayer


def play(task: dict) -> dict:
    """Give both colors the same seeded opening, budgets and opponent configuration."""
    seed = task["seed"] + task["index"] // 2
    hero_white = task["index"] % 2 == 0
    hero_config = {"seed": seed, "max_think_time_s": task["seconds"], **task["config"]}
    hero_id = "mcts"
    if task["hero_class"]:
        hero_id = "mcts_reference"
        hero_config["class"] = task["hero_class"]
    enemy_config = {"seed": seed, "max_think_time_s": task["seconds"]}
    factory = ProcessPlayer if task["memory"] else create_bot
    hero, enemy = factory(hero_id, hero_config), factory(task["opponent"], enemy_config)
    opening = generate_random_opening(2, random.Random(seed))
    try:
        game = MatchRunner(
            hero if hero_white else enemy,
            enemy if hero_white else hero,
            opening_moves=opening,
            max_plies=150,
            claim_draw=True,
        ).play()
    finally:
        if task["memory"]:
            hero.close()
            enemy.close()
    own = [
        m
        for i, m in enumerate(game.moves)
        if not m.is_random_opening and (i % 2 == 0) == hero_white
    ]
    theirs = [
        m
        for i, m in enumerate(game.moves)
        if not m.is_random_opening and (i % 2 == 0) != hero_white
    ]
    return {
        "game": task["index"] + 1,
        "seed": seed,
        "hero_color": "white" if hero_white else "black",
        "opening": opening,
        "score": None if game.error else game.result.score_for(hero_white),
        "termination": game.result.termination.value,
        "error": game.error,
        "plies": len(game.moves),
        "hero_times": [m.think_time_s for m in own],
        "enemy_times": [m.think_time_s for m in theirs],
        "hero_peak_mb": hero.memory_bytes / 1024**2 if task["memory"] else None,
        "enemy_peak_mb": enemy.memory_bytes / 1024**2 if task["memory"] else None,
        "simulations": sum(m.search_info.get("simulations", 0) for m in own),
        "leaf_nodes": sum(m.search_info.get("leaf_nodes", 0) for m in own),
        "enemy_depths": sorted({m.search_info.get("depth", 0) for m in theirs}),
        "pgn": game.pgn,
    }


def main() -> None:
    """Save every completed game before producing aggregate statistics."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", type=int, default=20)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--seconds", type=float, default=1)
    parser.add_argument("--seed", type=int, default=20261113)
    parser.add_argument("--opponent", default="bench_alphabeta3")
    parser.add_argument("--hero-class", default="")
    parser.add_argument("--config", type=json.loads, default={})
    parser.add_argument("--memory", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.games < 2 or args.games % 2 or args.workers < 1 or args.seconds <= 0:
        parser.error("even games >= 2, workers >= 1 and seconds > 0 are required")
    spec = importlib.util.find_spec(args.hero_class.partition(":")[0] or "ai.mcts.bot")
    assert spec is not None and spec.origin is not None
    source = Path(spec.origin).parent
    source_hashes = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in source.glob("*.py")
    }
    opponent_source = Path(__file__).resolve().parents[4] / "backend/ai/benchmarks"
    opponent_hashes = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in opponent_source.glob("*.py")
    }
    settings = vars(args) | {"output": str(args.output)}
    args.output.mkdir(parents=True, exist_ok=True)
    rows = []
    started = time.perf_counter()
    with (args.output / "games.jsonl").open("w", encoding="utf-8") as log:
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            futures = [pool.submit(play, settings | {"index": i}) for i in range(args.games)]
            for f in as_completed(futures):
                row = f.result()
                rows.append(row)
                log.write(json.dumps(row) + "\n")
                log.flush()
                counts = [sum(r["score"] == score for r in rows) for score in (1, 0.5, 0)]
                print(
                    f"{len(rows)}/{args.games} W/D/L={counts}; "
                    f"elapsed={time.perf_counter() - started:.1f}s",
                    flush=True,
                )
    times = [t for r in rows for t in r["hero_times"]]
    summary = {
        "settings": settings,
        "source_sha256": source_hashes,
        "opponent_source_sha256": opponent_hashes,
        "wins": sum(r["score"] == 1 for r in rows),
        "draws": sum(r["score"] == 0.5 for r in rows),
        "losses": sum(r["score"] == 0 for r in rows),
        "errors": sum(r["score"] is None for r in rows),
        "mean_move_s": statistics.mean(times) if times else 0,
        "max_move_s": max(times, default=0),
        "total_think_s": sum(times),
        "moves_over_budget": sum(t > args.seconds for t in times),
        "mean_peak_mb": statistics.mean(r["hero_peak_mb"] for r in rows) if args.memory else None,
        "mean_enemy_peak_mb": statistics.mean(r["enemy_peak_mb"] for r in rows)
        if args.memory
        else None,
        "wall_s": time.perf_counter() - started,
    }
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (args.output / "games.pgn").write_text(
        "\n\n".join(r["pgn"] for r in sorted(rows, key=lambda r: r["game"])) + "\n"
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
