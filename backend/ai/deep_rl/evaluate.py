"""Evaluate a policy against an opponent over alternating-color games."""

from __future__ import annotations

import argparse
import random
from dataclasses import dataclass
from pathlib import Path

import chess

from ai.deep_rl.opponents import GreedyCaptureOpponent, Opponent, RandomOpponent


@dataclass(frozen=True)
class EvalResult:
    """Aggregate evaluation results from the policy's perspective."""

    wins: int
    draws: int
    losses: int
    avg_plies: float


def evaluate(
    policy: object,
    opponent: Opponent,
    n_games: int,
    seed: int | None = None,
    max_plies: int = 300,
) -> EvalResult:
    """Play games with policy color alternating each game."""
    if n_games <= 0 or max_plies <= 0:
        raise ValueError("n_games and max_plies must be positive")
    rng = random.Random(seed)
    wins = draws = losses = total_plies = 0
    for game_index in range(n_games):
        policy_color = chess.WHITE if game_index % 2 == 0 else chess.BLACK
        board = chess.Board()
        plies = 0
        while board.outcome(claim_draw=True) is None and plies < max_plies:
            if board.turn == policy_color:
                move = policy.select_move(board.copy())
            else:
                move = opponent.select_move(board.copy(), rng)
            if move not in board.legal_moves:
                raise ValueError(f"player returned illegal move: {move}")
            board.push(move)
            plies += 1
        outcome = board.outcome(claim_draw=True)
        if outcome is None or outcome.winner is None:
            draws += 1
        elif outcome.winner == policy_color:
            wins += 1
        else:
            losses += 1
        total_plies += plies
    return EvalResult(wins, draws, losses, total_plies / n_games)


def main(argv: list[str] | None = None) -> int:
    """Run a command-line policy evaluation."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--weights", type=Path)
    parser.add_argument("--opponent", choices=("random", "greedy"), default="random")
    parser.add_argument("--games", type=int, default=50)
    args = parser.parse_args(argv)
    from ai.deep_rl.user.policy import load_policy

    policy = load_policy(args.weights)
    opponent = RandomOpponent() if args.opponent == "random" else GreedyCaptureOpponent()
    print(evaluate(policy, opponent, args.games))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
