"""Tests for sound event selection and failure-tolerant playback."""

from pathlib import Path

import chess

from gui.sound import SOUND_EVENTS, SoundManager, sound_for_move


def test_sound_events_and_check_takes_precedence_over_capture() -> None:
    board = chess.Board("4k3/4p3/8/8/8/8/8/4R1K1 w - - 0 1")
    assert SOUND_EVENTS == ("move", "capture", "check", "game_end")
    assert sound_for_move(board, chess.Move.from_uci("e1e7")) == "check"


def test_en_passant_is_classified_as_capture() -> None:
    board = chess.Board("4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 2")
    move = chess.Move.from_uci("e5d6")
    assert board.is_en_passant(move)
    assert sound_for_move(board, move) == "capture"


def test_sound_manager_plays_generated_wave_with_dummy_driver(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    sounds_dir = tmp_path / "sounds"
    sounds_dir.mkdir()
    source = Path("frontend/gui/assets/sounds/move.wav")
    (sounds_dir / "move.wav").write_bytes(source.read_bytes())
    manager = SoundManager(sounds_dir, enabled=True)
    manager.play("move")
    assert manager.enabled
    manager.enabled = False
    manager.play("move")
    assert not manager.enabled


def test_disabled_and_missing_sounds_never_raise(tmp_path) -> None:
    disabled = SoundManager(tmp_path / "missing", enabled=False)
    disabled.play("move")
    disabled.enabled = True
    disabled.play("move")
    disabled.play("unknown")
