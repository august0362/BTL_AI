"""Accessible semantic themes derived from the project's color palettes.
Redesigned with a modern, harmonious, and aesthetic 'Canva-style' UI/UX approach.
"""

from __future__ import annotations

import colorsys
import re
from dataclasses import dataclass
from pathlib import Path

THEME_DIR = Path(__file__).resolve().parents[1] / "resource" / "theme"
_HEX_PALETTE = re.compile(r"^Color Hunt Palette ([0-9a-fA-F]{24})\.png$")
_PIECE_OUTLINE = "#1C1B1A"  # Softer off-black for pieces
_NEAR_WHITE = "#FAF9F6"  # Warmer, aesthetic off-white
_NEAR_BLACK = "#2A2826"  # Softer, elegant dark charcoal


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


# Two handpicked themes: Cyber Frost (dark) and Frost Light (light).
# Ordered strictly from Darkest to Lightest for harmonious algorithmic generation
PALETTES: dict[str, tuple[str, str, str, str]] = {
    # Cyber Frost: Black Pine, Deep Ocean, Windstorm, Avalanche
    "dark_winter": ("#0A151B", "#1B3D59", "#6A97C0", "#D4EEF8"),
    # Frost Light: the daytime variant of Cyber Frost
    "cold": ("#0F1E2A", "#336288", "#9ECBF7", "#EEF4F9"),
    # Violet Nightfall: Ink Shadow, Indigo Night, Violet Mist, Pale Lilac
    "dark_cold": ("#090B0C", "#2F3559", "#7272B0", "#DCD5E5"),
    # Lantern Night: Tobi Brown, Apple Blossom, Bonfire, Buttermilk
    "fall": ("#482420", "#B24D37", "#F78358", "#FFEEB0"),
    # Periwinkle: Mystification, Orbital, Gladeye, First Snow
    "periwinkle": ("#2E3E6D", "#7087BB", "#A2B7E4", "#E5EDFA"),
    # Cherry Blossom: Indochine, Cinnamon Brandy, Hush Puppy, Lace Veil
    "summer": ("#9C5C34", "#D08F6B", "#E5B194", "#EBEBEA"),
    # Muted Romance: Twilight Navy, Dusty Rose, Lavender Mist, Almond Blush
    "winter": ("#4D516D", "#A8868C", "#B5A4B4", "#D3BCB6"),
}

NAMES: dict[str, tuple[str, str]] = {
    "dark_winter": ("Băng Giá", "Cyber Frost"),
    "cold": ("Băng Sáng", "Frost Light"),
    "dark_cold": ("Tím Đêm", "Violet Nightfall"),
    "fall": ("Đèn Lồng", "Lantern Night"),
    "periwinkle": ("Thiên Thanh", "Periwinkle"),
    "summer": ("Hoa Anh Đào", "Cherry Blossom"),
    "winter": ("Chiều Tím", "Muted Romance"),
}

COLOR_HUNT_NAMES: dict[str, tuple[str, str]] = {}


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


def _desaturate(color: str, amount: float) -> str:
    """Reduce color saturation for a more muted, premium aesthetic."""
    if not 0 <= amount <= 1:
        raise ValueError("amount must be between 0 and 1")
    hue, lightness, saturation = _hls(color)
    rgb = colorsys.hls_to_rgb(hue, lightness, max(0.0, saturation * (1 - amount)))
    return _hex(tuple(round(channel * 255) for channel in rgb))


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
    # Adjusted limits for a softer, more pastel/matte board aesthetic
    limits = ((0.75, 0.95, 0.28), (0.42, 0.65, 0.35))
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
    # Tuned to softer, aesthetic Canva-style semantic colors (Corals and Warm Golds)
    candidates = (
        ("#E27A77", "#D15C59", "#B33E3C", "#8C2624")  # Soft, dusty coral reds
        if danger
        else ("#EAD29C", "#D9B86A", "#B39147", "#8C6E2E")  # Creamy mustard / muted gold
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
        # Much softer elevation for a modern UI look
        surface = lighten(background, 0.035)
    else:
        background = lightest
        # Very subtle off-white elevation
        surface = darken(background, 0.02)

    if surface == background:
        surface = _mix(background, lightest if dark else darkest, 0.04)

    # --- AESTHETIC HARMONY WASH (UPDATED FOR REFLECTANCE) ---
    middle_colors = [
        lighten(_mix(_desaturate(color, 0.15), background, 0.12), 0.08)
        if dark
        else darken(_mix(_desaturate(color, 0.15), background, 0.12), 0.05)
        for color in ordered[1:3]
    ]

    surface_alt = _mix(surface, middle_colors[-1] if dark else middle_colors[0], 0.20)
    border = _mix(surface, lightest if dark else darkest, 0.25)

    primary_source = max(
        middle_colors, key=lambda color: colorsys.rgb_to_hls(*(v / 255 for v in _rgb(color)))[2]
    )
    secondary_source = next(color for color in middle_colors if color != primary_source)
    primary, on_primary = _accessible_fill(primary_source)
    secondary, on_secondary = _accessible_fill(secondary_source)

    # Modern hover states: Bật sáng mạnh hơn (18%) để tạo hiệu ứng phát sáng (Glow) khi tương tác
    primary_hover, on_primary_hover = _accessible_fill(lighten(primary, 0.18))
    secondary_hover, on_secondary_hover = _accessible_fill(lighten(secondary, 0.18))

    accent_sources = (
        [lightest, darkest, primary_source] if dark else [darkest, lightest, primary_source]
    )
    accent, on_accent = _accessible_fill(accent_sources[0])
    for accent_source in accent_sources:
        candidate, foreground = _distinct_fill(accent_source, secondary)
        if contrast_ratio(candidate, secondary) >= 1.5:
            accent, on_accent = candidate, foreground
            break

    # Harmonized text colors that feel integrated into the theme
    text_source = lightest if dark else darkest
    text_target = _with_lightness(text_source, 0.95 if dark else 0.12)
    text = _accessible_text(text_target, (background, surface), 4.5)
    muted_source = ordered[2] if dark else ordered[1]
    text_muted = _accessible_text(muted_source, (background,), 3.5)
    text_disabled = _mix(text_muted, background, 0.5)

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
        "board_hint": _visible_on_board(darken(board_dark, 0.20), board_squares),
    }
    roles["on_danger"] = _foreground(roles["danger"])
    _with_frost_roles(roles)
    fallback_name = f"Color Hunt #{theme_id.removeprefix('ch_')}"
    return Theme(
        theme_id,
        name_vi or fallback_name,
        name_en or fallback_name,
        colors,  # type: ignore[arg-type]
        roles,
    )


# Curated roles for the palettes of the Stitch "Cyber Frost Chess AI" design.
_HANDPICKED_ROLES: dict[str, dict[str, str]] = {
    "dark_winter": {
        "bg": "#0A151B",  # Black Pine night
        "surface": "#121D23",  # Frosted card
        "surface_alt": "#1D2A33",  # Raised row / selected row
        "border": "#2B3A45",  # Glass edge
        "text": "#D8E4EC",
        "text_muted": "#93A3B0",
        "text_disabled": "#4F5E69",
        "primary": "#9ECBF7",  # Ice blue call to action
        "primary_hover": "#BBDCFB",
        "on_primary_hover": "#002A45",
        "on_primary": "#002E4B",
        "secondary": "#1B3D59",  # Deep Ocean
        "secondary_hover": "#284A61",
        "on_secondary_hover": "#E5EDFA",
        "on_secondary": "#D4EEF8",
        "accent": "#6A97C0",  # Windstorm
        "on_accent": "#001D32",
        "attention": "#F3EED8",  # Sun Beam
        "danger": "#FFB4AB",
        "board_light": "#D4EEF8",  # Avalanche
        "board_dark": "#4F7699",  # Windstorm, deep enough for both piece colors
        "board_select": "#9ECBF7",
        "board_last": "#6A97C0",
        "board_hint": "#0A151B",
    },
    "cold": {
        "bg": "#EAF1F7",
        "surface": "#FFFFFF",
        "surface_alt": "#E1EBF4",
        "border": "#C5D4E1",
        "text": "#0F1E2A",
        "text_muted": "#4D6070",
        "text_disabled": "#9AABB9",
        "primary": "#336288",
        "primary_hover": "#3F74A0",
        "on_primary_hover": "#FFFFFF",
        "on_primary": "#FFFFFF",
        "secondary": "#D4E6F4",
        "secondary_hover": "#C2DBEF",
        "on_secondary_hover": "#0E334A",
        "on_secondary": "#0E334A",
        "accent": "#1B3D59",
        "on_accent": "#E5EDFA",
        "attention": "#7A5C00",
        "danger": "#BA1A1A",
        "board_light": "#E4F0F8",
        "board_dark": "#6A97C0",
        "board_select": "#336288",
        "board_last": "#9ECBF7",
        "board_hint": "#0A151B",
        "rim": "#FFFFFF",
        "glow": "#336288",
    },
    "dark_cold": {
        "bg": "#0B0C10",  # Ink Shadow
        "surface": "#15161F",
        "surface_alt": "#1F2132",
        "border": "#30334A",
        "text": "#E6E0EE",
        "text_muted": "#A89EB4",
        "text_disabled": "#575468",
        "primary": "#B9B3F0",
        "primary_hover": "#CCC7F6",
        "on_primary_hover": "#1E1A4A",
        "on_primary": "#1E1A4A",
        "secondary": "#2F3559",  # Indigo Night
        "secondary_hover": "#3B4270",
        "on_secondary_hover": "#EEE9F4",
        "on_secondary": "#DCD5E5",
        "accent": "#7A7AB8",  # Violet Mist
        "on_accent": "#0B0C14",
        "attention": "#E8D7A8",
        "danger": "#FFB4AB",
        "board_light": "#DCD5E5",  # Pale Lilac
        "board_dark": "#6C6CA8",
        "board_select": "#B9B3F0",
        "board_last": "#B7A8BD",
        "board_hint": "#0B0C10",
    },
    "fall": {
        "bg": "#1C0F0D",  # Tobi Brown night
        "surface": "#261613",
        "surface_alt": "#331E1A",
        "border": "#4A2C26",
        "text": "#FBE9D7",
        "text_muted": "#C9A493",
        "text_disabled": "#6E4E45",
        "primary": "#F78358",  # Bonfire
        "primary_hover": "#F99A75",
        "on_primary_hover": "#2A0F07",
        "on_primary": "#2A0F07",
        "secondary": "#482420",  # Tobi Brown
        "secondary_hover": "#5A2E28",
        "on_secondary_hover": "#FFF6D6",
        "on_secondary": "#FFEEB0",
        "accent": "#F59C6A",  # Copper River
        "on_accent": "#2A0F07",
        "attention": "#FEBF7C",  # Peach
        "danger": "#FF8A80",
        "board_light": "#FFEEB0",  # Buttermilk
        "board_dark": "#B24D37",  # Apple Blossom
        "board_select": "#FEBF7C",
        "board_last": "#F59C6A",
        "board_hint": "#1C0F0D",
    },
    "periwinkle": {
        "bg": "#11162A",
        "surface": "#181F38",
        "surface_alt": "#222B4A",
        "border": "#33406A",
        "text": "#E5EDFA",  # First Snow
        "text_muted": "#A2B0CF",
        "text_disabled": "#55608A",
        "primary": "#A2B7E4",  # Gladeye
        "primary_hover": "#BBD0ED",
        "on_primary_hover": "#13204A",
        "on_primary": "#13204A",
        "secondary": "#2E3E6D",  # Mystification
        "secondary_hover": "#3A4C80",
        "on_secondary_hover": "#FFFFFF",
        "on_secondary": "#E5EDFA",
        "accent": "#7087BB",  # Orbital
        "on_accent": "#0B1230",
        "attention": "#F3E3B0",
        "danger": "#FFB4AB",
        "board_light": "#E5EDFA",
        "board_dark": "#7087BB",
        "board_select": "#A2B7E4",
        "board_last": "#BBD0ED",
        "board_hint": "#11162A",
    },
    "summer": {
        "bg": "#F6F1EC",  # Lace Veil, warmed
        "surface": "#FFFFFF",
        "surface_alt": "#F3E6DC",
        "border": "#E2CDBE",
        "text": "#3A2216",
        "text_muted": "#7A5442",
        "text_disabled": "#BFA595",
        "primary": "#9C5C34",  # Indochine
        "primary_hover": "#B06A3E",
        "on_primary_hover": "#FFFFFF",
        "on_primary": "#FFFFFF",
        "secondary": "#EECEB9",  # Desert Field
        "secondary_hover": "#E8BFA4",
        "on_secondary_hover": "#4A2A18",
        "on_secondary": "#4A2A18",
        "accent": "#D08F6B",  # Cinnamon Brandy
        "on_accent": "#2A1408",
        "attention": "#8A5A00",
        "danger": "#BA1A1A",
        "board_light": "#F6E6DA",
        "board_dark": "#D08F6B",
        "board_select": "#9C5C34",
        "board_last": "#E5B194",  # Hush Puppy
        "board_hint": "#3A2216",
        "rim": "#FFFFFF",
        "glow": "#9C5C34",
    },
    "winter": {
        "bg": "#EEEBE7",  # Almond haze
        "surface": "#FBFAF8",
        "surface_alt": "#E6E0DD",
        "border": "#D3CAC6",
        "text": "#23253A",
        "text_muted": "#5E5A6E",
        "text_disabled": "#ABA4AE",
        "primary": "#4D516D",  # Twilight Navy
        "primary_hover": "#5D6282",
        "on_primary_hover": "#FFFFFF",
        "on_primary": "#FFFFFF",
        "secondary": "#DCCCC8",
        "secondary_hover": "#D3BCB6",  # Almond Blush
        "on_secondary_hover": "#3A2F3A",
        "on_secondary": "#3A2F3A",
        "accent": "#A8868C",  # Dusty Rose
        "on_accent": "#1A1420",
        "attention": "#7A5600",
        "danger": "#BA1A1A",
        "board_light": "#EFE6E2",
        "board_dark": "#A8868C",
        "board_select": "#4D516D",
        "board_last": "#B5A4B4",  # Lavender Mist
        "board_hint": "#23253A",
        "rim": "#FFFFFF",
        "glow": "#4D516D",
    },
}


def _handpicked(theme_id: str) -> Theme:
    """Build a curated theme, keeping its board overlays and danger color legible."""
    roles = dict(_HANDPICKED_ROLES[theme_id])
    squares = (roles["board_light"], roles["board_dark"])
    for key in ("board_select", "board_last", "board_hint"):
        roles[key] = _visible_on_board(roles[key], squares)
    roles["danger"], roles["on_danger"] = _accessible_fill(roles["danger"])
    return Theme(theme_id, *NAMES[theme_id], PALETTES[theme_id], _with_frost_roles(roles))


def _with_frost_roles(roles: dict[str, str]) -> dict[str, str]:
    """Add the glass rim and glow roles shared by every theme."""
    roles.setdefault("rim", _mix(roles["border"], roles["text"], 0.22))
    roles.setdefault("glow", roles["primary"])
    return roles


def load_themes(theme_dir: Path | None = None) -> dict[str, Theme]:
    """Build built-in themes and discover Color Hunt palettes from filenames."""
    themes = {
        theme_id: (
            _handpicked(theme_id)
            if theme_id in _HANDPICKED_ROLES
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


def side_colors(theme: Theme) -> tuple[str, str]:
    """Return the swatch colors that stand for White and Black on this theme."""
    roles = theme.roles
    return roles["board_light"], roles["bg"] if theme.is_dark else roles["text"]


def get_theme(theme_id: str) -> Theme:
    """Return a theme by its stable config id."""
    try:
        return THEMES[theme_id]
    except KeyError as exc:
        raise ValueError(f"unknown theme: {theme_id}") from exc
