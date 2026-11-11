"""Batched PUCT with virtual loss, subtree reuse, progressive widening and early stop."""

from __future__ import annotations

import logging
import math
import time
from typing import Any

import chess
import numpy as np
import torch

from .features import encode_masks, unpack_torch
from .model import PolicyValueNet
from .moves import legal_actions
from .rules import outcome, utility
from .search import Node, _backup, _set_edges

VIRTUAL_LOSS = 1.0
WIDEN_MIN = 10
EARLY_STOP_MIN = 256
log = logging.getLogger(__name__)


def _infer_batch(
    model: PolicyValueNet, planes: list[np.ndarray], device: str | torch.device
) -> tuple[np.ndarray, np.ndarray]:
    packed = np.asarray(planes, dtype=np.uint64)
    with torch.inference_mode():
        tensors = unpack_torch(torch.from_numpy(packed.view(np.int64)).to(device))
        logits, values = model(tensors)
    return logits.float().cpu().numpy(), values.float().cpu().numpy().reshape(-1)


def widen_limit(visits: int, legal: int) -> int:
    """Return ``K(N) = min(legal, max(10, ceil(2 * sqrt(N))))``."""
    return min(legal, max(WIDEN_MIN, math.ceil(2 * math.sqrt(visits))))


def _mark_widening(node: Node, board: chess.Board) -> None:
    """Rank edges by prior; replies to check, checks, captures and promotions stay eligible."""
    assert node.prior is not None
    node.order = np.argsort(-node.prior, kind="stable")
    forced = np.full(len(node.moves), board.is_check())
    if not forced.all():
        for index in node.order[WIDEN_MIN:]:
            move = node.moves[index]
            forced[index] = (
                move.promotion is not None or board.is_capture(move) or board.gives_check(move)
            )
    node.forced = forced


class TreeSearch:
    """PUCT that evaluates up to ``batch_size`` leaves per forward pass.

    Each move runs up to ``simulations`` NEW simulations on top of a subtree kept from earlier
    moves (same net and gamma, same game, at most ``max_reuse`` plies since the tree was built;
    ``max_reuse = 0`` always starts fresh). ``widening`` limits each node to its
    ``widen_limit`` best-prior edges plus forcing moves; ``early_stop`` ends the search, after
    ``EARLY_STOP_MIN`` new simulations, once the most visited root move cannot be overtaken.
    A positive ``max_think_time_s`` stops before the next batch once its budget expires;
    zero leaves the search limited only by the simulation count.
    With both off and ``batch_size = 1`` a fresh tree equals ``search.search``.
    """

    def __init__(
        self,
        device: str | torch.device = "cpu",
        simulations: int = 200,
        batch_size: int = 32,
        max_reuse: int = 0,
        c_puct: float = 1.5,
        widening: bool = False,
        early_stop: bool = False,
        max_think_time_s: float = 0.0,
    ) -> None:
        if simulations < 1 or batch_size < 1 or max_reuse < 0 or c_puct <= 0:
            raise ValueError("invalid MCTS configuration")
        self.device = device
        self.simulations = simulations
        self.batch_size = batch_size
        self.max_reuse = max_reuse
        self.c_puct = c_puct
        self.widening = widening
        self.early_stop = early_stop
        self.max_think_time_s = max_think_time_s
        self.root: Node | None = None
        self.key: tuple[str, tuple[chess.Move, ...]] = ("", ())
        self.owner: tuple[int, float] | None = None
        self.plies = 0
        self.stats: dict[str, Any] = {}

    def _reusable(self, board: chess.Board, model: PolicyValueNet, gamma: float) -> Node | None:
        """Return the stored tree's node for ``board``, or ``None`` if it cannot be reused."""
        if self.root is None or self.owner != (id(model), gamma):
            return None
        fen, stack = self.key
        played = board.move_stack
        extra = len(played) - len(stack)
        if extra <= 0 or self.plies + extra > self.max_reuse:
            return None
        if tuple(played[: len(stack)]) != stack or board.root().fen() != fen:
            return None
        node = self.root
        for move in played[len(stack) :]:
            if not node.expanded or move not in node.moves:
                return None
            child = node.children.get(node.moves.index(move))
            if child is None:
                return None
            node = child
        return node if node.expanded else None

    def _select(self, node: Node, board: chess.Board) -> int:
        """PUCT over the edges progressive widening allows at ``node`` (``board`` is there)."""
        if not self.widening or len(node.moves) <= WIDEN_MIN:
            return node.select(self.c_puct)
        assert node.visits is not None
        k = widen_limit(int(node.visits.sum()), len(node.moves))
        if k >= len(node.moves):
            return node.select(self.c_puct)
        if node.order is None or node.forced is None:
            _mark_widening(node, board)
        assert node.order is not None and node.forced is not None
        mask = node.forced.copy()
        mask[node.order[:k]] = True
        return node.select(self.c_puct, mask)

    def run(
        self, board: chess.Board, model: PolicyValueNet, gamma: float = 1.0
    ) -> tuple[list[chess.Move], np.ndarray, np.ndarray, int, int]:
        """Return moves, root visits, Q, evaluated positions and the reused root visits.

        Per-move diagnostics are kept in ``self.stats``.
        """
        if not 0 < gamma <= 1:
            raise ValueError("gamma must be in (0, 1]")
        if outcome(board) is not None:
            raise ValueError("cannot search a terminal position")
        started = time.perf_counter()
        deadline = started + self.max_think_time_s if self.max_think_time_s > 0 else math.inf
        root = self._reusable(board, model, gamma)
        board = board.copy(stack=True)
        positions = new_nodes = 0
        if root is None:
            root = Node(board.turn)
            logits, values = _infer_batch(model, [encode_masks(board)], self.device)
            _set_edges(root, *legal_actions(board), logits[0], float(values[0]))
            self.plies = 0
            positions = new_nodes = 1
        else:
            self.plies += len(board.move_stack) - len(self.key[1])
        assert root.visits is not None and root.sums is not None
        reused = int(root.visits.sum())
        done = depth_sum = depth_max = 0
        reason = None
        while done < self.simulations:
            if time.perf_counter() >= deadline:
                reason = "time_limit"
                break
            size = min(self.batch_size, self.simulations - done)
            depths, evaluated = self._batch(root, board, model, gamma, size)
            done += size
            positions += size
            new_nodes += evaluated
            depth_sum += sum(depths)
            depth_max = max(depth_max, *depths)
            if self.early_stop and EARLY_STOP_MIN <= done < self.simulations:
                second, best = (
                    (0, root.visits[0])
                    if len(root.moves) == 1
                    else (np.partition(root.visits, -2)[-2:])
                )
                if best > second + (self.simulations - done):
                    reason = "best_move_unreachable"
                    break
        self.root = root
        self.key = (board.root().fen(), tuple(board.move_stack))
        self.owner = (id(model), gamma)
        self.stats = {
            "new_simulations": done,
            "reused_root_visits": reused,
            "avg_leaf_depth": round(depth_sum / done, 2) if done else 0.0,
            "max_leaf_depth": depth_max,
            "new_nodes": new_nodes,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
            "early_stop_reason": reason,
        }
        log.debug("mcts %s", self.stats)
        n = root.visits.astype(np.float64)
        q = np.where(n > 0, root.sums / np.maximum(1, n), 0.0)
        return root.moves, root.visits.copy(), q, positions, reused

    def _batch(
        self, root: Node, board: chess.Board, model: PolicyValueNet, gamma: float, size: int
    ) -> tuple[list[int], int]:
        """Descend ``size`` times under virtual loss, then evaluate the new leaves together.

        Return each simulation's leaf depth and the number of positions sent to the network.
        A single descent needs no virtual loss, so ``size = 1`` backs up exactly like
        ``search.search`` (no floating-point drift from adding and removing the loss).
        """
        virtual = VIRTUAL_LOSS if size > 1 else 0.0
        pending: dict[int, tuple[Node, list, np.ndarray, np.ndarray, list]] = {}
        depths: list[int] = []
        for _ in range(size):
            node = root
            path: list[tuple[Node, int]] = []
            while node.expanded:
                index = self._select(node, board)
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
            depths.append(len(path))
            if node.terminal is not None:
                _backup(path, node.terminal, gamma, terminal=True)
            else:
                entry = pending.get(id(node))
                if entry is None:
                    moves, actions = legal_actions(board)
                    entry = pending[id(node)] = (node, moves, actions, encode_masks(board), [])
                entry[4].append(path)
                for parent, index in path if virtual else ():
                    assert parent.visits is not None and parent.sums is not None
                    parent.visits[index] += 1
                    parent.sums[index] -= virtual
            for _step in path:
                board.pop()
        if not pending:
            return depths, 0
        entries = list(pending.values())
        logits, values = _infer_batch(model, [entry[3] for entry in entries], self.device)
        for (node, moves, actions, _planes, paths), row, value in zip(
            entries, logits, values, strict=True
        ):
            _set_edges(node, moves, actions, row, float(value))
            for path in paths:
                for parent, index in path if virtual else ():
                    assert parent.visits is not None and parent.sums is not None
                    parent.visits[index] -= 1
                    parent.sums[index] += virtual
                _backup(path, float(value), gamma)
        return depths, len(entries)
