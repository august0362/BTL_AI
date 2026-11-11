"""Alpha-beta (negamax) using the V20 phase expert's Value as the evaluation.

Same algorithm as ``user/search.py::AlphaBetaPolicy`` (DQN v1.0), so the two networks can be
compared on one search; only the evaluation differs (§7.1):

- one network per move: the root phase's expert (``select_phase``);
- leaves lie exactly ``depth`` plies below the root and score the network's Value for the side
  to move there; nodes one ply above the leaves evaluate every child in one batch, and a
  position seen again within the same move reuses its value;
- terminal positions are exact: checkmate ``-(MATE - 0.01 * ply)``, any draw 0;
- moves are ordered by the network's policy logits;
- iterative deepening 1 → ``depth`` within ``max_think_time_s`` (0 = unlimited); depth 1 always
  completes.

On CUDA each network call replays a captured CUDA graph: a forward pass launches ~100 small
kernels, and on this laptop each launch costs more than the computation itself.
"""

from __future__ import annotations

import time

import chess
import numpy as np
import torch

from .features import PLANES, encode_masks, unpack, unpack_torch
from .model import PolicyValueNet
from .moves import legal_actions
from .policy import select_phase
from .rules import outcome

MATE = 3.0
_PLY_PENALTY = 0.01
_BATCH_SIZES = (1, 2, 4, 8, 16, 32, 64, 128, 256)  # a position has at most 218 legal moves


class _Timeout(Exception):
    pass


class _CudaGraphs:
    """One captured forward pass per (network, padded batch size), replayed with one launch."""

    def __init__(self, device: str) -> None:
        self.device = device
        self._graphs: dict = {}

    def __call__(
        self, model: PolicyValueNet, planes: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Run ``model`` on CPU ``(N, 19, 8, 8)`` planes; outputs are views valid until the
        next call."""
        n = len(planes)
        size = next(size for size in _BATCH_SIZES if size >= n)
        key = (id(model), size)
        if key not in self._graphs:
            self._graphs[key] = self._capture(model, size)
        graph, static, logits, values = self._graphs[key]
        static[:n].copy_(planes)
        graph.replay()
        return logits[:n], values[:n]

    def _capture(self, model: PolicyValueNet, size: int) -> tuple:
        with torch.cuda.device(self.device):  # capture streams belong to the current device
            static = torch.zeros(size, PLANES, 8, 8, device=self.device)
            stream = torch.cuda.Stream()
            stream.wait_stream(torch.cuda.current_stream())
            with torch.cuda.stream(stream):
                for _ in range(3):
                    model(static)
            torch.cuda.current_stream().wait_stream(stream)
            graph = torch.cuda.CUDAGraph()
            with torch.cuda.graph(graph):
                logits, values = model(static)
        return graph, static, logits, values


class V20AlphaBetaPolicy:
    """Choose the root phase's expert, then play the best alpha-beta move at ``depth``."""

    def __init__(
        self,
        models: dict[str, PolicyValueNet],
        device: str = "cpu",
        depth: int = 3,
        max_think_time_s: float = 1.0,
    ) -> None:
        if depth < 1:
            raise ValueError("depth must be >= 1")
        self.models = models
        self.device = device
        self.depth = depth
        self.max_think_time_s = max_think_time_s
        self.last_info: dict = {}
        self._model: PolicyValueNet | None = None
        self._deadline = 0.0
        self._nodes = 0
        self._values: dict[tuple[int, ...], float] = {}
        self._graphs = _CudaGraphs(device) if torch.device(device).type == "cuda" else None

    def select_move(self, board: chess.Board) -> chess.Move:
        """Return the best move of the deepest completed iteration."""
        board = board.copy(stack=True)
        started = time.perf_counter()
        limit = self.max_think_time_s
        self._deadline = started + limit if limit > 0 else float("inf")
        self._nodes = 0
        self._values = {}
        phase = select_phase(board)
        self._model = self.models[phase]
        order = self._ordered(board)
        best_move, best_score, depth_done = order[0], 0.0, 0
        for depth in range(1, self.depth + 1):
            try:
                scores = self._root(board, order, depth)
            except _Timeout:
                break
            order = sorted(order, key=lambda move: -scores[move])
            best_move, best_score, depth_done = order[0], scores[order[0]], depth
        self.last_info = {
            "mode": "alphabeta",
            "phase": phase,
            "depth": depth_done,
            "nodes": self._nodes,
            "eval": best_score,
            "time_s": time.perf_counter() - started,
        }
        return best_move

    def _evaluate(
        self, masks: list[tuple[int, ...]], with_logits: bool = False
    ) -> tuple[np.ndarray | None, np.ndarray]:
        """One network call for a batch: policy logits (if asked) and side-to-move values."""
        assert self._model is not None
        planes = np.asarray(masks, dtype=np.uint64)
        with torch.inference_mode():
            if self._graphs is not None:
                logits, values = self._graphs(self._model, torch.from_numpy(unpack(planes)))
            else:
                tensors = unpack_torch(torch.from_numpy(planes.view(np.int64)).to(self.device))
                logits, values = self._model(tensors)
            policy = logits.float().cpu().numpy() if with_logits else None
            values = values.float().cpu().numpy().reshape(-1)
        self._nodes += len(masks)
        return policy, values

    def _ordered(self, board: chess.Board) -> list[chess.Move]:
        """Legal moves sorted by the network's policy logits, best first."""
        moves, actions = legal_actions(board)
        logits = self._evaluate([encode_masks(board)], with_logits=True)[0]
        assert logits is not None
        return [moves[i] for i in np.argsort(-logits[0][actions], kind="stable")]

    def _check_time(self) -> None:
        if time.perf_counter() > self._deadline:
            raise _Timeout

    @staticmethod
    def _terminal(board: chess.Board, ply: int) -> float | None:
        """Exact score for the side to move if the game is over, otherwise None."""
        result = outcome(board)
        if result is None:
            return None
        return -(MATE - _PLY_PENALTY * ply) if result.winner is not None else 0.0

    def _root(self, board: chess.Board, order: list[chess.Move], depth: int) -> dict:
        if depth == 1:  # every child is a leaf: one batch, no deadline
            return dict(zip(order, self._leaf_scores(board, order, 0), strict=True))
        scores: dict[chess.Move, float] = {}
        alpha = -float("inf")
        for move in order:
            board.push(move)
            try:
                score = -self._negamax(board, depth - 1, -float("inf"), -alpha, 1)
            finally:
                board.pop()
            scores[move] = score
            alpha = max(alpha, score)
        return scores

    def _negamax(
        self, board: chess.Board, depth: int, alpha: float, beta: float, ply: int
    ) -> float:
        terminal = self._terminal(board, ply)
        if terminal is not None:
            return terminal
        self._check_time()
        if depth == 1:
            return max(self._leaf_scores(board, list(board.legal_moves), ply))
        best = -float("inf")
        for move in self._ordered(board):
            board.push(move)
            try:
                score = -self._negamax(board, depth - 1, -beta, -alpha, ply + 1)
            finally:
                board.pop()
            best = max(best, score)
            alpha = max(alpha, score)
            if alpha >= beta:
                break
        return best

    def _leaf_scores(self, board: chess.Board, moves: list[chess.Move], ply: int) -> list[float]:
        """Score of each move for the side to move at ``board``: children are scored by
        ``-Value`` in one network call; terminal children exactly."""
        scores = [0.0] * len(moves)
        pending: dict[tuple[int, ...], list[int]] = {}
        for index, move in enumerate(moves):
            board.push(move)
            terminal = self._terminal(board, ply + 1)
            if terminal is not None:
                scores[index] = -terminal
            else:
                masks = encode_masks(board)  # the exact network input, so a safe cache key
                value = self._values.get(masks)
                if value is None:
                    pending.setdefault(masks, []).append(index)
                else:
                    scores[index] = -value
            board.pop()
        if pending:
            values = self._evaluate(list(pending))[1]
            for (masks, indices), value in zip(pending.items(), values, strict=True):
                self._values[masks] = float(value)
                for index in indices:
                    scores[index] = -float(value)
        return scores
