"""Pygame application and logical-canvas screen manager."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import chess
import pygame

import gui.render as render_module
from ai import registry
from core.config import LOCAL_CONFIG_PATH, get_bot_config, load_config, save_local_config
from gui.controller import GameController
from gui.i18n import Translator
from gui.render import Render
from gui.replay_model import ReplayModel
from gui.scaling import Viewport
from gui.screens.game import GameScreen
from gui.screens.history import HistoryScreen
from gui.screens.leaderboard import LeaderboardScreen
from gui.screens.menu import MenuScreen
from gui.screens.replay import ReplayScreen
from gui.screens.settings import SettingsScreen
from gui.screens.setup_bots import SetupBotsScreen
from gui.screens.setup_human import SetupHumanScreen
from gui.screens.tournament import TournamentScreen
from gui.screens.tournament_history import TournamentHistoryScreen
from gui.sound import SoundManager
from gui.theme import THEME_IDS, get_theme
from gui.tournament_controller import TournamentController
from tournament.history import History
from tournament.players import HumanPlayer
from tournament.ranking import Ranking
from tournament.tournament_config import TournamentConfig
from tournament.tournament_history import TournamentHistory


class App:
    """Run the Chess AI Tournament GUI on a fixed logical canvas."""

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        data_dir: Path | None = None,
        local_config_path: Path | None = None,
    ) -> None:
        self._set_dpi_awareness()
        pygame.init()
        self.config = config if config is not None else load_config()
        self.local_config_path = Path(local_config_path or LOCAL_CONFIG_PATH)
        repo_root = Path(__file__).resolve().parents[2]
        self.data_dir = Path(data_dir) if data_dir is not None else repo_root / "database" / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        ranking_cfg = self.config.get("ranking", {})
        history_cfg = self.config.get("history", {})
        self.ranking = Ranking(
            self.data_dir / "ranking.json",
            elo_initial=ranking_cfg.get("elo_initial", 1200),
            elo_k=ranking_cfg.get("elo_k", 32),
            known_ids=registry.list_bots(
                include_benchmarks=True,
                max_benchmark_level=registry.benchmark_level(self.config),
            )
            + ["human"],
        )
        self.history = History(self.data_dir / "history", history_cfg.get("max_games", 20))
        self.tournament_settings = TournamentConfig.from_config(self.config)
        self.tournament_history = TournamentHistory(
            self.data_dir / "tournaments", self.tournament_settings.max_history
        )
        self.tournament = TournamentController(
            self.config, settings=self.tournament_settings, history=self.tournament_history
        )
        self._translator = Translator(
            self.config.get("ui", {}).get("language", "vi"), overrides=self._name_overrides()
        )
        window = self.config.get("window", {})
        self.window_size = self._default_window_size(window)
        self.window = pygame.display.set_mode(self.window_size, pygame.RESIZABLE)
        pygame.display.set_caption(self._translator.t("app.title"))
        self.viewport = Viewport.fit(*self.window_size)
        self.render_scale = self.viewport.scale
        self.canvas_size = (self.viewport.width, self.viewport.height)
        self.physical_canvas = pygame.Surface(self.canvas_size)
        self.renderer = Render(self.physical_canvas, self.render_scale)
        self.canvas = self.renderer
        Render.font.cache_clear()
        render_module.FONT_SCALE = self.render_scale
        ui = self.config.setdefault("ui", {})
        theme_id = ui.get("theme", "dark_winter")  # base theme is dark winter
        self.theme = get_theme(theme_id if theme_id in THEME_IDS else "dark_winter")
        ui["theme"] = self.theme.id
        self.clock = pygame.time.Clock()
        self.fps = window.get("fps", 120)
        self._controller: GameController | None = None
        self._current_screen_name = "menu"
        self.screen = MenuScreen(self)
        self._running = True
        self.notice_key = ""
        self.game_bot_id = ""
        self.bot_display_name = ""
        self._baseline_bot_ids: set[str] = set()
        self.human_color = chess.WHITE
        self.white_bot_id = ""
        self.black_bot_id = ""
        self.n_games = 1
        self.game_mode = "human_vs_bot"
        self.replay_model: ReplayModel | None = None
        self.sound = SoundManager(repo_root / "gui" / "assets" / "sounds", self.sound_enabled)

    @property
    def sound_enabled(self) -> bool:
        """Return whether game sounds are enabled."""
        return bool(self.config.get("ui", {}).get("sound_enabled", False))

    @property
    def translator(self) -> Translator:
        """Return the active string translator."""
        return self._translator

    @property
    def controller(self) -> GameController | None:
        """Return the current game controller, if a game is active."""
        return self._controller

    @property
    def current_screen_name(self) -> str:
        """Return the name of the visible screen."""
        return self._current_screen_name

    def _name_overrides(self) -> dict[str, str]:
        """Bot names set in ``[bots.<id>] display_name`` replace the locale names."""
        overrides = {}
        for bot_id, table in self.config.get("bots", {}).items():
            name = table.get("display_name") if isinstance(table, dict) else None
            if isinstance(name, str) and name.strip():
                overrides[f"players.{bot_id}"] = name.strip()
        return overrides

    def _bot_config(self, bot_id: str) -> dict[str, Any]:
        """Return a bot-specific configuration table."""
        return get_bot_config(self.config, bot_id)

    def _localized_bot_name(self, bot_id: str) -> str:
        """Return a localized bot name with its baseline marker when applicable."""
        name = self._translator.t(f"players.{bot_id}")
        if bot_id in self._baseline_bot_ids and bot_id != "baseline":
            name += f" {self._translator.t('players.baseline_suffix')}"
        return name

    def run(self) -> None:
        """Run the event loop until the window closes."""
        while self._running:
            self.render_frame()
            self.clock.tick(self.fps)

    def render_frame(self) -> None:
        """Process events, draw one logical frame, and present it."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.quit()
            elif event.type == pygame.VIDEORESIZE:
                self.resize(event.w, event.h)
            elif event.type == pygame.MOUSEMOTION:
                logical = self.viewport.to_logical(*event.pos)
                if logical is not None:
                    self.screen.handle_hover(*logical)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                logical = self.viewport.to_logical(*event.pos)
                if logical is not None:
                    self.screen.handle_click(*logical)
            elif event.type == pygame.MOUSEWHEEL:
                self.scroll_logical(event.y)
        if not self._running:
            return
        self.screen.update()
        from gui.widgets.button import Button

        Button.current_theme = self.theme
        self.screen.draw(self.renderer)
        self._present()

    def _present(self) -> None:
        """Blit the viewport-sized physical surface directly to the display."""
        self.window.fill((0, 0, 0))
        self.window.blit(self.physical_canvas, (self.viewport.offset_x, self.viewport.offset_y))
        pygame.display.flip()

    def goto(self, name: str) -> None:
        """Switch to an MVP screen, stopping a game when it is left."""
        screen_types = {
            "menu": MenuScreen,
            "setup_human": SetupHumanScreen,
            "setup_bots": SetupBotsScreen,
            "history": HistoryScreen,
            "replay": ReplayScreen,
            "leaderboard": LeaderboardScreen,
            "tournament": TournamentScreen,
            "tournament_history": TournamentHistoryScreen,
            "settings": SettingsScreen,
            "game": GameScreen,
        }
        if name not in screen_types:
            raise ValueError(f"unknown screen: {name}")
        if self._current_screen_name == "game" and name != "game" and self._controller is not None:
            self._controller.stop()
        self.screen.on_exit()
        if name != "menu":
            self.notice_key = ""
        self.screen = screen_types[name](self)
        self._current_screen_name = name

    def start_human_game(self, bot_id: str, human_color: chess.Color) -> None:
        """Create a human versus bot controller and open the game screen."""
        bot = registry.create_bot(bot_id, self._bot_config(bot_id))
        human = HumanPlayer(self._translator.t("players.human"))
        white, black = (human, bot) if human_color == chess.WHITE else (bot, human)
        self.game_bot_id = bot_id
        if bot.is_baseline:
            self._baseline_bot_ids.add(bot_id)
        else:
            self._baseline_bot_ids.discard(bot_id)
        self.bot_display_name = self._localized_bot_name(bot_id)
        self.human_color = human_color
        self.game_mode = "human_vs_bot"
        self._controller = GameController(
            white,
            black,
            mode="human_vs_bot",
            config=self.config,
            ranking=self.ranking,
            history=self.history,
        )
        self._controller.start()
        if self._current_screen_name == "game":
            self.screen.on_exit()
            self.screen = GameScreen(self)
        else:
            self.goto("game")

    def start_bot_game(self, white_id: str, black_id: str, n_games: int) -> None:
        """Create a bot versus bot game or best-of-three series."""
        white = registry.create_bot(white_id, self._bot_config(white_id))
        black = registry.create_bot(black_id, self._bot_config(black_id))
        for bot_id, bot in ((white_id, white), (black_id, black)):
            if bot.is_baseline:
                self._baseline_bot_ids.add(bot_id)
            else:
                self._baseline_bot_ids.discard(bot_id)
        self.white_bot_id, self.black_bot_id, self.n_games = white_id, black_id, n_games
        self.game_mode = "bot_vs_bot"
        self.game_bot_id = white_id
        self.bot_display_name = self._localized_bot_name(white_id)
        self.human_color = chess.WHITE
        self._controller = GameController(
            white,
            black,
            mode="bot_vs_bot",
            n_games=n_games,
            config=self.config,
            ranking=self.ranking,
            history=self.history,
        )
        self._controller.start()
        if self._current_screen_name == "game":
            self.screen.on_exit()
            self.screen = GameScreen(self)
        else:
            self.goto("game")

    def open_replay(self, game_id: str) -> None:
        """Open the saved game with the requested id."""
        self.replay_model = ReplayModel(self.history.load(game_id))
        self.replay_model.delay_ms = self.config.get("ui", {}).get("replay_delay_ms", 800)
        self.goto("replay")

    def start_tournament(self) -> None:
        """Run the AI ranking round-robin in a background thread."""
        self.tournament.start()

    def stop_tournament(self) -> None:
        """Ask the running AI ranking tournament to stop."""
        self.tournament.stop()

    def _save_ui(self, key: str, value: Any) -> None:
        self.config.setdefault("ui", {})[key] = value
        save_local_config({"ui": {key: value}}, self.local_config_path)

    @staticmethod
    def _set_dpi_awareness() -> None:
        """Request physical pixel coordinates on Windows before SDL initializes."""
        import sys

        if sys.platform != "win32":
            return
        try:
            import ctypes

            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except (AttributeError, OSError):
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except (AttributeError, OSError):
                pass

    @staticmethod
    def _default_window_size(window: dict[str, Any]) -> tuple[int, int]:
        """Return configured dimensions, or a DPI-scaled default capped to the display."""
        scale = 1.0
        try:
            import ctypes

            scale = ctypes.windll.user32.GetDpiForSystem() / 96
        except (AttributeError, OSError):
            pass
        try:
            info = pygame.display.Info()
            cap = min(0.9 * info.current_w / 960, 0.9 * info.current_h / 640)
            scale = min(scale, cap)
        except pygame.error:
            pass
        scale = max(0.5, scale)
        base_width, base_height = window.get("width", 960), window.get("height", 640)
        if (base_width, base_height) != (960, 640):
            return base_width, base_height
        return round(960 * scale), round(640 * scale)

    def set_theme(self, theme_id: str) -> None:
        """Apply a theme immediately and persist its stable id."""
        theme = get_theme(theme_id)
        self.theme = theme
        self._save_ui("theme", theme_id)
        self.goto(self._current_screen_name)

    def set_sound_enabled(self, enabled: bool) -> None:
        """Set and persist the sound preference."""
        self._save_ui("sound_enabled", bool(enabled))
        self.sound.enabled = bool(enabled)

    def set_bot_move_delay(self, ms: int) -> None:
        """Set and persist the Bot vs Bot move delay."""
        self._save_ui("bot_move_delay_ms", ms)
        if self.controller is not None:
            self.controller.set_bot_move_delay(ms)

    def set_language(self, language: str) -> None:
        """Change and persist the interface language."""
        if language not in ("vi", "en"):
            raise ValueError("language must be 'vi' or 'en'")
        self._save_ui("language", language)
        self._translator = Translator(language, overrides=self._name_overrides())
        pygame.display.set_caption(self._translator.t("app.title"))
        self.goto(self._current_screen_name)

    def set_replay_delay(self, ms: int) -> None:
        """Set and persist the default replay delay."""
        value = max(100, min(5000, int(ms)))
        self._save_ui("replay_delay_ms", value)
        if self.replay_model is not None:
            self.replay_model.delay_ms = value

    def reset_ranking(self) -> None:
        """Clear all recorded ranking results."""
        self.ranking.reset()

    def click_logical(self, x: float, y: float) -> None:
        """Dispatch a simulated left click in logical canvas coordinates."""
        self.screen.handle_click(x, y)

    def scroll_logical(self, dy: int) -> None:
        """Dispatch simulated vertical wheel movement to the active screen."""
        self.screen.handle_scroll(dy)

    def click_window(self, x: float, y: float) -> None:
        """Dispatch a simulated click after converting from window space."""
        logical = self.viewport.to_logical(x, y)
        if logical is not None:
            self.click_logical(*logical)

    def resize(self, width: int, height: int) -> None:
        """Resize the window and recalculate the letterboxed viewport."""
        if width <= 0 or height <= 0:
            return
        self.window_size = (width, height)
        self.window = pygame.display.set_mode(self.window_size, pygame.RESIZABLE)
        self.viewport = Viewport.fit(width, height)
        self.render_scale = self.viewport.scale
        self.canvas_size = (self.viewport.width, self.viewport.height)
        self.physical_canvas = pygame.Surface(self.canvas_size)
        self.renderer = Render(self.physical_canvas, self.render_scale)
        self.canvas = self.renderer
        Render.font.cache_clear()
        render_module.FONT_SCALE = self.render_scale

    def quit(self) -> None:
        """Stop any active game and shut down Pygame."""
        if self._controller is not None:
            self._controller.stop()
        self.tournament.stop()
        self._running = False
        pygame.quit()


def main() -> None:
    """Launch the desktop application."""
    App().run()
