"""V20 phase selection, MCTS policy and loader; importing this module does not load torch."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any

import chess

if TYPE_CHECKING:
    from .alphabeta import V20AlphaBetaPolicy
    from .model import PolicyValueNet

V20_FORMAT = "v20-phase-experts-1"
PHASE_THRESHOLD = 0.5
PHASES = ("start", "mid", "end")
SEARCHES = ("mcts", "alphabeta", "hybrid", "ramp")
END_G = 4
END_GAMMA = 0.995


def material_phase(board: chess.Board) -> int:
    """Return G: four per queen, two per rook, and one per bishop or knight."""
    return sum(
        weight * (len(board.pieces(piece, True)) + len(board.pieces(piece, False)))
        for piece, weight in (
            (chess.QUEEN, 4),
            (chess.ROOK, 2),
            (chess.BISHOP, 1),
            (chess.KNIGHT, 1),
        )
    )


def mid_probability(board: chess.Board) -> float:
    """Return the clipped V20 probability of switching from START to MID."""
    return max(0.0, min(1.0, (board.ply() - 16) / 20 + 0.2 * (24 - material_phase(board)) / 16))


def select_phase(board: chess.Board, threshold: float = PHASE_THRESHOLD) -> str:
    """Replay this side's positions to recover its one-way START/MID/END phase."""
    turn = board.turn
    position = board.root()
    max_probability = 0.0
    for index in range(len(board.move_stack) + 1):
        if position.turn == turn:
            if material_phase(position) <= 8:
                return "end"
            max_probability = max(max_probability, mid_probability(position))
        if index < len(board.move_stack):
            position.push(board.move_stack[index])
    return "mid" if max_probability >= threshold else "start"


def end_moves(board: chess.Board, end_g: int = END_G) -> int:
    """Count this side's positions from its first one with G <= ``end_g`` (0 = none yet)."""
    turn = board.turn
    position = board.root()
    count = 0
    for index in range(len(board.move_stack) + 1):
        if position.turn == turn and (count or material_phase(position) <= end_g):
            count += 1
        if index < len(board.move_stack):
            position.push(board.move_stack[index])
    return count


def end_probability(moves: int, ramp_moves: int) -> float:
    """Return the chance of using the END net on this side's ``moves``-th move after G <= end_g."""
    return min(1.0, moves / ramp_moves)


class V20Policy:
    """Choose the root phase's expert, then play its most visited MCTS move."""

    def __init__(
        self, models: dict[str, PolicyValueNet], device: str = "cpu", simulations: int = 96
    ) -> None:
        if simulations < 1:
            raise ValueError("simulations must be positive")
        self.models = models
        self.device = device
        self.simulations = simulations
        self.last_info: dict[str, Any] = {}

    def select_move(self, board: chess.Board) -> chess.Move:
        """Search with one expert and retain phase, visit budget, nodes, and Q."""
        from .search import search

        phase = select_phase(board)
        moves, visits, q, nodes = search(board, self.models[phase], self.device, self.simulations)
        best = int(visits.argmax())
        self.last_info = {
            "mode": "mcts",
            "phase": phase,
            "simulations": self.simulations,
            "nodes": nodes,
            "eval": float(q[best]),
        }
        return moves[best]


class V20HybridPolicy:
    """Alpha-beta while the root phase is START or MID, MCTS once it is END.

    The END expert's Tablebase knowledge sits in its policy, which only MCTS follows; alpha-beta
    keeps the tactical safety in the opening and middlegame.
    """

    def __init__(self, alphabeta: V20AlphaBetaPolicy, mcts: V20Policy) -> None:
        self.alphabeta = alphabeta
        self.mcts = mcts
        self.last_info: dict[str, Any] = {}

    def select_move(self, board: chess.Board) -> chess.Move:
        """Delegate to the search of the current phase; ``last_info["search"]`` names it."""
        player = self.mcts if select_phase(board) == "end" else self.alphabeta
        move = player.select_move(board)
        self.last_info = {**player.last_info, "mode": "hybrid", "search": player.last_info["mode"]}
        return move


class V20RampPolicy:
    """MCTS with the START/MID net while G > ``end_g``; afterwards the END net is picked with a
    probability that grows ``1/ramp_moves`` per own move (§7.1).

    The search evaluates ``batch_size`` leaves per forward pass, runs up to ``simulations`` new
    simulations per move and may keep its subtree for up to ``tree_reuse`` plies; ``widening``
    and ``early_stop`` are described in ``batched.TreeSearch``. A positive
    ``max_think_time_s`` also limits the search time per move.
    """

    def __init__(
        self,
        models: dict[str, PolicyValueNet],
        device: str = "cpu",
        simulations: int = 200,
        end_g: int = END_G,
        ramp_moves: int = 10,
        seed: int | None = None,
        batch_size: int = 32,
        tree_reuse: int = 0,
        widening: bool = False,
        early_stop: bool = False,
        max_think_time_s: float = 0.0,
    ) -> None:
        from .batched import TreeSearch

        if ramp_moves < 1:
            raise ValueError("ramp_moves must be positive")
        self.tree = TreeSearch(
            device,
            simulations,
            batch_size,
            tree_reuse,
            widening=widening,
            early_stop=early_stop,
            max_think_time_s=max_think_time_s,
        )
        self.models = models
        self.simulations = simulations
        self.end_g = end_g
        self.ramp_moves = ramp_moves
        self.rng = random.Random(seed)
        self.last_info: dict[str, Any] = {}

    def select_move(self, board: chess.Board) -> chess.Move:
        """Draw the net for this move, search with it and keep the draw in ``last_info``."""
        p_end = end_probability(end_moves(board, self.end_g), self.ramp_moves)
        net = "end" if self.rng.random() < p_end else "mid"
        gamma = END_GAMMA if net == "end" else 1.0
        moves, visits, q, nodes, reused = self.tree.run(board, self.models[net], gamma)
        best = int(visits.argmax())
        if not visits.any():
            assert self.tree.root is not None and self.tree.root.prior is not None
            best = int(self.tree.root.prior.argmax())
        self.last_info = {
            "mode": "ramp",
            "phase": net,
            "p_end": p_end,
            "simulations": self.simulations,
            "nodes": nodes,
            "reused": reused,
            "eval": float(q[best]),
            **self.tree.stats,
        }
        return moves[best]


def load_v20_policy(
    data: dict[str, Any],
    device: str = "cpu",
    simulations: int = 96,
    search: str = "mcts",
    depth: int = 3,
    max_think_time_s: float = 1.0,
    end_g: int = END_G,
    ramp_moves: int = 10,
    batch_size: int = 32,
    tree_reuse: int = 0,
    widening: bool = False,
    early_stop: bool = False,
) -> V20Policy | V20AlphaBetaPolicy | V20HybridPolicy | V20RampPolicy:
    """Validate packed V20 weights and strictly load all three phase experts.

    ``search = "mcts"`` plays ``simulations`` PUCT visits per move; ``"alphabeta"`` plays
    alpha-beta to ``depth`` within ``max_think_time_s`` seconds; ``"hybrid"`` plays alpha-beta
    in START/MID and MCTS in END; ``"ramp"`` plays MCTS and moves from the MID net to the END net
    over ``ramp_moves`` own moves once G <= ``end_g``, batching ``batch_size`` leaves per forward
    pass, reusing the subtree for up to ``tree_reuse`` plies, with optional progressive
    ``widening`` and ``early_stop`` (§7.1), within ``max_think_time_s`` seconds (0 = unlimited).
    """
    from .model import PolicyValueNet

    if search not in SEARCHES:
        raise ValueError(f"search must be one of {SEARCHES}")
    if not isinstance(data, dict) or data.get("format") != V20_FORMAT:
        raise ValueError(f"weights must have format {V20_FORMAT}")
    config = data.get("model_config")
    states = data.get("models")
    if not isinstance(config, dict) or not isinstance(states, dict) or set(states) != set(PHASES):
        raise ValueError("V20 weights require model_config and exactly start, mid, end models")
    models = {}
    try:
        for phase in PHASES:
            if not isinstance(states[phase], dict):
                raise ValueError(f"invalid state dictionary for {phase}")
            model = PolicyValueNet(**config).to(device)
            model.load_state_dict(states[phase], strict=True)
            models[phase] = model.eval()
    except (TypeError, RuntimeError, ValueError) as exc:
        raise ValueError(f"invalid V20 weights: {exc}") from exc
    if search == "mcts":
        return V20Policy(models, device, simulations)
    if search == "ramp":
        return V20RampPolicy(
            models,
            device,
            simulations,
            end_g,
            ramp_moves,
            None,
            batch_size,
            tree_reuse,
            widening,
            early_stop,
            max_think_time_s=max_think_time_s,
        )
    from .alphabeta import V20AlphaBetaPolicy

    alphabeta = V20AlphaBetaPolicy(models, device, depth, max_think_time_s)
    if search == "alphabeta":
        return alphabeta
    return V20HybridPolicy(alphabeta, V20Policy(models, device, simulations))
