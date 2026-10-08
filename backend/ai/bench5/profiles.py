"""The five Benchmark 5 profiles.

Four profiles follow one design write-up each (``chatgpt.txt``, ``gemini.txt``,
``deepseek.txt``, ``grok.txt`` in the repository root); the hybrid profile combines them.
When a source gives no number, the comment says which value was chosen and why.
"""

from __future__ import annotations

from dataclasses import dataclass

from ai.bench5.evaluation import EvalConfig, MopUp
from ai.bench5.search import LmrConfig, NullMoveConfig, QuiescenceConfig, SearchConfig

FLAT_VALUES = (0, 100, 320, 330, 500, 900, 0)


@dataclass(frozen=True)
class Profile5:
    """A named search plus evaluation configuration."""

    name: str
    search: SearchConfig
    evaluation: EvalConfig


# ----------------------------------------------------------------------------- GPT
def _gpt_lmr(depth: int, index: int) -> int:
    """R=1; R=2 only at depth >= 6 for very late moves."""
    return 2 if depth >= 6 and index >= 12 else 1


GPT = Profile5(
    name="gpt",
    search=SearchConfig(
        soft_fraction=0.85,  # "chạy tới khoảng 0.85 s"
        hard_fraction=0.97,  # "hard stop khoảng 0.97 s"
        check_mask=127,  # every 128 nodes so the per-move cap holds at ~10k nps
        aspiration=(30, 90, 270),  # "±30 cp; fail thì mở dần"
        aspiration_min_depth=4,
        tt_entries=262_144,  # "131k–262k entry"
        history_malus=True,  # "phạt các quiet thất bại trước beta cutoff"
        capture_split="attacked",  # bad captures last; SEE deferred, so a cheap proxy
        null_move=NullMoveConfig(min_depth=3, non_pv_only=True, min_pieces=2),  # zugzwang guard
        lmr=LmrConfig(min_depth=3, full_moves=3, reduction=_gpt_lmr, skip_killers=True),
        check_extensions=2,  # "tối đa tổng khoảng +2 ply/branch"
        quiescence=QuiescenceConfig(max_ply=10, promotions=True, delta_move=200),
        twofold=True,  # "lần lặp thứ 2 trong search coi gần 0"
    ),
    evaluation=EvalConfig(
        doubled=15,
        isolated=15,
        passed=(0, 5, 10, 20, 45, 80, 130, 0),  # "tăng mạnh bonus passer ở rank 5–7"
        bishop_pair=35,  # "+30..40"
        rook_open=20,
        rook_semi_open=10,
        # "hơn nhiều quân và đối thủ gần hết quân": push the king to the edge, approach it.
        mopup=MopUp(min_advantage=300, max_phase=6, enemy_center=10, king_manhattan=4),
    ),
)


# -------------------------------------------------------------------------- Gemini
def _gemini_null(depth: int) -> int:
    """R=2 at depth 3..4, R=3 from depth 5."""
    return 2 if depth < 5 else 3


def _gemini_draws(root_eval: int) -> tuple[int, int]:
    """Dynamic contempt: ahead >= +100 -> draw -80, behind <= -150 -> draw +50."""
    if root_eval >= 100:
        return -80, -80
    if root_eval <= -150:
        return 50, 50
    return 0, 0


GEMINI = Profile5(
    name="gemini",
    search=SearchConfig(
        soft_fraction=0.60,
        hard_fraction=0.92,
        check_mask=127,  # every 128 nodes so the per-move cap holds at ~10k nps
        reverse_futility=(2, 120),  # "static_eval - 120 * depth >= beta"
        null_move=NullMoveConfig(min_depth=3, reduction=_gemini_null, non_pv_only=False),
        lmr=LmrConfig(min_depth=3, full_moves=3, skip_killers=True),
        check_extensions=1,  # "tối đa 1 lần trên một nhánh"
        quiescence=QuiescenceConfig(max_ply=16, delta_node=950),  # no ply cap given
        twofold=True,  # "đã xuất hiện >= 1 lần ... coi như hòa"
        draw_scores=_gemini_draws,
    ),
    evaluation=EvalConfig(
        mg_values=FLAT_VALUES,
        eg_values=(0, 120, 300, 330, 530, 950, 0),
        mopup=MopUp(
            min_advantage=300,
            max_phase=4,
            enemy_without_pawns=True,
            enemy_center=4,  # 4 x CenterDistance
            king_manhattan=3,  # 3 x (14 - Manhattan)
        ),
    ),
)


# ------------------------------------------------------------------------ DeepSeek
def _deepseek_null(depth: int) -> int:
    return 2 + depth // 6


def _deepseek_lmr(depth: int, index: int) -> int:
    return 2 if index > 8 or depth > 6 else 1


def _deepseek_draws(root_eval: int) -> tuple[int, int]:
    """Contempt 30: twofold -30 when ahead; threefold/50-move -30 ahead, +30 behind."""
    if root_eval >= 30:
        return -30, -30
    if root_eval <= -30:
        return 0, 30
    return 0, 0


DEEPSEEK = Profile5(
    name="deepseek",
    search=SearchConfig(
        soft_fraction=0.50,
        hard_fraction=0.95,
        check_mask=127,  # every 128 nodes so the per-move cap holds at ~10k nps
        stop_on_mate=True,  # "|score| > MATE-100 -> thoát"
        aspiration=(25, 100),  # "±25 cp ở depth >= 4, fail -> ±100 -> full"
        aspiration_min_depth=4,
        tt_entries=500_000,
        tt_two_tier=True,  # "2 bảng (depth-preferred + always-replace)"
        history_by_piece=True,  # "history [piece][to]"
        countermove=True,
        capture_split="see",  # "MVV_LVA - SEE_penalty"
        null_move=NullMoveConfig(min_depth=3, reduction=_deepseek_null, non_pv_only=True),
        futility=(2, 150),  # "static + 150*depth < alpha"
        late_move_pruning=(3, 6, 2),  # "đã thử >= 6 + depth*2"
        see_pruning=(3, 100, 50),  # "SEE < -100*depth / -50*depth"
        lmr=LmrConfig(min_depth=3, full_moves=3, reduction=_deepseek_lmr, skip_killers=True),
        check_extensions=3,  # "cap 3/nhánh"
        quiescence=QuiescenceConfig(max_ply=12, delta_move=200, see_prune=True),
        twofold=True,
        draw_scores=_deepseek_draws,
        root_repetition_filter=50,  # "loại nước dẫn 2-fold nếu eval > +50"
    ),
    evaluation=EvalConfig(
        passed=(0, 10, 20, 35, 60, 100, 150, 0),  # "5/10/20/35/60/100/150", rank 7 = 150
        rook_seventh=25,
        knight_outpost=20,
        bishop_pair=30,
        king_open_file=20,
        king_semi_open_file=10,
        tempo=10,
        mopup=MopUp(
            min_advantage=400,
            max_non_pawn=1300,
            king_chebyshev=8,
            chase_passer=12,
            own_center=15,
            edge_bonus=50,
        ),
    ),
)


# ---------------------------------------------------------------------------- Grok
def _grok_null(depth: int) -> int:
    return 3 if depth >= 6 else 2  # "R=2–3 (tăng theo depth)"


def _grok_lmr(depth: int, index: int) -> int:
    return max(1, depth // 6 + index // 12)  # "depth/6 + move/12"


def _grok_draws(root_eval: int) -> tuple[int, int]:
    """Contempt 15 while ahead ("tránh hòa khi hơn")."""
    return (-15, -15) if root_eval > 0 else (0, 0)


GROK = Profile5(
    name="grok",
    search=SearchConfig(
        soft_fraction=0.75,  # "0.7–0.8"
        hard_fraction=0.95,
        check_mask=127,  # every 128 nodes so the per-move cap holds at ~10k nps
        stop_on_mate=True,  # "dừng sớm nếu mate tìm thấy"
        aspiration=(50,),  # "±50; fail thì research full window"
        aspiration_min_depth=4,
        tt_entries=1_000_000,  # "1–2M entries"
        capture_split="see",  # "MVV-LVA + SEE nếu có"
        null_move=NullMoveConfig(
            min_depth=3, reduction=_grok_null, non_pv_only=True, verify_depth=6
        ),
        futility=(2, 200),  # "futility/delta pruning nhẹ ở depth <= 2"
        lmr=LmrConfig(min_depth=3, full_moves=2, reduction=_grok_lmr, skip_killers=True),
        check_extensions=3,  # "Check +1 (max 3 trên nhánh)"
        capture_extension=True,  # "capture/promotion gần lá +1 nếu SEE >= 0"
        quiescence=QuiescenceConfig(
            max_ply=12, delta_move=200, see_prune=True, first_ply_checks=True
        ),
        twofold=False,  # "trong cây chỉ coi repetition 3 lần = 0"
        draw_scores=_grok_draws,
        root_repetition_penalty=15,  # "ở gốc phạt nhẹ repetition 2 lần"
    ),
    evaluation=EvalConfig(
        # Benchmark 4 terms kept, structure penalties raised as proposed.
        doubled=20,
        isolated=25,
        islands=10,
        passed=(0, 8, 15, 30, 50, 90, 150, 0),
        bishop_pair=30,
        rook_open=20,
        rook_semi_open=10,
        king_shield=15,
        king_open_file=20,
        king_semi_open_file=20,
        mobility=True,
        mopup=MopUp(min_advantage=200, max_phase=8, enemy_center=15, king_manhattan=4),
    ),
)


# -------------------------------------------------------------------------- Hybrid
def _hybrid_null(depth: int) -> int:
    return 2 + depth // 6


def _hybrid_lmr(depth: int, index: int) -> int:
    return 2 if index > 8 or depth > 6 else 1


def _hybrid_draws(root_eval: int) -> tuple[int, int]:
    """Contempt 25 against draws while ahead, accept them while clearly behind."""
    if root_eval > 50:
        return -25, -25
    if root_eval < -50:
        return 25, 25
    return 0, 0


HYBRID = Profile5(
    name="hybrid",
    search=SearchConfig(
        soft_fraction=0.60,
        hard_fraction=0.90,
        check_mask=127,  # every 128 nodes so the per-move cap holds at ~10k nps
        stop_on_mate=True,
        aspiration=(30, 100, 300),
        aspiration_min_depth=4,
        tt_entries=500_000,
        history_malus=True,
        countermove=True,
        capture_split="see",
        null_move=NullMoveConfig(min_depth=3, reduction=_hybrid_null, non_pv_only=True),
        reverse_futility=(2, 120),
        futility=(2, 150),
        lmr=LmrConfig(min_depth=3, full_moves=3, reduction=_hybrid_lmr, skip_killers=True),
        check_extensions=2,
        quiescence=QuiescenceConfig(max_ply=10, promotions=True, delta_move=200, see_prune=True),
        twofold=True,
        draw_scores=_hybrid_draws,
        mate_distance_pruning=True,
    ),
    evaluation=EvalConfig(
        mg_values=FLAT_VALUES,
        eg_values=(0, 120, 300, 330, 530, 950, 0),
        doubled=15,
        isolated=15,
        passed=(0, 5, 10, 20, 40, 70, 120, 0),
        bishop_pair=30,
        rook_open=20,
        rook_semi_open=10,
        rook_seventh=20,
        knight_outpost=15,
        king_shield=10,
        king_semi_open_file=10,
        tempo=10,
        mopup=MopUp(
            min_advantage=300,
            max_phase=6,
            enemy_without_pawns=True,
            enemy_center=10,
            king_manhattan=4,
            edge_bonus=20,
        ),
    ),
)

PROFILES: dict[str, Profile5] = {
    profile.name: profile for profile in (GPT, GEMINI, DEEPSEEK, GROK, HYBRID)
}
