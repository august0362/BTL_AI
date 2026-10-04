"""Board colors stay muted while board overlays remain visible."""

import colorsys

from gui.theme import THEMES, contrast_ratio


def test_every_theme_has_muted_board_tones_and_visible_overlays() -> None:
    for theme in THEMES.values():
        roles = theme.roles
        for key, saturation_limit, lightness_range in (
            ("board_light", 0.35, (0.78, 0.94)),
            ("board_dark", 0.45, (0.38, 0.62)),
        ):
            red, green, blue = (int(roles[key][index : index + 2], 16) / 255 for index in (1, 3, 5))
            _, lightness, saturation = colorsys.rgb_to_hls(red, green, blue)
            assert saturation <= saturation_limit + 0.02  # dung sai: chỉnh tương phản sau bước kẹp
            assert lightness_range[0] - 0.02 <= lightness <= lightness_range[1] + 0.02
        for overlay in ("board_select", "board_last", "board_hint"):
            assert all(
                contrast_ratio(roles[overlay], roles[square]) >= 1.3
                for square in ("board_light", "board_dark")
            )
