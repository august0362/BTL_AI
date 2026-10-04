"""Đang chạy baseline ngẫu nhiên. Thay toàn bộ lớp này bằng bot thật; bỏ kế thừa
RandomBaselineBot."""

from ai.baseline import RandomBaselineBot


class AlphaBetaRegressionBot(RandomBaselineBot):
    """Đang chạy baseline ngẫu nhiên. Thay toàn bộ lớp này bằng bot thật; bỏ kế thừa
    RandomBaselineBot."""

    bot_id = "alphabeta_regression"
    display_name = "Alpha-Beta Regression"
