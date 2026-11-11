"""Step through a saved game and export its PGN."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from core.types import MoveRecord
from gui.render import Render
from gui.screens.base import Screen
from gui.widgets.board_view import BoardView
from gui.widgets.button import Button
from gui.widgets.eval_bar import draw_eval_bar

if TYPE_CHECKING:
    from gui.app import App


class ReplayScreen(Screen):
    """Render replay controls and the selected position."""

    INFO = pygame.Rect(652, 8, 296, 82)
    MOVES = pygame.Rect(652, 98, 296, 296)
    EVAL = pygame.Rect(652, 402, 296, 72)
    CONTROLS = pygame.Rect(652, 482, 296, 104)

    def __init__(self, app: App) -> None:
        super().__init__(app)
        self.record_id = app.replay_model._record.game_id
        self.board_view = BoardView(app.theme, app.config.get("ui", {}).get("piece_set", "rhosgfx"))
        self.export = Button(pygame.Rect(652, 594, 142, 38), app.translator.t("history.export_pgn"))
        self.back = Button(pygame.Rect(802, 594, 146, 38), app.translator.t("setup.back"))
        self.controls = [Button(pygame.Rect(666 + i * 55, 494, 49, 36), "") for i in range(5)]
        self.controls[2].style = "primary"
        self.speed = Button(pygame.Rect(666, 540, 116, 34), self._speed_label())
        self.notice = ""

    def _speed_label(self) -> str:
        model = self.app.replay_model
        return f"{model.delay_ms} ms" if model else ""

    def handle_click(self, x: float, y: float) -> None:
        point = (x, y)
        model = self.app.replay_model
        if model is None:
            return
        for i, button in enumerate(self.controls):
            if button.contains(point):
                if i == 0:
                    model.first()
                elif i == 1:
                    model.prev()
                elif i == 2:
                    model.pause() if model.playing else model.play(pygame.time.get_ticks())
                elif i == 3:
                    model.next()
                else:
                    model.last()
                return
        if self.speed.contains(point):
            self.app.set_replay_delay(500 if model.delay_ms >= 2000 else model.delay_ms + 500)
            self.speed.label = self._speed_label()
        elif self.export.contains(point):
            record = self.app.history.load(self.record_id)
            path = self.app.history.export_pgn(
                record.game_id, self.app.data_dir / "exports" / f"{record.game_id}.pgn"
            )
            self.notice = self.app.translator.t("history.exported", path=str(path))
        elif self.back.contains(point):
            self.app.goto("history")

    def update(self) -> None:
        model = self.app.replay_model
        if model is not None:
            model.tick(pygame.time.get_ticks())

    def draw(self, canvas: Render) -> None:
        roles = self.app.theme.roles
        t = self.app.translator.t
        canvas.draw_backdrop(roles)
        model = self.app.replay_model
        if model is None:
            return
        record = model._record
        self.board_view.draw(
            canvas,
            model.board,
            flipped=record.black_id == "human",
            moves=tuple(record.moves[: model.index]),
        )

        self._card(canvas, self.INFO)
        canvas.text(
            11,
            t("replay.eyebrow").upper(),
            roles["glow"],
            (self.INFO.left + 14, self.INFO.top + 10),
            bold=True,
        )
        canvas.text(
            16,
            f"{record.white_name} vs {record.black_name}",
            roles["text"],
            (self.INFO.left + 14, self.INFO.top + 28),
            bold=True,
            max_width=self.INFO.width - 28,
        )
        winner = record.result.winner
        outcome = (
            t("game.result.draw")
            if winner is None
            else t("game.result.win", name=record.white_name if winner else record.black_name)
        )
        canvas.text(
            12,
            self.notice or f"{outcome} · {t(f'termination.{record.result.termination.value}')}",
            roles["glow"] if self.notice else roles["text_muted"],
            (self.INFO.left + 14, self.INFO.top + 56),
            max_width=self.INFO.width - 28,
        )

        self._card(canvas, self.MOVES, t("panel.moves"))
        self._draw_moves(canvas, record.moves, model.index)

        value = model.current_move.material_eval if model.current_move else 0.0
        self._card(canvas, self.EVAL, t("panel.eval_bar"))
        draw_eval_bar(
            canvas,
            pygame.Rect(self.EVAL.left + 14, self.EVAL.top + 44, 196, 10),
            value,
            self.app.theme,
        )
        canvas.text(
            16,
            f"{value:+.2f}",
            roles["primary"],
            (self.EVAL.left + 224, self.EVAL.top + 38),
            bold=True,
        )

        self._card(canvas, self.CONTROLS)
        for index, button in enumerate(self.controls):
            button.draw(canvas, 10)
            self._draw_icon(canvas, button, index, model.playing)
        self.speed.label = self._speed_label()
        self.speed.draw(canvas, 13)
        progress = t("replay.progress", index=model.index, total=len(record.moves))
        width = round(canvas.font(12, canvas.scale, True).size(progress)[0] / canvas.scale)
        canvas.text(
            12, progress, roles["text_muted"], (self.CONTROLS.right - 14 - width, 549), bold=True
        )
        self.export.draw(canvas, 13)
        self.back.draw(canvas, 13)

    def _card(self, canvas: Render, rect: pygame.Rect, label: str = "") -> None:
        """Draw a side-panel glass card with an optional small-caps title."""
        roles = self.app.theme.roles
        canvas.draw_glass(
            rect, roles["surface"], alpha=225, border=roles["border"], rim=roles["rim"]
        )
        if label:
            canvas.draw_circle(roles["glow"], (rect.left + 13, rect.top + 14), 3)
            canvas.text(
                11,
                label.upper(),
                roles["text_muted"],
                (rect.left + 23, rect.top + 7),
                bold=True,
                max_width=rect.width - 36,
            )

    def _draw_icon(self, canvas: Render, button: Button, index: int, playing: bool) -> None:
        """Draw the first / previous / play-pause / next / last glyph on a control button."""
        roles = self.app.theme.roles
        if index == 2:
            color = roles["on_primary"]
        elif button.hovered:
            color = roles.get("on_secondary_hover", roles["on_secondary"])
        else:
            color = roles["text"]
        x, y = button.rect.center
        if index == 2:
            if playing:
                canvas.draw_rect(color, (x - 6, y - 7, 4, 14), radius=1)
                canvas.draw_rect(color, (x + 2, y - 7, 4, 14), radius=1)
            else:
                canvas.draw_polygon(color, ((x - 5, y - 8), (x - 5, y + 8), (x + 8, y)))
            return
        forward = index > 2
        sign = 1 if forward else -1
        tip = x + 4 * sign
        canvas.draw_polygon(color, ((tip, y), (tip - 9 * sign, y - 7), (tip - 9 * sign, y + 7)))
        if index in (0, 4):
            canvas.draw_rect(color, (tip if forward else tip - 2, y - 7, 2, 14))

    def _draw_moves(self, canvas: Render, moves: list[MoveRecord], index: int) -> None:
        """Draw all SAN moves and highlight the move at the replay position."""
        roles = self.app.theme.roles
        rect = pygame.Rect(self.MOVES.left + 8, self.MOVES.top + 34, self.MOVES.width - 16, 254)
        line_height = 24
        visible = max(1, rect.height // line_height)
        current_row = max(0, (index - 1) // 2)
        row_count = (len(moves) + 1) // 2
        first_row = min(max(0, current_row - visible // 2), max(0, row_count - visible))
        column = (rect.width - 44) // 2
        for row in range(first_row, min(row_count, first_row + visible)):
            y = rect.top + (row - first_row) * line_height
            if row % 2:
                canvas.draw_rect(roles["surface_alt"], (rect.left, y, rect.width, 22), radius=6)
            canvas.text(
                13, f"{row + 1}", roles["text_muted"], (0, 0), center=(rect.left + 18, y + 11)
            )
            for offset in range(2):
                move_index = row * 2 + offset
                if move_index >= len(moves):
                    continue
                x = rect.left + 40 + offset * column
                current = move_index == index - 1
                if current:
                    canvas.draw_glass(
                        (x - 4, y + 1, column - 4, 20), roles["accent"], alpha=70, radius=5
                    )
                    canvas.draw_rect(roles["glow"], (x - 4, y + 3, 2, 16))
                canvas.text(
                    13,
                    moves[move_index].san,
                    roles["text"],
                    (x, y + 2),
                    bold=current,
                    max_width=column - 8,
                )
