"""Fresh-tree scalar-value PUCT search matching V20 without root noise."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import chess
import numpy as np
import torch

from .features import encode_masks, unpack_torch
from .model import PolicyValueNet
from .moves import legal_actions
from .rules import outcome, utility


@dataclass
class Node:
    """A position and its outgoing edge statistics, in its side-to-move view."""

    to_play: chess.Color
    moves: list[chess.Move] = field(default_factory=list)
    actions: np.ndarray | None = None
    prior: np.ndarray | None = None
    visits: np.ndarray | None = None
    sums: np.ndarray | None = None
    children: dict[int, Node] = field(default_factory=dict)
    estimate: float = 0.0
    terminal: float | None = None
    order: np.ndarray | None = None
    forced: np.ndarray | None = None

    @property
    def expanded(self) -> bool:
        """Whether network inference has initialized the outgoing edges."""
        return self.prior is not None

    def select(self, c_puct: float, mask: np.ndarray | None = None) -> int:
        """Choose the largest PUCT score, using parent value minus 0.2 as FPU.

        ``mask`` (progressive widening) limits the choice to its ``True`` edges.
        """
        visits = self.visits
        assert visits is not None and self.sums is not None and self.prior is not None
        q = np.where(visits > 0, self.sums / np.maximum(1, visits), self.estimate - 0.2)
        bonus = c_puct * self.prior * math.sqrt(float(visits.sum()) + 1) / (1 + visits)
        score = q + bonus
        if mask is not None:
            score = np.where(mask, score, -np.inf)
        return int(np.argmax(score))


def _infer(
    model: PolicyValueNet, board: chess.Board, device: str | torch.device
) -> tuple[np.ndarray, float]:
    planes = np.asarray([encode_masks(board)], dtype=np.uint64)
    with torch.inference_mode():
        tensors = unpack_torch(torch.from_numpy(planes.view(np.int64)).to(device))
        logits, values = model(tensors)
    return logits.float().cpu().numpy()[0], float(values.float().cpu().numpy().reshape(-1)[0])


def _expand(node: Node, board: chess.Board, logits: np.ndarray, value: float) -> None:
    _set_edges(node, *legal_actions(board), logits, value)


def _set_edges(
    node: Node, moves: list[chess.Move], actions: np.ndarray, logits: np.ndarray, value: float
) -> None:
    z = logits[actions].astype(np.float64)
    z -= z.max()
    p = np.exp(z)
    node.moves = moves
    node.actions = actions
    node.prior = p / p.sum()
    node.visits = np.zeros(len(moves), dtype=np.int32)
    node.sums = np.zeros(len(moves), dtype=np.float64)
    node.estimate = float(value)


def _backup(
    path: list[tuple[Node, int]], value: float, gamma: float = 1.0, terminal: bool = False
) -> None:
    """Negate the leaf's side-to-move value at each preceding ply, discounting by ``gamma``.

    A terminal leaf's last edge is not discounted (V22 END convention); ``gamma = 1`` is V20.
    """
    for depth, (parent, index) in enumerate(reversed(path)):
        value = -value if (terminal and depth == 0) or gamma == 1.0 else -gamma * value
        assert parent.visits is not None and parent.sums is not None
        parent.visits[index] += 1
        parent.sums[index] += value


def search(
    board: chess.Board,
    model: PolicyValueNet,
    device: str | torch.device,
    simulations: int,
    c_puct: float = 1.5,
    gamma: float = 1.0,
) -> tuple[list[chess.Move], np.ndarray, np.ndarray, int]:
    """Return moves, visits, Q, and evaluated positions (including terminal leaves).

    Expand the root, then run ``simulations`` root visits, as in the Kaggle search.
    Preserve the input board and its full history; use one model throughout the tree.
    """
    if simulations < 1 or c_puct <= 0 or not 0 < gamma <= 1:
        raise ValueError("invalid MCTS configuration")
    if outcome(board) is not None:
        raise ValueError("cannot search a terminal position")
    board = board.copy(stack=True)
    root = Node(board.turn)
    logits, value = _infer(model, board, device)
    _expand(root, board, logits, value)
    positions = 1
    for _ in range(simulations):
        node = root
        path: list[tuple[Node, int]] = []
        while node.expanded:
            index = node.select(c_puct)
            path.append((node, index))
            board.push(node.moves[index])
            child = node.children.get(index)
            if child is None:
                child = Node(board.turn)
                result = outcome(board)
                if result is not None:
                    child.terminal = utility(result.winner, board.turn)
                node.children[index] = child
            node = child
        if node.terminal is not None:
            _backup(path, node.terminal, gamma, terminal=True)
        else:
            logits, value = _infer(model, board, device)
            _expand(node, board, logits, value)
            _backup(path, value, gamma)
        positions += 1
        for _step in path:
            board.pop()
    assert root.visits is not None and root.sums is not None
    n = root.visits.astype(np.float64)
    q = np.where(n > 0, root.sums / np.maximum(1, n), 0.0)
    return root.moves, root.visits.copy(), q, positions
