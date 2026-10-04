"""Load, merge, and save the project's TOML configuration."""

import tomllib
from copy import deepcopy
from pathlib import Path
from typing import Any

import tomli_w

_CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"
DEFAULT_CONFIG_PATH = _CONFIG_DIR / "default.toml"
LOCAL_CONFIG_PATH = _CONFIG_DIR / "local.toml"


def load_config(
    default_path: str | Path = DEFAULT_CONFIG_PATH,
    local_path: str | Path | None = LOCAL_CONFIG_PATH,
) -> dict[str, Any]:
    """Load defaults and apply local TOML overrides when present."""
    with Path(default_path).open("rb") as default_file:
        defaults = tomllib.load(default_file)
    if local_path is None or not Path(local_path).is_file():
        return defaults
    with Path(local_path).open("rb") as local_file:
        local = tomllib.load(local_file)
    return deep_merge(defaults, local)


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge mappings into a fresh result without changing inputs."""
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(merged.get(key), dict) and isinstance(value, dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def save_local_config(
    updates: dict[str, Any],
    local_path: str | Path = LOCAL_CONFIG_PATH,
) -> None:
    """Merge updates into the local TOML file and write the result."""
    path = Path(local_path)
    if path.is_file():
        with path.open("rb") as local_file:
            current = tomllib.load(local_file)
    else:
        current = {}
    merged = deep_merge(current, updates)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as local_file:
        tomli_w.dump(merged, local_file)


def get_bot_config(config: dict[str, Any], bot_id: str) -> dict[str, Any]:
    """Return the configuration table for one bot, or an empty mapping."""
    bots = config.get("bots", {})
    if not isinstance(bots, dict):
        return {}
    bot_config = bots.get(bot_id, {})
    return bot_config if isinstance(bot_config, dict) else {}
