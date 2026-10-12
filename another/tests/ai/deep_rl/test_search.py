import chess
import pytest

torch = pytest.importorskip("torch")

from ai.deep_rl.bot import DeepRLBot  # noqa: E402
from ai.deep_rl.user.model import Model  # noqa: E402
from ai.deep_rl.user.policy import DQNPolicy, load_policy, save_weights  # noqa: E402
from ai.deep_rl.user.search import MATE, AlphaBetaPolicy  # noqa: E402

MATE_IN_ONE = "6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1"  # Ra8#


def _model() -> Model:
    torch.manual_seed(0)
    return Model(channels=8, blocks=1).eval()


@pytest.mark.parametrize("depth", [2, 3])
def test_search_finds_mate_in_one(depth: int) -> None:
    policy = AlphaBetaPolicy(_model(), depth=depth, max_think_time_s=0)
    board = chess.Board(MATE_IN_ONE)
    assert policy.select_move(board) == chess.Move.from_uci("a1a8")
    assert policy.last_info["depth"] == depth
    assert policy.last_info["eval"] > MATE - 1
    assert board.fen() == MATE_IN_ONE  # board restored


def test_depth_three_avoids_back_rank_mate() -> None:
    board = chess.Board("6k1/5ppp/8/8/8/8/8/R5K1 b - - 0 1")  # threat: Ra8#
    board.push(AlphaBetaPolicy(_model(), depth=3, max_think_time_s=0).select_move(board))
    assert not any(_mates(board, reply) for reply in board.legal_moves)


def _mates(board: chess.Board, move: chess.Move) -> bool:
    board.push(move)
    try:
        return board.is_checkmate()
    finally:
        board.pop()


def test_depth_one_matches_argmax_policy() -> None:
    model = _model()
    board = chess.Board()
    search = AlphaBetaPolicy(model, depth=1, max_think_time_s=0)
    assert search.select_move(board) == DQNPolicy(model).select_move(board)


def test_time_limit_falls_back_to_completed_depth() -> None:
    policy = AlphaBetaPolicy(_model(), depth=3, max_think_time_s=1e-9)
    board = chess.Board()
    assert policy.select_move(board) in board.legal_moves
    assert policy.last_info["depth"] == 1


def test_load_policy_depth_and_bot_config(tmp_path, monkeypatch) -> None:
    path = tmp_path / "w.pt"
    save_weights(_model(), path)
    assert isinstance(load_policy(path), DQNPolicy)
    assert isinstance(load_policy(path, depth=3), AlphaBetaPolicy)

    monkeypatch.setattr("ai.deep_rl.bot.resolve_weights", lambda url, sha: path)
    bot = DeepRLBot({"depth": 2, "max_think_time_s": 0})
    assert isinstance(bot.policy, AlphaBetaPolicy) and bot.policy.depth == 2
    board = chess.Board(MATE_IN_ONE)
    assert bot.select_move(board) == chess.Move.from_uci("a1a8")
    assert bot.last_search_info["depth"] == 2
