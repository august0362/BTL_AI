"""WCAG checks and resource discovery for generated themes."""

import colorsys

import pytest

import gui.theme as theme_module
from gui.theme import THEMES, contrast_ratio, darken, derive_theme, lighten, relative_luminance


def test_wcag_contrast_helpers_match_known_values():
    assert relative_luminance("#000000") == 0
    assert relative_luminance("#FFFFFF") == pytest.approx(1)
    assert contrast_ratio("#000000", "#FFFFFF") == pytest.approx(21)
    assert contrast_ratio("#777777", "#FFFFFF") == pytest.approx(4.48, abs=0.01)


def test_hls_adjustments_preserve_hue():
    source = "#3E0F8D"
    hue = colorsys.rgb_to_hls(*(channel / 255 for channel in bytes.fromhex(source[1:])))[0]
    for adjusted in (lighten(source, 0.25), darken(source, 0.25)):
        channels = tuple(int(adjusted[index : index + 2], 16) / 255 for index in (1, 3, 5))
        assert colorsys.rgb_to_hls(*channels)[0] == pytest.approx(hue, abs=0.001)


def test_every_theme_passes_contrast_and_piece_outline_thresholds():
    assert len(THEMES) == 24
    for theme in THEMES.values():
        roles = theme.roles
        assert contrast_ratio(roles["text"], roles["bg"]) >= 4.5
        assert contrast_ratio(roles["text"], roles["surface"]) >= 4.5
        assert contrast_ratio(roles["text_muted"], roles["bg"]) >= 3
        assert contrast_ratio(roles["on_primary"], roles["primary"]) >= 4.5
        assert contrast_ratio(roles["on_primary_hover"], roles["primary_hover"]) >= 4.5
        assert contrast_ratio(roles["on_secondary"], roles["secondary"]) >= 4.5
        assert contrast_ratio(roles["on_secondary_hover"], roles["secondary_hover"]) >= 4.5
        assert contrast_ratio(roles["on_accent"], roles["accent"]) >= 4.5
        assert contrast_ratio(roles["on_danger"], roles["danger"]) >= 4.5
        assert contrast_ratio(roles["accent"], roles["secondary"]) >= 1.5
        assert contrast_ratio(roles["attention"], roles["bg"]) >= 3
        assert contrast_ratio(roles["danger"], roles["bg"]) >= 3
        assert contrast_ratio(roles["board_light"], roles["board_dark"]) >= 1.6
        assert contrast_ratio("#1A1A1A", roles["board_light"]) >= 3
        assert contrast_ratio("#1A1A1A", roles["board_dark"]) >= 3


def test_dark_light_classification_uses_palette_luminance_rule():
    dark = derive_theme(["#000000", "#112233", "#445566", "#FFFFFF"])
    light = derive_theme(["#444444", "#666666", "#888888", "#999999"])
    assert dark.is_dark
    assert not light.is_dark
    for theme in THEMES.values():
        darkest = min(theme.palette, key=relative_luminance)
        lightest = max(theme.palette, key=relative_luminance)
        expected_dark = (
            relative_luminance(darkest) < 0.08 and contrast_ratio(darkest, lightest) >= 4.5
        )
        assert theme.is_dark is expected_dark


def test_duplicate_color_hunt_palette_is_skipped():
    assert "ch_e3f2fd" not in THEMES
    assert sum(theme_id.startswith("ch_") for theme_id in THEMES) == 18


def test_unknown_resource_palette_gets_a_fallback_name(tmp_path, monkeypatch):
    filename = "Color Hunt Palette 123456ABCDEF9876543210FF.png"
    (tmp_path / filename).touch()
    monkeypatch.setattr(theme_module, "THEME_DIR", tmp_path)

    themes = theme_module.load_themes()
    theme = themes["ch_123456"]
    assert theme.palette == ("#123456", "#ABCDEF", "#987654", "#3210FF")
    assert theme.name_vi == "Color Hunt #123456"
    assert theme.name_en == "Color Hunt #123456"
    assert contrast_ratio(theme.roles["text"], theme.roles["bg"]) >= 4.5
