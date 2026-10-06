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
_NEAR_WHITE = "#FAF9F6"     # Warmer, aesthetic off-white
_NEAR_BLACK = "#2A2826"     # Softer, elegant dark charcoal


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


# Redesigned palettes based on modern, aesthetic Canva product templates
# Ordered strictly from Darkest to Lightest for harmonious algorithmic generation
PALETTES: dict[str, tuple[str, str, str, str]] = {
    # Inspired by Matcha/Sage green product designs (Earthy, calming)
    "dark_winter": ("#1B291C", "#3C5740", "#98A88E", "#F3F6EB"),
    # Inspired by Lavender/Purple midnight cosmetics (Mysterious, elegant)
    "dark_cold": ("#2A1E35", "#513B6B", "#A895C2", "#F5F3F7"),
    # Inspired by Clean minimalist UI / Sky blue (Fresh, airy)
    "cold": ("#1E2A38", "#53708F", "#B2C5D8", "#F0F4F8"),
    # Inspired by Mocha/Chocolate flyers (Warm, rich, appetizing)
    "fall": ("#3E2211", "#7A4E35", "#D2B49E", "#FAF4F0"),
    # Inspired by Blush pink/Skincare highlights (Soft, sweet, inviting)
    "summer": ("#4A1C22", "#A65A68", "#E6ACB4", "#FDF5F5"),
    # Inspired by Beige minimalist aesthetic/Tote bags (Neutral, sophisticated)
    "winter": ("#242322", "#6B6661", "#C4BFBA", "#F5F3EF"),
}

NAMES: dict[str, tuple[str, str]] = {
    "dark_winter": ("Trà Xanh", "Matcha Latte"),
    "dark_cold": ("Oải Hương", "Deep Lavender"),
    "cold": ("Bầu Trời", "Aesthetic Sky"),
    "fall": ("Cà Phê", "Mocha Chocolate"),
    "summer": ("Mỹ Phẩm", "Blush Pink"),
    "winter": ("Tối Giản", "Minimalist Beige"),
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
        ("#E27A77", "#D15C59", "#B33E3C", "#8C2624") # Soft, dusty coral reds
        if danger
        else ("#EAD29C", "#D9B86A", "#B39147", "#8C6E2E") # Creamy mustard / muted gold
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
    # Giảm bớt ép màu rực để giữ lại sức sống, kết hợp tăng độ sáng/tối nhẹ để tạo độ phản quang
    middle_colors = [
        lighten(_mix(_desaturate(color, 0.15), background, 0.12), 0.08) if dark
        else darken(_mix(_desaturate(color, 0.15), background, 0.12), 0.05)
        for color in ordered[1:3]
    ]
        
    # Tăng độ tương phản của viền và bề mặt phụ để khối nổi khối (3D highlight/Specular)
    surface_alt = _mix(surface, middle_colors[-1] if dark else middle_colors[0], 0.20)
    border = _mix(surface, lightest if dark else darkest, 0.25)  # Tăng lên 25% để viền sắc nét, bắt sáng hơn

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
    fallback_name = f"Color Hunt #{theme_id.removeprefix('ch_')}"
    return Theme(
        theme_id,
        name_vi or fallback_name,
        name_en or fallback_name,
        colors,  # type: ignore[arg-type]
        roles,
    )


def _handpicked_dark_winter() -> Theme:
    """Build the new Matcha (dark_winter) palette with curated Canva-style visual balance."""
    # Updated to the beautiful earthy matcha tone from the palette
    colors = PALETTES["dark_winter"]
    roles = {
        "bg": "#1B291C",              # Deep rich forest black-green
        "surface": "#243625",         # Smooth elevated leaf tone
        "surface_alt": "#2E4530",     # Subtle tertiary background
        "border": "#3C5740",          # Soft integrated border
        "text": "#F3F6EB",            # Creamy matcha milk text
        "text_muted": "#98A88E",      # Sage green muted text
        "text_disabled": "#5A6D56",   # Deep olive disabled text
        "primary": "#4C6B45",         # Bold leaf green
        "primary_hover": "#5A7D52",   # Lighter pop for hover
        "on_primary_hover": "#F3F6EB",
        "on_primary": "#FFFFFF",
        "secondary": "#3C5740",
        "secondary_hover": "#49694E",
        "on_secondary_hover": "#F3F6EB",
        "on_secondary": "#F3F6EB",
        "accent": "#98A88E",          # Soft sage accent
        "on_accent": "#141D14",
        "attention": "#D6A85B",       # Warm earthy gold
        "danger": "#D16A65",          # Soft coral red
        "board_light": "#E9EFE4",     # Soft pastel matcha paper
        "board_dark": "#7B9675",      # Earthy green board tone
        "board_select": "#66A374",    
        "board_last": "#D6A85B",      
        "board_hint": "#2A402D",      
    }
    
    # Ensuring algorithm safety and accessibility remains intact
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