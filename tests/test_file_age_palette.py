"""Design-system contracts for the shared file-age palette."""

from __future__ import annotations

import colorsys
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STYLES_CSS = ROOT / "src" / "metabrowser" / "static" / "styles.css"
FILTER_CONTROLS = ROOT / "src" / "metabrowser" / "static" / "filter_controls.js"
DESIGN_SYSTEM = ROOT / "docs" / "design-system.md"

MINIMUM_TEXT_CONTRAST = 4.5
AGE_STATES = ("live", "sec", "min", "hr", "day", "wk", "old")
AGE_BUCKETS = AGE_STATES[1:]
APPROVED_LIGHT_AGE_PALETTE = {
    "live": (0.66, 0.26, 55.0, 1.0),
    "sec": (0.66, 0.26, 55.0, 1.0),
    "min": (0.72, 0.23, 97.5, 1.0),
    "hr": (0.64, 0.2, 104.0, 1.0),
    "day": (0.56, 0.14, 107.1, 1.0),
    "wk": (0.5, 0.07, 107.8, 1.0),
    "old": (0.48, 0.012, 106.6, 1.0),
}
AGE_SURFACES = (
    "--bg",
    "--sidebar-bg",
    "--hover-bg",
    "--code-bg",
    "--panel-header-bg",
    "--viz-surface-raised",
)

TOKEN_RE = re.compile(r"^\s*(--[\w-]+):\s*([^;]+);", re.MULTILINE)
VAR_RE = re.compile(r"var\((?P<token>--[\w-]+)\)")
HSL_RE = re.compile(
    r"hsl\(\s*(?P<hue>[\d.]+)\s+(?P<saturation>[\d.]+)%\s+"
    r"(?P<lightness>[\d.]+)%\s*\)"
)
OKLCH_RE = re.compile(
    r"oklch\(\s*(?P<lightness>[\d.]+)%\s+(?P<chroma>[\d.]+)\s+"
    r"(?P<hue>[\d.]+)(?:\s*/\s*(?P<alpha>[\d.]+))?\s*\)"
)


def _css_block(css: str, selector: str) -> str:
    selector_start = css.index(selector)
    opening_brace = css.index("{", selector_start)
    depth = 0
    for index in range(opening_brace, len(css)):
        if css[index] == "{":
            depth += 1
        elif css[index] == "}":
            depth -= 1
            if depth == 0:
                return css[opening_brace + 1 : index]
    raise AssertionError(f"Unclosed CSS block for {selector}")


def _tokens(block: str) -> dict[str, str]:
    return dict(TOKEN_RE.findall(block))


def _resolved_color(tokens: dict[str, str], token: str) -> str:
    seen: set[str] = set()
    current = token
    while current not in seen:
        seen.add(current)
        value = tokens[current]
        match = VAR_RE.fullmatch(value)
        if match is None:
            return value
        current = match.group("token")
    raise AssertionError(f"Circular color token reference from {token}")


def _oklch(value: str) -> tuple[float, float, float, float]:
    match = OKLCH_RE.fullmatch(value)
    assert match is not None, f"Expected an oklch() color, got {value!r}"
    alpha = match.group("alpha")
    return (
        float(match.group("lightness")) / 100,
        float(match.group("chroma")),
        float(match.group("hue")),
        float(alpha) if alpha is not None else 1.0,
    )


def _oklch_to_srgb(value: str) -> tuple[float, float, float]:
    lightness, chroma, hue, _alpha = _oklch(value)
    angle = math.radians(hue)
    axis_a = chroma * math.cos(angle)
    axis_b = chroma * math.sin(angle)

    l_root = lightness + 0.3963377774 * axis_a + 0.2158037573 * axis_b
    m_root = lightness - 0.1055613458 * axis_a - 0.0638541728 * axis_b
    s_root = lightness - 0.0894841775 * axis_a - 1.291485548 * axis_b
    l_value = l_root**3
    m_value = m_root**3
    s_value = s_root**3

    linear = (
        4.0767416621 * l_value - 3.3077115913 * m_value + 0.2309699292 * s_value,
        -1.2684380046 * l_value + 2.6097574011 * m_value - 0.3413193965 * s_value,
        -0.0041960863 * l_value - 0.7034186147 * m_value + 1.707614701 * s_value,
    )

    def compand(channel: float) -> float:
        if channel <= 0.0031308:
            return 12.92 * channel
        return 1.055 * channel ** (1 / 2.4) - 0.055

    srgb = (compand(linear[0]), compand(linear[1]), compand(linear[2]))
    assert all(0 <= channel <= 1 for channel in srgb), f"Out-of-gamut color {value!r}"
    return srgb


def _color_to_srgb(value: str) -> tuple[float, float, float]:
    oklch_match = OKLCH_RE.fullmatch(value)
    if oklch_match is not None:
        return _oklch_to_srgb(value)
    hsl_match = HSL_RE.fullmatch(value)
    assert hsl_match is not None, f"Unsupported opaque CSS color {value!r}"
    return colorsys.hls_to_rgb(
        float(hsl_match.group("hue")) / 360,
        float(hsl_match.group("lightness")) / 100,
        float(hsl_match.group("saturation")) / 100,
    )


def _relative_luminance(value: str) -> float:
    def linearize(channel: float) -> float:
        if channel <= 0.04045:
            return channel / 12.92
        return ((channel + 0.055) / 1.055) ** 2.4

    red, green, blue = (linearize(channel) for channel in _color_to_srgb(value))
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def _contrast_ratio(first: str, second: str) -> float:
    first_luminance = _relative_luminance(first)
    second_luminance = _relative_luminance(second)
    lighter = max(first_luminance, second_luminance)
    darker = min(first_luminance, second_luminance)
    return (lighter + 0.05) / (darker + 0.05)


def test_file_age_tokens_use_one_oklch_palette_in_both_themes() -> None:
    css = STYLES_CSS.read_text(encoding="utf-8")
    light_tokens = _tokens(_css_block(css, ":root {"))
    dark_tokens = {**light_tokens, **_tokens(_css_block(css, '[data-theme="dark"] {'))}

    for theme, tokens in (("light", light_tokens), ("dark", dark_tokens)):
        for state in AGE_STATES:
            for family in ("", "fill-"):
                token = f"--file-age-{family}{state}"
                assert token in tokens, f"{theme} theme is missing {token}"
                _oklch(_resolved_color(tokens, token))

        colors = [_oklch(_resolved_color(tokens, f"--file-age-{bucket}")) for bucket in AGE_BUCKETS]
        later_chroma = [color[1] for color in colors[1:]]
        assert later_chroma == sorted(later_chroma, reverse=True), (
            f"{theme} foreground age chroma after the fresh tier must fade monotonically"
        )
        assert all(60 <= color[2] <= 120 for color in colors[1:]), (
            f"{theme} post-fresh ages must remain in the gold-to-yellow family"
        )

        live = _resolved_color(tokens, "--file-age-live")
        assert _resolved_color(tokens, "--file-age-sec") == live
        assert _resolved_color(tokens, "--file-age-fill-sec") == _resolved_color(
            tokens, "--file-age-fill-live"
        )
        live_hue = _oklch(live)[2]
        assert 25 <= live_hue <= 55, f"{theme} Live must stay warm salmon, got {live_hue}"


def test_dark_file_age_foregrounds_meet_contrast_on_every_age_surface() -> None:
    css = STYLES_CSS.read_text(encoding="utf-8")
    light_tokens = _tokens(_css_block(css, ":root {"))
    dark_tokens = {**light_tokens, **_tokens(_css_block(css, '[data-theme="dark"] {'))}

    for state in AGE_STATES:
        foreground = _resolved_color(dark_tokens, f"--file-age-{state}")
        for surface_token in AGE_SURFACES:
            surface = _resolved_color(dark_tokens, surface_token)
            contrast = _contrast_ratio(foreground, surface)
            assert contrast >= MINIMUM_TEXT_CONTRAST, (
                f"dark --file-age-{state} has {contrast:.2f}:1 contrast against {surface_token}"
            )


def test_light_theme_uses_the_approved_file_age_palette() -> None:
    css = STYLES_CSS.read_text(encoding="utf-8")
    tokens = _tokens(_css_block(css, ":root {"))

    actual = {
        state: tuple(
            round(component, 4)
            for component in _oklch(_resolved_color(tokens, f"--file-age-{state}"))
        )
        for state in AGE_STATES
    }
    assert actual == APPROVED_LIGHT_AGE_PALETTE


def test_file_age_palette_is_a_documented_shared_primitive() -> None:
    css = STYLES_CSS.read_text(encoding="utf-8")
    filter_controls = FILTER_CONTROLS.read_text(encoding="utf-8")
    docs = DESIGN_SYSTEM.read_text(encoding="utf-8")
    file_age_docs = docs[
        docs.index("## File Age") : docs.index("\n## ", docs.index("## File Age") + 1)
    ]

    assert "--file-age-accent-" not in css
    assert "--file-age-marker-" not in css
    assert ".file-age-marker" not in css
    assert "file-age-marker" not in filter_controls
    assert ".chip-menu-item.age-min {" not in css
    assert ":is(.age-live, .age-sec, .age-min)" in css
    assert "font-weight: var(--file-age-weight-recent);" in css
    assert "var(--file-age-fill-live)" in _css_block(css, ".badge-live {")
    assert ".badge-live::before" not in css
    assert "## File Age" in docs
    assert "OKLCH" in docs
    assert "text color" in file_age_docs.lower()
    assert "marker" not in file_age_docs.lower()
