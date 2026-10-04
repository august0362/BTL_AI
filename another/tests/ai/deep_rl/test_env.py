import chess
import pytest

from ai.deep_rl.env import ChessEnv, RewardConfig
from ai.deep_rl.opponents import RandomOpponent


class FirstMoveOpponent:
    def select_move(self, board, rng=None):
        return next(iter(board.legal_moves))


def test_reset_step_opponent_reply_and_seeded_determinism() -> None:
    first = ChessEnv(opponent=RandomOpponent(), agent_color="random", seed=12)
    second = ChessEnv(opponent=RandomOpponent(), agent_color="random", seed=12)
    obs1, info1 = first.reset()
    obs2, info2 = second.reset()
    assert (obs1 == obs2).all()
    assert info1["agent_color"] == info2["agent_color"]
    move1, move2 = info1["legal_moves"][0], info2["legal_moves"][0]
    next1 = first.step(move1)
    next2 = second.step(move2)
    assert first.board.fen() == second.board.fen()
    assert next1[2:4] == next2[2:4]
    expected_plies = 2 if info1["agent_color"] == chess.WHITE else 3
    assert next1[4]["plies"] == expected_plies


def test_win_loss_draw_rewards_and_material_shaping() -> None:
    env = ChessEnv(agent_color=chess.WHITE, reward=RewardConfig(win=2, draw=0.5, loss=-3))
    env.reset()
    env.board.set_fen("7k/8/5KQ1/8/8/8/8/8 w - - 0 1")
    env.plies = 0
    move = chess.Move.from_uci("g6g7")
    _, reward, terminated, _, _ = env.step(move)
    assert terminated
    assert reward == 2

    loss_env = ChessEnv(agent_color=chess.WHITE, reward=RewardConfig(loss=-3))
    _, loss_info = loss_env.reset()
    loss_env._result = lambda: chess.Outcome(
        termination=chess.Termination.CHECKMATE,
        winner=chess.BLACK,
    )
    _, loss_reward, loss_terminated, _, _ = loss_env.step(loss_info["legal_moves"][0])
    assert loss_terminated and loss_reward == -3

    material_env = ChessEnv(
        opponent=FirstMoveOpponent(),
        agent_color=chess.WHITE,
        reward=RewardConfig(material_coef=0.1),
    )
    material_env.reset()
    material_env.board.set_fen("4k3/8/8/3q4/8/8/8/3RK2R w - - 0 1")
    capture = chess.Move.from_uci("d1d5")
    assert capture in material_env.board.legal_moves
    _, shaped, _, _, _ = material_env.step(capture)
    assert shaped > 0


def test_draw_and_truncation() -> None:
    env = ChessEnv(agent_color=chess.WHITE)
    env.reset()
    env.board.set_fen("7k/8/6K1/8/8/8/8/8 w - - 0 1")
    _, reward, terminated, truncated, _ = env.step(next(iter(env.board.legal_moves)))
    assert terminated and reward == 0 and not truncated

    limited = ChessEnv(agent_color=chess.WHITE, max_plies=1)
    _, info = limited.reset()
    _, _, terminated, truncated, info = limited.step(info["legal_moves"][0])
    assert not terminated and truncated and info["plies"] == 1


def test_step_rejects_illegal_move_and_calls_opponent() -> None:
    env = ChessEnv(opponent=FirstMoveOpponent(), agent_color=chess.WHITE)
    _, info = env.reset()
    with pytest.raises(ValueError):
        env.step(chess.Move.from_uci("e2e5"))
    _, _, _, _, next_info = env.step(info["legal_moves"][0])
    assert next_info["plies"] == 2
