"""Chủ sở hữu cài bộ nạp policy suy luận tại đây.

Dùng ``encoding`` để tiền xử lý bàn cờ; ``env`` và ``opponents`` hỗ trợ kiểm
tra policy; ``metrics`` dùng cho đánh giá ngoài quá trình chơi. Trả về đối
tượng thỏa ``ai.deep_rl.policy_api.Policy``. Chữ ký bắt buộc:
``load_policy(weights_path: Path | None, device: str = "cpu") -> Policy``.
"""

from pathlib import Path

from ai.deep_rl.policy_api import Policy


def load_policy(weights_path: Path | None, device: str = "cpu") -> Policy:
    """Nạp trọng số và trả về policy do chủ sở hữu tự triển khai."""
    raise NotImplementedError
