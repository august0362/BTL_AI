"""Chủ sở hữu cài logic chọn nước và cập nhật tác nhân tại đây.

Dùng ``encoding`` để mã hóa bàn cờ, ``env.ChessEnv`` để tương tác, và
``opponents`` để chọn đối thủ. Ghi tiến trình bằng ``metrics.MetricsLogger``.
Dự kiến chữ ký: ``Agent(model, ...)``, ``select_action(board, training=False)``
và ``update(batch)``. Không đặt thuật toán học trong hạ tầng chung.
"""


class Agent:
    """Chỗ đặt tác nhân do chủ sở hữu tự triển khai."""

    def __init__(self, model: object, **kwargs: object) -> None:
        raise NotImplementedError

    def select_action(self, board: object, training: bool = False) -> object:
        """Chọn nước đi hoặc chỉ số hành động cho bàn cờ."""
        raise NotImplementedError

    def update(self, batch: object) -> dict:
        """Cập nhật mô hình từ một batch dữ liệu."""
        raise NotImplementedError
