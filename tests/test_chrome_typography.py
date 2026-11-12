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
PLUGINS_DIR = STATIC_DIR.parent / "builtin_plugins"
# Every stylesheet the app ships: a plugin's chrome is chrome.
STYLE_FILES = (STATIC_DIR / "styles.css", *sorted(PLUGINS_DIR.glob("*/*.css")))
SEARCH_PALETTE_JS = STATIC_DIR / "search-palette.js"
KEYBOARD_SHORTCUTS_JS = STATIC_DIR / "keyboard-shortcuts.js"

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
#   .git-commit-sha             an object id, where every character is identity
MONO_ALLOWED_SELECTORS = frozenset(
    {
        "code.hljs",
        ".code-block code",
        # A source view's line numbers sit on the code's own lines, so they take the
        # code's face and line box; any other face would drift off the lines.
        ".source-line-numbers",
        ".md-body:not(.metabrowser-kpress-host) code",
        ".log-event-raw pre",
        ".log-event-raw code",
        # A diff's lines and a comment's hunk of one: the user's code.
        ".metabrowser-diff-host .diff-line",
        ".metabrowser-diff-host .diff-split-side",
        ".github-pull-hunk",
        # A JSON or YAML document's own structure, whose indent carries meaning.
        ".structured-tree",
        ".compression-badge",
        ".metabrowser-kpress-error-detail",
        ".log-event-header",
        ".git-commit-sha",
    }
)

# Surfaces that render a file path, a parent path, or a path segment. These carry the
# navigation face, so they must never declare monospace.
PATH_SELECTORS = (
    ".header-path",
    ".file-header-path",
    ".search-palette-description",
    ".tally-tree",
    # The changed-file list in a commit view is a list of paths, and it
    # navigates like the tree does.
    ".git-file-path",
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
    return "\n".join(path.read_text() for path in STYLE_FILES)


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
    palette_source = SEARCH_PALETTE_JS.read_text()
    shortcut_source = KEYBOARD_SHORTCUTS_JS.read_text()
    assert 'createElement("kbd")' in shortcut_source
    assert "options.shortcuts.appendBinding" in palette_source
    assert 'createElement("kbd")' not in palette_source
    # The old monospaced hint string is gone.
    assert "↑↓ choose · Enter open · Esc close" not in palette_source


def test_single_keys_share_the_registry_keycap() -> None:
    """A key that is not a binding, such as a standalone Shift, renders as a binding's does.

    Bindings and single keys go through one keycap constructor in the registry,
    so the two entry points cannot drift into different markup.
    """
    shortcut_source = KEYBOARD_SHORTCUTS_JS.read_text()
    assert shortcut_source.count('createElement("kbd")') == 1
    keycap = shortcut_source[shortcut_source.index("function createKeycap(") :]
    keycap = keycap[: keycap.index("\n  }\n")]
    assert 'keycap.className = "kbd";' in keycap
    for entry_point in ("function appendBinding(", "function appendKey("):
        body = shortcut_source[shortcut_source.index(entry_point) :]
        assert "createKeycap(hostDocument" in body[: body.index("\n  }\n")], entry_point


def test_both_open_keys_stay_bound_though_the_hint_names_one() -> None:
    """The alias is unadvertised, not unbound.

    The compact strip shows a single preferred key per command, so `/` no
    longer appears at the bottom of the navigation pane. It must still open
    Quick File, still reach the nav surface, and still be listed in Help.
    """

    source = SEARCH_PALETTE_JS.read_text()
    command_start = source.index('id: "quick-file.open"')
    command = source[source.rfind("options.shortcuts.register", 0, command_start) : command_start]
    assert 'bindings: [{ key: "t" }, { key: "/" }]' in command
    assert (
        'surfaces: { help: "always", nav: "always", reveal: "always" }'
        in source[command_start : command_start + 300]
    )
