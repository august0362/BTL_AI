"""Spec for the Genetic Alpha-Beta genome, evaluator, search and trainer."""

from __future__ import annotations

import io
import json
import math
import random
import sys
from pathlib import Path

import chess
import pytest

from ai import genetic_alphabeta
from ai.base_bot import BotUnavailableError
from ai.genetic_alphabeta import bot as bot_module
from ai.genetic_alphabeta import evolution
from ai.genetic_alphabeta.evaluation import evaluate, game_phase
from ai.genetic_alphabeta.genome import (
    DEFAULT_GENOME,
    GENOME_SIZE,
    PIECE_VALUES,
    PST_PIECES,
    PST_SLOTS,
    STRUCTURE_FIELDS,
    WEIGHTS_FILENAME,
    WEIGHTS_VERSION,
    Genome,
    crossover,
    load_genome,
    mutate,
    random_genome,
    save_genome,
)
from ai.genetic_alphabeta.search import best_move, ordered_moves

WEIGHTS_PATH = Path(genetic_alphabeta.__file__).with_name(WEIGHTS_FILENAME)
KQK_FEN = "k7/8/8/8/4K3/8/8/3Q4 w - - 0 1"


def genome_with(piece: str, slot: int, value: float, *, endgame: bool = False) -> Genome:
    """Return a genome whose only non-zero gene is one table slot."""
    rows = [[0.0] * PST_SLOTS for _ in PST_PIECES]
    rows[PST_PIECES.index(piece)][slot] = value
    tables = tuple(tuple(row) for row in rows)
    return Genome(pst_eg=tables) if endgame else Genome(pst_mg=tables)


def test_genome_defaults_are_empty() -> None:
    """Every gene starts at 0: evolution must discover all knowledge itself."""
    assert DEFAULT_GENOME.to_list() == [0.0] * GENOME_SIZE
    assert len(DEFAULT_GENOME.pst_mg) == len(PST_PIECES)
    assert all(len(row) == PST_SLOTS for row in DEFAULT_GENOME.pst_eg)


def test_piece_values_are_fixed_and_outside_the_genome() -> None:
    """Search ordering keeps classical values; the genome cannot mutate them."""
    assert PIECE_VALUES[chess.PAWN] == 1.0
    assert PIECE_VALUES[chess.KNIGHT] == 3.0
    assert PIECE_VALUES[chess.BISHOP] == 3.0
    assert PIECE_VALUES[chess.ROOK] == 5.0
    assert PIECE_VALUES[chess.QUEEN] == 9.0
    assert PIECE_VALUES[chess.KING] == 0.0
    assert not hasattr(DEFAULT_GENOME, "piece_value")
    assert not hasattr(DEFAULT_GENOME, "pawn")


def test_genome_roundtrip_through_lists_and_dicts() -> None:
    """to_list/from_list and to_dict/from_dict preserve every gene."""
    genome = random_genome(random.Random(7))
    assert Genome.from_list(genome.to_list()) == genome
    assert Genome.from_dict(genome.to_dict()) == genome


def test_genome_saves_and_loads_versioned_json(tmp_path: Path) -> None:
    """The written file is version 2 and reloads identically."""
    genome = random_genome(random.Random(11))
    path = save_genome(genome, tmp_path / WEIGHTS_FILENAME)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["version"] == WEIGHTS_VERSION
    assert set(data["pst_mg"]) == set(PST_PIECES)
    assert load_genome(path) == genome


def test_legacy_flat_genome_is_migrated() -> None:
    """Version 1 weights keep their structural terms and drop piece values."""
    legacy = {
        "pawn": 1.4,
        "knight": 2.4,
        "bishop": 2.9,
        "rook": 3.5,
        "queen": 8.8,
        "center": 0.02,
        "mobility": 0.03,
        "shield": 0.07,
        "doubled": 0.27,
        "isolated": 0.25,
        "passed": 0.23,
        "bishop_pair": 0.42,
        "rook_open": 0.11,
        "tempo": 0.04,
    }
    genome = Genome.from_dict(legacy)
    assert genome.to_list()[: 2 * len(PST_PIECES) * PST_SLOTS] == [0.0] * (
        2 * len(PST_PIECES) * PST_SLOTS
    )
    assert genome.bishop_pair == pytest.approx(0.42)
    assert genome.tempo == pytest.approx(0.04)
    flat = [1.0, 3.0, 3.0, 5.0, 9.0, 0.02, 0.03, 0.07, 0.27, 0.25, 0.23, 0.42, 0.11, 0.04]
    assert Genome.from_list(flat) == genome


def test_shipped_weights_use_the_current_version() -> None:
    """The committed weights file is a v2 genome that the bot can load."""
    data = json.loads(WEIGHTS_PATH.read_text(encoding="utf-8"))
    assert data["version"] == WEIGHTS_VERSION
    assert set(data["pst_eg"]) == set(PST_PIECES)
    assert load_genome(WEIGHTS_PATH) == load_genome(WEIGHTS_PATH)


def test_game_phase_runs_from_opening_to_endgame() -> None:
    """Phase is 1.0 with full material and shrinks with the pieces."""
    assert game_phase(chess.Board()) == 1.0
    phase = game_phase(chess.Board(KQK_FEN))
    assert 0.0 < phase < 1.0
    assert game_phase(chess.Board("8/8/8/4k3/8/8/8/4K3 w - - 0 1")) == 0.0


def test_material_comes_from_fixed_values_only() -> None:
    """An empty genome still scores material as 1/3/3/5/9."""
    assert evaluate(chess.Board(KQK_FEN), DEFAULT_GENOME) == pytest.approx(9.0)
    assert evaluate(chess.Board(), DEFAULT_GENOME) == 0.0


def test_piece_square_tables_are_colour_symmetric() -> None:
    """Mirrored knights read the same gene, so their bonuses cancel out."""
    genome = genome_with("knight", 2 * 4 + 2, 0.5)  # c3 / c6
    board = chess.Board("r1bqkb1r/pppppppp/2n5/8/8/2N5/PPPPPPPP/R1BQKB1R w KQkq - 0 1")
    assert evaluate(board, genome) == pytest.approx(0.0)
    assert evaluate(chess.Board(KQK_FEN), genome) == pytest.approx(9.0)


def test_evaluation_tapers_between_midgame_and_endgame_tables() -> None:
    """An endgame-only table earns nothing while phase is 1.0 and pays in KQK."""
    genome = genome_with("king", 3 * 4 + 3, 0.6, endgame=True)  # e4 slot
    assert evaluate(chess.Board(), genome) == 0.0
    assert evaluate(chess.Board(KQK_FEN), genome) == pytest.approx(9.0 + 0.6 * (1 - 4 / 24))


def test_move_ordering_ignores_the_genome() -> None:
    """Capture ordering uses fixed values: the queen capture comes first."""
    board = chess.Board("4k3/8/8/3p1q2/4Q3/8/8/4K3 w - - 0 1")
    moves = [move.uci() for move in ordered_moves(board)]
    assert moves.index("e4f5") < moves.index("e4d5")


def test_genome_mutation_keeps_penalties_non_negative() -> None:
    """Structural genes are magnitudes, so mutation never makes them negative."""
    rng = random.Random(5)
    genome = DEFAULT_GENOME
    for _ in range(20):
        genome = mutate(genome, rng, rate=1.0, scale=1.0)
        assert all(getattr(genome, name) >= 0.0 for name in STRUCTURE_FIELDS)
    child = crossover(DEFAULT_GENOME, random_genome(rng), rng)
    assert len(child.to_list()) == GENOME_SIZE


def test_search_returns_a_legal_move_on_an_empty_genome() -> None:
    """The zero genome still searches material and returns a legal move."""
    board = chess.Board()
    move, nodes, _ = best_move(board, DEFAULT_GENOME, 1)
    assert move in board.legal_moves
    assert nodes > 0


def test_match_lower_bound_uses_paired_openings() -> None:
    """The acceptance bound is computed from per-opening scores."""
    even = evolution.MatchResult((0.5, 0.5, 0.5, 0.5))
    assert even.games == 8
    assert even.score == pytest.approx(0.5)
    assert even.lower_bound == pytest.approx(0.0)
    assert evolution.MatchResult((0.0, 0.5, 0.5, 1.0)).lower_bound < 0.0
    winning = evolution.MatchResult((1.0, 1.0, 1.0, 1.0))
    assert winning.lower_bound > 0.0
    assert evolution.MatchResult((1.0,)).lower_bound == -math.inf


def test_opening_suite_returns_distinct_playable_openings() -> None:
    """Openings are unique, replayable UCI lists."""
    rng = random.Random(2)
    suite = evolution.opening_suite(rng, 5)
    assert len(suite) == 5
    assert len({tuple(opening) for opening in suite}) == 5
    for opening in suite:
        board = chess.Board()
        for uci in opening:
            board.push(chess.Move.from_uci(uci))
        assert not board.is_game_over()


def test_paired_match_plays_both_colours() -> None:
    """Each opening is played twice, once per colour."""
    openings = evolution.opening_suite(random.Random(1), 1)
    result = evolution.match(DEFAULT_GENOME, DEFAULT_GENOME, openings, depth=1, max_plies=6)
    assert result.openings == 1
    assert result.games == 2
    assert 0.0 <= result.score <= 1.0


def test_evolve_writes_a_resumable_checkpoint(tmp_path: Path) -> None:
    """A tiny run returns a genome and stores the best one per generation."""
    checkpoint = tmp_path / "checkpoint.json"
    best = evolution.evolve(
        pop_size=2,
        generations=1,
        elite=2,
        seed=3,
        depth=1,
        openings_per_opponent=1,
        validation_openings=2,
        checkpoint_path=checkpoint,
        max_plies=6,
    )
    assert isinstance(best, Genome)
    saved = evolution.load_checkpoint(checkpoint)
    assert saved.generation == 1
    assert saved.best == best


def test_bot_refuses_to_start_without_weights(monkeypatch: pytest.MonkeyPatch) -> None:
    """A missing weights file means evolution has not run: do not play."""
    monkeypatch.setattr(bot_module, "WEIGHTS_FILENAME", "missing_weights.json")
    with pytest.raises(BotUnavailableError):
        bot_module.GeneticAlphaBetaBot({"fast_mode": True, "seed": 0})


def test_bot_allows_an_empty_genome_for_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    """`allow_random_init` keeps the contract test runnable without the file."""
    monkeypatch.setattr(bot_module, "WEIGHTS_FILENAME", "missing_weights.json")
    bot = bot_module.GeneticAlphaBetaBot({"fast_mode": True, "allow_random_init": True, "seed": 0})
    assert bot.select_move(chess.Board()) in chess.Board().legal_moves


def test_evolve_starts_from_the_incumbent_genome() -> None:
    """A fresh run seeds the population from the saved genome instead of zero."""
    incumbent = random_genome(random.Random(3))
    assert evolution.evolve(generations=0, incumbent=incumbent) == incumbent


def test_evolve_saves_an_accepted_champion_before_the_run_ends(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An accepted generation lands on the weights file immediately, not only at the end."""
    weights = tmp_path / WEIGHTS_FILENAME
    incumbent = random_genome(random.Random(4))
    file_exists_when_ranking: list[bool] = []

    def fake_fitness(*args: object, **kwargs: object) -> float:
        file_exists_when_ranking.append(weights.is_file())
        return 0.0

    monkeypatch.setattr(evolution, "fitness", fake_fitness)
    monkeypatch.setattr(
        evolution, "match", lambda *args, **kwargs: evolution.MatchResult((1.0, 1.0))
    )
    best = evolution.evolve(
        pop_size=2,
        generations=2,
        seed=1,
        checkpoint_path=tmp_path / "checkpoint.json",
        incumbent=incumbent,
        weights_path=weights,
    )
    assert weights.is_file()
    assert load_genome(weights) == best
    assert file_exists_when_ranking[0] is False
    assert file_exists_when_ranking[-1] is True


def test_evolve_never_truncates_weights_without_an_accepted_champion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A run that accepts nothing leaves the saved weights byte-identical."""
    weights = save_genome(random_genome(random.Random(6)), tmp_path / WEIGHTS_FILENAME)
    sentinel = load_genome(weights)
    monkeypatch.setattr(
        evolution, "match", lambda *args, **kwargs: evolution.MatchResult((0.0, 0.0))
    )
    best = evolution.evolve(
        pop_size=2,
        generations=1,
        seed=2,
        checkpoint_path=tmp_path / "checkpoint.json",
        incumbent=sentinel,
        weights_path=weights,
    )
    assert best == sentinel
    assert load_genome(weights) == sentinel


def test_load_saved_genome_ignores_missing_and_broken_files(tmp_path: Path) -> None:
    """A missing or corrupt weights file falls back to training from scratch."""
    assert evolution._load_saved_genome(tmp_path / "absent.json") is None
    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    assert evolution._load_saved_genome(broken) is None
    good = save_genome(random_genome(random.Random(8)), tmp_path / WEIGHTS_FILENAME)
    assert evolution._load_saved_genome(good) == load_genome(good)


def test_safe_print_survives_a_legacy_console_encoding(monkeypatch: pytest.MonkeyPatch) -> None:
    """Vietnamese progress labels must not crash when stdout uses a legacy code page."""
    buffer = io.BytesIO()
    stream = io.TextIOWrapper(buffer, encoding="cp1252", newline="")
    monkeypatch.setattr(sys, "stdout", stream)
    evolution._safe_print("thế hệ 1")
    evolution._safe_print("hết", end="")
    stream.flush()
    assert buffer.getvalue() == b"th? h? 1\nh?t"


def test_main_trains_on_the_saved_genome_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The CLI feeds weights.json back into training instead of restarting from zero."""
    saved = save_genome(random_genome(random.Random(12)), tmp_path / WEIGHTS_FILENAME)
    current = load_genome(saved)
    captured: dict[str, object] = {}

    def fake_evolve(**kwargs: object) -> Genome:
        captured.update(kwargs)
        return current

    monkeypatch.setattr(evolution, "__file__", str(tmp_path / "evolution.py"))
    monkeypatch.setattr(evolution, "evolve", fake_evolve)
    monkeypatch.setattr(sys, "argv", ["evolution"])
    evolution.main()
    assert captured["incumbent"] == current
    assert captured["weights_path"] == saved
    assert captured["seed"] is None
    assert load_genome(saved) == current


def test_main_does_not_downgrade_weights_after_a_stale_resume(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A resume that wins nothing must not overwrite newer weights with the checkpoint."""
    saved = save_genome(random_genome(random.Random(21)), tmp_path / WEIGHTS_FILENAME)
    current = load_genome(saved)

    def fake_evolve(**kwargs: object) -> Genome:
        return random_genome(random.Random(22))

    monkeypatch.setattr(evolution, "__file__", str(tmp_path / "evolution.py"))
    monkeypatch.setattr(evolution, "evolve", fake_evolve)
    monkeypatch.setattr(sys, "argv", ["evolution", "--resume"])
    evolution.main()
    assert load_genome(saved) == current
