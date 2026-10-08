"""Human versus bot game screen."""

from __future__ import annotations

from typing import TYPE_CHECKING

import chess
import pygame

from gui import board_geometry, game_info
from gui.assets_loader import get_font, render_fit
from gui.controller import ControllerSnapshot
from gui.move_input import MoveInput
from gui.render import Render
from gui.screens.base import Screen
from gui.sound import sound_for_move
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
        self.stop_button = Button(pygame.Rect(656, 592, 132, 34), app.translator.t("game.stop"))
        self.stop_button.style = "danger"
        self.menu_button = Button(
            pygame.Rect(800, 592, 136, 34), app.translator.t("game.back_to_menu")
        )
        self.result_again = Button(
            pygame.Rect(284, 412, 166, 46), app.translator.t("game.play_again")
        )
        self.result_menu = Button(
            pygame.Rect(464, 412, 166, 46), app.translator.t("game.back_to_menu")
        )
        self.is_bot_game = app.game_mode == "bot_vs_bot"
        self.sound_button = Button(pygame.Rect(648, 8, 96, 30), "")
        self.pause_button = Button(pygame.Rect(748, 8, 80, 30), app.translator.t("game.pause"))
        self.speed_button = Button(pygame.Rect(832, 8, 120, 30), self._speed_label())
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
        canvas.fill(self.app.theme.roles["bg"])
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
        canvas.draw_rect(self.app.theme.roles["surface"], (640, 0, 320, 640))
        self._draw_panel(canvas, snapshot)
        self.sound_button.label = self.app.translator.t(
            "settings.sound_on" if self.app.sound_enabled else "settings.sound_off"
        )
        self._draw_sound_button(canvas)
        if self.is_bot_game:
            self.pause_button.label = self.app.translator.t(
                "game.resume" if snapshot.paused else "game.pause"
            )
            self.pause_button.draw(canvas, get_font(11, bold=True))
            self.speed_button.draw(canvas, get_font(11, bold=True))
        if snapshot.finished:
            self._draw_result(canvas, snapshot)

    def _draw_sound_button(self, canvas: Render) -> None:
        label = self.sound_button.label
        self.sound_button.label = ""
        self.sound_button.draw(canvas, get_font(11, bold=True))
        self.sound_button.label = label
        color = self.app.theme.roles["text"]
        canvas.draw_polygon(
            color,
            [(652, 18), (658, 18), (667, 12), (667, 34), (658, 28), (652, 28)],
        )
        if self.app.sound_enabled:
            canvas.draw_arc(color, pygame.Rect(662, 14, 14, 18), -0.9, 0.9, 2)
            canvas.draw_arc(color, pygame.Rect(662, 10, 21, 26), -0.9, 0.9, 2)
        else:
            canvas.draw_line(color, (670, 15), (681, 29), 2)
            canvas.draw_line(color, (681, 15), (670, 29), 2)
        canvas.text(13, self.sound_button.label, color, (689, 15), bold=True, max_width=47)

    def _draw_panel(self, canvas: pygame.Surface, snapshot: ControllerSnapshot) -> None:
        font = get_font(15)
        header = get_font(16, bold=True)
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
        status = (
            self.app.translator.t("game.thinking", name=bot_name)
            if snapshot.thinking
            else self.app.translator.t("game.your_turn")
            if snapshot.waiting_for_human
            else ""
        )
        body_heights = {
            "players": 88 + (20 if status else 0)
            if self.is_bot_game
            else 46 + (20 if status else 0),
            "eval": 96,
            "moves": 130,
            "timing": 38,
            "captured": 24,
        }
        section_y = 44
        for key, section in self.sections.items():
            height = 28 + (body_heights[key] if section.expanded else 0)
            section.rect.top = section_y
            section.rect.height = height
            section_y += height + 4

        players = self.sections["players"]
        players.draw_header(canvas, self.app.translator.t("panel.score"), header, self.app.theme)
        if players.expanded:
            white_label = self.app.translator.t("setup.color_white")
            black_label = self.app.translator.t("setup.color_black")
            canvas.blit(
                render_fit(font, f"{white_label}  {white_name}", self.app.theme.roles["text"], 248),
                (680, players.rect.top + 31),
            )
            canvas.blit(
                render_fit(
                    font, f"{black_label}  {black_name}", self.app.theme.roles["text_muted"], 248
                ),
                (680, players.rect.top + 54),
            )
            if self.is_bot_game:
                series = snapshot.series_result
                score_a, score_b = (
                    (series.score_a, series.score_b)
                    if series is not None
                    else self._series_scores(snapshot)
                )
                if not snapshot.first_is_white:
                    score_a, score_b = score_b, score_a  # keep "White - Black" order
                score = f"{score_a:g} - {score_b:g}"
                info = self.app.translator.t(
                    "game.game_index", index=snapshot.game_index, total=snapshot.n_games
                )
                canvas.blit(
                    render_fit(
                        get_font(12), f"{score}   ·   {info}", self.app.theme.roles["accent"], 248
                    ),
                    (680, players.rect.top + 77),
                )
            if status:
                canvas.blit(
                    render_fit(
                        get_font(13),
                        status,
                        self.app.theme.roles["attention"]
                        if snapshot.waiting_for_human
                        else self.app.theme.roles["accent"],
                        248,
                    ),
                    (680, players.rect.top + (96 if self.is_bot_game else 77)),
                )

        evaluation = self.sections["eval"]
        evaluation.draw_header(
            canvas, self.app.translator.t("panel.eval_bar"), header, self.app.theme
        )
        if evaluation.expanded:
            value = snapshot.moves[-1].material_eval if snapshot.moves else 0.0
            body_y = evaluation.rect.top + 32
            draw_eval_bar(canvas, pygame.Rect(668, body_y, 24, 72), value, self.app.theme)
            canvas.blit(
                font.render(f"{value:+.2f}", True, self.app.theme.roles["text"]), (705, body_y + 15)
            )
            canvas.blit(
                render_fit(
                    font,
                    self.app.translator.t("game.check") if snapshot.board.is_check() else "",
                    self.app.theme.roles["danger"],
                    220,
                ),
                (705, body_y + 42),
            )

        moves = self.sections["moves"]
        moves.draw_header(canvas, self.app.translator.t("panel.moves"), header, self.app.theme)
        if moves.expanded:
            draw_move_list(
                canvas,
                pygame.Rect(656, moves.rect.top + 32, 280, 122),
                snapshot.moves,
                font,
                self.app.theme,
            )

        timing = self.sections["timing"]
        timing.draw_header(
            canvas, self.app.translator.t("panel.think_time"), header, self.app.theme
        )
        if timing.expanded:
            summary = game_info.think_time_summary(snapshot.moves)
            for row, color in enumerate((chess.WHITE, chess.BLACK)):
                latest, average = summary[color]
                text = "—" if latest is None else f"{latest:.2f}s / {average:.2f}s"
                canvas.blit(
                    render_fit(get_font(13), text, self.app.theme.roles["text"], 244),
                    (682, timing.rect.top + 32 + row * 18),
                )

        captured = self.sections["captured"]
        captured.draw_header(
            canvas, self.app.translator.t("panel.captured"), header, self.app.theme
        )
        if captured.expanded:
            pieces = game_info.captured_pieces(snapshot.board)
            white = self.app.translator.t("setup.color_white")
            black = self.app.translator.t("setup.color_black")
            text = f"{white}: {len(pieces[chess.WHITE])}   ·   {black}: {len(pieces[chess.BLACK])}"
            canvas.blit(
                render_fit(get_font(13), text, self.app.theme.roles["text"], 248),
                (680, captured.rect.top + 34),
            )
        self.stop_button.draw(canvas, get_font(13, bold=True))
        self.menu_button.draw(canvas, get_font(13, bold=True))

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
        side = round(640 * canvas.scale)
        veil = pygame.Surface((side, side), pygame.SRCALPHA)
        veil.fill((*pygame.Color(self.app.theme.roles["bg"])[:3], 205))
        canvas.surface.blit(veil, (0, 0))
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
        canvas.blit(
            render_fit(get_font(28, bold=True), title, self.app.theme.roles["text"], 440),
            (100, 270),
        )
        canvas.blit(
            render_fit(get_font(17), reason, self.app.theme.roles["text_muted"], 440), (100, 316)
        )
        self.result_again.draw(canvas, get_font(15, bold=True))
        self.result_menu.draw(canvas, get_font(15, bold=True))

    def on_exit(self) -> None:
        self.input.clear()
