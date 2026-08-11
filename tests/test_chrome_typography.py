"""Contract checks for the chrome typography and keyboard-key design system.

Two rules are enforced here so they cannot drift back:

1. Chrome uses the sans UI face. Monospace is for rendered content (code, raw log
   payloads, highlighted source) and for a short, named list of deliberate exceptions.
   File paths — including parent paths — are chrome and are never monospaced.
2. Keyboard keys render through one component with one treatment: caps, bold, and a
   thin border built from tokens.

The rules themselves are documented next to the CSS they govern, in the
``── Typography roles ──`` and ``── Keyboard keys ──`` blocks of ``static/styles.css``.
"""

from __future__ import annotations

import re
from pathlib import Path

STATIC_DIR = Path(__file__).resolve().parents[1] / "src" / "metabrowser" / "static"
STYLES_CSS = STATIC_DIR / "styles.css"
SEARCH_PALETTE_JS = STATIC_DIR / "search_palette.js"

CSS_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
CSS_RULE_RE = re.compile(r"(?P<selectors>[^{}]+)\{(?P<body>[^{}]*)\}")
MONO_DECLARATION_RE = re.compile(r"(?:^|;)\s*font(?:-family)?\s*:[^;]*--font-mono")

# Monospace is legitimate here. Anything else that reaches for --font-mono is a
# regression: it is chrome, and chrome is sans.
#
# Rendered content — the user's own text, where character alignment carries meaning:
#   code.hljs, .code-block code, .md-body:not(.metabrowser-kpress-host) code,
#   .log-event-raw *
# Named exceptions, each deliberate:
#   .compression-badge          a 7px glyph, iconography rather than text
#   .metabrowser-kpress-error-detail   a verbatim error payload
#   .log-event-header           structured log values (type, timestamps), not paths
MONO_ALLOWED_SELECTORS = frozenset(
    {
        "code.hljs",
        ".code-block code",
        ".md-body:not(.metabrowser-kpress-host) code",
        ".log-event-raw pre",
        ".log-event-raw code",
        ".compression-badge",
        ".metabrowser-kpress-error-detail",
        ".log-event-header",
    }
)

# Surfaces that render a file path, a parent path, or a path segment. These carry the
# navigation face, so they must never declare monospace.
PATH_SELECTORS = (
    ".header-path",
    ".file-header-path",
    ".search-palette-description",
    ".tally-tree",
)

KBD_TOKENS = (
    "--kbd-font-family",
    "--kbd-font-size",
    "--kbd-font-weight",
    "--kbd-letter-spacing",
    "--kbd-text-transform",
    "--kbd-border",
    "--kbd-radius",
    "--kbd-padding",
    "--kbd-color",
    "--kbd-bg",
)


def _read_styles() -> str:
    return STYLES_CSS.read_text()


def _rules(css: str) -> list[tuple[str, str]]:
    """Return (selector, body) for each declaration block, comments stripped."""
    stripped = CSS_COMMENT_RE.sub("", css)
    return [
        (match.group("selectors").strip(), match.group("body"))
        for match in CSS_RULE_RE.finditer(stripped)
    ]


def test_monospace_is_confined_to_content_and_named_exceptions() -> None:
    offenders = []
    for selectors, body in _rules(_read_styles()):
        if not MONO_DECLARATION_RE.search(body):
            continue
        individual = [part.strip() for part in selectors.split(",") if part.strip()]
        for selector in individual:
            if selector not in MONO_ALLOWED_SELECTORS:
                offenders.append(selector)
    assert offenders == [], (
        f"Chrome uses the sans face; these selectors reach for --font-mono: {offenders}. "
        "Add a documented exception to MONO_ALLOWED_SELECTORS only if the surface "
        "renders content rather than chrome."
    )


def test_path_surfaces_never_declare_monospace() -> None:
    for selectors, body in _rules(_read_styles()):
        individual = {part.strip() for part in selectors.split(",") if part.strip()}
        for path_selector in PATH_SELECTORS:
            if path_selector in individual:
                assert not MONO_DECLARATION_RE.search(body), (
                    f"{path_selector} renders a file path and must use the sans nav face."
                )


def test_keyboard_key_tokens_are_defined_once_as_a_system() -> None:
    css = _read_styles()
    for token in KBD_TOKENS:
        assert f"{token}:" in css, f"Missing keyboard-key token {token}"


def test_keyboard_keys_render_caps_bold_and_bordered() -> None:
    css = _read_styles()
    kbd_rules = [body for selectors, body in _rules(css) if ".kbd" in selectors]
    assert kbd_rules, "No .kbd component rule found"
    base = kbd_rules[0]
    assert "var(--kbd-text-transform)" in base
    assert "var(--kbd-font-weight)" in base
    assert "var(--kbd-border)" in base
    assert "var(--kbd-font-family)" in base

    # The treatment is defined by tokens, so the caps and bold values live with them.
    assert "--kbd-text-transform: uppercase;" in css
    assert "--kbd-font-weight: var(--weight-bold);" in css


def test_palette_filename_and_parent_path_share_one_size() -> None:
    """A result row reads as one line of navigation, not a heading over fine print."""
    rules = dict(_rules(_read_styles()))
    label = rules[".search-palette-label"]
    description = rules[".search-palette-description"]
    size = re.compile(r"font-size:\s*([^;]+);")
    label_size = size.search(label)
    description_size = size.search(description)
    assert label_size and description_size
    assert label_size.group(1).strip() == description_size.group(1).strip()


def test_palette_hint_renders_keys_through_the_kbd_component() -> None:
    source = SEARCH_PALETTE_JS.read_text()
    assert '"kbd"' in source, "The palette hint should build kbd elements, not a plain string"
    # The old monospaced hint string is gone.
    assert "↑↓ choose · Enter open · Esc close" not in source


def test_both_open_keys_are_advertised_in_the_hint() -> None:
    source = SEARCH_PALETTE_JS.read_text()
    assert "OPEN_KEYS" in source, "The open-key set should be one named constant"
