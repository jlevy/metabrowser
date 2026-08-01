from __future__ import annotations

import colorsys
import re
from pathlib import Path

STATIC_DIR = Path(__file__).resolve().parents[1] / "src" / "metabrowser" / "static"
STYLES_CSS = STATIC_DIR / "styles.css"
HIGHLIGHT_THEME_CSS = STATIC_DIR / "vendor" / "highlight-github.min.css"

MINIMUM_TEXT_CONTRAST = 4.5
HUE_CIRCLE_DEGREES = 360.0
PERCENT_SCALE = 100.0
SRGB_LINEAR_THRESHOLD = 0.04045
SRGB_LINEAR_DIVISOR = 12.92
SRGB_TRANSFER_OFFSET = 0.055
SRGB_TRANSFER_SCALE = 1.055
SRGB_TRANSFER_EXPONENT = 2.4
CONTRAST_LUMINANCE_OFFSET = 0.05
RED_LUMINANCE_WEIGHT = 0.2126
GREEN_LUMINANCE_WEIGHT = 0.7152
BLUE_LUMINANCE_WEIGHT = 0.0722

SYNTAX_FOREGROUND_TOKENS = (
    "--color-syntax-keyword",
    "--color-syntax-title",
    "--color-syntax-key",
    "--color-syntax-string",
    "--color-syntax-number",
    "--color-syntax-bool",
    "--color-syntax-null",
    "--color-syntax-built-in",
    "--color-syntax-comment",
    "--color-syntax-tag",
    "--color-syntax-punct",
    "--color-syntax-summary",
)
SYNTAX_DIFF_PAIRS = (
    ("--color-syntax-addition", "--color-syntax-addition-bg"),
    ("--color-syntax-deletion", "--color-syntax-deletion-bg"),
)

TOKEN_RE = re.compile(r"^\s*(--[\w-]+):\s*([^;]+);", re.MULTILINE)
HSL_RE = re.compile(
    r"hsl\(\s*(?P<hue>[\d.]+)\s+(?P<saturation>[\d.]+)%\s+(?P<lightness>[\d.]+)%\s*\)"
)
VAR_RE = re.compile(r"var\((?P<token>--[\w-]+)\)")
HIGHLIGHT_CLASS_RE = re.compile(r"\.hljs(?:-[A-Za-z0-9_-]+)?")


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


def _parse_hsl(value: str) -> tuple[float, float, float]:
    match = HSL_RE.fullmatch(value)
    assert match is not None, f"Expected an opaque hsl() color, got {value!r}"
    hue = float(match.group("hue")) / HUE_CIRCLE_DEGREES
    saturation = float(match.group("saturation")) / PERCENT_SCALE
    lightness = float(match.group("lightness")) / PERCENT_SCALE
    return colorsys.hls_to_rgb(hue, lightness, saturation)


def _linear_channel(channel: float) -> float:
    if channel <= SRGB_LINEAR_THRESHOLD:
        return channel / SRGB_LINEAR_DIVISOR
    return ((channel + SRGB_TRANSFER_OFFSET) / SRGB_TRANSFER_SCALE) ** SRGB_TRANSFER_EXPONENT


def _relative_luminance(color: tuple[float, float, float]) -> float:
    red, green, blue = (_linear_channel(channel) for channel in color)
    return (
        RED_LUMINANCE_WEIGHT * red + GREEN_LUMINANCE_WEIGHT * green + BLUE_LUMINANCE_WEIGHT * blue
    )


def _contrast_ratio(first: str, second: str) -> float:
    first_luminance = _relative_luminance(_parse_hsl(first))
    second_luminance = _relative_luminance(_parse_hsl(second))
    lighter = max(first_luminance, second_luminance)
    darker = min(first_luminance, second_luminance)
    return (lighter + CONTRAST_LUMINANCE_OFFSET) / (darker + CONTRAST_LUMINANCE_OFFSET)


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


def test_syntax_foregrounds_meet_contrast_in_both_themes() -> None:
    css = STYLES_CSS.read_text(encoding="utf-8")
    light_tokens = _tokens(_css_block(css, ":root"))
    dark_overrides = _tokens(_css_block(css, '[data-theme="dark"]'))

    required_theme_tokens = (
        *SYNTAX_FOREGROUND_TOKENS,
        *(token for pair in SYNTAX_DIFF_PAIRS for token in pair),
    )
    for token in required_theme_tokens:
        assert token in light_tokens, f"Light theme is missing {token}"
        assert token in dark_overrides, f"Dark theme is missing {token}"

    for theme, tokens in (
        ("light", light_tokens),
        ("dark", {**light_tokens, **dark_overrides}),
    ):
        for foreground_token in SYNTAX_FOREGROUND_TOKENS:
            for surface_token in ("--bg", "--code-bg"):
                contrast = _contrast_ratio(
                    _resolved_color(tokens, foreground_token),
                    _resolved_color(tokens, surface_token),
                )
                assert contrast >= MINIMUM_TEXT_CONTRAST, (
                    f"{theme} {foreground_token} has {contrast:.2f}:1 contrast "
                    f"against {surface_token}"
                )
        for foreground_token, background_token in SYNTAX_DIFF_PAIRS:
            contrast = _contrast_ratio(
                _resolved_color(tokens, foreground_token),
                _resolved_color(tokens, background_token),
            )
            assert contrast >= MINIMUM_TEXT_CONTRAST, (
                f"{theme} {foreground_token} has {contrast:.2f}:1 contrast "
                f"against {background_token}"
            )


def test_metabrowser_owns_every_highlight_theme_color() -> None:
    css = STYLES_CSS.read_text(encoding="utf-8")
    vendor_css = HIGHLIGHT_THEME_CSS.read_text(encoding="utf-8")

    palette_start = css.index("html .hljs {")
    palette_end = css.index("/* Full-file code views", palette_start)
    palette = css[palette_start:palette_end]
    vendor_classes = set(HIGHLIGHT_CLASS_RE.findall(vendor_css))

    assert "color: var(--text);" in palette
    missing_classes = sorted(vendor_classes - set(HIGHLIGHT_CLASS_RE.findall(palette)))
    assert not missing_classes, f"Highlight.js classes without host palette: {missing_classes}"
