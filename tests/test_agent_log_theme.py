"""Theme and ownership contracts for the built-in agent-log plugin."""

from __future__ import annotations

import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE_CSS = ROOT / "src" / "metabrowser" / "static" / "styles.css"
PLUGIN_CSS = ROOT / "src" / "metabrowser" / "builtin_plugins" / "agent_log" / "styles.css"

MINIMUM_TEXT_CONTRAST = 4.5
PALETTE_PAIRS = (
    ("--agent-log-kind-neutral-text", "--agent-log-kind-neutral-bg"),
    ("--agent-log-kind-muted-text", "--agent-log-kind-neutral-bg"),
    ("--agent-log-kind-init-text", "--agent-log-kind-init-bg"),
    ("--agent-log-kind-tool-text", "--agent-log-kind-tool-bg"),
    ("--agent-log-kind-thinking-text", "--agent-log-kind-thinking-bg"),
    ("--agent-log-kind-result-text", "--agent-log-kind-result-bg"),
    ("--agent-log-kind-error-text", "--agent-log-kind-error-bg"),
)

TOKEN_RE = re.compile(r"^\s*(--[\w-]+):\s*([^;]+);", re.MULTILINE)
OKLCH_RE = re.compile(
    r"oklch\(\s*(?P<lightness>[\d.]+)%?\s+(?P<chroma>[\d.]+)\s+(?P<hue>[\d.]+)\s*\)"
)
CSS_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
CSS_RULE_RE = re.compile(r"(?P<selectors>[^{}]+)\{(?P<body>[^{}]*)\}")


def _css_block(css: str, selector: str) -> str:
    selector_start = css.index(selector)
    opening_brace = css.index("{", selector_start)
    closing_brace = css.index("}", opening_brace)
    return css[opening_brace + 1 : closing_brace]


def _tokens(block: str) -> dict[str, str]:
    return dict(TOKEN_RE.findall(block))


def _relative_luminance(value: str) -> float:
    """Luminance of an opaque oklch() literal.

    Every color in the stylesheets is oklch (see the design system's
    Color and Theming section), so this converts back through OKLab
    rather than reading a notation whose lightness is not luminance.
    """
    match = OKLCH_RE.fullmatch(value.strip())
    assert match is not None, f"Expected an opaque oklch() color, got {value!r}"
    lightness = float(match.group("lightness")) / 100
    chroma = float(match.group("chroma"))
    hue = math.radians(float(match.group("hue")))
    a = chroma * math.cos(hue)
    b = chroma * math.sin(hue)
    long, medium, short = (
        (lightness + 0.3963377774 * a + 0.2158037573 * b) ** 3,
        (lightness - 0.1055613458 * a - 0.0638541728 * b) ** 3,
        (lightness - 0.0894841775 * a - 1.2914855480 * b) ** 3,
    )
    red, green, blue = (
        +4.0767416621 * long - 3.3077115913 * medium + 0.2309699292 * short,
        -1.2684380046 * long + 2.6097574011 * medium - 0.3413193965 * short,
        -0.0041960863 * long - 0.7034186147 * medium + 1.7076147010 * short,
    )
    # Already linear-light, which is what luminance wants.
    return 0.2126 * max(0.0, red) + 0.7152 * max(0.0, green) + 0.0722 * max(0.0, blue)


def _contrast_ratio(first: str, second: str) -> float:
    first_luminance = _relative_luminance(first)
    second_luminance = _relative_luminance(second)
    lighter = max(first_luminance, second_luminance)
    darker = min(first_luminance, second_luminance)
    return (lighter + 0.05) / (darker + 0.05)


def test_agent_log_visual_language_belongs_to_the_plugin() -> None:
    core_css = CORE_CSS.read_text(encoding="utf-8")
    plugin_css = PLUGIN_CSS.read_text(encoding="utf-8")
    core_selectors = {
        selector.strip()
        for match in CSS_RULE_RE.finditer(CSS_COMMENT_RE.sub("", core_css))
        for selector in match.group("selectors").split(",")
    }

    for selector in (".log-summary", ".log-event-header", ".log-event-kind"):
        assert selector not in core_selectors
        assert selector in plugin_css


def test_agent_log_component_rules_use_tokens_only() -> None:
    plugin_css = PLUGIN_CSS.read_text(encoding="utf-8")
    rules = CSS_RULE_RE.finditer(CSS_COMMENT_RE.sub("", plugin_css))
    for match in rules:
        selectors = match.group("selectors").strip()
        if selectors in {":root", '[data-theme="dark"]'}:
            continue
        body = match.group("body")
        for literal in ("#", "rgb(", "hsl("):
            assert literal not in body, f"{selectors} must use theme tokens, found {literal!r}"

    assert "background: var(--agent-log-surface);" in _css_block(plugin_css, ".log-summary {")
    assert "background: var(--agent-log-surface);" in _css_block(plugin_css, ".log-event-header {")


def test_agent_log_palette_meets_contrast_in_both_themes() -> None:
    plugin_css = PLUGIN_CSS.read_text(encoding="utf-8")
    light_tokens = _tokens(_css_block(plugin_css, ":root {"))
    dark_tokens = _tokens(_css_block(plugin_css, '[data-theme="dark"] {'))

    for theme, tokens in (
        ("light", light_tokens),
        ("dark", {**light_tokens, **dark_tokens}),
    ):
        for foreground_token, background_token in PALETTE_PAIRS:
            assert foreground_token in tokens, f"{theme} theme is missing {foreground_token}"
            assert background_token in tokens, f"{theme} theme is missing {background_token}"
            contrast = _contrast_ratio(tokens[foreground_token], tokens[background_token])
            assert contrast >= MINIMUM_TEXT_CONTRAST, (
                f"{theme} {foreground_token} has {contrast:.2f}:1 contrast "
                f"against {background_token}"
            )
