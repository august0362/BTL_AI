"""Offline genetic trainer for the evaluation genome.

Only run on demand (``python -m ai.genetic_alphabeta.evolution``); never imported
during games so bot startup stays instant.

Fitness games are self-play between genomes (this package never imports another
bot). Every genome of a generation faces the same opponents and the same paired
opening suite, so scores are comparable: each opening is played twice with the
colours swapped. A generation champion only replaces the incumbent when the
one-sided 95 % lower bound of its score edge is above zero.

Commands::

    python -m ai.genetic_alphabeta.evolution              # train, save weights.json
    python -m ai.genetic_alphabeta.evolution --resume     # continue from checkpoint
    python -m ai.genetic_alphabeta.evolution --verify     # evolved vs empty genome
"""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
from dataclasses import dataclass
from pathlib import Path

import chess

from ai.genetic_alphabeta.genome import (
    CHECKPOINT_FILENAME,
    DEFAULT_GENOME,
    WEIGHTS_FILENAME,
    WEIGHTS_VERSION,
    Genome,
    crossover,
    load_genome,
    mutate,
    random_genome,
    save_genome,
)
from ai.genetic_alphabeta.search import best_move

GAME_DEPTH = 2
OPENING_PLIES = 4
MAX_PLIES = 200
OPENINGS_PER_OPPONENT = 2
VALIDATION_OPENINGS = 20
CONFIDENCE_Z = 1.645
MIN_OPENINGS_FOR_BOUND = 2


def random_opening(rng: random.Random, plies: int = OPENING_PLIES) -> list[str]:
    """Return one random opening (UCI moves) that leaves a playable position."""
    while True:
        board = chess.Board()
        moves: list[str] = []
        for _ in range(plies):
            legal = sorted(board.legal_moves, key=lambda move: move.uci())
            if not legal:
                break
            move = rng.choice(legal)
            board.push(move)
            moves.append(move.uci())
        if not board.is_game_over():
            return moves


def opening_suite(rng: random.Random, count: int, plies: int = OPENING_PLIES) -> list[list[str]]:
    """Return `count` paired openings, avoiding duplicates when the pool allows."""
    suite: list[list[str]] = []
    seen: set[tuple[str, ...]] = set()
    for _ in range(max(1, count) * 100):
        if len(suite) >= count:
            break
        opening = random_opening(rng, plies)
        key = tuple(opening)
        if key not in seen:
            seen.add(key)
            suite.append(opening)
    while len(suite) < count:
        suite.append(random_opening(rng, plies))
    return suite


def play_game(
    white: Genome,
    black: Genome,
    opening: list[str],
    depth: int = GAME_DEPTH,
    max_plies: int = MAX_PLIES,
) -> float:
    """Play one game from a fixed opening; return the score from White's side."""
    board = chess.Board()
    for uci in opening:
        board.push(chess.Move.from_uci(uci))
    genomes = {chess.WHITE: white, chess.BLACK: black}
    while not board.is_game_over() and board.ply() < max_plies:
        if board.can_claim_draw():
            return 0.5
        move, _, _ = best_move(board, genomes[board.turn], depth)
        board.push(move)
    if board.is_game_over():
        result = board.result(claim_draw=True)
        if result == "1-0":
            return 1.0
        if result == "0-1":
            return 0.0
    return 0.5


@dataclass(frozen=True)
class MatchResult:
    """Score of one genome against one opponent over paired openings."""

    paired: tuple[float, ...]

    @property
    def openings(self) -> int:
        """Number of paired openings played."""
        return len(self.paired)

    @property
    def games(self) -> int:
        """Number of games (two per paired opening)."""
        return 2 * len(self.paired)

    @property
    def score(self) -> float:
        """Points per game in 0..1; 0.5 is an even match."""
        return statistics.fmean(self.paired) if self.paired else 0.5

    @property
    def lower_bound(self) -> float:
        """One-sided 95 % lower bound of (score - 0.5), paired by opening."""
        if len(self.paired) < MIN_OPENINGS_FOR_BOUND:
            return -math.inf
        spread = statistics.stdev(self.paired) / math.sqrt(len(self.paired))
        return self.score - 0.5 - CONFIDENCE_Z * spread


def _show_progress(label: str, done: int, total: int) -> None:
    """Print one updating progress line when a label is given."""
    if label:
        print(f"\r{label}: ván {done}/{total}", end="", flush=True)


def match(
    genome: Genome,
    opponent: Genome,
    openings: list[list[str]],
    depth: int = GAME_DEPTH,
    max_plies: int = MAX_PLIES,
    label: str = "",
) -> MatchResult:
    """Play every opening twice (colours swapped) against one opponent."""
    paired: list[float] = []
    total = 2 * len(openings)
    for done, opening in enumerate(openings, start=1):
        as_white = play_game(genome, opponent, opening, depth, max_plies)
        as_black = 1.0 - play_game(opponent, genome, opening, depth, max_plies)
        paired.append((as_white + as_black) / 2.0)
        _show_progress(label, 2 * done, total)
    if label:
        print()
    return MatchResult(tuple(paired))


def fitness(
    genome: Genome,
    opponents: list[Genome],
    openings: list[list[str]],
    depth: int = GAME_DEPTH,
    max_plies: int = MAX_PLIES,
    label: str = "",
) -> float:
    """Average score of `genome` against every opponent over the paired openings."""
    points = 0.0
    games = 0
    for index, opponent in enumerate(opponents, start=1):
        result = match(genome, opponent, openings, depth, max_plies, f"{label} vs đối thủ {index}")
        points += result.score * result.games
        games += result.games
    return points / games if games else 0.0


@dataclass(frozen=True)
class Checkpoint:
    """Best genome so far plus the generation that produced it."""

    generation: int
    best: Genome


def save_checkpoint(checkpoint: Checkpoint, path: Path) -> Path:
    """Write a resumable checkpoint (best genome + generation)."""
    target = Path(path)
    data = {
        "version": WEIGHTS_VERSION,
        "generation": checkpoint.generation,
        "best": checkpoint.best.to_dict(),
    }
    target.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8", newline="\n")
    return target


def load_checkpoint(path: Path) -> Checkpoint:
    """Read a checkpoint written by `save_checkpoint`."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return Checkpoint(generation=int(data["generation"]), best=Genome.from_dict(data["best"]))


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
    openings_per_opponent: int = OPENINGS_PER_OPPONENT,
    validation_openings: int = VALIDATION_OPENINGS,
    resume: bool = False,
    checkpoint_path: Path | None = None,
    max_plies: int = MAX_PLIES,
) -> Genome:
    """Run tournament selection + uniform crossover + mutation; return the champion.

    All genomes of a generation share the opponent list (empty genome plus the
    incumbent champion) and the paired-opening suite. The champion of the
    generation replaces the incumbent only when the one-sided 95 % lower bound
    of its edge over the incumbent clears zero on a fresh opening suite.
    """
    rng = random.Random(seed)
    checkpoint_file = checkpoint_path or Path(__file__).with_name(CHECKPOINT_FILENAME)
    best = DEFAULT_GENOME
    first_generation = 1
    if resume and checkpoint_file.is_file():
        checkpoint = load_checkpoint(checkpoint_file)
        best = checkpoint.best
        first_generation = checkpoint.generation + 1
        print(f"Tiếp tục từ thế hệ {checkpoint.generation} ({checkpoint_file})")
    population = [best, *(random_genome(rng) for _ in range(max(0, pop_size - 1)))]
    for generation in range(first_generation, generations + 1):
        openings = opening_suite(rng, openings_per_opponent)
        opponents = [DEFAULT_GENOME] if best == DEFAULT_GENOME else [DEFAULT_GENOME, best]
        scored = []
        for index, genome in enumerate(population, start=1):
            label = f"thế hệ {generation} · cá thể {index}/{len(population)}"
            scored.append((fitness(genome, opponents, openings, depth, max_plies, label), genome))
        scored.sort(key=lambda item: item[0], reverse=True)
        challenger = scored[0][1]
        validator = random.Random((seed or 0) * 1_000_003 + generation)
        validation = match(
            challenger,
            best,
            opening_suite(validator, validation_openings),
            depth,
            max_plies,
            f"thế hệ {generation} · kiểm định",
        )
        accepted = validation.lower_bound > 0.0
        if accepted:
            best = challenger
        print(
            f"thế hệ {generation}: luyện={scored[0][0]:.3f} "
            f"kiểm định={validation.score:.3f} "
            f"(cận dưới {validation.lower_bound:+.3f}) "
            f"{'nhận' if accepted else 'giữ'}"
        )
        save_checkpoint(Checkpoint(generation, best), checkpoint_file)
        next_pop = [genome for _, genome in scored[: max(2, elite)]]
        while len(next_pop) < pop_size:
            child = crossover(_pick_parent(scored, rng), _pick_parent(scored, rng), rng)
            next_pop.append(mutate(child, rng))
        population = next_pop
    return best


def verify(
    weights_path: Path,
    depth: int = GAME_DEPTH,
    paired_openings: int = VALIDATION_OPENINGS,
    seed: int | None = 0,
    max_plies: int = MAX_PLIES,
) -> MatchResult:
    """Play a saved genome against the empty genome and print the sanity check."""
    genome = load_genome(weights_path)
    openings = opening_suite(random.Random(seed), paired_openings)
    result = match(genome, DEFAULT_GENOME, openings, depth, max_plies, "kiểm tra vs genome 0")
    print(
        f"Genome đã tiến hóa vs genome 0: {result.score:.3f} "
        f"trên {result.games} ván (cận dưới {result.lower_bound:+.3f})"
    )
    return result


def main() -> None:
    """Evolve a genome and save the champion next to this file."""
    parser = argparse.ArgumentParser(description="Evolve Genetic Alpha-Beta weights.")
    parser.add_argument("--pop", type=int, default=12)
    parser.add_argument("--generations", type=int, default=6)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--depth", type=int, default=GAME_DEPTH)
    parser.add_argument(
        "--openings",
        type=int,
        default=OPENINGS_PER_OPPONENT,
        help="paired openings per opponent during training",
    )
    parser.add_argument(
        "--validation",
        type=int,
        default=VALIDATION_OPENINGS,
        help="paired openings of the acceptance match (40 games by default)",
    )
    parser.add_argument("--elite", type=int, default=2)
    parser.add_argument("--resume", action="store_true", help="continue from the checkpoint")
    parser.add_argument(
        "--verify",
        action="store_true",
        help="play weights.json against the empty genome and exit",
    )
    args = parser.parse_args()
    weights_file = Path(__file__).with_name(WEIGHTS_FILENAME)
    if args.verify:
        verify(weights_file, args.depth, args.validation, args.seed)
        return
    best = evolve(
        pop_size=args.pop,
        generations=args.generations,
        seed=args.seed,
        depth=args.depth,
        openings_per_opponent=args.openings,
        validation_openings=args.validation,
        elite=args.elite,
        resume=args.resume,
    )
    if best == DEFAULT_GENOME and weights_file.is_file():
        print("Không genome nào vượt kiểm định — giữ nguyên weights.json hiện tại")
        return
    path = save_genome(best, weights_file)
    print(f"Đã lưu genome vào {path}")


if __name__ == "__main__":
    main()
