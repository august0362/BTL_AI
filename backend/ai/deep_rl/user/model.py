"""Mạng CNN dự đoán Q-value cho cả 4672 nước đi từ tensor bàn cờ ``(B, 18, 8, 8)``.

Thân: conv 3×3 rồi các khối residual. Đầu ra: conv 1×1 ra 73 kiểu nước trên mỗi ô, sắp lại
thành ``ô_đi × 73 + kiểu`` (khớp ``features.move_to_action``), qua ``tanh`` để Q nằm trong
[-1, 1] như phần thưởng. Dùng GroupNorm (không có running stats) nên mạng đóng băng chỉ cần
soft update tham số.
"""

from __future__ import annotations

import torch
from torch import nn

from ai.deep_rl.user.features import ACTIONS, MOVE_TYPES, PLANES


def _norm(channels: int) -> nn.GroupNorm:
    return nn.GroupNorm(min(8, channels), channels)


class ResidualBlock(nn.Module):
    """Hai lớp conv 3×3 có đường tắt."""

    def __init__(self, channels: int) -> None:
        super().__init__()
        self.conv1 = nn.Conv2d(channels, channels, 3, padding=1, bias=False)
        self.norm1 = _norm(channels)
        self.conv2 = nn.Conv2d(channels, channels, 3, padding=1, bias=False)
        self.norm2 = _norm(channels)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Trả về ``relu(x + F(x))``."""
        out = torch.relu(self.norm1(self.conv1(x)))
        out = self.norm2(self.conv2(out))
        return torch.relu(x + out)


class Model(nn.Module):
    """Q-network: ``(B, 18, 8, 8)`` → ``(B, 4672)``."""

    def __init__(self, channels: int = 64, blocks: int = 6) -> None:
        super().__init__()
        self.channels = channels
        self.blocks = blocks
        self.stem = nn.Sequential(
            nn.Conv2d(PLANES, channels, 3, padding=1, bias=False), _norm(channels), nn.ReLU()
        )
        self.body = nn.Sequential(*(ResidualBlock(channels) for _ in range(blocks)))
        self.head = nn.Conv2d(channels, MOVE_TYPES, 1)

    def forward(self, observations: torch.Tensor) -> torch.Tensor:
        """Tính Q-value cho mọi hành động (chưa mask)."""
        x = self.body(self.stem(observations.float()))
        q = self.head(x).permute(0, 2, 3, 1).reshape(x.shape[0], ACTIONS)
        return torch.tanh(q)

    def config(self) -> dict[str, int]:
        """Kích thước mạng, lưu cùng trọng số để dựng lại khi nạp."""
        return {"channels": self.channels, "blocks": self.blocks}
