"""Đang chạy baseline ngẫu nhiên. Thay toàn bộ lớp này bằng bot thật; bỏ kế thừa
RandomBaselineBot."""

from ai.baseline import RandomBaselineBot


class GeneticAlphaBetaBot(RandomBaselineBot):
    """Đang chạy baseline ngẫu nhiên. Thay toàn bộ lớp này bằng bot thật; bỏ kế thừa
    RandomBaselineBot."""

    bot_id = "genetic_alphabeta"
    display_name = "Genetic Alpha-Beta"
