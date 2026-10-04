"""Chủ sở hữu cài bộ nhớ kinh nghiệm tại đây.

Dùng ``encoding`` để lưu quan sát ở dạng số và ``env.ChessEnv`` để lấy chuyển
tiếp trạng thái, phần thưởng, kết thúc. ``metrics`` có thể ghi thống kê lấy mẫu.
Dự kiến chữ ký: ``ReplayBuffer(capacity)``, ``add(state, action, reward,
next_state, done)`` và ``sample(batch_size)``.
"""


class ReplayBuffer:
    """Chỗ đặt bộ nhớ replay do chủ sở hữu tự triển khai."""

    def __init__(self, capacity: int) -> None:
        raise NotImplementedError

    def add(
        self, state: object, action: object, reward: float, next_state: object, done: bool
    ) -> None:
        """Thêm một chuyển tiếp vào bộ nhớ."""
        raise NotImplementedError

    def sample(self, batch_size: int) -> object:
        """Lấy một batch chuyển tiếp."""
        raise NotImplementedError
