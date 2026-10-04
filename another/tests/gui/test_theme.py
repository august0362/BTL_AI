"""Semantic palette completeness and contrast contracts."""

from pathlib import Path

from gui.theme import THEMES

ROOT = Path(__file__).resolve().parents[3]
REQUIRED = {
    "bg",
    "surface",
    "surface_alt",
    "border",
    "text",
    "text_muted",
    "text_disabled",
    "primary",
    "primary_hover",
    "on_primary",
    "secondary",
    "secondary_hover",
    "on_secondary",
    "accent",
    "attention",
    "danger",
    "board_light",
    "board_dark",
    "board_select",
    "board_last",
    "board_hint",
}


def luminance(color: str) -> float:
    channels = [int(color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [
        value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
        for value in channels
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(first: str, second: str) -> float:
    light, dark = sorted((luminance(first), luminance(second)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


def test_all_themes_have_complete_roles_and_required_contrast():
    for theme in THEMES.values():
        roles = theme.roles
        assert REQUIRED <= roles.keys()
        assert contrast(roles["text"], roles["bg"]) >= 4.5
        assert contrast(roles["text"], roles["surface"]) >= 4.5
        assert contrast(roles["on_primary"], roles["primary"]) >= 4.5
        assert contrast(roles["text_muted"], roles["bg"]) >= 3
        assert contrast(roles["board_light"], roles["board_dark"]) >= 1.6
        assert roles["surface"] != roles["bg"]
        assert roles["text"] != roles["bg"]
        assert roles["primary"] != roles["bg"]


def test_default_config_theme_exists():
    import tomllib

    config = tomllib.loads(
        (ROOT / "backend" / "config" / "default.toml").read_text(encoding="utf-8")
    )
    assert config["ui"]["theme"] in THEMES
