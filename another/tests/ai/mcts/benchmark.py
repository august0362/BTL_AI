"""Paired-color evaluation through the existing registry and MatchRunner.

Run from the project root with backend/frontend/another on PYTHONPATH.
This is an experiment runner, not a probabilistic pass/fail unit test.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import random
import statistics
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

import chess

from ai.registry import create_bot
from tournament.match_runner import MatchRunner, generate_random_opening


def wilson_interval(successes: int, total: int) -> tuple[float, float]:
    """Return a descriptive 95% Wilson interval for the observed win fraction."""
    z = 1.959963984540054
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    radius = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return center - radius, center + radius


def play_game(task: dict) -> dict:
    """Run one legal game and retain enough information to audit its result."""
    index = task["index"]
    pair_seed = task["seed"] + index // 2
    opening = generate_random_opening(task["opening_plies"], random.Random(pair_seed))
    mcts_is_white = index % 2 == 0
    config = {
        "seed": pair_seed,
        "max_think_time_s": task["seconds"],
        "use_heuristics": not task["pure"],
        "claim_draw": True,
    }
    if task["simulations"] is not None:
        config["simulations"] = task["simulations"]
    mcts = create_bot("mcts", config)
    opponent = create_bot(
        task["opponent"], {"seed": pair_seed, "max_think_time_s": task["seconds"]}
    )
    white, black = (mcts, opponent) if mcts_is_white else (opponent, mcts)
    record = MatchRunner(
        white, black, opening_moves=opening, max_plies=task["max_plies"], claim_draw=True
    ).play()
    color = chess.WHITE if mcts_is_white else chess.BLACK
    own_moves = [
        move
        for i, move in enumerate(record.moves)
        if not move.is_random_opening and (i % 2 == 0) == mcts_is_white
    ]
    info = [move.search_info for move in own_moves]
    return {
        "game": index + 1,
        "pair": index // 2 + 1,
        "seed": pair_seed,
        "mcts_color": "white" if mcts_is_white else "black",
        "opening": opening,
        "plies": len(record.moves),
        "termination": record.result.termination.value,
        "error": record.error,
        "score": None if record.error else record.result.score_for(color),
        "move_times_s": [move.think_time_s for move in own_moves],
        "simulations": sum(item.get("simulations", 0) for item in info),
        "rollout_cutoffs": sum(item.get("rollout_cutoffs", 0) for item in info),
        "pgn": record.pgn,
    }


def main() -> None:
    """Save full JSON/PGN evidence and print progress after each completed game."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", type=int, default=100)
    parser.add_argument("--seconds", type=float, default=1.0)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--seed", type=int, default=20261015)
    parser.add_argument("--max-plies", type=int, default=150)
    parser.add_argument("--opening-plies", type=int, default=2)
    parser.add_argument(
        "--opponent", default="bench_random", choices=["bench_random", "bench_alphabeta3"]
    )
    parser.add_argument("--simulations", type=int)
    parser.add_argument("--pure", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.games < 2 or args.games % 2 or args.workers < 1 or args.seconds < 0:
        parser.error("games must be positive and even; workers >= 1; seconds >= 0")
    if args.seconds == 0 and args.simulations is None:
        parser.error("a simulation limit is required when seconds=0")
    if args.simulations is not None and args.simulations < 1:
        parser.error("simulations must be positive")
    args.output.mkdir(parents=True, exist_ok=True)
    source = Path(__file__).resolve().parents[4] / "backend" / "ai" / "mcts"
    hashes = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(source.glob("*.py"))
    }
    settings = vars(args) | {"output": str(args.output)}
    metadata = {
        "started_at": datetime.now(UTC).isoformat(),
        "settings": settings,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "chess": chess.__version__,
        "cpu_count": os.cpu_count(),
        "sha256": hashes,
    }
    started = time.perf_counter()
    results = []
    with (args.output / "games.jsonl").open("w", encoding="utf-8") as log:
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            futures = [pool.submit(play_game, settings | {"index": i}) for i in range(args.games)]
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
                log.write(json.dumps(result, ensure_ascii=False) + "\n")
                log.flush()
                wins = sum(row["score"] == 1 for row in results)
                draws = sum(row["score"] == 0.5 for row in results)
                losses = sum(row["score"] == 0 for row in results)
                errors = sum(row["error"] is not None for row in results)
                print(
                    f"{len(results)}/{args.games}: W/D/L={wins}/{draws}/{losses}; "
                    f"errors={errors}; elapsed={time.perf_counter() - started:.1f}s",
                    flush=True,
                )
    results.sort(key=lambda row: row["game"])
    times = sorted(t for row in results for t in row["move_times_s"])
    completed = [row for row in results if row["score"] is not None]
    wins = sum(row["score"] == 1 for row in completed)
    draws = sum(row["score"] == 0.5 for row in completed)
    losses = sum(row["score"] == 0 for row in completed)
    simulations = sum(row["simulations"] for row in completed)
    summary = metadata | {
        "games_completed": len(completed),
        "errors": len(results) - len(completed),
        "wins": wins,
        "draws": draws,
        "losses": losses,
        "win_rate": wins / len(completed) if completed else None,
        "score_rate": (wins + 0.5 * draws) / len(completed) if completed else None,
        "win_rate_wilson_95": wilson_interval(wins, len(completed)) if completed else None,
        "interval_note": "Descriptive only: paired games are not fully independent.",
        "target_70_percent_wins_met": len(completed) == args.games and wins / args.games >= 0.70,
        "mean_move_time_s": statistics.mean(times) if times else None,
        "p95_move_time_s": times[math.ceil(0.95 * len(times)) - 1] if times else None,
        "max_move_time_s": max(times) if times else None,
        "moves_above_budget": sum(t > args.seconds for t in times) if args.seconds else None,
        "simulations": simulations,
        "rollout_cutoff_ratio": sum(row["rollout_cutoffs"] for row in completed) / simulations
        if simulations
        else None,
        "wall_time_s": time.perf_counter() - started,
    }
    (args.output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (args.output / "games.pgn").write_text(
        "\n\n".join(row["pgn"] for row in results) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
