"""Step through a saved game and export its PGN."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from core.types import MoveRecord
from gui.assets_loader import get_font
from gui.render import Render
from gui.screens.base import Screen
from gui.widgets.board_view import BoardView
from gui.widgets.button import Button
from gui.widgets.eval_bar import draw_eval_bar

if TYPE_CHECKING:
    from gui.app import App


class ReplayScreen(Screen):
    """Render replay controls and the selected position."""

    def __init__(self, app: App) -> None:
        super().__init__(app)
        self.record_id = app.replay_model._record.game_id
        self.board_view = BoardView(app.theme, app.config.get("ui", {}).get("piece_set", "rhosgfx"))
        self.export = Button(pygame.Rect(660, 570, 130, 38), app.translator.t("history.export_pgn"))
        self.back = Button(pygame.Rect(810, 570, 120, 38), app.translator.t("setup.back"))
        keys = ("first", "prev", "play", "next", "last")
        self.controls = [
            Button(pygame.Rect(652 + i * 58, 510, 54, 34), app.translator.t(f"replay.{key}"))
            for i, key in enumerate(keys)
        ]
        self.speed = Button(pygame.Rect(770, 465, 150, 34), self._speed_label())
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
        canvas.fill(self.app.theme.roles["bg"])
        model = self.app.replay_model
        if model is None:
            return
        record = model._record
        self.board_view.draw(
            canvas,
            model.board,
            flipped=record.black_id == "human",
            moves=tuple(model._record.moves[: model.index]),
        )
        canvas.draw_rect(self.app.theme.roles["surface"], (640, 0, 320, 640))
        canvas.blit(
            get_font(23, bold=True).render(
                self.app.translator.t("replay.title"), True, self.app.theme.roles["text"]
            ),
            (670, 24),
        )
        canvas.blit(
            get_font(12).render(
                f"{record.white_name} vs {record.black_name}", True, self.app.theme.roles["text"]
            ),
            (660, 64),
        )
        self._draw_moves(canvas, record.moves, model.index)
        value = model.current_move.material_eval if model.current_move else 0.0
        draw_eval_bar(canvas, pygame.Rect(670, 402, 22, 70), value, self.app.theme)
        canvas.blit(
            get_font(14).render(f"{value:+.2f}", True, self.app.theme.roles["text"]), (706, 426)
        )
        for button in self.controls:
            button.draw(canvas, get_font(10))
        self.speed.label = self._speed_label()
        self.speed.draw(canvas, get_font(13))
        self.export.draw(canvas, get_font(12))
        self.back.draw(canvas, get_font(13))
        if self.notice:
            canvas.blit(
                get_font(10).render(self.notice[:45], True, self.app.theme.roles["accent"]),
                (655, 615),
            )

    def _draw_moves(self, canvas: Render, moves: list[MoveRecord], index: int) -> None:
        """Draw all SAN moves and highlight the move at the replay position."""
        rect = pygame.Rect(656, 100, 280, 280)
        canvas.draw_rect(self.app.theme.roles["surface"], rect, radius=10)
        font = get_font(13)
        line_height = 24
        visible = max(1, rect.height // line_height)
        current_row = max(0, (index - 1) // 2)
        row_count = (len(moves) + 1) // 2
        first_row = min(max(0, current_row - visible // 2), max(0, row_count - visible))
        for row in range(first_row, min(row_count, first_row + visible)):
            y = rect.top + 5 + (row - first_row) * line_height
            for offset in range(2):
                move_index = row * 2 + offset
                if move_index >= len(moves):
                    continue
                x = rect.left + (39 if offset == 0 else 139)
                if move_index == index - 1:
                    canvas.draw_rect(
                        self.app.theme.roles["surface_alt"],
                        (x - 4, y - 2, 92, 21),
                        radius=4,
                    )
                canvas.blit(
                    font.render(moves[move_index].san, True, self.app.theme.roles["text"]),
                    (x, y),
                )
            canvas.blit(
                font.render(f"{row + 1:>2}.", True, self.app.theme.roles["text_muted"]),
                (rect.left + 8, y),
            )
