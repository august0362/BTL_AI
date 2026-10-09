"""Benchmark 8 "Luna" profile: Dragon's settings plus the Luna switches kept by matches."""

from __future__ import annotations

from dataclasses import dataclass

from ai.benchmarks_extension.bench8.evaluation import EvalConfig8, MopUp8
from ai.benchmarks_extension.bench8.search import (
    Lmr8,
    NullMove8,
    Quiescence8,
    SearchConfig8,
    TimeConfig8,
)

TOURNAMENT_PLY_LIMIT = 150  # the AI ranking draws a game after 150 plies


@dataclass(frozen=True)
class Profile8:
    """A named search plus evaluation configuration."""

    name: str
    search: SearchConfig8
    evaluation: EvalConfig8


def luna_draws(root_eval: int) -> tuple[int, int]:
    """Dragon's small contempt: a draw costs 10/20 cp when ahead, is worth 10/20 when behind."""
    if root_eval >= 200:
        value = -20
    elif root_eval >= 60:
        value = -10
    elif root_eval <= -200:
        value = 20
    elif root_eval <= -60:
        value = 10
    else:
        value = 0
    return value, value


LUNA = Profile8(
    name="luna",
    search=SearchConfig8(
        time=TimeConfig8(soft=0.6, hard=0.95, policy="stability", early=0.5, late=0.92),
        aspiration=(25, 100, 300),
        tt_bits=18,
        tt_ways=2,
        countermove=True,
        history_malus=True,
        capture_history=True,
        continuation=(1, 2),
        capture_order="see",
        null_move=NullMove8(
            min_depth=3,
            base=2,
            depth_div=4,
            eval_div=200,
            eval_cap=2,
            static_ge_beta=True,
            verify_depth=8,
            verify_low_material=True,
        ),
        reverse_futility=(6, 80, 40),
        razoring=(3, 300, 100),
        futility=(4, 100, 100),
        futility_spares_good_quiets=True,
        late_move_pruning=(5, 9, 15, 22),
        lmp_improving_pct=140,
        see_pruning=(5, 60, 25),
        probcut=(5, 120, 4),
        singular=(7, 3, 0, 3),
        iir_min_depth=4,
        lmr=Lmr8(min_depth=3, full_moves=3, history_divisor=8_000),
        check_extensions=2,
        recapture_extension=True,
        quiescence=Quiescence8(max_ply=10, promotions=True, delta=200, see_prune=True),
        twofold=True,
        draw_scores=luna_draws,
        correction=(14, 60),
        book=True,
        fast_see=True,
    ),
    evaluation=EvalConfig8(
        tables="pesto",
        doubled=12,
        isolated=12,
        backward=8,
        passed=(0, 5, 10, 20, 40, 70, 120, 0),
        passer_protected=10,
        passer_connected=10,
        passer_king_distance=4,
        unstoppable_passer=300,
        bishop_pair=30,
        rook_open=20,
        rook_semi_open=10,
        rook_seventh=15,
        knight_outpost=15,
        king_open_file=15,
        king_semi_open_file=10,
        tempo=10,
        mopup=MopUp8(min_advantage=300, max_phase=6, kbnk_corner=True),
        scaling=True,
        fifty_move_scaling=True,
    ),
)
