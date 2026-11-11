"""V20 residual policy network with a scalar negamax value head."""

from __future__ import annotations

import torch
from torch import nn

from .features import PLANES
from .moves import ACTIONS, MOVE_TYPES

DEFAULT_CONFIG = {"channels": 128, "blocks": 12, "head_channels": 64}


def _norm(channels: int) -> nn.GroupNorm:
    groups = next(group for group in range(min(8, channels), 0, -1) if channels % group == 0)
    return nn.GroupNorm(groups, channels)


class ResidualBlock(nn.Module):
    """Two convolutions with GroupNorm and an identity residual connection."""

    def __init__(self, channels: int) -> None:
        super().__init__()
        self.layers = nn.Sequential(
            nn.Conv2d(channels, channels, 3, padding=1, bias=False),
            _norm(channels),
            nn.ReLU(),
            nn.Conv2d(channels, channels, 3, padding=1, bias=False),
            _norm(channels),
        )

    def forward(self, observations: torch.Tensor) -> torch.Tensor:
        """Apply the residual block without changing tensor dimensions."""
        return torch.relu(observations + self.layers(observations))


class PolicyValueNet(nn.Module):
    """Map ``(B, 19, 8, 8)`` to policy logits ``(B, 4672)`` and value ``(B,)``."""

    def __init__(self, channels: int = 128, blocks: int = 12, head_channels: int = 64) -> None:
        super().__init__()
        if channels < 1 or blocks < 1 or head_channels < 1:
            raise ValueError("channels, blocks and head_channels must be positive")
        self.channels = channels
        self.blocks = blocks
        self.head_channels = head_channels
        self.stem = nn.Sequential(
            nn.Conv2d(PLANES, channels, 3, padding=1, bias=False),
            _norm(channels),
            nn.ReLU(),
        )
        self.body = nn.Sequential(*(ResidualBlock(channels) for _ in range(blocks)))
        self.policy_head = nn.Sequential(
            nn.Conv2d(channels, head_channels, 1, bias=False),
            _norm(head_channels),
            nn.ReLU(),
            nn.Conv2d(head_channels, MOVE_TYPES, 1),
        )
        self.value_head = nn.Sequential(
            nn.Conv2d(channels, 8, 1, bias=False),
            _norm(8),
            nn.ReLU(),
            nn.Flatten(),
            nn.Linear(8 * 8 * 8, 128),
            nn.ReLU(),
            nn.Linear(128, 1),
            nn.Tanh(),
        )

    def features(self, observations: torch.Tensor) -> torch.Tensor:
        """Return the shared backbone output."""
        return self.body(self.stem(observations.float()))

    def forward(self, observations: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """Return policy logits in action order and the side-to-move value."""
        x = self.features(observations)
        logits = self.policy_head(x).permute(0, 2, 3, 1).reshape(x.shape[0], ACTIONS)
        return logits, self.value_head(x).squeeze(1)

    def value(self, observations: torch.Tensor) -> torch.Tensor:
        """Return the scalar value without evaluating the policy head."""
        return self.value_head(self.features(observations)).squeeze(1)

    def config(self) -> dict[str, int]:
        """Return construction parameters for checkpoints."""
        return {
            "channels": self.channels,
            "blocks": self.blocks,
            "head_channels": self.head_channels,
        }
