"""Accessible semantic themes derived from the project's color palettes."""

from __future__ import annotations

import colorsys
import re
from dataclasses import dataclass
from pathlib import Path

THEME_DIR = Path(__file__).resolve().parents[1] / "resource" / "theme"
_HEX_PALETTE = re.compile(r"^Color Hunt Palette ([0-9a-fA-F]{24})\.png$")
_PIECE_OUTLINE = "#1A1A1A"
_NEAR_WHITE = "#F7F6F1"
_NEAR_BLACK = "#19232B"


@dataclass(frozen=True)
class Theme:
    """A named palette with semantic interface and board colors."""

    id: str
    name_vi: str
    name_en: str
    palette: tuple[str, str, str, str]
    roles: dict[str, str]

    @property
    def is_dark(self) -> bool:
        """Return whether the theme uses a dark screen background."""
        return relative_luminance(self.roles["bg"]) < 0.18


PALETTES: dict[str, tuple[str, str, str, str]] = {
    "dark_winter": ("#092328", "#12544F", "#2A835F", "#8BBB92"),
    "dark_cold": ("#091540", "#1B2CC1", "#7692FF", "#ABD2FA"),
    "cold": ("#E3F2FD", "#90CAF9", "#2196F3", "#0D47A1"),
    "fall": ("#E2A16F", "#FFF0DD", "#D1D3D4", "#86B0BD"),
    "summer": ("#FFEED6", "#A5AF79", "#827148", "#E8A07C"),
    "winter": ("#777C6D", "#B7B89F", "#CBCBCB", "#EEEEEE"),
}
NAMES: dict[str, tuple[str, str]] = {
    "dark_winter": ("Rừng đêm", "Night Forest"),
    "dark_cold": ("Biển đêm", "Deep Sea"),
    "cold": ("Bầu trời", "Sky"),
    "fall": ("Mùa thu", "Autumn"),
    "summer": ("Mùa hè", "Summer"),
    "winter": ("Mùa đông", "Winter"),
}
COLOR_HUNT_NAMES: dict[str, tuple[str, str]] = {
    "ch_3368a0": ("Biển sương", "Coastal Mist"),
    "ch_3e0f8d": ("Hoàng hôn tím", "Violet Dusk"),
    "ch_499a13": ("Lá xuân", "Spring Leaf"),
    "ch_601d49": ("Mận chín", "Plum"),
    "ch_a5b68d": ("Đồng cỏ", "Meadow"),
    "ch_bf9264": ("Vườn ô liu", "Olive Grove"),
    "ch_e4e0e1": ("Cà phê", "Coffee"),
    "ch_fbdb93": ("Rượu vang", "Wine"),
    "ch_fbefef": ("Anh đào", "Sakura"),
    "ch_fdf4d2": ("Oải hương", "Lavender"),
    "ch_ff9d9d": ("Kem trái cây", "Sorbet"),
    "ch_ffcdb2": ("Đào", "Peach"),
    "ch_ffdab3": ("Chiều tà", "Dusk"),
    "ch_ffdcdc": ("Sữa dâu", "Strawberry Milk"),
    "ch_ffeecc": ("Kẹo bông", "Cotton Candy"),
    "ch_fff2c6": ("Mây trời", "Daydream"),
    "ch_fff2d7": ("Cát vàng", "Sand"),
    "ch_fff8e8": ("Giấy cổ", "Parchment"),
}


def _rgb(value: str) -> tuple[int, int, int]:
    normalized = value.removeprefix("#")
    if len(normalized) != 6:
        raise ValueError(f"expected a six-digit RGB color, got {value!r}")
    try:
        return tuple(bytes.fromhex(normalized))  # type: ignore[return-value]
    except ValueError as exc:
        raise ValueError(f"invalid RGB color: {value!r}") from exc


def _hex(rgb: tuple[int, int, int]) -> str:
    return f"#{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}"


def _hls(color: str) -> tuple[float, float, float]:
    red, green, blue = (channel / 255 for channel in _rgb(color))
    return colorsys.rgb_to_hls(red, green, blue)


def _with_lightness(color: str, lightness: float) -> str:
    hue, _, saturation = _hls(color)
    rgb = colorsys.hls_to_rgb(hue, min(1.0, max(0.0, lightness)), saturation)
    return _hex(tuple(round(channel * 255) for channel in rgb))


def lighten(color: str, amount: float) -> str:
    """Lighten a color in HLS space while preserving its hue and saturation."""
    if not 0 <= amount <= 1:
        raise ValueError("amount must be between 0 and 1")
    _, lightness, _ = _hls(color)
    return _with_lightness(color, lightness + (1 - lightness) * amount)


def darken(color: str, amount: float) -> str:
    """Darken a color in HLS space while preserving its hue and saturation."""
    if not 0 <= amount <= 1:
        raise ValueError("amount must be between 0 and 1")
    _, lightness, _ = _hls(color)
    return _with_lightness(color, lightness * (1 - amount))


def relative_luminance(color: str) -> float:
    """Calculate WCAG relative luminance for a six-digit RGB color."""
    channels = [channel / 255 for channel in _rgb(color)]
    linear = [
        value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
        for value in channels
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast_ratio(first: str, second: str) -> float:
    """Return the WCAG contrast ratio between two RGB colors."""
    light, dark = sorted((relative_luminance(first), relative_luminance(second)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


def _mix(color: str, target: str, amount: float) -> str:
    first, second = _rgb(color), _rgb(target)
    return _hex(
        tuple(round(a * (1 - amount) + b * amount) for a, b in zip(first, second, strict=True))
    )


def _tones(color: str):
    _, original, _ = _hls(color)
    for index in range(1001):
        lightness = index / 1000
        yield abs(lightness - original), lightness, _with_lightness(color, lightness)


def _foreground(color: str) -> str:
    return max((_NEAR_WHITE, _NEAR_BLACK), key=lambda text: contrast_ratio(text, color))


def _accessible_fill(color: str) -> tuple[str, str]:
    candidates = [
        (distance, fill, text)
        for distance, _, fill in _tones(color)
        for text in (_NEAR_WHITE, _NEAR_BLACK)
        if contrast_ratio(text, fill) >= 4.5
    ]
    if not candidates:
        return color, _foreground(color)
    _, fill, text = min(candidates, key=lambda candidate: candidate[0])
    return fill, text


def _accessible_text(color: str, backgrounds: tuple[str, ...], minimum: float) -> str:
    candidates = [
        (distance, candidate)
        for distance, _, candidate in _tones(color)
        if all(contrast_ratio(candidate, background) >= minimum for background in backgrounds)
    ]
    if candidates:
        return min(candidates, key=lambda item: item[0])[1]
    return max(
        (_NEAR_WHITE, _NEAR_BLACK),
        key=lambda text: min(contrast_ratio(text, background) for background in backgrounds),
    )


def _distinct_fill(color: str, other: str) -> tuple[str, str]:
    candidates = [
        (distance, fill, text)
        for distance, _, fill in _tones(color)
        if contrast_ratio(fill, other) >= 1.5
        for text in (_NEAR_WHITE, _NEAR_BLACK)
        if contrast_ratio(text, fill) >= 4.5
    ]
    if not candidates:
        return _accessible_fill(color)
    _, fill, text = min(candidates, key=lambda candidate: candidate[0])
    return fill, text


def _tone_for_minimum_luminance(color: str, minimum: float) -> str:
    candidates = [
        (distance, candidate)
        for distance, _, candidate in _tones(color)
        if relative_luminance(candidate) >= minimum
    ]
    return min(candidates, key=lambda item: item[0])[1] if candidates else "#FFFFFF"


def _tone_for_board_contrast(color: str, other: str) -> str:
    candidates = [
        (distance, candidate)
        for distance, _, candidate in _tones(color)
        if contrast_ratio(candidate, other) >= 1.6
    ]
    return min(candidates, key=lambda item: item[0])[1] if candidates else "#FFFFFF"


def _muted_board_tones(light: str, dark: str) -> tuple[str, str]:
    """Clamp board colors while retaining their hues and required contrast."""
    sources = (_hls(light), _hls(dark))
    limits = ((0.785, 0.935, 0.34), (0.385, 0.615, 0.44))  # chừa sai số làm tròn hex
    options = []
    for (hue, old_lightness, old_saturation), (low, high, max_saturation) in zip(
        sources, limits, strict=True
    ):
        choices = []
        for saturation_step in range(36):
            saturation = min(max_saturation, saturation_step / 100)
            for lightness_step in range(round(low * 100), round(high * 100) + 1):
                lightness = lightness_step / 100
                rgb = colorsys.hls_to_rgb(hue, lightness, saturation)
                color = _hex(tuple(round(channel * 255) for channel in rgb))
                score = abs(lightness - old_lightness) + abs(saturation - old_saturation)
                choices.append((score, color))
        options.append([color for _, color in sorted(choices)])
    for board_light in options[0]:
        for board_dark in options[1]:
            if (
                contrast_ratio(board_light, board_dark) >= 1.6
                and contrast_ratio(_PIECE_OUTLINE, board_light) >= 3
                and contrast_ratio(_PIECE_OUTLINE, board_dark) >= 3
            ):
                return board_light, board_dark
    raise ValueError("could not derive accessible muted board colors")


def _visible_on_board(color: str, squares: tuple[str, str]) -> str:
    """Adjust an overlay's lightness until it contrasts with both square tones."""
    hue, _, saturation = _hls(color)
    candidates = []
    for lightness_step in range(101):
        lightness = lightness_step / 100
        rgb = colorsys.hls_to_rgb(hue, lightness, saturation)
        candidate = _hex(tuple(round(channel * 255) for channel in rgb))
        if all(contrast_ratio(candidate, square) >= 1.3 for square in squares):
            candidates.append((abs(lightness - _hls(color)[1]), candidate))
    if candidates:
        return min(candidates)[1]
    return max(("#000000", "#FFFFFF"), key=lambda c: min(contrast_ratio(c, s) for s in squares))


def _signal_color(background: str, *, danger: bool) -> str:
    candidates = (
        ("#FF7972", "#E34B48", "#B3261E", "#8E2424")
        if danger
        else ("#FFD166", "#F2B134", "#9A5D00", "#765000")
    )
    valid = []
    for source in candidates:
        color, foreground = _accessible_fill(source)
        if contrast_ratio(color, background) >= 3 and contrast_ratio(color, foreground) >= 4.5:
            valid.append(color)
    if valid:
        return min(valid, key=lambda color: abs(relative_luminance(color) - 0.42))
    source = max(candidates, key=lambda color: contrast_ratio(color, background))
    return _accessible_fill(source)[0]


def derive_theme(
    palette: list[str],
    *,
    theme_id: str = "custom",
    name_vi: str | None = None,
    name_en: str | None = None,
) -> Theme:
    """Derive accessible interface and chessboard roles from four palette colors."""
    if len(palette) != 4:
        raise ValueError("a theme palette must contain exactly four colors")
    colors = tuple(_hex(_rgb(color)) for color in palette)
    ordered = sorted(colors, key=relative_luminance)
    darkest, lightest = ordered[0], ordered[-1]
    dark = relative_luminance(darkest) < 0.08 and contrast_ratio(darkest, lightest) >= 4.5

    if dark:
        background = darkest
        surface = lighten(background, 0.08)
        middle_tone = ordered[2]
    else:
        background = lightest
        surface = darken(background, 0.035)
        middle_tone = ordered[1]
    if surface == background:
        surface = _mix(background, lightest if dark else darkest, 0.06)
    surface_alt = _mix(surface, middle_tone, 0.16)
    border = _mix(middle_tone, background, 0.26)

    middle_colors = ordered[1:3]
    primary_source = max(
        middle_colors, key=lambda color: colorsys.rgb_to_hls(*(v / 255 for v in _rgb(color)))[2]
    )
    secondary_source = next(color for color in middle_colors if color != primary_source)
    primary, on_primary = _accessible_fill(primary_source)
    secondary, on_secondary = _accessible_fill(secondary_source)
    primary_hover, on_primary_hover = _accessible_fill(lighten(primary, 0.12))
    secondary_hover, on_secondary_hover = _accessible_fill(lighten(secondary, 0.12))
    accent_sources = (
        [lightest, darkest, primary_source] if dark else [darkest, lightest, primary_source]
    )
    accent, on_accent = _accessible_fill(accent_sources[0])
    for accent_source in accent_sources:
        candidate, foreground = _distinct_fill(accent_source, secondary)
        if contrast_ratio(candidate, secondary) >= 1.5:
            accent, on_accent = candidate, foreground
            break

    text_source = lightest if dark else darkest
    text_target = _with_lightness(text_source, 0.94 if dark else 0.10)
    text = _accessible_text(text_target, (background, surface), 4.5)
    muted_source = ordered[2] if dark else ordered[1]
    text_muted = _accessible_text(muted_source, (background,), 3)
    text_disabled = _mix(text_muted, background, 0.46)

    board_dark = _tone_for_minimum_luminance(darkest, 0.14)
    board_light = _tone_for_minimum_luminance(lightest, 0.54)
    if contrast_ratio(board_light, board_dark) < 1.6:
        board_light = _tone_for_board_contrast(lightest, board_dark)
    if contrast_ratio(board_light, board_dark) < 1.6:
        board_dark = _tone_for_board_contrast(darkest, board_light)
    board_light, board_dark = _muted_board_tones(board_light, board_dark)
    board_squares = (board_light, board_dark)

    roles = {
        "bg": background,
        "surface": surface,
        "surface_alt": surface_alt,
        "border": border,
        "text": text,
        "text_muted": text_muted,
        "text_disabled": text_disabled,
        "primary": primary,
        "primary_hover": primary_hover,
        "on_primary_hover": on_primary_hover,
        "on_primary": on_primary,
        "secondary": secondary,
        "secondary_hover": secondary_hover,
        "on_secondary_hover": on_secondary_hover,
        "on_secondary": on_secondary,
        "accent": accent,
        "on_accent": on_accent,
        "attention": _signal_color(background, danger=False),
        "danger": _signal_color(background, danger=True),
        "board_light": board_light,
        "board_dark": board_dark,
        "board_select": _visible_on_board(primary, board_squares),
        "board_last": _visible_on_board(_signal_color(background, danger=False), board_squares),
        "board_hint": _visible_on_board(darken(board_dark, 0.28), board_squares),
    }
    roles["on_danger"] = _foreground(roles["danger"])
    fallback_name = f"Color Hunt #{theme_id.removeprefix('ch_')}"
    return Theme(
        theme_id,
        name_vi or fallback_name,
        name_en or fallback_name,
        colors,  # type: ignore[arg-type]
        roles,
    )


def _handpicked_dark_winter() -> Theme:
    """Build the original forest palette while retaining its curated visual balance."""
    colors = PALETTES["dark_winter"]
    roles = {
        "bg": "#092328",
        "surface": "#0E3236",
        "surface_alt": "#12423F",
        "border": "#1E5F57",
        "text": "#EAF4EC",
        "text_muted": "#8BBB92",
        "text_disabled": "#668078",
        "primary": "#2A835F",
        "primary_hover": "#369C74",
        "on_primary_hover": "#19232B",
        "on_primary": "#FFFFFF",
        "secondary": "#12544F",
        "secondary_hover": "#1B6D63",
        "on_secondary_hover": "#EAF4EC",
        "on_secondary": "#EAF4EC",
        "accent": "#8BBB92",
        "on_accent": "#111111",
        "attention": "#E9B949",
        "danger": "#D9534F",
        "board_light": "#DDEBDD",
        "board_dark": "#5F9C7C",
        "board_select": "#46B49A",
        "board_last": "#E9B949",
        "board_hint": "#26383B",
    }
    roles["board_light"], roles["board_dark"] = _muted_board_tones(
        roles["board_light"], roles["board_dark"]
    )
    squares = (roles["board_light"], roles["board_dark"])
    for key in ("board_select", "board_last", "board_hint"):
        roles[key] = _visible_on_board(roles[key], squares)
    roles["danger"], roles["on_danger"] = _accessible_fill(roles["danger"])
    return Theme("dark_winter", *NAMES["dark_winter"], colors, roles)


def load_themes(theme_dir: Path | None = None) -> dict[str, Theme]:
    """Build built-in themes and discover Color Hunt palettes from filenames."""
    themes = {
        theme_id: (
            _handpicked_dark_winter()
            if theme_id == "dark_winter"
            else derive_theme(
                list(colors),
                theme_id=theme_id,
                name_vi=NAMES[theme_id][0],
                name_en=NAMES[theme_id][1],
            )
        )
        for theme_id, colors in PALETTES.items()
    }
    seen = {tuple(sorted(theme.palette)) for theme in themes.values()}
    directory = Path(theme_dir) if theme_dir is not None else THEME_DIR
    if not directory.is_dir():
        return themes
    for path in sorted(directory.iterdir()):
        match = _HEX_PALETTE.fullmatch(path.name)
        if not match:
            continue
        hex_palette = match.group(1).upper()
        colors = tuple(f"#{hex_palette[index : index + 6]}" for index in range(0, 24, 6))
        canonical = tuple(sorted(colors))
        if canonical in seen:
            continue
        theme_id = f"ch_{hex_palette[:6].lower()}"
        name_vi, name_en = COLOR_HUNT_NAMES.get(
            theme_id, (f"Color Hunt #{hex_palette[:6]}", f"Color Hunt #{hex_palette[:6]}")
        )
        themes[theme_id] = derive_theme(
            list(colors), theme_id=theme_id, name_vi=name_vi, name_en=name_en
        )
        seen.add(canonical)
    return themes


THEMES = load_themes()
THEME_IDS = tuple(THEMES)


def get_theme(theme_id: str) -> Theme:
    """Return a theme by its stable config id."""
    try:
        return THEMES[theme_id]
    except KeyError as exc:
        raise ValueError(f"unknown theme: {theme_id}") from exc
