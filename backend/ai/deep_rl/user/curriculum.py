"""Lấy ván quyết định từ PGN và chọn pha Backplay cho self-play."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import chess
import chess.pgn

from ai.deep_rl.user.pretrain import _pgn_texts


@dataclass(frozen=True)
class Phase:
    """Một pha self-play và giới hạn độ dài tương ứng."""

    name: str
    back_range: tuple[int, int] | None
    max_plies: int


def load_decisive_games(pgn_paths: list[str | Path]) -> list[list[chess.Move]]:
    """Đọc mainline các ván thắng/thua hợp lệ từ PGN, ZIP hoặc thư mục."""
    games: list[list[chess.Move]] = []
    for path in pgn_paths:
        for _, text in _pgn_texts(Path(path)):
            stream = io.StringIO(text)
            while (game := chess.pgn.read_game(stream)) is not None:
                if game.errors or game.headers.get("Result") not in ("1-0", "0-1"):
                    continue
                games.append(list(game.mainline_moves()))
    return games


def load_mate_puzzles(
    path: str | Path,
) -> dict[int, list[tuple[str, list[chess.Move]]]]:
    """Đọc puzzle chiếu hết và kiểm tra toàn bộ lời giải UCI."""
    puzzles: dict[int, list[tuple[str, list[chess.Move]]]] = {level: [] for level in range(1, 5)}
    with Path(path).open(newline="", encoding="utf-8") as stream:
        for row_number, row in enumerate(csv.DictReader(stream), start=2):
            try:
                level = int(row["level"])
                fen = row["fen"]
                board = chess.Board(fen)
                moves = [chess.Move.from_uci(uci) for uci in row["solution"].split()]
                if level not in puzzles or board.is_game_over() or len(moves) != 2 * level - 1:
                    raise ValueError("level, starting position, or solution length is invalid")
                if not board.legal_moves:
                    raise ValueError("starting position has no legal moves")
                for move in moves:
                    if move not in board.legal_moves:
                        raise ValueError(f"illegal solution move {move.uci()}")
                    board.push(move)
                if not board.is_checkmate():
                    raise ValueError("solution does not end in checkmate")
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"invalid mate puzzle at CSV row {row_number}: {exc}") from exc
            puzzles[level].append((fen, moves))
    return puzzles


def load_tactic_puzzles(path: str | Path) -> list[tuple[str, list[chess.Move]]]:
    """Đọc puzzle chiến thuật (``puzzle_id,theme,fen,solution``); kiểm tra lời giải hợp lệ."""
    puzzles: list[tuple[str, list[chess.Move]]] = []
    with Path(path).open(newline="", encoding="utf-8") as stream:
        for row_number, row in enumerate(csv.DictReader(stream), start=2):
            try:
                board = chess.Board(row["fen"])
                moves = [chess.Move.from_uci(uci) for uci in row["solution"].split()]
                if not moves or board.is_game_over():
                    raise ValueError("empty solution or finished starting position")
                for move in moves:
                    if move not in board.legal_moves:
                        raise ValueError(f"illegal solution move {move.uci()}")
                    board.push(move)
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"invalid tactic puzzle at CSV row {row_number}: {exc}") from exc
            puzzles.append((row["fen"], moves))
    return puzzles


def _randint(rng: Any, low: int, high: int) -> int:
    """Lấy số nguyên trong khoảng đóng từ các API RNG phổ biến."""
    if hasattr(rng, "integers"):
        return int(rng.integers(low, high + 1))
    return int(rng.randint(low, high))


def start_board(moves: list[chess.Move], back_min: int, back_max: int, rng: Any) -> chess.Board:
    """Phát lại lịch sử PGN đến vị trí ngẫu nhiên, không kết thúc."""
    if back_min < 0 or back_max < back_min:
        raise ValueError("back_range không hợp lệ")
    back = min(_randint(rng, back_min, back_max), len(moves))
    replay_count = len(moves) - back
    board = chess.Board()
    for move in moves[:replay_count]:
        board.push(move)
    while replay_count and board.is_game_over(claim_draw=True):
        board.pop()
        replay_count -= 1
    return board


PHASES = ("endgame", "middlegame", "full", "full150")


def phase_by_name(name: str, config: Any) -> Phase:
    """Pha curriculum theo tên (``endgame``, ``middlegame``, ``full``, ``full150``)."""
    if name == "endgame":
        return Phase(
            "endgame",
            (config.endgame_back_min, config.endgame_back_max),
            config.endgame_max_plies,
        )
    if name == "middlegame":
        return Phase(
            "middlegame",
            (config.middlegame_back_min, config.middlegame_back_max),
            config.middlegame_max_plies,
        )
    if name == "full":
        return Phase("full", None, config.long_max_plies)
    if name == "full150":
        return Phase("full150", None, config.max_plies)
    raise ValueError(f"unknown phase {name!r}")


def phase_for(game_index: int, config: Any) -> Phase:
    """Chọn pha theo chỉ số ván toàn cục và tỉ lệ trong cấu hình."""
    count = config.games
    endgame_end = config.endgame_fraction * count
    middle_end = endgame_end + config.middlegame_fraction * count
    free_end = middle_end + config.free_fraction * count
    if game_index < endgame_end:
        return phase_by_name("endgame", config)
    if game_index < middle_end:
        return phase_by_name("middlegame", config)
    if game_index < free_end:
        return phase_by_name("full", config)
    return phase_by_name("full150", config)


def parse_phase_mix(value: str) -> dict[str, dict[str, float]]:
    """Đọc tỉ lệ ôn pha cũ, vd ``"middlegame:endgame=0.25;full150:endgame=0.15,middlegame=0.2"``.

    Với mỗi pha: xác suất một ván mới bắt đầu kiểu tàn cuộc / trung cuộc thay vì kiểu của pha.
    """
    mix: dict[str, dict[str, float]] = {}
    if not value:
        return mix
    try:
        for entry in value.split(";"):
            phase, items = entry.split(":", maxsplit=1)
            phase = phase.strip()
            if phase not in PHASES or phase in mix:
                raise ValueError(f"unknown or duplicate phase {phase!r}")
            shares: dict[str, float] = {}
            for item in items.split(","):
                kind, share_text = item.split("=", maxsplit=1)
                kind, share = kind.strip(), float(share_text)
                if kind not in ("endgame", "middlegame") or kind == phase:
                    raise ValueError(f"invalid start kind {kind!r} for phase {phase!r}")
                if not 0.0 <= share <= 1.0:
                    raise ValueError("shares must be in [0, 1]")
                shares[kind] = share
            mix[phase] = shares
    except ValueError as exc:
        raise ValueError(f"invalid phase_mix {value!r}: {exc}") from exc
    return mix


def draw_start_kind(
    phase: str, mix: dict[str, dict[str, float]], puzzle_share: float, rng: Any
) -> str:
    """Bốc kiểu bắt đầu của một ván thường: ``puzzle``, kiểu ôn trong ``mix``, hoặc ``phase``.

    Không dùng ``rng`` khi không có gì để trộn (giữ nguyên chuỗi ngẫu nhiên cũ).
    """
    shares = mix.get(phase, {})
    if puzzle_share <= 0 and not shares:
        return phase
    draw = float(rng.random())
    cumulative = puzzle_share
    if draw < cumulative:
        return "puzzle"
    for kind, share in shares.items():
        cumulative += share
        if draw < cumulative:
            return kind
    return phase
