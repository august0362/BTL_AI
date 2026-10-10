"""Nạp trọng số đã train và trả về policy chọn nước có Q lớn nhất (argmax) để đấu.

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


def save_weights(model: object, path: str | Path) -> None:
    """Lưu file trọng số dùng cho bot (chỉ mạng chính, khoảng 2 MB)."""
    import torch

    state = {key: value.cpu() for key, value in model.state_dict().items()}
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    torch.save({"format": WEIGHTS_FORMAT, "config": model.config(), "model": state}, path)


def load_policy(weights_path: Path | None, device: str = "cpu") -> Policy:
    """Nạp trọng số; chưa có trọng số thì báo ``NotImplementedError`` để bot đi ngẫu nhiên."""
    if weights_path is None:
        raise NotImplementedError("deep_rl chưa có trọng số (weights_url trống)")
    import torch

    from ai.deep_rl.user.model import Model

    data = torch.load(weights_path, map_location=device, weights_only=True)
    if data.get("format") != WEIGHTS_FORMAT:
        raise ValueError(f"file trọng số không đúng định dạng {WEIGHTS_FORMAT}")
    model = Model(**data["config"]).to(device)
    model.load_state_dict(data["model"])
    model.eval()
    return DQNPolicy(model, device)
