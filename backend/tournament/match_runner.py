"""Run one chess match between two tournament players."""

from __future__ import annotations

import random
import threading
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime

import chess

from core.game_state import GameState
from core.material import eval_bar_value
from core.types import GameResult, MoveRecord, Termination
from tournament.players import MatchAborted, Player
from tournament.records import GameRecord


def generate_random_opening(plies: int, rng: random.Random) -> list[str]:
    """Generate a deterministic sequence of random legal opening moves."""
    if plies <= 0:
        return []

    for _ in range(100):
        board = chess.Board()
        moves: list[str] = []
        for _ in range(plies):
            if board.is_game_over():
                break
            legal_moves = sorted(board.legal_moves, key=lambda move: move.uci())
            if not legal_moves:
                break
            move = rng.choice(legal_moves)
            moves.append(move.uci())
            board.push(move)
        if len(moves) == plies and not board.is_game_over():
            return moves
    raise RuntimeError("Could not generate a non-terminal random opening after 100 attempts")


class MatchRunner:
    """Coordinate player moves and record the resulting game."""

    def __init__(
        self,
        white: Player,
        black: Player,
        *,
        mode: str = "bot_vs_bot",
        random_opening_plies: int = 0,
        opening_moves: list[str] | None = None,
        max_plies: int = 300,
        claim_draw: bool = True,
        eval_scale: float = 8.0,
        rng: random.Random | None = None,
        on_move: Callable[[MoveRecord, GameState], None] | None = None,
        series_id: str | None = None,
        series_game_index: int | None = None,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        self.white = white
        self.black = black
        self.mode = mode
        self.random_opening_plies = random_opening_plies
        self.opening_moves = list(opening_moves) if opening_moves is not None else None
        self.max_plies = max_plies
        self.claim_draw = claim_draw
        self.eval_scale = eval_scale
        self.rng = rng if rng is not None else random.Random()
        self.on_move = on_move
        self.series_id = series_id
        self.series_game_index = series_game_index
        self.clock = clock
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()

    def request_stop(self) -> None:
        """Stop after the current selection and release any paused or waiting player."""
        self._stop_event.set()
        self._pause_event.set()
        for player in (self.white, self.black):
            cancel = getattr(player, "cancel", None)
            if cancel is not None:
                try:
                    cancel()
                except Exception:
                    pass

    def pause(self) -> None:
        """Pause before the next move."""
        self._pause_event.clear()

    def resume(self) -> None:
        """Resume a paused match."""
        self._pause_event.set()

    def play(self) -> GameRecord:
        """Play to a terminal result or an aborted state and return its record."""
        started_at = datetime.now(UTC).isoformat()
        state = GameState(max_plies=self.max_plies, claim_draw=self.claim_draw)
        moves: list[MoveRecord] = []
        opening = list(self.opening_moves or [])
        result: GameResult | None = None
        error: str | None = None

        try:
            for player_to_reset in (self.white, self.black):
                try:
                    player_to_reset.reset()
                except Exception as exc:
                    if error is None:
                        error = f"{player_to_reset.bot_id}: {exc}"
            if error is not None:
                raise _PlayerFailure
            if self.opening_moves is None and self.random_opening_plies > 0:
                opening = generate_random_opening(self.random_opening_plies, self.rng)

            for uci in opening:
                if self._stop_event.is_set():
                    raise MatchAborted
                move = chess.Move.from_uci(uci)
                record = self._push_move(state, move, 0.0, {}, True)
                moves.append(record)
                if self.on_move is not None:
                    self.on_move(record, state)

            while not state.is_over():
                self._pause_event.wait()
                if self._stop_event.is_set():
                    raise MatchAborted
                player = self.white if state.turn == chess.WHITE else self.black
                started = self.clock()
                try:
                    move = player.select_move(state.board)
                except MatchAborted:
                    raise
                except Exception as exc:
                    error = f"{player.bot_id}: {exc}"
                    raise _PlayerFailure from exc
                think_time = max(0.0, self.clock() - started)
                if self._stop_event.is_set():
                    raise MatchAborted
                if not isinstance(move, chess.Move) or move not in state.legal_moves():
                    error = f"{player.bot_id}: Illegal move: {move}"
                    raise _PlayerFailure
                search_info = dict(getattr(player, "last_search_info", {}) or {})
                record = self._push_move(state, move, think_time, search_info, False)
                moves.append(record)
                if self.on_move is not None:
                    self.on_move(record, state)
            result = state.result()
        except MatchAborted:
            result = GameResult(None, Termination.ABORTED)
            error = None
        except _PlayerFailure:
            result = GameResult(None, Termination.ABORTED)
        except Exception as exc:
            # Keep player callbacks and setup failures from escaping into the GUI thread.
            result = GameResult(None, Termination.ABORTED)
            if error is None:
                player_id = getattr(locals().get("player"), "bot_id", "match")
                error = f"{player_id}: {exc}"

        if result is None:
            result = GameResult(None, Termination.ABORTED)
        record = GameRecord(
            game_id=uuid.uuid4().hex,
            started_at=started_at,
            mode=self.mode,
            white_id=self.white.bot_id,
            black_id=self.black.bot_id,
            white_name=self.white.display_name,
            black_name=self.black.display_name,
            opening_moves=opening,
            moves=moves,
            result=result,
            pgn=state.to_pgn(
                {
                    "White": self.white.display_name,
                    "Black": self.black.display_name,
                    "Date": datetime.now(UTC).strftime("%Y.%m.%d"),
                }
            ),
            series_id=self.series_id,
            series_game_index=self.series_game_index,
            error=error,
        )
        return record

    def _push_move(
        self,
        state: GameState,
        move: chess.Move,
        think_time: float,
        search_info: dict,
        is_random_opening: bool,
    ) -> MoveRecord:
        """Push a move and make its record."""
        san = state.push(move)
        board = state.board
        return MoveRecord(
            ply=state.ply_count,
            uci=move.uci(),
            san=san,
            think_time_s=think_time,
            search_info=search_info,
            material_eval=eval_bar_value(board, self.eval_scale),
            is_random_opening=is_random_opening,
        )


class _PlayerFailure(Exception):
    """Internal signal that a player produced an invalid move or raised."""
