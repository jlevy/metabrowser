"""Theme and ownership contracts for the built-in agent-log plugin."""

from __future__ import annotations

import colorsys
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
HSL_RE = re.compile(
    r"hsl\(\s*(?P<hue>[\d.]+)\s+(?P<saturation>[\d.]+)%\s+(?P<lightness>[\d.]+)%\s*\)"
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
    match = HSL_RE.fullmatch(value)
    assert match is not None, f"Expected an opaque HSL color, got {value!r}"
    red, green, blue = colorsys.hls_to_rgb(
        float(match.group("hue")) / 360,
        float(match.group("lightness")) / 100,
        float(match.group("saturation")) / 100,
    )

    def linear(channel: float) -> float:
        return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4

    return 0.2126 * linear(red) + 0.7152 * linear(green) + 0.0722 * linear(blue)


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
