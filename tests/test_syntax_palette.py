from __future__ import annotations

import math
import re
from pathlib import Path

STATIC_DIR = Path(__file__).resolve().parents[1] / "src" / "metabrowser" / "static"
STYLES_CSS = STATIC_DIR / "styles.css"
HIGHLIGHT_THEME_CSS = STATIC_DIR / "vendor" / "highlight-github.min.css"
DIFF_STYLES_CSS = STATIC_DIR.parent / "builtin_plugins" / "diff" / "styles.css"

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
VAR_RE = re.compile(r"var\((?P<token>--[\w-]+)\)")
CSS_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
CSS_RULE_RE = re.compile(r"(?P<selectors>[^{}]+)\{(?P<body>[^{}]*)\}")
COLOR_DECLARATION_RE = re.compile(r"(?:^|;)\s*(?:background-)?color\s*:")
HIGHLIGHT_CLASS_RE = re.compile(r"\.(hljs(?:-[\w-]+)?)")
EXPECTED_HIGHLIGHT_COLOR_CLASSES = {
    "hljs-addition",
    "hljs-attr",
    "hljs-attribute",
    "hljs-built_in",
    "hljs-bullet",
    "hljs-code",
    "hljs-comment",
    "hljs-deletion",
    "hljs-doctag",
    "hljs-emphasis",
    "hljs-formula",
    "hljs-keyword",
    "hljs-literal",
    "hljs-meta",
    "hljs-name",
    "hljs-number",
    "hljs-operator",
    "hljs-quote",
    "hljs-regexp",
    "hljs-section",
    "hljs-selector-attr",
    "hljs-selector-class",
    "hljs-selector-id",
    "hljs-selector-pseudo",
    "hljs-selector-tag",
    "hljs-string",
    "hljs-strong",
    "hljs-subst",
    "hljs-symbol",
    "hljs-template-tag",
    "hljs-template-variable",
    "hljs-title",
    "hljs-type",
    "hljs-variable",
}


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


def _css_rules(css: str) -> tuple[tuple[str, str], ...]:
    without_comments = CSS_COMMENT_RE.sub("", css)
    return tuple(
        (" ".join(selector.split()), match.group("body"))
        for match in CSS_RULE_RE.finditer(without_comments)
        for selector in match.group("selectors").split(",")
    )


def _rule_body(css: str, selector: str) -> str:
    return next(body for candidate, body in _css_rules(css) if candidate == selector)


OKLCH_RE = re.compile(
    r"oklch\(\s*(?P<lightness>[\d.]+)%?\s+(?P<chroma>[\d.]+)\s+(?P<hue>[\d.]+)\s*\)"
)


def _parse_color(value: str) -> tuple[float, float, float]:
    """sRGB 0..1 for an opaque oklch() literal.

    Every color in the stylesheets is oklch (see the design system's
    Color and Theming section), so contrast is measured by converting
    back through OKLab rather than by reading a notation that separates
    lightness from luminance the way hsl did.
    """
    match = OKLCH_RE.fullmatch(value.strip())
    assert match is not None, f"Expected an opaque oklch() color, got {value!r}"
    lightness = float(match.group("lightness")) / 100
    chroma = float(match.group("chroma"))
    hue = math.radians(float(match.group("hue")))
    a = chroma * math.cos(hue)
    b = chroma * math.sin(hue)
    l_, m_, s_ = (
        lightness + 0.3963377774 * a + 0.2158037573 * b,
        lightness - 0.1055613458 * a - 0.0638541728 * b,
        lightness - 0.0894841775 * a - 1.2914855480 * b,
    )
    long, medium, short = l_**3, m_**3, s_**3
    linear = (
        +4.0767416621 * long - 3.3077115913 * medium + 0.2309699292 * short,
        -1.2684380046 * long + 2.6097574011 * medium - 0.3413193965 * short,
        -0.0041960863 * long - 0.7034186147 * medium + 1.7076147010 * short,
    )

    def to_srgb(channel: float) -> float:
        channel = max(0.0, min(1.0, channel))
        if channel <= 0.0031308:
            return channel * 12.92
        return 1.055 * channel ** (1 / 2.4) - 0.055

    red, green, blue = linear
    return (to_srgb(red), to_srgb(green), to_srgb(blue))


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
    return _contrast_ratio_rgb(_parse_color(first), _parse_color(second))


def _contrast_ratio_rgb(
    first: tuple[float, float, float], second: tuple[float, float, float]
) -> float:
    first_luminance = _relative_luminance(first)
    second_luminance = _relative_luminance(second)
    lighter = max(first_luminance, second_luminance)
    darker = min(first_luminance, second_luminance)
    return (lighter + CONTRAST_LUMINANCE_OFFSET) / (darker + CONTRAST_LUMINANCE_OFFSET)


def _mix_srgb(
    foreground: tuple[float, float, float],
    background: tuple[float, float, float],
    foreground_ratio: float,
) -> tuple[float, float, float]:
    channels = tuple(
        foreground_ratio * foreground_channel + (1 - foreground_ratio) * background_channel
        for foreground_channel, background_channel in zip(foreground, background, strict=True)
    )
    return (channels[0], channels[1], channels[2])


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
    light_tokens = _tokens(_css_block(css, ":root {"))
    dark_overrides = _tokens(_css_block(css, '[data-theme="dark"] {'))

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


def test_metabrowser_owns_highlight_layout_and_semantic_colors() -> None:
    css = STYLES_CSS.read_text(encoding="utf-8")

    host_color_rules = tuple(
        (selector, body)
        for selector, body in _css_rules(css)
        if (selector == ".hljs" or selector.startswith(".hljs "))
        and COLOR_DECLARATION_RE.search(body)
    )
    styled_classes = {
        match.group(1)
        for selector, _body in host_color_rules
        for match in HIGHLIGHT_CLASS_RE.finditer(selector)
        if match.group(1) != "hljs"
    }
    base_rule_bodies = [body for selector, body in host_color_rules if selector == ".hljs"]

    assert not HIGHLIGHT_THEME_CSS.exists()
    assert "html .hljs" not in css
    assert any("color: var(--text);" in body for body in base_rule_bodies)
    assert any("background: var(--code-bg);" in body for body in base_rule_bodies)
    assert styled_classes >= EXPECTED_HIGHLIGHT_COLOR_CLASSES

    layout_rules = dict(_css_rules(css))
    assert "display: block;" in layout_rules["pre code.hljs"]
    assert "overflow-x: auto;" in layout_rules["pre code.hljs"]
    assert "padding: 1em;" in layout_rules["pre code.hljs"]
    assert "padding: 3px 5px;" in layout_rules["code.hljs"]


def test_syntax_foregrounds_meet_contrast_over_diff_tints() -> None:
    css = STYLES_CSS.read_text(encoding="utf-8")
    light_tokens = _tokens(_css_block(css, ":root {"))
    dark_overrides = _tokens(_css_block(css, '[data-theme="dark"] {'))

    for theme, tokens in (
        ("light", light_tokens),
        ("dark", {**light_tokens, **dark_overrides}),
    ):
        background = _parse_color(_resolved_color(tokens, "--bg"))
        surfaces = {
            "context": background,
            "addition": _mix_srgb(
                _parse_color(_resolved_color(tokens, "--status-success")), background, 0.12
            ),
            "deletion": _mix_srgb(
                _parse_color(_resolved_color(tokens, "--status-error")), background, 0.12
            ),
        }
        for foreground_token in SYNTAX_FOREGROUND_TOKENS:
            foreground = _parse_color(_resolved_color(tokens, foreground_token))
            for surface_name, surface in surfaces.items():
                contrast = _contrast_ratio_rgb(foreground, surface)
                assert contrast >= MINIMUM_TEXT_CONTRAST, (
                    f"{theme} {foreground_token} has {contrast:.2f}:1 contrast "
                    f"over the diff {surface_name} surface"
                )


def test_diff_syntax_hosts_and_split_geometry_keep_the_css_contract() -> None:
    css = DIFF_STYLES_CSS.read_text(encoding="utf-8")
    token_host = _rule_body(css, ".metabrowser-diff-host .diff-line-text.hljs")
    assert "background: transparent;" in token_host
    assert "padding: 0;" in token_host
    assert "overflow-x: auto;" in _rule_body(css, ".metabrowser-diff-host .diff-file-body")
    assert "minmax(20em, 1fr) minmax(20em, 1fr)" in _rule_body(
        css, ".metabrowser-diff-host .diff-split-row"
    )
    assert "user-select: none;" in _rule_body(css, ".metabrowser-diff-host .diff-split-empty")
    assert "user-select: none;" in _rule_body(
        css,
        '.metabrowser-diff-host .diff-root[data-selection-side="old"] .diff-split-new .diff-line-text',
    )
    assert "user-select: none;" in _rule_body(
        css,
        '.metabrowser-diff-host .diff-root[data-selection-side="new"] .diff-split-old .diff-line-text',
    )
    assert "@media (prefers-reduced-motion: reduce)" in css
