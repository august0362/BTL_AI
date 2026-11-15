"""V20 phase experts searched with alpha-beta instead of MCTS (§7.1)."""

from __future__ import annotations

from pathlib import Path

import chess
import pytest

from ai.deep_rl.user import policy
from ai.deep_rl.v20.policy import PHASES, V20_FORMAT, V20Policy, load_v20_policy

torch = pytest.importorskip("torch")

from ai.deep_rl.bot import DeepRLBot  # noqa: E402
from ai.deep_rl.v20.alphabeta import V20AlphaBetaPolicy  # noqa: E402
from ai.deep_rl.v20.model import PolicyValueNet  # noqa: E402
from ai.deep_rl.v20.moves import ACTIONS, move_to_action  # noqa: E402

_TINY_CONFIG = {"channels": 8, "blocks": 1, "head_channels": 4}
MATE_IN_ONE = "6k1/5ppp/8/8/8/8/5PPP/R5K1 w - - 0 1"  # Ra8#
# Black threatens Ra1#; only Kh1 walks into it (every pawn move or Kf1 leaves an escape square).
BACK_RANK_THREAT = "r5k1/5ppp/8/8/8/8/5PPP/6K1 w - - 0 1"


def _data() -> dict:
    torch.manual_seed(0)
    state = PolicyValueNet(**_TINY_CONFIG).state_dict()
    return {
        "format": V20_FORMAT,
        "model_config": _TINY_CONFIG,
        "models": {phase: dict(state) for phase in PHASES},
    }


class _Trap(torch.nn.Module):
    """Every position is worth -1 to its side to move; the policy prefers Kh1."""

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        logits = torch.zeros(len(x), ACTIONS)
        logits[:, move_to_action(chess.Move.from_uci("g1h1"), chess.WHITE)] = 10.0
        return logits, -torch.ones(len(x), 1)


def test_plays_legal_moves_and_reports_search_info() -> None:
    player = load_v20_policy(_data(), search="alphabeta", depth=2, max_think_time_s=0)
    assert isinstance(player, V20AlphaBetaPolicy)
    board = chess.Board()
    for _ in range(4):
        snapshot = board.copy(stack=True)
        move = player.select_move(board)
        assert board == snapshot and board.move_stack == snapshot.move_stack
        assert move in board.legal_moves
        board.push(move)
        info = player.last_info
        assert info["mode"] == "alphabeta" and info["phase"] == "start"
        assert info["depth"] == 2 and info["nodes"] > 0 and info["time_s"] >= 0


@pytest.mark.parametrize("depth", [1, 2, 3])
def test_finds_mate_in_one_whatever_the_weights(depth: int) -> None:
    player = load_v20_policy(_data(), search="alphabeta", depth=depth, max_think_time_s=0)
    assert player.select_move(chess.Board(MATE_IN_ONE)) == chess.Move.from_uci("a1a8")
    assert player.last_info["phase"] == "end"
    assert player.last_info["eval"] == pytest.approx(3.0 - 0.01)


def test_depth_two_refuses_a_move_that_allows_mate_in_one() -> None:
    trap = _Trap()
    models = {phase: trap for phase in PHASES}
    shallow = V20AlphaBetaPolicy(models, depth=1, max_think_time_s=0)
    assert shallow.select_move(chess.Board(BACK_RANK_THREAT)) == chess.Move.from_uci("g1h1")
    deep = V20AlphaBetaPolicy(models, depth=2, max_think_time_s=0)
    board = chess.Board(BACK_RANK_THREAT)
    board.push(deep.select_move(board))
    assert not any(_is_mate(board, reply) for reply in board.legal_moves)


def _is_mate(board: chess.Board, reply: chess.Move) -> bool:
    board.push(reply)
    try:
        return board.is_checkmate()
    finally:
        board.pop()


def test_hybrid_uses_alphabeta_before_end_and_mcts_in_end() -> None:
    player = load_v20_policy(_data(), search="hybrid", simulations=8, depth=1, max_think_time_s=0)
    assert player.select_move(chess.Board()) in chess.Board().legal_moves
    assert player.last_info["mode"] == "hybrid" and player.last_info["search"] == "alphabeta"
    assert player.last_info["phase"] == "start"
    end = chess.Board(MATE_IN_ONE)
    assert player.select_move(end) in end.legal_moves
    assert player.last_info["search"] == "mcts" and player.last_info["phase"] == "end"
    assert player.last_info["simulations"] == 8


@pytest.mark.skipif(not torch.cuda.is_available(), reason="needs a CUDA GPU")
def test_cuda_graphs_match_the_plain_forward_pass() -> None:
    data = _data()
    gpu = load_v20_policy(data, "cuda", search="alphabeta", depth=2, max_think_time_s=0)
    cpu = load_v20_policy(data, "cpu", search="alphabeta", depth=2, max_think_time_s=0)
    board = chess.Board()
    for san in "e4 e5 Nf3".split():
        board.push_san(san)
    assert gpu.select_move(board) == cpu.select_move(board)
    assert gpu.last_info["nodes"] == cpu.last_info["nodes"]
    assert gpu.last_info["eval"] == pytest.approx(cpu.last_info["eval"], abs=1e-4)


def test_loader_routes_search_and_rejects_unknown(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "v20.pt"
    torch.save(_data(), path)
    assert isinstance(policy.load_policy(path), V20Policy)
    assert isinstance(policy.load_policy(path, search="alphabeta", depth=2), V20AlphaBetaPolicy)
    with pytest.raises(ValueError):
        policy.load_policy(path, search="foo")

    monkeypatch.setattr("ai.deep_rl.bot.resolve_weights", lambda url, sha: path)
    bot = DeepRLBot({"search": "alphabeta", "depth": 1, "max_think_time_s": 0})
    assert isinstance(bot.policy, V20AlphaBetaPolicy) and bot.policy.depth == 1
    board = chess.Board(MATE_IN_ONE)
    assert bot.select_move(board) == chess.Move.from_uci("a1a8")
    assert bot.last_search_info["mode"] == "alphabeta"


def test_ramp_counts_own_moves_after_g_threshold() -> None:
    from ai.deep_rl.v20.policy import end_moves, end_probability

    board = chess.Board("4k3/8/8/8/8/8/8/R3K3 w - - 0 1")  # G = 2
    assert end_moves(chess.Board()) == 0 and end_moves(board) == 1
    board.push_san("Ra2")
    board.push_san("Kd7")
    assert end_moves(board) == 2
    assert end_probability(0, 10) == 0.0 and end_probability(2, 10) == 0.2
    assert end_probability(15, 10) == 1.0


def test_ramp_policy_uses_mid_before_threshold_and_end_after_ramp() -> None:
    player = load_v20_policy(_data(), search="ramp", simulations=4, ramp_moves=1)
    assert player.select_move(chess.Board()) in chess.Board().legal_moves
    assert player.last_info["phase"] == "mid" and player.last_info["p_end"] == 0.0
    endgame = chess.Board("4k3/8/8/8/8/8/8/R3K3 w - - 0 1")
    assert player.select_move(endgame) in endgame.legal_moves
    assert player.last_info["phase"] == "end" and player.last_info["mode"] == "ramp"


def test_tree_search_matches_plain_search_and_starts_fresh_each_move() -> None:
    import numpy as np

    from ai.deep_rl.v20.search import search
    from ai.deep_rl.v20.tree import TreeSearch

    torch.manual_seed(0)
    model = PolicyValueNet(**_TINY_CONFIG).eval()
    board = chess.Board()
    plain = search(board, model, "cpu", 24, gamma=0.995)
    tree = TreeSearch("cpu", 24)
    moves, visits, q, nodes = tree.run(board, model, 0.995)
    assert moves == plain[0] and np.array_equal(visits, plain[1]) and np.allclose(q, plain[2])
    assert nodes == plain[3] == 25 and tree.stats["new_simulations"] == 24
    assert tree.stats["stop_reason"] is None
    board.push(moves[int(visits.argmax())])
    _moves, visits, _q, _nodes = tree.run(board, model)
    assert visits.sum() == 24  # no subtree kept from the previous move
    with pytest.raises(ValueError):
        tree.run(chess.Board("k7/1Q6/1K6/8/8/8/8/8 b - - 0 1"), model)  # checkmated: terminal
