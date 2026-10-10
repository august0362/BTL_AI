"""Bộ nhớ kinh nghiệm (replay buffer) dạng vòng, nén bit để tiết kiệm RAM.

Mỗi mẫu là ``(s, a, r, s', done, mask')``: ``s``, ``s'`` là plane 0/1 nén còn 144 byte,
``mask'`` (nước hợp lệ ở ``s'``) nén còn 584 byte. 500.000 mẫu chiếm khoảng 0,5 GB.
"""

from __future__ import annotations

import numpy as np

from ai.deep_rl.user.features import ACTIONS, PLANES

_STATE_BYTES = PLANES * 64 // 8
_MASK_BYTES = ACTIONS // 8


class ReplayBuffer:
    """Lưu tối đa ``capacity`` chuyển tiếp; đầy thì ghi đè mẫu cũ nhất."""

    def __init__(self, capacity: int) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        self.capacity = capacity
        self.states = np.zeros((capacity, _STATE_BYTES), dtype=np.uint8)
        self.next_states = np.zeros((capacity, _STATE_BYTES), dtype=np.uint8)
        self.next_masks = np.zeros((capacity, _MASK_BYTES), dtype=np.uint8)
        self.actions = np.zeros(capacity, dtype=np.int64)
        self.rewards = np.zeros(capacity, dtype=np.float32)
        self.dones = np.zeros(capacity, dtype=np.float32)
        self._next = 0
        self._size = 0

    def __len__(self) -> int:
        return self._size

    def add(
        self,
        state: np.ndarray,
        action: int,
        reward: float,
        next_state: np.ndarray,
        done: bool,
        next_mask: np.ndarray,
    ) -> None:
        """Thêm một chuyển tiếp; ``state``/``next_state`` là ``uint8 (18, 8, 8)``."""
        index = self._next
        self.states[index] = np.packbits(state.reshape(-1))
        self.next_states[index] = np.packbits(next_state.reshape(-1))
        self.next_masks[index] = np.packbits(next_mask)
        self.actions[index] = action
        self.rewards[index] = reward
        self.dones[index] = float(done)
        self._next = (index + 1) % self.capacity
        self._size = min(self._size + 1, self.capacity)

    def sample(self, batch_size: int, rng: np.random.Generator) -> dict[str, np.ndarray]:
        """Lấy ngẫu nhiên ``batch_size`` mẫu, đã giải nén."""
        if self._size == 0:
            raise ValueError("cannot sample from an empty buffer")
        index = rng.integers(0, self._size, size=batch_size)
        shape = (batch_size, PLANES, 8, 8)
        return {
            "states": np.unpackbits(self.states[index], axis=1).reshape(shape),
            "actions": self.actions[index],
            "rewards": self.rewards[index],
            "next_states": np.unpackbits(self.next_states[index], axis=1).reshape(shape),
            "next_masks": np.unpackbits(self.next_masks[index], axis=1).astype(np.bool_),
            "dones": self.dones[index],
        }
