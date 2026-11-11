"""Randomly initialized residual CNN with a policy head and a two-player value head.

* Policy: 4672 logits (``v20.moves.ACTIONS`` layout); illegal moves are masked by the caller.
* Value: ``(B, 2)`` in [-1, 1] = (utility of the side to move, utility of the other side).
  Two outputs because a draw is worth -0.1 to *both* players, so one value cannot be negated
  to get the opponent's utility.

Inputs are always encoded with ``evaluated_player = board.turn``.
"""

from __future__ import annotations

import torch
from torch import nn

from ..v20.features import PLANES
from ..v20.moves import ACTIONS, MOVE_TYPES


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
    """Map ``(B, PLANES, 8, 8)`` to ``(policy logits (B, 4672), values (B, 2))``."""

    def __init__(self, channels: int = 64, blocks: int = 6) -> None:
        super().__init__()
        if channels < 1 or blocks < 0:
            raise ValueError("channels must be positive and blocks must be nonnegative")
        self.channels = channels
        self.blocks = blocks
        self.stem = nn.Sequential(
            nn.Conv2d(PLANES, channels, 3, padding=1, bias=False),
            _norm(channels),
            nn.ReLU(),
        )
        self.body = nn.Sequential(*(ResidualBlock(channels) for _ in range(blocks)))
        self.policy_head = nn.Sequential(
            nn.Conv2d(channels, channels, 1, bias=False),
            _norm(channels),
            nn.ReLU(),
            nn.Conv2d(channels, MOVE_TYPES, 1),
        )
        self.value_head = nn.Sequential(
            nn.Conv2d(channels, 8, 1, bias=False),
            _norm(8),
            nn.ReLU(),
            nn.Flatten(),
            nn.Linear(8 * 8 * 8, 128),
            nn.ReLU(),
            nn.Linear(128, 2),
            nn.Tanh(),
        )

    def forward(self, observations: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """Return policy logits laid out as ``square * 73 + move_type`` and the value pair."""
        x = self.body(self.stem(observations.float()))
        logits = self.policy_head(x).permute(0, 2, 3, 1).reshape(x.shape[0], ACTIONS)
        return logits, self.value_head(x)

    def config(self) -> dict[str, int]:
        """Return construction parameters for checkpoints."""
        return {"channels": self.channels, "blocks": self.blocks}
