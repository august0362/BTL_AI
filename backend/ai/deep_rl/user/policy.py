"""Nạp trọng số đã train và trả về policy để đấu: argmax Q (``depth = 1``) hoặc alpha-beta
với điểm lá là max Q (``depth >= 2``, xem ``search.py``).

``torch`` chỉ được import khi thật sự nạp trọng số, để bot không bắt buộc có torch.
"""

from __future__ import annotations

from pathlib import Path

import chess

from ai.deep_rl.policy_api import Policy

WEIGHTS_FORMAT = "deep_rl_dqn_v1"


class DQNPolicy:
    """Chọn nước hợp lệ có Q-value lớn nhất."""

    def __init__(self, model: object, device: str = "cpu") -> None:
        self.model = model
        self.device = device

    def select_move(self, board: chess.Board) -> chess.Move:
        """Trả về nước hợp lệ có Q lớn nhất theo mạng."""
        import torch

        from ai.deep_rl.user.features import encode, legal_actions

        moves, actions = legal_actions(board)
        with torch.no_grad():
            q = self.model(torch.as_tensor(encode(board)[None], device=self.device))[0]
        return moves[int(q[torch.as_tensor(actions, device=self.device)].argmax())]


def load_file(path: str | Path, device: str | object = "cpu") -> dict:
    """``torch.load(..., weights_only=True)``. Một số bản torch (vd trên Kaggle) đã nạp
    ``torch._utils`` nhưng không gắn vào ``torch``, khiến ``torch.load`` báo
    ``no attribute '_utils'``; gắn tay trước khi nạp."""
    import importlib

    import torch

    if "_utils" not in vars(torch):
        torch._utils = importlib.import_module("torch._utils")
    data = torch.load(path, map_location=device, weights_only=True)
    data.setdefault("meta", {})
    return data


def save_weights(model: object, path: str | Path, meta: dict | None = None) -> None:
    """Lưu file trọng số dùng cho bot (chỉ mạng chính, khoảng 2 MB)."""
    import torch

    state = {key: value.cpu() for key, value in model.state_dict().items()}
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {"format": WEIGHTS_FORMAT, "config": model.config(), "model": state, "meta": meta or {}},
        path,
    )


def load_policy(
    weights_path: Path | None,
    device: str = "cpu",
    depth: int = 1,
    max_think_time_s: float = 0.0,
) -> Policy:
    """Nạp trọng số; chưa có trọng số thì báo ``NotImplementedError`` để bot đi ngẫu nhiên.

    ``depth = 1``: chọn argmax Q. ``depth >= 2``: alpha-beta độ sâu ``depth`` trong tối đa
    ``max_think_time_s`` giây mỗi nước (0 = không giới hạn).
    """
    if weights_path is None:
        raise NotImplementedError("deep_rl chưa có trọng số (weights_url trống)")
    from ai.deep_rl.user.model import Model

    data = load_file(weights_path, device)
    if data.get("format") != WEIGHTS_FORMAT:
        raise ValueError(f"file trọng số không đúng định dạng {WEIGHTS_FORMAT}")
    model = Model(**data["config"]).to(device)
    model.load_state_dict(data["model"])
    model.eval()
    potential_scale = float(data.get("meta", {}).get("potential_scale", 0.0))
    if depth <= 1:
        return DQNPolicy(model, device)
    from ai.deep_rl.user.search import AlphaBetaPolicy

    return AlphaBetaPolicy(model, device, depth, max_think_time_s, potential_scale)
