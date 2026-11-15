"""PUCT on a fresh tree each move, limited by a simulation count and a time budget."""

from __future__ import annotations

import logging
import math
import time
from typing import Any

import chess
import numpy as np
import torch

from .model import PolicyValueNet
from .moves import legal_actions
from .rules import outcome, utility
from .search import Node, _backup, _infer, _set_edges

log = logging.getLogger(__name__)


class TreeSearch:
    """PUCT that builds a new tree every move and evaluates one leaf per network call.

    Each move runs up to ``simulations`` simulations. A positive ``max_think_time_s`` stops
    before the next simulation once its budget expires; zero leaves the search limited only by
    the simulation count, which then equals ``search.search``.
    """

    def __init__(
        self,
        device: str | torch.device = "cpu",
        simulations: int = 200,
        c_puct: float = 1.5,
        max_think_time_s: float = 0.0,
    ) -> None:
        if simulations < 1 or c_puct <= 0:
            raise ValueError("invalid MCTS configuration")
        self.device = device
        self.simulations = simulations
        self.c_puct = c_puct
        self.max_think_time_s = max_think_time_s
        self.root: Node | None = None
        self.stats: dict[str, Any] = {}

    def run(
        self,
        board: chess.Board,
        model: PolicyValueNet,
        gamma: float = 1.0,
    ) -> tuple[list[chess.Move], np.ndarray, np.ndarray, int]:
        """Return moves, root visits, Q and evaluated positions (including terminal leaves).

        Per-move diagnostics are kept in ``self.stats``; the input board is left unchanged.
        """
        if not 0 < gamma <= 1:
            raise ValueError("gamma must be in (0, 1]")
        if outcome(board) is not None:
            raise ValueError("cannot search a terminal position")
        started = time.perf_counter()
        limit = self.max_think_time_s
        deadline = started + limit if limit > 0 else math.inf
        board = board.copy(stack=True)
        root = Node(board.turn)
        logits, value = _infer(model, board, self.device)
        _set_edges(root, *legal_actions(board), logits, value)
        self.root = root
        done = depth_sum = depth_max = 0
        reason = None
        while done < self.simulations:
            if time.perf_counter() >= deadline:
                reason = "time_limit"
                break
            depth = self._simulate(root, board, model, gamma)
            done += 1
            depth_sum += depth
            depth_max = max(depth_max, depth)
        self.stats = {
            "new_simulations": done,
            "avg_leaf_depth": round(depth_sum / done, 2) if done else 0.0,
            "max_leaf_depth": depth_max,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
            "stop_reason": reason,
        }
        log.debug("mcts %s", self.stats)
        assert root.visits is not None and root.sums is not None
        n = root.visits.astype(np.float64)
        q = np.where(n > 0, root.sums / np.maximum(1, n), 0.0)
        return root.moves, root.visits.copy(), q, done + 1

    def _simulate(self, root: Node, board: chess.Board, model: PolicyValueNet, gamma: float) -> int:
        """Descend to a leaf, evaluate it, back the value up; return the leaf depth."""
        node = root
        path: list[tuple[Node, int]] = []
        while node.expanded:
            index = node.select(self.c_puct)
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
            logits, value = _infer(model, board, self.device)
            _set_edges(node, *legal_actions(board), logits, value)
            _backup(path, value, gamma)
        for _step in path:
            board.pop()
        return len(path)
