"""Tournament adapter for the owner-provided deep RL policy."""

from __future__ import annotations

import chess

from ai.base_bot import BotUnavailableError
from ai.baseline import RandomBaselineBot
from ai.deep_rl.user.policy import load_policy
from ai.deep_rl.weights import resolve_weights


class DeepRLBot(RandomBaselineBot):
    """Use a policy supplied by the deep RL package owner."""

    bot_id = "deep_rl"
    display_name = "Deep RL"

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config)
        settings = self.config.get("bots", {}).get(self.bot_id, self.config)
        self.policy = None
        self.is_baseline = False
        try:
            weights_path = resolve_weights(
                settings.get("weights_url", ""),
                settings.get("weights_sha256", ""),
            )
            self.policy = load_policy(
                weights_path,
                device=settings.get("device", "cpu"),
                depth=int(settings.get("depth", 3)),
                max_think_time_s=float(settings.get("max_think_time_s", 1.0)),
                simulations=int(settings.get("simulations", 64)),
                search=str(settings.get("search", "mcts")),
                end_g=int(settings.get("end_g", 4)),
                ramp_moves=int(settings.get("ramp_moves", 10)),
                batch_size=int(settings.get("batch_size", 32)),
                tree_reuse=int(settings.get("tree_reuse", 0)),
                widening=bool(settings.get("widening", False)),
                early_stop=bool(settings.get("early_stop", False)),
            )
        except NotImplementedError:
            self.is_baseline = True
        except Exception as exc:
            raise BotUnavailableError(f"{self.bot_id}: không tải được trọng số: {exc}") from exc

    def select_move(self, board: chess.Board) -> chess.Move:
        """Return a legal move selected by the configured policy."""
        if self.policy is None:
            return super().select_move(board)
        move = self.policy.select_move(board.copy())
        if move not in board.legal_moves:
            raise ValueError(f"Deep RL policy returned illegal move: {move}")
        self.last_search_info = dict(getattr(self.policy, "last_info", {}))
        return move
