"""PUCT Monte Carlo tree search guided by ``PolicyValueNet``, batched across many games.

Values are kept as a pair ``(u_white, u_black)`` all the way up the tree. At each node the
player to move picks children by *their own* component (general-sum / Max-N style backup),
so a draw stays -0.1 for both sides instead of being negated. Terminal nodes use the exact
chess utilities from ``rules``; non-terminal leaves use the network's value pair.

Network value pair convention: ``values[0]`` = payoff of the side to move at that position,
``values[1]`` = payoff of the other side. ``_expand`` converts it to the absolute
``(u_white, u_black)`` pair, so changing perspective is a component swap, never a negation.

One simulation per tree per network call: ``run_simulations`` walks every tree to a leaf,
evaluates all new leaves in one batch, then expands and backs up. An optional ``value_fn``
replaces only the leaf value (priors still come from the policy head); it is used to compare
the learned value with a handcrafted heuristic under the same search.
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable
from dataclasses import dataclass, field

import chess
import numpy as np
import torch

from ..v20.features import encode
from ..v20.moves import legal_actions
from ..v20.rules import outcome
from .model import PolicyValueNet
from .rules import utility

ValueFn = Callable[[chess.Board], tuple[float, float]]  # (side to move, other side)


@dataclass(frozen=True)
class MCTSConfig:
    """Search parameters; ``time_limit_s`` > 0 bounds single-game play (bot / evaluation)."""

    simulations: int = 96
    c_puct: float = 1.5
    fpu_reduction: float = 0.2
    dirichlet_alpha: float = 0.3
    dirichlet_fraction: float = 0.25
    time_limit_s: float = 0.0

    def __post_init__(self) -> None:
        if self.simulations < 1 or self.c_puct <= 0:
            raise ValueError("simulations and c_puct must be positive")
        if not 0 <= self.dirichlet_fraction <= 1 or self.time_limit_s < 0:
            raise ValueError("invalid Dirichlet fraction or time limit")


@dataclass
class Node:
    """A position reached in the tree; edge statistics are stored on the parent."""

    to_play: chess.Color
    terminal: tuple[float, float] | None = None
    moves: list[chess.Move] = field(default_factory=list)
    actions: np.ndarray | None = None
    prior: np.ndarray | None = None
    visits: np.ndarray | None = None  # N per child
    value_sum: np.ndarray | None = None  # sum of the mover's utility per child
    children: dict[int, Node] = field(default_factory=dict)
    estimate: float = 0.0  # network value for ``to_play`` (used for first-play urgency)

    @property
    def expanded(self) -> bool:
        """True once legal moves and priors are known."""
        return self.prior is not None

    def select(self, config: MCTSConfig) -> int:
        """PUCT child index from the mover's perspective."""
        total = float(self.visits.sum())
        q = np.where(
            self.visits > 0,
            self.value_sum / np.maximum(self.visits, 1),
            self.estimate - config.fpu_reduction,
        )
        u = config.c_puct * self.prior * math.sqrt(total + 1) / (1 + self.visits)
        return int(np.argmax(q + u))


def _pair_index(color: chess.Color) -> int:
    return 0 if color == chess.WHITE else 1


@torch.inference_mode()
def infer(
    model: PolicyValueNet, states: np.ndarray, device: str | torch.device
) -> tuple[np.ndarray, np.ndarray]:
    """Batched network call on ``features.encode`` states (encoded from boards that keep their
    move stack); returns ``(logits (B, 4672), values (B, 2))``."""
    logits, values = model(torch.from_numpy(states).to(device))
    return logits.float().cpu().numpy(), values.float().cpu().numpy()


def _expand(
    node: Node,
    moves: list[chess.Move],
    actions: np.ndarray,
    logits: np.ndarray,
    values: np.ndarray,
) -> tuple[float, float]:
    """Fill priors from masked softmax logits; return the leaf's (u_white, u_black)."""
    legal = logits[actions].astype(np.float64)
    legal = np.exp(legal - legal.max())
    node.moves, node.actions = moves, actions
    node.prior = legal / legal.sum()
    node.visits = np.zeros(len(moves), dtype=np.float64)
    node.value_sum = np.zeros(len(moves), dtype=np.float64)
    mover, other = float(values[0]), float(values[1])
    node.estimate = mover
    return (mover, other) if node.to_play == chess.WHITE else (other, mover)


def add_dirichlet(node: Node, config: MCTSConfig, rng: np.random.Generator) -> None:
    """Mix exploration noise into an expanded root's priors."""
    if config.dirichlet_fraction <= 0 or len(node.moves) < 2:
        return
    noise = rng.dirichlet([config.dirichlet_alpha] * len(node.moves))
    node.prior = (1 - config.dirichlet_fraction) * node.prior + config.dirichlet_fraction * noise


@dataclass
class Tree:
    """A search rooted at ``board`` (pushed/popped in place, restored after every step)."""

    board: chess.Board
    root: Node = field(init=False)
    noise: bool = False
    max_depth: int = 0

    def __post_init__(self) -> None:
        self.root = Node(self.board.turn)


def run_simulations(
    trees: list[Tree],
    model: PolicyValueNet,
    device: str | torch.device,
    config: MCTSConfig,
    simulations: int,
    rng: np.random.Generator,
    deadline: float = math.inf,
    value_fn: ValueFn | None = None,
) -> int:
    """Run up to ``simulations`` simulations on every tree; returns network calls made."""
    calls = 0
    for _ in range(simulations):
        if time.perf_counter() >= deadline:
            break
        pending: list[tuple[Tree, Node, list[tuple[Node, int]], list[chess.Move], np.ndarray]] = []
        states: list[np.ndarray] = []
        leaf_values: list[tuple[float, float]] = []
        for tree in trees:
            board, node, path = tree.board, tree.root, []
            while node.expanded and node.terminal is None:
                index = node.select(config)
                path.append((node, index))
                board.push(node.moves[index])
                child = node.children.get(index)
                if child is None:
                    child = Node(board.turn)
                    result = outcome(board)
                    if result is not None:
                        child.terminal = (
                            utility(result.winner, chess.WHITE),
                            utility(result.winner, chess.BLACK),
                        )
                    node.children[index] = child
                node = child
            tree.max_depth = max(tree.max_depth, len(path))
            if node.terminal is not None:
                _backup(path, node.terminal)
            else:
                moves, actions = legal_actions(board)
                pending.append((tree, node, path, moves, actions))
                states.append(encode(board))
                if value_fn is not None:
                    leaf_values.append(value_fn(board))
            for _ in path:
                board.pop()
        if not pending:
            continue
        logits, values = infer(model, np.stack(states), device)
        calls += 1
        for row, (tree, node, path, moves, actions) in enumerate(pending):
            leaf = leaf_values[row] if value_fn is not None else values[row]
            pair = _expand(node, moves, actions, logits[row], leaf)
            if node is tree.root and tree.noise:
                add_dirichlet(node, config, rng)
            _backup(path, pair)
    return calls


def _backup(path: list[tuple[Node, int]], pair: tuple[float, float]) -> None:
    for node, index in path:
        node.visits[index] += 1
        node.value_sum[index] += pair[_pair_index(node.to_play)]


def visit_policy(root: Node) -> np.ndarray:
    """Root visit distribution over ``root.moves`` (the policy training target)."""
    total = root.visits.sum()
    if total <= 0:
        return root.prior.copy()
    return root.visits / total


def choose(root: Node, temperature: float, rng: np.random.Generator) -> int:
    """Sample by visits (temperature 1) or pick the most visited child (temperature 0)."""
    visits = root.visits if root.visits.sum() > 0 else root.prior
    if temperature > 0:
        weights = visits ** (1 / temperature)
        return int(rng.choice(len(weights), p=weights / weights.sum()))
    best = np.flatnonzero(visits == visits.max())
    return int(best[0] if len(best) == 1 else rng.choice(best))


class MCTSPolicy:
    """Single-game MCTS player with ``select_move`` (bot, evaluation and opponents)."""

    def __init__(
        self,
        model: PolicyValueNet,
        device: str | torch.device = "cpu",
        config: MCTSConfig | None = None,
        seed: int = 0,
        value_fn: ValueFn | None = None,
    ) -> None:
        self.model = model.to(device).eval()
        self.device = device
        self.config = config or MCTSConfig(dirichlet_fraction=0.0)
        self.rng = np.random.default_rng(seed)
        self.value_fn = value_fn
        self.last_search_info: dict[str, int | float | str] = {}

    def select_move(self, board: chess.Board) -> chess.Move:
        """Most visited legal move after the configured simulations or time budget.

        No root noise is used here (``Tree.noise`` defaults to False): evaluation is deterministic
        for a given seed and simulation count.
        """
        started = time.perf_counter()
        if not any(board.legal_moves):
            raise ValueError("cannot select a move from a position with no legal moves")
        tree = Tree(board.copy(stack=True))
        deadline = started + self.config.time_limit_s if self.config.time_limit_s else math.inf
        # Always finish at least the root expansion plus one simulation.
        search = (self.model, self.device, self.config)
        calls = run_simulations([tree], *search, 2, self.rng, value_fn=self.value_fn)
        calls += run_simulations(
            [tree],
            *search,
            max(0, self.config.simulations - 2),
            self.rng,
            deadline,
            self.value_fn,
        )
        root = tree.root
        index = choose(root, 0.0, self.rng)
        self.last_search_info = {
            "nodes": int(root.visits.sum()),
            "inference_calls": calls,
            "evaluator_calls": calls,
            "depth": tree.max_depth,
            "elapsed_s": time.perf_counter() - started,
            "mode": "mcts",
            "eval": float(root.value_sum[index] / max(root.visits[index], 1)),
        }
        return root.moves[index]
