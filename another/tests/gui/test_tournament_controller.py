"""Đặc tả tiến trình của bộ điều khiển giải xếp hạng AI."""

from gui.tournament_controller import TournamentSnapshot


def make_snapshot(**overrides) -> TournamentSnapshot:
    values = {
        "running": True,
        "finished": False,
        "stopped": False,
        "games_done": 0,
        "games_total": 10,
        "current_pair": None,
        "standings": (),
        "result": None,
        "error": None,
        "plies_current": 0,
        "plies_limit": 100,
    }
    values.update(overrides)
    return TournamentSnapshot(**values)


def test_progress_is_zero_before_the_first_move():
    assert make_snapshot().progress == 0.0


def test_progress_counts_plies_inside_the_current_game():
    # 1 ván xong + 50/100 nước của ván đang đấu, trên tổng 10 ván.
    assert make_snapshot(games_done=1, plies_current=50).progress == 0.15
    assert make_snapshot(plies_current=50).progress == 0.05


def test_progress_is_clamped_and_never_divides_by_zero():
    assert make_snapshot(games_total=0).progress == 0.0
    assert make_snapshot(games_done=10, plies_current=100).progress == 1.0
    assert make_snapshot(games_done=9, plies_current=999).progress == 1.0
    assert make_snapshot(plies_limit=0, plies_current=5).progress == 0.0
