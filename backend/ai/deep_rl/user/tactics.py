"""Đo chiến thuật của mạng: ở thế có quân đối thủ bị treo, nước Q cao nhất có ăn quân đó không.

"Quân treo" = quân đối thủ đáng ≥ 3 điểm (Mã, Tượng, Xe, Hậu) ăn được mà ô đó không bị ăn lại.
Thế cờ lấy từ các ván đi ngẫu nhiên với seed cố định, nên mọi lần đo dùng cùng một bộ thế.
Mốc tham khảo (300 thế, seed 7): v1 69 %, pretrain v7 69 %, v8 47 %.
"""

from __future__ import annotations

import random

import chess
import numpy as np
import torch

from ai.deep_rl.user.agent import masked_q
from ai.deep_rl.user.features import action_mask, encode, legal_actions

_VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 0,
}


def free_captures(board: chess.Board) -> set[chess.Move]:
    """Các nước ăn quân ≥ 3 điểm mà ô đích không bị đối thủ ăn lại."""
    captures = set()
    for move in board.legal_moves:
        if not board.is_capture(move) or board.is_en_passant(move):
            continue
        victim = board.piece_at(move.to_square)
        if victim is None or _VALUES[victim.piece_type] < 3:
            continue
        child = board.copy(stack=False)
        child.push(move)
        if not child.is_attacked_by(child.turn, move.to_square):
            captures.add(move)
    return captures


def tactic_positions(count: int = 300, seed: int = 7) -> list[tuple[chess.Board, set[chess.Move]]]:
    """``count`` thế cờ có ít nhất một quân treo, kèm tập nước ăn quân treo."""
    rng = random.Random(seed)
    positions: list[tuple[chess.Board, set[chess.Move]]] = []
    while len(positions) < count:
        board = chess.Board()
        for _ in range(rng.randint(6, 60)):
            if board.is_game_over():
                break
            board.push(rng.choice(list(board.legal_moves)))
        if board.is_game_over():
            continue
        captures = free_captures(board)
        if captures:
            positions.append((board, captures))
    return positions


@torch.no_grad()
def tactics_rate(
    model: torch.nn.Module,
    positions: list[tuple[chess.Board, set[chess.Move]]],
    device: str | torch.device = "cpu",
) -> float:
    """Tỉ lệ thế mà nước có Q cao nhất là một nước ăn quân treo (một lần chạy mạng)."""
    if not positions:
        return float("nan")
    legal = [legal_actions(board) for board, _ in positions]
    states = torch.as_tensor(np.stack([encode(board) for board, _ in positions]), device=device)
    masks = torch.as_tensor(np.stack([action_mask(actions) for _, actions in legal]), device=device)
    q = masked_q(model(states), masks).cpu().numpy()
    hits = 0
    for row, (moves, actions), (_, captures) in zip(q, legal, positions, strict=True):
        hits += moves[int(np.argmax(row[actions]))] in captures
    return hits / len(positions)
