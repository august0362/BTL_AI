"""run.bat launcher: model download, update, offline fallback and config layer."""

import hashlib
import json
from pathlib import Path

import pytest

import launcher
from core.config import load_config


def _asset(src: Path, name: str = "net.pt") -> dict:
    data = src.read_bytes()
    return {
        "name": name,
        "dir": "backend/ai/deep_rl/weights",
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "url": src.as_uri(),
    }


def _manifest(version: str, asset: dict) -> dict:
    return {"format": 1, "version": version, "assets": [asset], "config": {"bots": {"x": {"a": 1}}}}


@pytest.fixture
def env(tmp_path: Path) -> tuple[Path, Path, Path]:
    root = tmp_path / "app"
    (root / "backend" / "ai").mkdir(parents=True)
    local = root / "backend" / "config" / "models.json"
    local.parent.mkdir(parents=True)
    store = tmp_path / "release"
    store.mkdir()
    return root, local, store


def test_fresh_install_then_no_redownload(env, monkeypatch):
    root, local, store = env
    (store / "v1.pt").write_bytes(b"one" * 1000)
    remote = _manifest("v1", _asset(store / "v1.pt"))
    assert launcher.update_models(lambda: remote, root, local)
    target = root / "backend/ai/deep_rl/weights/net.pt"
    assert target.read_bytes() == b"one" * 1000
    assert json.loads(local.read_text(encoding="utf-8")) == remote

    calls = []
    monkeypatch.setattr(launcher, "download", lambda *a: calls.append(a))
    assert launcher.update_models(lambda: remote, root, local)
    assert calls == []


def test_update_replaces_only_after_verification(env):
    root, local, store = env
    (store / "v1.pt").write_bytes(b"old")
    launcher.update_models(lambda: _manifest("v1", _asset(store / "v1.pt")), root, local)
    target = root / "backend/ai/deep_rl/weights/net.pt"

    (store / "v2.pt").write_bytes(b"new!")
    bad = _asset(store / "v2.pt")
    bad["sha256"] = "0" * 64
    assert launcher.update_models(lambda: _manifest("v2", bad), root, local)
    assert target.read_bytes() == b"old"  # corrupted update kept the known-good file
    assert json.loads(local.read_text(encoding="utf-8"))["version"] == "v1"
    assert not list(target.parent.glob("*.download"))

    assert launcher.update_models(lambda: _manifest("v2", _asset(store / "v2.pt")), root, local)
    assert target.read_bytes() == b"new!"
    assert json.loads(local.read_text(encoding="utf-8"))["version"] == "v2"


def test_offline_uses_verified_local_models(env):
    root, local, store = env
    (store / "v1.pt").write_bytes(b"abc")
    launcher.update_models(lambda: _manifest("v1", _asset(store / "v1.pt")), root, local)

    def offline():
        raise OSError("no network")

    assert launcher.update_models(offline, root, local)
    (root / "backend/ai/deep_rl/weights/net.pt").write_bytes(b"xyz")  # damaged and offline
    assert not launcher.update_models(offline, root, local)


def test_incompatible_format_and_unsafe_path_are_refused(env):
    root, local, store = env
    (store / "v1.pt").write_bytes(b"abc")
    future = _manifest("v9", _asset(store / "v1.pt")) | {"format": 99}
    assert not launcher.update_models(lambda: future, root, local)
    with pytest.raises(ValueError):
        launcher.asset_path({"dir": "../outside/weights", "name": "x.pt"}, root)


def test_config_merges_models_manifest_under_local(tmp_path: Path):
    (tmp_path / "default.toml").write_text("[bots.x]\na = 0\nb = 0\n", encoding="utf-8")
    manifest = {"config": {"bots": {"x": {"a": 1, "b": 1}}}}
    (tmp_path / "models.json").write_text(json.dumps(manifest), encoding="utf-8")
    (tmp_path / "local.toml").write_text("[bots.x]\nb = 2\n", encoding="utf-8")
    config = load_config(tmp_path / "default.toml", tmp_path / "local.toml")
    assert config["bots"]["x"] == {"a": 1, "b": 2}
