"""Game state wrapper around a python-chess board."""

import chess
import chess.pgn

from core.types import GameOverError, GameResult, IllegalMoveError, Termination


class GameState:
    """Own a chess board and apply the project's end-of-game rules."""

    def __init__(
        self,
        fen: str | None = None,
        max_plies: int = 300,
        claim_draw: bool = True,
    ) -> None:
        """Create a game from the standard position or the supplied FEN."""
        if max_plies <= 0:
            raise ValueError("max_plies must be positive")
        self._board = chess.Board(fen) if fen is not None else chess.Board()
        self._starting_fen = self._board.fen()
        self._max_plies = max_plies
        self._claim_draw = claim_draw
        self._ply_count = 0

    @property
    def board(self) -> chess.Board:
        """Return an independent board copy, including its move history."""
        return self._board.copy()

    @property
    def turn(self) -> chess.Color:
        """Return the color whose turn it is to move."""
        return self._board.turn

    @property
    def fen(self) -> str:
        """Return the current position as FEN."""
        return self._board.fen()

    @property
    def starting_fen(self) -> str:
        """Return the position's FEN when this game was created."""
        return self._starting_fen

    @property
    def ply_count(self) -> int:
        """Return the number of half-moves played through this state."""
        return self._ply_count

    def legal_moves(self) -> list[chess.Move]:
        """Return all legal moves in the current position."""
        return list(self._board.legal_moves)

    def push(self, move: chess.Move) -> str:
        """Play a legal move and return its SAN notation."""
        if self.is_over():
            raise GameOverError("The game is already over")
        if move not in self._board.legal_moves:
            raise IllegalMoveError(f"Illegal move: {move}")
        san = self._board.san(move)
        self._board.push(move)
        self._ply_count += 1
        return san

    def is_over(self) -> bool:
        """Return whether the game has reached a terminal result."""
        return self.result() is not None

    def result(self) -> GameResult | None:
        """Return the terminal result using the documented rule precedence."""
        if self._board.is_checkmate():
            return GameResult(
                winner=not self._board.turn,
                termination=Termination.CHECKMATE,
            )
        if self._board.is_stalemate():
            return GameResult(winner=None, termination=Termination.STALEMATE)
        if self._board.is_insufficient_material():
            return GameResult(
                winner=None,
                termination=Termination.INSUFFICIENT_MATERIAL,
            )
        if self._claim_draw and self._board.is_repetition(3):
            return GameResult(
                winner=None,
                termination=Termination.THREEFOLD_REPETITION,
            )
        if self._claim_draw and self._board.halfmove_clock >= 100:
            return GameResult(winner=None, termination=Termination.FIFTY_MOVES)

        outcome = self._board.outcome(claim_draw=False)
        if outcome is not None:
            if outcome.termination is chess.Termination.FIVEFOLD_REPETITION:
                return GameResult(
                    winner=None,
                    termination=Termination.THREEFOLD_REPETITION,
                )
            if outcome.termination is chess.Termination.SEVENTYFIVE_MOVES:
                return GameResult(winner=None, termination=Termination.FIFTY_MOVES)

        if self._ply_count >= self._max_plies:
            return GameResult(winner=None, termination=Termination.MAX_PLIES)
        return None

    def to_pgn(self, headers: dict[str, str]) -> str:
        """Export this game's move history and headers as PGN text."""
        game = chess.pgn.Game.from_board(self._board)
        game.headers.update(headers)
        result = self.result()
        if result is None:
            game.headers["Result"] = "*"
        elif result.termination is Termination.ABORTED:
            game.headers["Result"] = "*"
        elif result.winner is chess.WHITE:
            game.headers["Result"] = "1-0"
        elif result.winner is chess.BLACK:
            game.headers["Result"] = "0-1"
        else:
            game.headers["Result"] = "1/2-1/2"
        return str(game)
