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


def backpropagate(node: Node, white_reward: float) -> None:
    """Update every ancestor using its own previous mover's perspective."""
    while node is not None:
        node.visits += 1
        node.total_reward += white_reward if node.player_just_moved else 1.0 - white_reward
        node = node.parent


def robust_child(root: Node) -> Node:
    """Choose by visit count, then mean reward; preserve insertion order on ties."""
    return max(root.children, key=lambda child: (child.visits, child.mean_reward))
