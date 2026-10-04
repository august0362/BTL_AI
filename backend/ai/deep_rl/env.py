"""Gym-style chess environment with one opponent reply per agent action."""

from __future__ import annotations

import random
from dataclasses import dataclass

import chess
import numpy as np

from ai.deep_rl.encoding import encode_board
from ai.deep_rl.opponents import Opponent, RandomOpponent

_PIECE_VALUES = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}


@dataclass(frozen=True)
class RewardConfig:
    """Terminal result rewards and optional material-difference shaping."""

    win: float = 1.0
    draw: float = 0.0
    loss: float = -1.0
    material_coef: float = 0.0


class ChessEnv:
    """A small chess environment that does not require Gymnasium."""

    def __init__(
        self,
        opponent: Opponent | None = None,
        agent_color: chess.Color | str = "random",
        reward: RewardConfig | None = None,
        max_plies: int = 200,
        random_opening_plies: tuple[int, int] = (0, 0),
        seed: int | None = None,
    ) -> None:
        if max_plies <= 0:
            raise ValueError("max_plies must be positive")
        low, high = random_opening_plies
        if low < 0 or high < low:
            raise ValueError("random_opening_plies must be a nonnegative ordered pair")
        if agent_color not in (chess.WHITE, chess.BLACK, "random"):
            raise ValueError("agent_color must be chess.WHITE, chess.BLACK, or 'random'")
        self.opponent = opponent or RandomOpponent()
        self.agent_color = agent_color
        self.reward_config = reward or RewardConfig()
        self.max_plies = max_plies
        self.random_opening_plies = random_opening_plies
        self.rng = random.Random(seed)
        self.board = chess.Board()
        self.plies = 0
        self._done = False

    def reset(self, *, seed: int | None = None) -> tuple[np.ndarray, dict]:
        """Start a new game and return the encoded position and metadata."""
        if seed is not None:
            self.rng.seed(seed)
        self.board = chess.Board()
        self.plies = 0
        self._done = False
        if self.agent_color == "random":
            self._agent_color = self.rng.choice((chess.WHITE, chess.BLACK))
        else:
            self._agent_color = self.agent_color
        opening_plies = self.rng.randint(*self.random_opening_plies)
        for _ in range(opening_plies):
            if self._result() is not None:
                break
            self.board.push(self.rng.choice(list(self.board.legal_moves)))
            self.plies += 1
        if self.board.turn != self._agent_color:
            self._opponent_move()
        return encode_board(self.board), self._info()

    def step(self, move: chess.Move | int) -> tuple[np.ndarray, float, bool, bool, dict]:
        """Apply an agent move and an opponent reply, if the game continues."""
        if self._done:
            raise RuntimeError("step called after episode ended; call reset")
        if self.board.turn != self._agent_color:
            raise RuntimeError("the agent does not have the move")
        if isinstance(move, int):
            from ai.deep_rl.encoding import action_to_move

            move = action_to_move(move, self.board)
        if move not in self.board.legal_moves:
            raise ValueError(f"illegal move: {move}")
        before = self._material()
        self.board.push(move)
        self.plies += 1
        result = self._result()
        if result is None and self.plies < self.max_plies:
            self._opponent_move()
            result = self._result()
        terminated = result is not None
        truncated = result is None and self.plies >= self.max_plies
        self._done = terminated or truncated
        reward = self.reward_config.material_coef * (self._material() - before)
        if result is not None:
            reward += self._terminal_reward(result)
        info = self._info()
        if result is not None:
            info["result"] = result
        return encode_board(self.board), float(reward), terminated, truncated, info

    def _opponent_move(self) -> None:
        if self._result() is not None or self.plies >= self.max_plies:
            return
        move = self.opponent.select_move(self.board.copy(), self.rng)
        if move not in self.board.legal_moves:
            raise ValueError(f"opponent returned illegal move: {move}")
        self.board.push(move)
        self.plies += 1

    def _material(self) -> float:
        score = sum(
            value
            * (
                len(self.board.pieces(piece_type, self._agent_color))
                - len(self.board.pieces(piece_type, not self._agent_color))
            )
            for piece_type, value in _PIECE_VALUES.items()
        )
        return float(score)

    def _terminal_reward(self, result: chess.Outcome) -> float:
        if result.winner is None:
            return self.reward_config.draw
        return (
            self.reward_config.win
            if result.winner == self._agent_color
            else self.reward_config.loss
        )

    def _result(self) -> chess.Outcome | None:
        return self.board.outcome(claim_draw=True)

    def _info(self) -> dict:
        return {
            "board": self.board.copy(),
            "legal_moves": list(self.board.legal_moves),
            "agent_color": self._agent_color,
            "plies": self.plies,
        }
