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
    steps: torch.Tensor | None = None,
    online_q: torch.Tensor | None = None,
) -> torch.Tensor:
    """Tính mục tiêu Bellman negamax cho các mẫu một hoặc nhiều bước."""
    if online_q is None:
        best_next = masked_q(next_q, next_mask).max(dim=1).values
    else:
        actions = masked_q(online_q, next_mask).argmax(dim=1)
        best_next = next_q.gather(1, actions[:, None]).squeeze(1)
    best_next = torch.where(dones > 0, torch.zeros_like(best_next), best_next)
    if steps is None:
        steps = torch.ones_like(rewards)
    discounts = torch.pow(torch.full_like(rewards, -gamma), steps)
    return rewards + discounts * best_next


def margin_loss(
    q: torch.Tensor,
    legal_masks: torch.Tensor,
    expert_actions: torch.Tensor,
    margin: float,
) -> torch.Tensor:
    """Tính loss biên lớn trên các nước hợp lệ của chuyên gia."""
    actions = expert_actions.long()
    alternatives = torch.arange(q.shape[1], device=q.device)[None, :] != actions[:, None]
    candidates = q + margin * alternatives
    best = candidates.masked_fill(~legal_masks.bool(), -torch.inf).max(dim=1).values
    return (best - q.gather(1, actions[:, None]).squeeze(1)).clamp_min(0).mean()


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
        margin: float = 0.05,
        margin_weight: float = 1.0,
        double_dqn: int = 0,
    ) -> None:
        self.device = torch.device(device)
        self.online = model.to(self.device)
        self.target = copy.deepcopy(self.online)
        self.target.requires_grad_(False)
        self.gamma = gamma
        self.tau = tau
        self.huber_delta = huber_delta
        self.grad_clip = grad_clip
        self.margin = margin
        self.margin_weight = margin_weight
        self.double_dqn = bool(double_dqn)
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
        if temperature is None or temperature <= 0:
            return q.argmax(dim=1).cpu().numpy()
        legal = torch.as_tensor(masks, device=self.device)
        legal_q = q.masked_fill(~legal, 0.0)
        count = legal.sum(dim=1, keepdim=True).clamp_min(1)
        mean = legal_q.sum(dim=1, keepdim=True) / count
        centered = (q - mean).masked_fill(~legal, 0.0)
        variance = centered.square().sum(dim=1, keepdim=True) / count
        normalized = centered / (variance.sqrt() + 1e-6)
        normalized = normalized.masked_fill(~legal, MASK_VALUE)
        probs = torch.softmax(normalized / temperature, dim=1)
        return torch.multinomial(probs, 1).squeeze(1).cpu().numpy()

    def select_action(self, board: chess.Board, training: bool = False) -> chess.Move:
        """Chọn nước cho một bàn cờ (argmax); ``training`` giữ cho đúng chữ ký khung cũ."""
        del training
        return DQNPolicy(self.online, self.device).select_move(board)

    def update(
        self,
        batch: dict[str, np.ndarray],
        expert_batch: dict[str, np.ndarray] | None = None,
    ) -> dict[str, float]:
        """Cập nhật TD trên replay và tùy chọn thêm loss biên từ chuyên gia."""
        device = self.device
        expert_count = 0 if expert_batch is None else len(expert_batch["actions"])
        states_np = batch["states"]
        if expert_batch is not None:
            states_np = np.concatenate((states_np, expert_batch["states"]))
        states = torch.as_tensor(states_np, device=device)
        actions_np = batch["actions"]
        if expert_batch is not None:
            actions_np = np.concatenate((actions_np, expert_batch["actions"]))
        actions = torch.as_tensor(actions_np, device=device)
        q_all = self.online(states)
        q_taken = q_all.gather(1, actions[:, None]).squeeze(1)
        batch_count = len(batch["actions"])
        rewards = torch.as_tensor(batch["rewards"], device=device)
        next_states = torch.as_tensor(batch["next_states"], device=device)
        next_masks = torch.as_tensor(batch["next_masks"], device=device)
        dones = torch.as_tensor(batch["dones"], device=device)
        steps = torch.as_tensor(
            batch.get("steps", np.ones(len(batch["actions"]))),
            device=device,
            dtype=torch.int64,
        )
        if expert_batch is not None:
            rewards = torch.cat((rewards, torch.as_tensor(expert_batch["rewards"], device=device)))
            next_states = torch.cat(
                (next_states, torch.as_tensor(expert_batch["next_states"], device=device))
            )
            next_masks = torch.cat(
                (next_masks, torch.as_tensor(expert_batch["next_masks"], device=device))
            )
            dones = torch.cat((dones, torch.as_tensor(expert_batch["dones"], device=device)))
            expert_steps = torch.as_tensor(
                expert_batch.get("steps", np.ones(len(expert_batch["actions"]))),
                device=device,
                dtype=torch.int64,
            )
            steps = torch.cat((steps, expert_steps))
        with torch.no_grad():
            online_next = self.online(next_states) if self.double_dqn else None
            targets = bellman_targets(
                rewards,
                dones,
                self.target(next_states),
                next_masks,
                self.gamma,
                steps,
                online_next,
            )
        td_loss = functional.huber_loss(q_taken, targets, delta=self.huber_delta)
        if expert_batch is None or expert_count == 0:
            expert_loss = torch.zeros((), device=device)
        else:
            masks = torch.as_tensor(expert_batch["masks"], device=device)
            expert_actions = torch.as_tensor(expert_batch["actions"], device=device)
            expert_loss = margin_loss(q_all[batch_count:], masks, expert_actions, self.margin)
        loss = td_loss + self.margin_weight * expert_loss

        self.optimizer.zero_grad(set_to_none=True)
        loss.backward()
        nn.utils.clip_grad_norm_(self.online.parameters(), self.grad_clip)
        self.optimizer.step()
        self.soft_update()
        return {
            "loss": float(loss.item()),
            "td_loss": float(td_loss.item()),
            "margin_loss": float(expert_loss.item()),
            "q_mean": float(q_taken.mean().item()),
        }

    @torch.no_grad()
    def soft_update(self) -> None:
        """``θ_target ← τ·θ_online + (1 − τ)·θ_target``."""
        for target, online in zip(self.target.parameters(), self.online.parameters(), strict=True):
            target.lerp_(online, self.tau)
