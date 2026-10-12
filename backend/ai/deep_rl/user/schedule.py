"""Lộ trình đan xen: tỉ lệ các loại ván và các kho mẫu thay đổi dần theo tiến độ train.

Chuỗi lộ trình: các mốc ``tiến_độ:loại=tỉ_lệ,…`` cách nhau bởi ``;``, vd
``"0:mate=0.3,endgame=0.7;1:endgame=0.2,full150=0.8"``. Giữa hai mốc tỉ lệ nội suy tuyến tính;
trước mốc đầu / sau mốc cuối giữ nguyên. Loại không ghi ở một mốc có tỉ lệ 0 ở mốc đó.
"""

from __future__ import annotations

from typing import Any

GAME_KINDS = ("mate", "tactic", "endgame", "middlegame", "full", "full150")
BATCH_KINDS = ("pgn", "mate", "tactic", "decisive")
LEVEL_KINDS = ("L1", "L2", "L3", "L4")

Schedule = list[tuple[float, dict[str, float]]]


def parse_schedule(value: str, kinds: tuple[str, ...]) -> Schedule:
    """Đọc chuỗi lộ trình thành danh sách mốc (tiến độ tăng dần)."""
    anchors: Schedule = []
    try:
        for entry in value.split(";"):
            progress_text, items = entry.split(":", maxsplit=1)
            progress = float(progress_text)
            if not 0.0 <= progress <= 1.0:
                raise ValueError("progress must be in [0, 1]")
            shares: dict[str, float] = {}
            for item in items.split(","):
                kind, share_text = item.split("=", maxsplit=1)
                kind, share = kind.strip(), float(share_text)
                if kind not in kinds:
                    raise ValueError(f"unknown kind {kind!r} (allowed: {', '.join(kinds)})")
                if share < 0:
                    raise ValueError("shares must be non-negative")
                shares[kind] = share
            anchors.append((progress, shares))
    except ValueError as exc:
        raise ValueError(f"invalid schedule {value!r}: {exc}") from exc
    if not anchors:
        raise ValueError("schedule is empty")
    anchors.sort(key=lambda anchor: anchor[0])
    return anchors


def schedule_at(anchors: Schedule, progress: float) -> dict[str, float]:
    """Tỉ lệ từng loại ở ``progress`` (nội suy tuyến tính giữa hai mốc kề nhau)."""
    if progress <= anchors[0][0]:
        return dict(anchors[0][1])
    for (left, low), (right, high) in zip(anchors, anchors[1:], strict=False):
        if progress <= right:
            weight = 0.0 if right == left else (progress - left) / (right - left)
            kinds = set(low) | set(high)
            return {
                kind: low.get(kind, 0.0) + weight * (high.get(kind, 0.0) - low.get(kind, 0.0))
                for kind in kinds
            }
    return dict(anchors[-1][1])


def draw_kind(shares: dict[str, float], rng: Any) -> str:
    """Bốc một loại theo tỉ lệ (chuẩn hóa về tổng 1)."""
    total = sum(shares.values())
    if total <= 0:
        raise ValueError("schedule shares sum to zero")
    draw = float(rng.random()) * total
    cumulative = 0.0
    kind = next(iter(shares))
    for kind, share in shares.items():
        cumulative += share
        if draw < cumulative:
            return kind
    return kind


def mate_level_cap(progress: float, max_level: int) -> int:
    """Cấp chiếu hết cao nhất được bốc: tăng dần 1 → ``max_level`` theo tiến độ."""
    return max(1, min(max_level, 1 + int(progress * max_level)))
