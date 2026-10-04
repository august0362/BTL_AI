"""Chủ sở hữu cài mạng PyTorch tại đây; dùng đầu vào từ ``encoding.encode_board``.

Hãy dùng ``encoding.encode_board`` hoặc ``encoding.encode_afterstates`` để tạo
tensor đầu vào. ``env.ChessEnv`` cung cấp các ván để lấy dữ liệu huấn luyện.
Dự kiến chữ ký: ``Model.__init__(self)`` và ``Model.forward(self, observations)``.
"""


class Model:
    """Chỗ đặt mô hình do chủ sở hữu tự triển khai."""

    def __init__(self) -> None:
        raise NotImplementedError

    def forward(self, observations: object) -> object:
        """Tính đầu ra của mô hình từ batch quan sát."""
        raise NotImplementedError
