"""Đang chạy baseline ngẫu nhiên. Thay toàn bộ lớp này bằng bot thật; bỏ kế thừa
RandomBaselineBot."""

from ai.baseline import RandomBaselineBot


class MctsBot(RandomBaselineBot):
    """Đang chạy baseline ngẫu nhiên. Thay toàn bộ lớp này bằng bot thật; bỏ kế thừa
    RandomBaselineBot."""

    bot_id = "mcts"
    display_name = "MCTS"
