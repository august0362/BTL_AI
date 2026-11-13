"""Tree statistics, always stored from the perspective of the previous mover."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import chess


@dataclass(slots=True)
class Node:
    """One move in a UCT tree; board positions are replayed on simulation copies."""

    player_just_moved: chess.Color
    untried_moves: list[chess.Move]
    parent: Node | None = None
    move: chess.Move | None = None
    children: list[Node] = field(default_factory=list)
    visits: int = 0
    total_reward: float = 0.0
    terminal_white_reward: float | None = None
    leaf_reward: float = 0.5
    reply_reward: float = 0.5

    @property
    def mean_reward(self) -> float:
        """Return the average reward (neutral for an unvisited node)."""
        return self.total_reward / self.visits if self.visits else 0.5

    def uct(self, parent_visits: int, exploration: float) -> float:
        """Return UCT, giving an unvisited child priority without dividing by zero."""
        if self.visits == 0:
            return math.inf
        return self.mean_reward + exploration * math.sqrt(
            math.log(max(1, parent_visits)) / self.visits
        )

    def select_child(self, exploration: float) -> Node:
        """Choose a child for the player to move at this node."""
        return max(self.children, key=lambda child: child.uct(self.visits, exploration))

    def select_heuristic_child(self, exploration: float) -> Node:
        """Mix samples with the opponent's best known reply, then explore with UCT."""
        log_parent = math.log(max(1, self.visits))
        return max(
            self.children,
            key=lambda c: (
                (0.2 * c.mean_reward + 0.8 * c.reply_reward)
                + exploration * math.sqrt(log_parent / c.visits)
                if c.visits
                else math.inf
            ),
        )


def backpropagate(node: Node, white_reward: float) -> None:
    """Update every ancestor using its own previous mover's perspective."""
    while node is not None:
        node.visits += 1
        node.total_reward += white_reward if node.player_just_moved else 1.0 - white_reward
        node = node.parent


def robust_child(root: Node) -> Node:
    """Choose by visit count, then mean reward; preserve insertion order on ties."""
    return max(root.children, key=lambda child: (child.visits, child.mean_reward))


def backup_replies(node: Node, white_reward: float) -> None:
    """Keep a tactical prior until all opponent replies have been tried."""
    node.leaf_reward = white_reward if node.player_just_moved else 1 - white_reward
    node.reply_reward = node.leaf_reward
    node = node.parent
    while node is not None:
        value = 1 - max(c.reply_reward for c in node.children)
        node.reply_reward = min(node.leaf_reward, value) if node.untried_moves else value
        node = node.parent


def release_tree(root: Node) -> None:
    """Break parent/child cycles immediately rather than waiting for cyclic GC."""
    pending = [root]
    while pending:
        node = pending.pop()
        pending.extend(node.children)
        node.parent = None
        node.children.clear()
        node.untried_moves.clear()
