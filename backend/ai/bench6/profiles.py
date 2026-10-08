"""Benchmark 6: one profile per design write-up.

Each Benchmark 6 profile follows only its own updated file in the repository root
(``chatgpt.txt``, ``gemini.txt``, ``grok.txt``, ``deepseek.txt``) on top of the matching
Benchmark 5 profile. When a file gives no number, the comment says what was chosen.
Benchmark 7 combines the four files and was tuned by matches (see documents/CONTEXT.md).
Rules every profile obeys: the per-move limit ``max_think_time_s`` is never exceeded (files
asking for 1.5-2 s "panic" time are capped at the hard limit), and no opening book or
tablebase is downloaded (the DeepSeek book is hand-written in ``search.BOOK_LINES``).
"""

from __future__ import annotations

from dataclasses import dataclass

from ai.bench6.evaluation import EvalConfig6, MopUp6
from ai.bench6.search import (
    Lmr6,
    NullMove6,
    Quiescence6,
    SearchConfig6,
    TimeConfig6,
)


@dataclass(frozen=True)
class Profile6:
    """A named search plus evaluation configuration."""

    name: str
    search: SearchConfig6
    evaluation: EvalConfig6


# ----------------------------------------------------------------------------- GPT
def _gpt_draws(root_eval: int) -> tuple[int, int]:
    """Small dynamic draw value: avoid draws slightly when winning, seek them when losing."""
    if root_eval >= 300:
        value = -15
    elif root_eval >= 100:
        value = -8
    elif root_eval <= -300:
        value = 15
    elif root_eval <= -100:
        value = 8
    else:
        value = 0
    return value, value


GPT6 = Profile6(
    name="gpt",
    search=SearchConfig6(
        # "best move giữ nguyên 2-3 iteration, swing < 20-30 -> stop 0.45-0.70 s;
        #  bất ổn -> 0.95-0.98 s"; also stop when the next iteration cannot finish.
        time=TimeConfig6(soft=0.7, hard=0.97, policy="stability", early=0.45, late=0.95),
        check_mask=127,  # every 128 nodes so the per-move cap holds at ~10k nps
        aspiration=(30, 90, 270),
        tt_bits=16,  # "65,536 buckets x 2"
        tt_ways=2,
        countermove=True,
        capture_history=True,
        continuation=(1,),  # "quiet move được đánh giá cả theo move vừa đi trước đó"
        capture_order="see",  # "SEE trở thành thành phần bắt buộc"
        # R: depth 3-5 -> 2, 6-8 -> 3, >= 9 -> 3-4, +1 when static - beta is large
        null_move=NullMove6(
            min_depth=3,
            base=2,
            depth_div=6,
            eval_div=200,
            eval_cap=1,
            static_ge_beta=True,
            verify_low_material=True,
        ),
        reverse_futility=(4, 90, 30),  # "~80-100 cp x depth, điều chỉnh theo improving"
        futility=(2, -10, 130),  # d1 ~120, d2 ~250
        futility_spares_good_quiets=True,  # not for killer/countermove/high history
        late_move_pruning=(5, 10, 18),  # d1 ~5, d2 ~10, d3 ~18
        lmp_improving_pct=140,  # "+30-50% khi improving"
        see_pruning=(4, 50, 0),  # captures with SEE < -50 x depth
        probcut=(5, 150, 3),  # "depth >= 5, margin 120-180, depth - 3"
        singular=(6, 3, 0, 3),  # "depth >= 6, TT entry đủ sâu"
        lmr=Lmr6(min_depth=3, full_moves=3, history_divisor=8_000),
        check_extensions=2,  # "limited check"
        quiescence=Quiescence6(max_ply=10, promotions=True, delta=175, see_prune=True),
        twofold=True,
        draw_scores=_gpt_draws,
        correction=(14, 60),  # "16k-32k entry x 2 màu, clamp ±50-80"
    ),
    evaluation=EvalConfig6(
        doubled=15,
        isolated=15,
        passed=(0, 5, 10, 20, 45, 80, 130, 0),
        passer_protected=15,
        passer_connected=15,
        passer_king_distance=4,
        unstoppable_passer=300,  # "rule-of-square cho pawn races"
        bishop_pair=35,
        rook_open=20,
        rook_semi_open=10,
        rook_seventh=15,
        rooks_connected=10,
        knight_outpost=20,  # "+10 ... +30"
        bishop_outpost=10,
        mobility=(4, 4, 2, 1),
        king_open_file=15,
        king_semi_open_file=10,
        king_danger=4,  # "N/B = 2, R = 3, Q = 5 rồi danger tăng phi tuyến"
        threat_pawn=30,
        threat_minor=25,
        hanging=25,
        mopup=MopUp6(min_advantage=300, max_phase=6, enemy_center=10, king_manhattan=4),
        scaling=True,  # opposite bishops, low-material draws
        fifty_move_scaling=True,
        lazy_margin=250,  # "expensive king/threat terms chỉ chạy khi thực sự cần"
    ),
)


# -------------------------------------------------------------------------- Gemini
def _gemini_draws(root_eval: int) -> tuple[int, int]:
    if root_eval >= 100:
        return -80, -80
    if root_eval <= -150:
        return 50, 50
    return 0, 0


GEMINI6 = Profile6(
    name="gemini",
    search=SearchConfig6(
        # Panic (score drop > 50) runs to the hard limit (the 1.5-2 s of the file is capped);
        # an easy move (same best move from depth 2 to 5) stops at 0.3 s.
        time=TimeConfig6(soft=0.6, hard=0.92, policy="panic_easy", early=0.3, late=0.92),
        check_mask=127,  # every 128 nodes so the per-move cap holds at ~10k nps
        stop_on_mate=False,
        aspiration=(30,),  # "score ± 30, fail -> mở rộng phía fail thêm 100"
        aspiration_grow=100,
        aspiration_min_depth=3,
        tt_bits=20,  # "TT = [None] * 1048576, index = hash & 0xFFFFF"
        tt_ways=1,
        countermove=False,
        history_malus=False,
        capture_order="mvv",
        null_move=NullMove6(
            min_depth=3, base=2, depth_div=5, static_ge_beta=False, non_pv_only=False
        ),
        reverse_futility=(2, 120, 0),
        razoring=(3, 300, 0),  # "Razoring (depth 3): static <= alpha - 300"
        futility=(2, 0, 150),  # "+150 cp ... +300 cp"
        # Benchmark 5 Gemini LMR: one ply for quiet moves from the 4th, killers kept.
        lmr=Lmr6(
            min_depth=3,
            full_moves=3,
            base=1.0,
            divisor=1e9,
            pv_less=0,
            not_improving_more=0,
            killer_less=1,
            cut_node_more=0,
        ),
        check_extensions=1,
        mate_distance_pruning=False,
        quiescence=Quiescence6(
            max_ply=16, promotions=False, delta=0, delta_node=950, see_prune=True
        ),  # "Fast-SEE ... cắt bỏ hoàn toàn nước này trong QS"
        twofold=True,
        draw_scores=_gemini_draws,
    ),
    evaluation=EvalConfig6(
        # "PeSTO ... gom luôn điểm cấu trúc Tốt ..., mobility ngầm định" -> PeSTO + mop-up.
        tables="pesto",
        doubled=0,
        isolated=0,
        passed=(0, 0, 0, 0, 0, 0, 0, 0),
        bishop_pair=0,
        rook_open=0,
        rook_semi_open=0,
        mopup=MopUp6(
            min_advantage=300,
            max_phase=4,
            enemy_without_pawns=True,
            enemy_center=4,
            king_manhattan=3,
            edge_bonus=0,
        ),
    ),
)


# ---------------------------------------------------------------------------- Grok
def _grok_draws(root_eval: int) -> tuple[int, int]:
    """Contempt +10..30 by material advantage ("Contempt động (+10-30 tùy material)")."""
    if root_eval >= 300:
        value = -30
    elif root_eval >= 100:
        value = -20
    elif root_eval > 0:
        value = -10
    else:
        value = 0
    return value, value


GROK6 = Profile6(
    name="grok",
    search=SearchConfig6(
        time=TimeConfig6(soft=0.7, hard=0.95, policy="complexity", late=0.95),
        aspiration=(40, 120, 400),  # "±30-50 cp, mở rộng x2-4 khi fail"
        tt_bits=21,  # "1-4M entries"
        tt_ways=1,
        countermove=True,
        history_malus=True,
        continuation=(1, 2),  # "continuation (1-2 ply trước)"
        capture_order="see",
        null_move=NullMove6(min_depth=3, base=2, depth_div=6, static_ge_beta=True, verify_depth=8),
        reverse_futility=(4, 125, 0),  # "depth <= 3-4, margin 100-150 x depth"
        razoring=(3, 300, 125),
        futility=(2, 200, 0),
        singular=(6, 3, 0, 12),  # "R ~ depth/2, margin 75-150"
        iir_min_depth=5,  # "IIR: không có TT-move ở depth >= 4-5 -> giảm 1"
        # "R = 1 + log(depth)*log(moveCount)/2, ±1 theo history; không reduce killer"
        lmr=Lmr6(
            min_depth=3,
            full_moves=2,
            base=1.0,
            divisor=2.0,
            pv_less=1,
            not_improving_more=0,
            killer_less=9,
            cut_node_more=0,
            history_divisor=8_000,
        ),
        check_extensions=4,  # "Check +1 (max 3-4)"
        capture_extension=True,
        recapture_extension=True,
        mate_distance_pruning=True,
        quiescence=Quiescence6(
            max_ply=14, promotions=True, delta=175, see_prune=True, first_ply_checks=2
        ),  # "Capture + check (giới hạn số check)"
        twofold=False,  # "Trong cây chỉ 3-fold = 0; ở gốc phạt nhẹ 2-fold"
        draw_scores=_grok_draws,
        root_repetition_penalty=15,
    ),
    evaluation=EvalConfig6(
        doubled=20,
        isolated=25,
        backward=15,
        islands=10,
        phalanx=5,
        supported=5,
        candidate=6,
        passed=(0, 8, 15, 30, 50, 90, 150, 0),
        passer_protected=10,
        passer_blocked_pct=50,
        unstoppable_passer=300,  # "KPK (rule of square + opposition)"
        bishop_pair=30,
        rook_open=20,
        rook_semi_open=10,
        rook_seventh=20,
        knight_outpost=20,
        bishop_outpost=10,
        mobility=(4, 4, 2, 1),
        king_shield=15,
        king_open_file=20,
        king_semi_open_file=20,
        king_storm=8,
        threat_pawn=30,
        threat_minor=20,
        hanging=30,
        mopup=MopUp6(min_advantage=175, max_phase=8, enemy_center=15, king_manhattan=4),
        scaling=True,
        lazy_margin=300,  # "early-out khi material extreme"
    ),
)


# ------------------------------------------------------------------------ DeepSeek
def _deepseek_draws(root_eval: int) -> tuple[int, int]:
    """Contempt 40 when ahead >= 100, otherwise 30 (twofold: 0 when behind)."""
    contempt = 40 if root_eval >= 100 else 30
    if root_eval >= 30:
        return -contempt, -contempt
    if root_eval <= -30:
        return 0, contempt
    return 0, 0


DEEPSEEK6 = Profile6(
    name="deepseek",
    search=SearchConfig6(
        # soft 0.5 / hard 0.95 with stability, score-stability, panic, phase and move-number
        # factors; "panic 1.5 T" is capped by the hard limit.
        time=TimeConfig6(soft=0.5, hard=0.95, policy="factors", late=0.95),
        aspiration=(25, 100, 300),
        tt_bits=18,  # "TT bucket 4-way + aging, 1M entry"
        tt_ways=4,
        countermove=True,
        history_malus=True,
        capture_history=True,
        continuation=(1, 2, 3),
        capture_order="see",
        null_move=NullMove6(
            min_depth=3,
            base=3,
            depth_div=5,
            eval_div=200,
            eval_cap=3,
            static_ge_beta=True,
            verify_depth=8,
        ),
        reverse_futility=(6, 80, 0),
        razoring=(3, 300, 100),
        futility=(4, 100, 100),
        late_move_pruning=(8, 10, 12),  # Benchmark 5 LMP kept: 6 + 2 x depth, depth <= 3
        history_pruning=(4, 1_500),  # "LMP history-based, depth <= 4"
        see_pruning=(3, 100, 50),  # kept from Benchmark 5
        probcut=(5, 100, 4),  # "depth >= 5, search depth-4"
        multicut=(5, 3, 6, 3),  # ">= 3 nước fail high ở reduced depth"
        iid=(5, 2),  # "IID depth >= 5, PV, không TT move, search depth-2"
        singular=(6, 3, 25, 0),  # "TT depth >= depth-3, LOWER/EXACT, window ±25"
        lmr=Lmr6(
            min_depth=3,
            full_moves=3,
            base=0.0,
            divisor=2.0,
            pv_less=1,
            not_improving_more=0,
            killer_less=1,
            cut_node_more=0,
            history_divisor=8_000,
            captures=True,  # "LMR cho captures: giảm 1"
        ),
        check_extensions=6,  # "Check extension cap 6"
        recapture_extension=True,
        pawn_seventh_extension=True,
        bad_capture_reduction=True,  # "Negative extension: bad captures (SEE<0) -1"
        mate_distance_pruning=True,
        quiescence=Quiescence6(max_ply=12, promotions=False, delta=200, see_prune=True),
        twofold=True,
        draw_scores=_deepseek_draws,
        root_repetition_filter=50,  # "đang hơn >= 50 cp -> loại nước dẫn 2-fold"
        book=True,  # "Book viết tay 20-30 vị trí"
    ),
    evaluation=EvalConfig6(
        doubled=15,
        isolated=15,
        backward=12,
        islands=8,
        phalanx=6,
        supported=6,
        candidate=6,
        passed=(0, 10, 20, 35, 60, 100, 150, 0),
        passer_protected=15,
        passer_connected=15,
        passer_blocked_pct=60,
        passer_king_distance=5,
        rook_behind_passer=15,
        unstoppable_passer=300,
        bishop_pair=30,
        rook_open=20,
        rook_semi_open=10,
        rook_seventh=25,
        knight_outpost=20,
        bishop_outpost=10,
        mobility=(4, 5, 2, 1),  # "N=4, B=5, R=2, Q=1"
        king_shield=12,
        king_open_file=20,
        king_semi_open_file=10,
        king_storm=6,
        king_danger=4,
        threat_pawn=30,
        threat_minor=20,
        hanging=25,
        development=12,  # 3-phase evaluation: opening development term
        tempo=10,
        mopup=MopUp6(
            min_advantage=300,
            max_phase=6,
            enemy_center=10,
            king_manhattan=4,
            edge_bonus=50,
            kbnk_corner=True,
        ),
        scaling=True,
        fifty_move_scaling=True,
        lazy_margin=250,  # "nếu node/s giảm > 20% -> xem lại": skip costly terms when moot
    ),
)


PROFILES6: dict[str, Profile6] = {
    profile.name: profile for profile in (GPT6, GEMINI6, GROK6, DEEPSEEK6)
}
