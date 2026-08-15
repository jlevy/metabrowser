"""Contract checks for the partial-content notice.

Every surface that tells a reader "this is only part of the file" is one
primitive, `.partial-notice`, defined once in `static/styles.css`. Use sites
add positioning, visibility, and query hooks; they do not restate the fill,
border, or type.

The rule and its reasoning are in docs/design-system.md, "Continuing partial
content". It is enforced because it already drifted once: the source view's
banner carried an info-blue fill with a warning border while the byte view
announced the same condition with no box at all.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = REPO_ROOT / "src" / "metabrowser" / "static"
PLUGINS_DIR = STATIC_DIR.parent / "builtin_plugins"
CORE_CSS = STATIC_DIR / "styles.css"
PLUGIN_CSS = tuple(sorted(PLUGINS_DIR.glob("*/styles.css")))
SDK_JS = STATIC_DIR / "plugin_sdk.js"

CSS_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
CSS_RULE_RE = re.compile(r"(?P<selectors>[^{}]+)\{(?P<body>[^{}]*)\}")

PRIMITIVE = ".partial-notice"

# Classes that mark a partial-content surface at a use site. Each rides along
# with the primitive in the markup; none may restyle it.
USE_SITE_CLASSES = (
    "metabrowser-source-truncation-warning",
    "metabrowser-source-more-footer",
    "binary-bytes-notice",
)

# Properties that constitute the notice's visual identity. A use site that sets
# one of these has forked the primitive, which is exactly the drift this guards.
OWNED_PROPERTIES = (
    "background",
    "background-color",
    "border",
    "border-color",
    "border-width",
    "border-style",
    "font-family",
    "font-size",
    "color",
)


def _rules(css: str) -> list[tuple[str, str]]:
    """(selector text, declaration body) for each rule, comments stripped."""
    stripped = CSS_COMMENT_RE.sub("", css)
    return [(m.group("selectors").strip(), m.group("body")) for m in CSS_RULE_RE.finditer(stripped)]


def _declared_properties(body: str) -> set[str]:
    names: set[str] = set()
    for declaration in body.split(";"):
        name, _, _value = declaration.partition(":")
        name = name.strip().lower()
        if name:
            names.add(name)
    return names


def test_primitive_is_defined_once_in_core() -> None:
    """The notice is a shell primitive, so plugins can consume it."""
    core_rules = [sel for sel, _ in _rules(CORE_CSS.read_text()) if sel == PRIMITIVE]
    assert len(core_rules) == 1, f"expected exactly one bare {PRIMITIVE} rule, found {core_rules}"

    for plugin_css in PLUGIN_CSS:
        for selector, _body in _rules(plugin_css.read_text()):
            assert PRIMITIVE not in selector, (
                f"{plugin_css.name} restyles {PRIMITIVE}; the primitive belongs to core"
            )


def test_primitive_uses_the_surface_fill_and_the_warning_border() -> None:
    """White, not blue.

    Blue carries an established meaning elsewhere in the system, and a partial
    load is not an informational aside. The warning border alone marks the box
    as incomplete.
    """
    body = next(body for sel, body in _rules(CORE_CSS.read_text()) if sel == PRIMITIVE)
    assert "background: var(--bg)" in body, "the notice fill is the ordinary surface"
    assert "var(--status-warning)" in body, "the notice border is the warning token"
    assert "--status-info-bg" not in body, "info blue does not mean 'partial'"


def test_no_use_site_restyles_the_primitive() -> None:
    """Use sites position and hide; they do not repaint."""
    offenders: list[str] = []
    for css_path in (CORE_CSS, *PLUGIN_CSS):
        for selector, body in _rules(css_path.read_text()):
            if not any(cls in selector for cls in USE_SITE_CLASSES):
                continue
            for prop in sorted(_declared_properties(body) & set(OWNED_PROPERTIES)):
                offenders.append(f"{css_path.name}: `{selector}` sets {prop}")
    assert not offenders, (
        "partial-content use sites must carry .partial-notice rather than "
        "restating it:\n  " + "\n  ".join(offenders)
    )


def test_every_notice_the_sdk_emits_carries_the_primitive() -> None:
    """One builder, so markup cannot drift even if a caller is careless."""
    src = SDK_JS.read_text()
    assert "function partialNoticeHtml" in src
    assert 'class="partial-notice' in src
    # The two text-view entry points delegate rather than building their own.
    for fn in ("renderTextTruncationWarning", "renderTextLoadMoreFooter"):
        assert fn in src
    assert src.count('<div class="partial-notice') == 1, (
        "the notice box is built in exactly one place"
    )


def test_plugin_views_build_the_notice_through_the_sdk() -> None:
    """A plugin announcing partial content uses the shell's box, not its own."""
    for index_js in sorted(PLUGINS_DIR.glob("*/*.js")):
        source = index_js.read_text()
        if "partial-notice" not in source:
            continue
        assert "partialNoticeHtml" in source, (
            f"{index_js.relative_to(REPO_ROOT)} names the notice class without "
            "going through mb.partialNoticeHtml"
        )
