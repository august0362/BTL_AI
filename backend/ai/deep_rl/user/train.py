"""Chủ sở hữu cài vòng lặp huấn luyện tại đây.

Dùng ``env.ChessEnv`` để tạo ván, ``encoding`` cho đầu vào, ``opponents`` để
trộn đối thủ, và ``metrics.MetricsLogger`` để ghi loss/tỷ lệ thắng/epsilon.
Dự kiến chữ ký: ``main(argv: list[str] | None = None) -> int``; lệnh notebook
gọi ``python -m ai.deep_rl.user.train --out <thư_mục>``.
"""


def main(argv: list[str] | None = None) -> int:
    """Điểm vào vòng lặp huấn luyện do chủ sở hữu tự viết."""
    raise NotImplementedError


if __name__ == "__main__":
    raise SystemExit(main())
