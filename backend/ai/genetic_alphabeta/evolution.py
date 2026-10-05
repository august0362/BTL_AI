"""Offline genetic trainer for the evaluation weights.

Only run on demand (``python -m ai.genetic_alphabeta.evolution``); never imported
during games so bot startup stays instant.
"""

from __future__ import annotations

import argparse
import random
from pathlib import Path

import chess

from ai.genetic_alphabeta.genome import (
    DEFAULT_GENOME,
    WEIGHTS_FILENAME,
    Genome,
    crossover,
    mutate,
    random_genome,
    save_genome,
)
from ai.genetic_alphabeta.search import best_move

GAME_DEPTH = 1
OPENING_PLIES = 4
MAX_PLIES = 200


def random_opening(board: chess.Board, rng: random.Random, plies: int) -> None:
    """Push a few random legal moves to diversify training games."""
    for _ in range(plies):
        moves = sorted(board.legal_moves, key=lambda move: move.uci())
        if not moves:
            break
        board.push(rng.choice(moves))


def play_game(
    white: Genome,
    black: Genome,
    rng: random.Random,
    depth: int = GAME_DEPTH,
    max_plies: int = MAX_PLIES,
) -> float:
    """Play one quick game; return the score from White's perspective."""
    board = chess.Board()
    random_opening(board, rng, OPENING_PLIES)
    genomes = {chess.WHITE: white, chess.BLACK: black}
    while not board.is_game_over() and board.ply() < max_plies:
        if board.can_claim_draw():
            return 0.5
        move, _, _ = best_move(board, genomes[board.turn], depth)
        board.push(move)
    result = board.result(claim_draw=True)
    if result == "1-0":
        return 1.0
    if result == "0-1":
        return 0.0
    return 0.5


def fitness(
    genome: Genome,
    opponents: list[Genome],
    rng: random.Random,
    games_per_pair: int = 2,
    depth: int = GAME_DEPTH,
) -> float:
    """Average score of `genome` against each opponent, alternating colors."""
    total = 0.0
    games = 0
    for opponent in opponents:
        for game_index in range(games_per_pair):
            if game_index % 2 == 0:
                total += play_game(genome, opponent, rng, depth)
            else:
                total += 1.0 - play_game(opponent, genome, rng, depth)
            games += 1
    return total / games if games else 0.0


def _pick_parent(scored: list[tuple[float, Genome]], rng: random.Random) -> Genome:
    """Tournament-pick one parent genome from scored (fitness, genome) pairs."""
    contenders = rng.sample(scored, min(3, len(scored)))
    return max(contenders, key=lambda item: item[0])[1]


def evolve(
    pop_size: int = 12,
    generations: int = 6,
    elite: int = 2,
    seed: int | None = None,
    depth: int = GAME_DEPTH,
) -> Genome:
    """Run tournament selection + uniform crossover + mutation; return best."""
    rng = random.Random(seed)
    population = [random_genome(rng) for _ in range(pop_size)]
    best = DEFAULT_GENOME
    for _ in range(generations):
        scored = []
        for genome in population:
            opponents = [DEFAULT_GENOME, best, rng.choice(population)]
            scored.append((fitness(genome, opponents, rng, depth=depth), genome))
        scored.sort(key=lambda item: item[0], reverse=True)
        challenger = scored[0][1]
        if fitness(challenger, [best], rng, depth=depth) >= 0.5:
            best = challenger

        next_pop = [genome for _, genome in scored[: max(2, elite)]]
        while len(next_pop) < pop_size:
            next_pop.append(
                mutate(crossover(_pick_parent(scored, rng), _pick_parent(scored, rng), rng), rng)
            )
        population = next_pop
    return best


def main() -> None:
    """Evolve weights and save the winner next to this file."""
    parser = argparse.ArgumentParser(description="Evolve Genetic Alpha-Beta weights.")
    parser.add_argument("--pop", type=int, default=12)
    parser.add_argument("--generations", type=int, default=6)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    best = evolve(pop_size=args.pop, generations=args.generations, seed=args.seed)
    path = save_genome(best, Path(__file__).with_name(WEIGHTS_FILENAME))
    print(f"Saved {best.to_dict()} to {path}")


if __name__ == "__main__":
    main()
