"""Bot policy for V11 weights (format ``v11-policy-value-mcts-2``): network + MCTS, no noise.

Same search as the V11.2 tournament: ``simulations`` per move (default 64), most-visited move;
``max_think_time_s`` > 0 additionally bounds each move.
"""

from __future__ import annotations

from typing import Any

import chess

V11_FORMAT = "v11-policy-value-mcts-2"


class V11Policy:
    """Wrap ``mcts.MCTSPolicy`` with the ``Policy`` interface used by ``DeepRLBot``."""

    def __init__(self, player: Any) -> None:
        self.player = player
        self.last_info: dict[str, Any] = {}

    def select_move(self, board: chess.Board) -> chess.Move:
        """Most visited legal move after the search (board keeps its move history)."""
        move = self.player.select_move(board)
        self.last_info = dict(self.player.last_search_info)
        return move


def load_v11_policy(
    data: dict, device: str = "cpu", simulations: int = 64, max_think_time_s: float = 0.0
) -> V11Policy:
    """Build the network from a loaded V11 weights file and return the MCTS policy."""
    from ai.deep_rl.v11.mcts import MCTSConfig, MCTSPolicy
    from ai.deep_rl.v11.model import PolicyValueNet

    if data.get("format") != V11_FORMAT:
        raise ValueError(f"file trọng số không đúng định dạng {V11_FORMAT}")
    model = PolicyValueNet(**data["model_config"]).to(device)
    model.load_state_dict(data["model"])
    model.eval()
    config = MCTSConfig(
        simulations=simulations,
        dirichlet_fraction=0.0,
        time_limit_s=max(0.0, max_think_time_s),
    )
    return V11Policy(MCTSPolicy(model, device, config))
