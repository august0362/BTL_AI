"""Tác nhân DQN: mạng chính, mạng đóng băng (target network), chọn nước và cập nhật.

Luồng chọn nước: tensor bàn cờ → CNN → vector Q (4672) → action masking (nước không hợp lệ
nhận -1e9) → softmax(Q/τ) để bốc nước khi train, hoặc argmax khi đấu.

Cập nhật (phương trình Bellman, kiểu negamax vì bàn cờ luôn lật về phía bên sắp đi):
``y = r − γ · max_{a' hợp lệ} Q_target(s', a')`` (``y = r`` khi ván kết thúc), loss Huber
với ngưỡng 1, rồi soft update ``θ_target ← τ·θ + (1 − τ)·θ_target``.
"""

from __future__ import annotations

import copy

import chess
import numpy as np
import torch
from torch import nn
from torch.nn import functional

from ai.deep_rl.user.policy import DQNPolicy

MASK_VALUE = -1e9  # đủ âm để softmax cho xác suất 0 mà không tràn số (NaN)


def masked_q(q_values: torch.Tensor, legal_mask: torch.Tensor) -> torch.Tensor:
    """Gán ``MASK_VALUE`` cho các hành động không hợp lệ."""
    return q_values.masked_fill(~legal_mask, MASK_VALUE)


def bellman_targets(
    rewards: torch.Tensor,
    dones: torch.Tensor,
    next_q: torch.Tensor,
    next_mask: torch.Tensor,
    gamma: float,
) -> torch.Tensor:
    """``y = r − γ · max Q(s')`` trên các nước hợp lệ; ``y = r`` khi ``done``."""
    best_next = masked_q(next_q, next_mask).max(dim=1).values
    best_next = torch.where(dones > 0, torch.zeros_like(best_next), best_next)
    return rewards - gamma * best_next


class Agent:
    """Giữ mạng chính và mạng đóng băng, chọn nước và học từ batch của replay buffer."""

    def __init__(
        self,
        model: nn.Module,
        *,
        gamma: float = 0.99,
        lr: float = 1e-4,
        tau: float = 0.005,
        huber_delta: float = 1.0,
        grad_clip: float = 10.0,
        device: str | torch.device = "cpu",
    ) -> None:
        self.device = torch.device(device)
        self.online = model.to(self.device)
        self.target = copy.deepcopy(self.online)
        self.target.requires_grad_(False)
        self.gamma = gamma
        self.tau = tau
        self.huber_delta = huber_delta
        self.grad_clip = grad_clip
        self.optimizer = torch.optim.Adam(self.online.parameters(), lr=lr)

    @torch.no_grad()
    def act(
        self,
        states: np.ndarray,
        masks: np.ndarray,
        temperature: float | None = None,
    ) -> np.ndarray:
        """Chọn hành động cho một batch: argmax nếu ``temperature`` là None, không thì
        bốc theo softmax(Q/τ). Chỉ chọn trong các nước hợp lệ."""
        q = self.online(torch.as_tensor(states, device=self.device))
        q = masked_q(q, torch.as_tensor(masks, device=self.device))
        if temperature is None:
            return q.argmax(dim=1).cpu().numpy()
        probs = torch.softmax(q / temperature, dim=1)
        return torch.multinomial(probs, 1).squeeze(1).cpu().numpy()

    def select_action(self, board: chess.Board, training: bool = False) -> chess.Move:
        """Chọn nước cho một bàn cờ (argmax); ``training`` giữ cho đúng chữ ký khung cũ."""
        del training
        return DQNPolicy(self.online, self.device).select_move(board)

    def update(self, batch: dict[str, np.ndarray]) -> dict[str, float]:
        """Một bước gradient trên batch từ ``ReplayBuffer.sample``; trả về loss và Q trung bình."""
        device = self.device
        states = torch.as_tensor(batch["states"], device=device)
        actions = torch.as_tensor(batch["actions"], device=device)
        rewards = torch.as_tensor(batch["rewards"], device=device)
        next_states = torch.as_tensor(batch["next_states"], device=device)
        next_masks = torch.as_tensor(batch["next_masks"], device=device)
        dones = torch.as_tensor(batch["dones"], device=device)

        q_taken = self.online(states).gather(1, actions[:, None]).squeeze(1)
        with torch.no_grad():
            targets = bellman_targets(
                rewards, dones, self.target(next_states), next_masks, self.gamma
            )
        loss = functional.huber_loss(q_taken, targets, delta=self.huber_delta)

        self.optimizer.zero_grad(set_to_none=True)
        loss.backward()
        nn.utils.clip_grad_norm_(self.online.parameters(), self.grad_clip)
        self.optimizer.step()
        self.soft_update()
        return {"loss": float(loss.item()), "q_mean": float(q_taken.mean().item())}

    @torch.no_grad()
    def soft_update(self) -> None:
        """``θ_target ← τ·θ_online + (1 − τ)·θ_target``."""
        for target, online in zip(self.target.parameters(), self.online.parameters(), strict=True):
            target.lerp_(online, self.tau)
