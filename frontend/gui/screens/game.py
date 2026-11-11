"""Human versus bot game screen."""

from __future__ import annotations

from typing import TYPE_CHECKING

import chess
import pygame

from gui import board_geometry, game_info
from gui.controller import ControllerSnapshot
from gui.move_input import MoveInput
from gui.render import Render
from gui.screens.base import Screen
from gui.sound import sound_for_move
from gui.theme import side_colors
from gui.widgets.board_view import BoardView
from gui.widgets.button import Button
from gui.widgets.eval_bar import draw_eval_bar
from gui.widgets.move_list import draw_move_list
from gui.widgets.panel import PanelSection
from gui.widgets.promotion_dialog import PromotionDialog

if TYPE_CHECKING:
    from gui.app import App


class GameScreen(Screen):
    """Render a controller snapshot and route human board input."""

    def __init__(self, app: App) -> None:
        super().__init__(app)
        cfg = app.config
        self.input = MoveInput()
        self.flipped = app.human_color == chess.BLACK
        self.board_view = BoardView(app.theme, cfg.get("ui", {}).get("piece_set", "rhosgfx"))
        self.dialog: PromotionDialog | None = None
        self.sections = {
            "players": PanelSection("players", 24, 64),
            "eval": PanelSection("eval", 106, 145),
            "moves": PanelSection("moves", 266, 186),
            "timing": PanelSection("timing", 467, 74, expanded=False),
            "captured": PanelSection("captured", 554, 62, expanded=False),
        }
        self.stop_button = Button(pygame.Rect(652, 594, 142, 38), app.translator.t("game.stop"))
        self.stop_button.style = "danger"
        self.menu_button = Button(
            pygame.Rect(802, 594, 146, 38), app.translator.t("game.back_to_menu")
        )
        self.result_again = Button(
            pygame.Rect(140, 376, 172, 46), app.translator.t("game.play_again")
        )
        self.result_again.style = "primary"
        self.result_menu = Button(
            pygame.Rect(328, 376, 172, 46), app.translator.t("game.back_to_menu")
        )
        self.is_bot_game = app.game_mode == "bot_vs_bot"
        self.sound_button = Button(pygame.Rect(652, 8, 92, 30), "")
        self.pause_button = Button(pygame.Rect(750, 8, 84, 30), app.translator.t("game.pause"))
        self.speed_button = Button(pygame.Rect(840, 8, 108, 30), self._speed_label())
        self.speaker_button_rect = self.sound_button.rect
        self.pause_button_rect = self.pause_button.rect
        self.speed_button_rect = self.speed_button.rect
        self._played_moves = 0
        self._played_finished_games = 0

    def _speed_label(self) -> str:
        delay = self.app.config.get("ui", {}).get("bot_move_delay_ms", 300)
        return f"{self.app.translator.t('game.speed')}: {delay}"

    def _cycle_speed(self) -> None:
        """Cycle the Bot vs Bot delay and refresh its label."""
        current = self.app.config.get("ui", {}).get("bot_move_delay_ms", 300)
        delay = {0: 150, 150: 300, 300: 800, 800: 0}.get(current, 0)
        self.app.set_bot_move_delay(delay)
        self.speed_button.label = self._speed_label()

    def update(self) -> None:
        snapshot = self.app.controller.snapshot()
        if len(snapshot.moves) < self._played_moves:
            self._played_moves = 0
        if len(snapshot.moves) > self._played_moves:
            board = chess.Board()
            for item in snapshot.moves[: self._played_moves]:
                board.push_uci(item.uci)
            for item in snapshot.moves[self._played_moves :]:
                move = chess.Move.from_uci(item.uci)
                self.app.sound.play(sound_for_move(board, move))
                board.push(move)
            self._played_moves = len(snapshot.moves)
        if len(snapshot.finished_games) > self._played_finished_games:
            self.app.sound.play("game_end")
            self._played_finished_games = len(snapshot.finished_games)

    def handle_click(self, x: float, y: float) -> None:
        point = (x, y)
        snapshot = self.app.controller.snapshot()
        if self.dialog:
            choice = self.dialog.choice_at(point)
            if choice is False:
                self.input.clear()
                self.dialog = None
            elif choice is not None:
                self.app.controller.submit_human_move(self.input.choose_promotion(choice))
                self.dialog = None
            return
        if snapshot.finished:
            if self.result_again.contains(point):
                if self.is_bot_game:
                    self.app.start_bot_game(
                        self.app.white_bot_id, self.app.black_bot_id, self.app.n_games
                    )
                else:
                    self.app.start_human_game(self.app.game_bot_id, self.app.human_color)
            elif self.result_menu.contains(point):
                self.app.goto("menu")
            elif self.is_bot_game and self.speed_button.contains(point):
                self._cycle_speed()
            elif self.sound_button.contains(point):
                self.app.set_sound_enabled(not self.app.sound_enabled)
            elif self.menu_button.contains(point):
                self.app.goto("menu")
            else:
                for section in self.sections.values():
                    if section.hit_header(point):
                        section.expanded = not section.expanded
                        break
            return
        if self.stop_button.contains(point):
            self.app.controller.stop()
            return
        if self.menu_button.contains(point):
            self.app.goto("menu")
            return
        if self.sound_button.contains(point):
            self.app.set_sound_enabled(not self.app.sound_enabled)
            return
        if self.is_bot_game and self.pause_button.contains(point):
            self.app.controller.resume() if snapshot.paused else self.app.controller.pause()
            return
        if self.is_bot_game and self.speed_button.contains(point):
            self._cycle_speed()
            return
        for section in self.sections.values():
            if section.hit_header(point):
                section.expanded = not section.expanded
                return
        if not snapshot.waiting_for_human or not (0 <= x < 640 and 0 <= y < 640):
            return
        square = board_geometry.square_at(x, y, flipped=self.flipped)
        result = self.input.click(snapshot.board, square, self.app.human_color)
        if result.kind == "move" and result.move is not None:
            self.app.controller.submit_human_move(result.move)
        elif result.kind == "promotion":
            self.dialog = PromotionDialog(
                self.app.human_color, self.board_view.piece_set, self.app.theme
            )

    def draw(self, canvas: Render) -> None:
        roles = self.app.theme.roles
        canvas.draw_backdrop(roles)
        snapshot = self.app.controller.snapshot()
        targets = self.input.legal_targets(snapshot.board) if snapshot.waiting_for_human else set()
        self.board_view.draw(
            canvas,
            snapshot.board,
            flipped=self.flipped,
            selected=self.input.selected,
            targets=targets,
            moves=snapshot.moves,
            dialog=self.dialog,
            translator=self.app.translator,
        )
        canvas.draw_line(roles["border"], (640, 0), (640, 640), 1)
        self._draw_panel(canvas, snapshot)
        self.sound_button.label = self.app.translator.t(
            "settings.sound_on" if self.app.sound_enabled else "settings.sound_off"
        )
        self._draw_sound_button(canvas)
        if self.is_bot_game:
            self.pause_button.label = self.app.translator.t(
                "game.resume" if snapshot.paused else "game.pause"
            )
            self.pause_button.draw(canvas, 12)
            self.speed_button.draw(canvas, 12)
        if snapshot.finished:
            self._draw_result(canvas, snapshot)

    def _draw_sound_button(self, canvas: Render) -> None:
        label = self.sound_button.label
        self.sound_button.label = ""
        self.sound_button.draw(canvas, 12)
        self.sound_button.label = label
        color = self.app.theme.roles["text"]
        left, top = self.sound_button.rect.topleft
        canvas.draw_polygon(
            color,
            [
                (left + 10, top + 11),
                (left + 15, top + 11),
                (left + 22, top + 6),
                (left + 22, top + 24),
                (left + 15, top + 19),
                (left + 10, top + 19),
            ],
        )
        if self.app.sound_enabled:
            canvas.draw_arc(color, pygame.Rect(left + 18, top + 9, 10, 12), -0.9, 0.9, 2)
            canvas.draw_arc(color, pygame.Rect(left + 18, top + 5, 16, 20), -0.9, 0.9, 2)
        else:
            canvas.draw_line(color, (left + 26, top + 11), (left + 33, top + 19), 2)
            canvas.draw_line(color, (left + 33, top + 11), (left + 26, top + 19), 2)
        canvas.text(
            12, self.sound_button.label, color, (left + 40, top + 7), bold=True, max_width=48
        )

    def _player_names(self, snapshot: ControllerSnapshot) -> tuple[str, str, str]:
        """Return White, Black and the name of the side that is thinking."""
        bot_name = self.app.bot_display_name
        human_name = self.app.translator.t("players.human")
        if self.is_bot_game:
            first_name = self.app._localized_bot_name(self.app.white_bot_id)
            second_name = self.app._localized_bot_name(self.app.black_bot_id)
            white_name, black_name = (
                (first_name, second_name) if snapshot.first_is_white else (second_name, first_name)
            )
            # Name the bot whose turn it is, not always the one that started as White.
            if snapshot.thinking_color is not None:
                bot_name = white_name if snapshot.thinking_color == chess.WHITE else black_name
        else:
            white_name = human_name if self.app.human_color else bot_name
            black_name = bot_name if self.app.human_color else human_name
        return white_name, black_name, bot_name

    def _layout_sections(self, status: str) -> dict[str, int]:
        """Stack the panel cards and give the move list the remaining height."""
        header = PanelSection.HEADER
        body = {
            "players": (82 if self.is_bot_game else 64) + (20 if status else 0),
            "eval": 40,
            "moves": 0,
            "timing": 44,
            "captured": 26,
        }
        fixed = sum(
            header + 6 + (body[key] + 4 if section.expanded else 0)
            for key, section in self.sections.items()
            if key != "moves"
        )
        body["moves"] = max(48, 586 - 46 - fixed - header - 4)
        top = 46
        for key, section in self.sections.items():
            height = header + (body[key] + 4 if section.expanded else 0)
            section.rect.top = top
            section.rect.height = height
            top += height + 6
        return body

    def _draw_panel(self, canvas: Render, snapshot: ControllerSnapshot) -> None:
        roles = self.app.theme.roles
        t = self.app.translator.t
        white_name, black_name, bot_name = self._player_names(snapshot)
        status = (
            t("game.thinking", name=bot_name)
            if snapshot.thinking
            else t("game.your_turn")
            if snapshot.waiting_for_human
            else ""
        )
        body = self._layout_sections(status)
        header = PanelSection.HEADER

        players = self.sections["players"]
        players.draw_header(canvas, t("panel.score"), 11, self.app.theme)
        if players.expanded:
            left = players.rect.left
            y = players.rect.top + header
            for color, name in ((chess.WHITE, white_name), (chess.BLACK, black_name)):
                active = not snapshot.finished and snapshot.board.turn == color
                if active:
                    canvas.draw_glass(
                        (left + 8, y, players.rect.width - 16, 28),
                        roles["accent"],
                        alpha=55,
                        radius=8,
                    )
                chip = side_colors(self.app.theme)[0 if color == chess.WHITE else 1]
                canvas.draw_circle(chip, (left + 22, y + 14), 7)
                canvas.draw_circle(roles["glow"], (left + 22, y + 14), 7, 1)
                canvas.text(
                    14,
                    name,
                    roles["text"] if active else roles["text_muted"],
                    (left + 38, y + 5),
                    bold=active,
                    max_width=players.rect.width - 52,
                )
                y += 30
            if self.is_bot_game:
                series = snapshot.series_result
                score_a, score_b = (
                    (series.score_a, series.score_b)
                    if series is not None
                    else self._series_scores(snapshot)
                )
                if not snapshot.first_is_white:
                    score_a, score_b = score_b, score_a  # keep "White - Black" order
                info = t("game.game_index", index=snapshot.game_index, total=snapshot.n_games)
                canvas.text(18, f"{score_a:g} - {score_b:g}", roles["primary"], (left + 16, y))
                canvas.text(
                    12,
                    info,
                    roles["text_muted"],
                    (left + 110, y + 4),
                    max_width=players.rect.width - 124,
                )
                y += 22
            if status:
                canvas.text(
                    12,
                    status,
                    roles["attention"] if snapshot.waiting_for_human else roles["glow"],
                    (left + 16, y + 2),
                    bold=True,
                    max_width=players.rect.width - 30,
                )

        evaluation = self.sections["eval"]
        evaluation.draw_header(canvas, t("panel.eval_bar"), 11, self.app.theme)
        if evaluation.expanded:
            value = snapshot.moves[-1].material_eval if snapshot.moves else 0.0
            body_y = evaluation.rect.top + header
            draw_eval_bar(
                canvas,
                pygame.Rect(evaluation.rect.left + 14, body_y + 14, 170, 10),
                value,
                self.app.theme,
            )
            canvas.text(
                18,
                f"{value:+.2f}",
                roles["text"],
                (evaluation.rect.left + 198, body_y + 4),
            )
            if snapshot.board.is_check():
                canvas.text(
                    12,
                    t("game.check"),
                    roles["danger"],
                    (evaluation.rect.left + 180, evaluation.rect.top + 7),
                    bold=True,
                    max_width=80,
                )

        moves = self.sections["moves"]
        moves.draw_header(canvas, t("panel.moves"), 11, self.app.theme)
        if moves.expanded:
            draw_move_list(
                canvas,
                pygame.Rect(
                    moves.rect.left + 8,
                    moves.rect.top + header,
                    moves.rect.width - 16,
                    body["moves"],
                ),
                snapshot.moves,
                13,
                self.app.theme,
            )

        timing = self.sections["timing"]
        timing.draw_header(canvas, t("panel.think_time"), 11, self.app.theme)
        if timing.expanded:
            summary = game_info.think_time_summary(snapshot.moves)
            for row, color in enumerate((chess.WHITE, chess.BLACK)):
                latest, average = summary[color]
                label = t("setup.color_white" if color == chess.WHITE else "setup.color_black")
                text = "—" if latest is None else f"{latest:.2f}s / {average:.2f}s"
                y = timing.rect.top + header + row * 20
                canvas.text(12, label, roles["text_muted"], (timing.rect.left + 16, y + 1))
                canvas.text(13, text, roles["text"], (timing.rect.left + 96, y), bold=True)

        captured = self.sections["captured"]
        captured.draw_header(canvas, t("panel.captured"), 11, self.app.theme)
        if captured.expanded:
            pieces = game_info.captured_pieces(snapshot.board)
            white = t("setup.color_white")
            black = t("setup.color_black")
            text = f"{white}: {len(pieces[chess.WHITE])}   ·   {black}: {len(pieces[chess.BLACK])}"
            canvas.text(
                13,
                text,
                roles["text"],
                (captured.rect.left + 16, captured.rect.top + header),
                max_width=captured.rect.width - 30,
            )
        self.stop_button.draw(canvas, 14)
        self.menu_button.draw(canvas, 14)

    def _series_scores(self, snapshot: ControllerSnapshot) -> tuple[float, float]:
        """Calculate the live score from games already completed in the series."""
        score_a = 0.0
        score_b = 0.0
        for record in snapshot.finished_games:
            a_is_white = record.white_id == self.app.white_bot_id
            if record.result.winner is None:
                score_a += 0.5
                score_b += 0.5
                continue
            a_won = (record.result.winner == chess.WHITE) == a_is_white
            if a_won:
                score_a += 1.0
            else:
                score_b += 1.0
        return score_a, score_b

    def _draw_result(self, canvas: pygame.Surface, snapshot: ControllerSnapshot) -> None:
        roles = self.app.theme.roles
        canvas.draw_glass((0, 0, 640, 640), roles["bg"], alpha=170, radius=0)
        canvas.draw_glass(
            (100, 196, 440, 248),
            roles["surface"],
            alpha=240,
            radius=16,
            border=roles["rim"],
            rim=roles["glow"],
        )
        record = snapshot.finished_games[-1] if snapshot.finished_games else None
        if record is None:
            title = self.app.translator.t("game.result.aborted")
            reason = ""
        elif record.error:
            title = self.app.translator.t("game.result.error", message=record.error)
            reason = self.app.translator.t("termination.aborted")
        elif record.result.winner is None:
            title = self.app.translator.t("game.result.draw")
            reason = self.app.translator.t(f"termination.{record.result.termination.value}")
        else:
            winner_id, winner = (
                (record.white_id, record.white_name)
                if record.result.winner == chess.WHITE
                else (record.black_id, record.black_name)
            )
            if winner_id in self.app._baseline_bot_ids:
                winner = self.app._localized_bot_name(winner_id)
            title = self.app.translator.t("game.result.win", name=winner)
            reason = self.app.translator.t(f"termination.{record.result.termination.value}")
        if self.is_bot_game and snapshot.series_result is not None and snapshot.finished:
            series = snapshot.series_result
            score = f"{series.score_a:g} - {series.score_b:g}"
            key = "game.result.series_draw" if series.winner is None else "game.result.series_win"
            winner_id = self.app.white_bot_id if series.winner == "a" else self.app.black_bot_id
            name = self.app._localized_bot_name(winner_id)
            title = self.app.translator.t(key, name=name, score=score)
            reason = ""
        canvas.text(
            12,
            self.app.translator.t("game.game_over").upper(),
            roles["glow"],
            (0, 0),
            bold=True,
            center=(320, 228),
        )
        canvas.text(26, title, roles["text"], (0, 0), bold=True, max_width=400, center=(320, 276))
        canvas.text(16, reason, roles["text_muted"], (0, 0), max_width=400, center=(320, 320))
        self.result_again.draw(canvas, 15)
        self.result_menu.draw(canvas, 15)

    def on_exit(self) -> None:
        self.input.clear()
