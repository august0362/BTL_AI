"""Selection, expansion, bounded rollout and alternating-perspective backup."""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from dataclasses import dataclass

import chess

from ai.mcts.evaluation import estimated_white_reward, move_priority
from ai.mcts.node import Node, backpropagate, robust_child


@dataclass(frozen=True, slots=True)
class SearchConfig:
    """Limits and optional heuristic assistance for one fresh tree."""

    simulations: int = 100_000
    exploration_constant: float = 2**0.5
    rollout_max_plies: int = 4
    max_think_time_s: float = 1.0
    use_heuristics: bool = True
    claim_draw: bool = True


@dataclass(slots=True)
class SearchResult:
    """Chosen move and JSON-compatible diagnostics."""

    move: chess.Move
    info: dict


def terminal_reward(board: chess.Board, *, claim_draw: bool = True) -> float | None:
    """Return a white-relative outcome using actual, not prospective, draw claims."""
    outcome = board.outcome(claim_draw=False)
    if outcome is not None:
        if outcome.winner is None:
            return 0.5
        return 1.0 if outcome.winner else 0.0
    if claim_draw and (board.halfmove_clock >= 100 or board.is_repetition(3)):
        return 0.5
    return None


def rollout(
    board: chess.Board,
    config: SearchConfig,
    rng: random.Random,
    *,
    deadline: float | None = None,
    clock: Callable[[], float] = time.perf_counter,
) -> tuple[float, bool, int]:
    """Simulate on a private board; mark cutoffs separately from real draws."""
    plies = 0
    while True:
        reward = terminal_reward(board, claim_draw=config.claim_draw)
        if reward is not None:
            return reward, False, plies
        if plies >= config.rollout_max_plies or (deadline is not None and clock() >= deadline):
            reward = estimated_white_reward(board) if config.use_heuristics else 0.5
            return reward, True, plies
        moves = list(board.legal_moves)
        if config.use_heuristics and rng.random() >= 0.15:
            rng.shuffle(moves)
            move = max(moves, key=lambda candidate: move_priority(board, candidate))
        else:
            move = rng.choice(moves)
        board.push(move)
        plies += 1


def expand(node: Node, board: chess.Board, rng: random.Random, *, claim_draw: bool) -> Node:
    """Try exactly one previously unexpanded legal move and attach one child."""
    index = rng.randrange(len(node.untried_moves))
    move = node.untried_moves.pop(index)
    board.push(move)
    terminal = terminal_reward(board, claim_draw=claim_draw)
    child = Node(
        player_just_moved=not board.turn,
        untried_moves=list(board.legal_moves) if terminal is None else [],
        parent=node,
        move=move,
        terminal_white_reward=terminal,
    )
    node.children.append(child)
    return child


def search(
    board: chess.Board,
    config: SearchConfig,
    rng: random.Random,
    *,
    started: float | None = None,
    clock: Callable[[], float] = time.perf_counter,
) -> SearchResult:
    """Run UCT and return the robust child; never modify the supplied board."""
    started = clock() if started is None else started
    seconds = config.max_think_time_s
    # Cooperative timing with a reserve, not an OS-level hard real-time guarantee.
    deadline = started + seconds * 0.97 if seconds > 0 else None
    original = board.copy(stack=True)
    terminal = terminal_reward(original, claim_draw=config.claim_draw)
    if terminal is not None:
        raise ValueError("mcts: cannot select a move in a finished game")
    moves = list(original.legal_moves)
    root = Node(player_just_moved=not original.turn, untried_moves=list(moves))
    nodes, max_depth, simulations, cutoffs, rollout_plies = 1, 0, 0, 0, 0
    shortcut = None
    chosen = moves[0]
    chosen_reward = 0.5

    if len(moves) == 1:
        shortcut = "only_legal_move"
    elif config.use_heuristics:
        for move in moves:
            if deadline is not None and clock() >= deadline:
                break
            original.push(move)
            is_mate = original.is_checkmate()
            original.pop()
            if is_mate:
                chosen, chosen_reward, shortcut = move, 1.0, "mate_in_one"
                break

    if shortcut is None:
        for _ in range(config.simulations):
            if deadline is not None and clock() >= deadline:
                break
            simulation = original.copy(stack=True)
            node, depth = root, 0
            while not node.untried_moves and node.children:
                node = node.select_child(config.exploration_constant)
                simulation.push(node.move)
                depth += 1
                if deadline is not None and clock() >= deadline:
                    break
            if node.untried_moves and (deadline is None or clock() < deadline):
                node = expand(node, simulation, rng, claim_draw=config.claim_draw)
                nodes += 1
                depth += 1
            if node.terminal_white_reward is not None:
                reward, cutoff, plies = node.terminal_white_reward, False, 0
            else:
                reward, cutoff, plies = rollout(
                    simulation, config, rng, deadline=deadline, clock=clock
                )
            backpropagate(node, reward)
            simulations += 1
            cutoffs += int(cutoff)
            rollout_plies += plies
            max_depth = max(max_depth, depth)
        if root.children:
            best = robust_child(root)
            chosen, chosen_reward = best.move, best.mean_reward

    info = {
        "depth": max_depth,
        "nodes": nodes,
        "eval": 2 * chosen_reward - 1,
        "simulations": simulations,
        "rollout_cutoffs": cutoffs,
        "rollout_cutoff_ratio": cutoffs / simulations if simulations else 0.0,
        "rollout_plies": rollout_plies,
        "algorithm": "mcts_uct_assisted" if config.use_heuristics else "pure_mcts_uct",
        "root_visits": root.visits,
        "root_children": [
            {"move": child.move.uci(), "visits": child.visits, "mean_reward": child.mean_reward}
            for child in root.children
        ],
        "shortcut": shortcut,
        "elapsed_s": clock() - started,
    }
    return SearchResult(chosen, info)
