"""Benchmark 7 "Dragon" profile: the four Benchmark 6 designs combined and tuned by
matches (see documents/CONTEXT.md §4.9.2)."""

from __future__ import annotations

from dataclasses import dataclass

from ai.bench7.evaluation import EvalConfig6, MopUp6
from ai.bench7.search import Lmr6, NullMove6, Quiescence6, SearchConfig6, TimeConfig6


@dataclass(frozen=True)
class Profile7:
    """A named search plus evaluation configuration."""

    name: str
    search: SearchConfig6
    evaluation: EvalConfig6


# ------------------------------------------------------------------------ Bench 7
def _b7_draws(root_eval: int) -> tuple[int, int]:
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


B7 = Profile7(
    name="b7",
    search=SearchConfig6(
        time=TimeConfig6(soft=0.6, hard=0.95, policy="stability", early=0.5, late=0.92),
        aspiration=(25, 100, 300),
        tt_bits=18,
        tt_ways=2,
        countermove=True,
        history_malus=True,
        capture_history=True,
        continuation=(1, 2),
        capture_order="see",
        null_move=NullMove6(
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
        lmr=Lmr6(min_depth=3, full_moves=3, history_divisor=8_000),
        check_extensions=2,
        recapture_extension=True,
        quiescence=Quiescence6(max_ply=10, promotions=True, delta=200, see_prune=True),
        twofold=True,
        draw_scores=_b7_draws,
        correction=(14, 60),
        book=True,
    ),
    evaluation=EvalConfig6(
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
        mopup=MopUp6(min_advantage=300, max_phase=6, kbnk_corner=True),
        scaling=True,
        fifty_move_scaling=True,
    ),
)
