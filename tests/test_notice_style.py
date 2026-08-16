"""Contract checks for notices.

A notice is any box the app draws to say something *about* the content it is
showing — that a file is only partly loaded, that a document could not be
rendered. They are one primitive, `.notice`, defined once in
`static/styles.css`: the ordinary surface as fill, with severity carried by
the border alone.

The rule and its reasoning are in docs/design-system.md, "Notices". It is
enforced because it drifted twice. The partial-content banner wore an
info-blue fill with a warning border while the byte view announced the same
condition with no box at all; and the KPress render error — an error — wore
that same blue fill with an orange border, so it announced itself in the color
of an aside under a border naming the wrong severity.
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

PRIMITIVE = ".notice"

# Every use site of the notice primitive. Each carries `.notice` in the markup
# alongside its own class; none may restate the primitive's fill or type.
USE_SITE_CLASSES = (
    "metabrowser-source-truncation-warning",
    "metabrowser-source-more-footer",
    "binary-bytes-notice",
    "partial-notice",
    "metabrowser-kpress-render-error",
)

# The notice's visual identity. A use site that sets one of these has forked
# the primitive, which is exactly the drift this guards.
#
# `border-color` is absent on purpose: severity is expressed as
# `[data-severity]` on the primitive, and those rules are part of it.
OWNED_PROPERTIES = (
    "background",
    "background-color",
    "border",
    "border-width",
    "border-style",
    "font-family",
    "font-size",
    "color",
)

# Fills that mean something other than "a surface". A notice never wears one:
# one tone per box, and it is the one on the edge.
STATUS_TINTS = ("--status-info-bg", "--status-success-bg", "--status-success-soft-bg")


def _rules(css: str) -> list[tuple[str, str]]:
    """(selector text, declaration body) for each rule, comments stripped."""
    stripped = CSS_COMMENT_RE.sub("", css)
    return [(m.group("selectors").strip(), m.group("body")) for m in CSS_RULE_RE.finditer(stripped)]


def _top_level_rules(css: str) -> list[tuple[str, str]]:
    """Rules outside any at-rule.

    `@media print` legitimately re-addresses the primitive, so counting how
    many times it is *defined* has to ignore nested blocks — otherwise the
    print override reads as a second definition.
    """
    stripped = CSS_COMMENT_RE.sub("", css)
    out: list[tuple[str, str]] = []
    depth = 0
    start = 0
    prelude = ""
    body_start = 0
    for index, char in enumerate(stripped):
        if char == "{":
            depth += 1
            if depth == 1:
                prelude = stripped[start:index].strip()
                body_start = index + 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                if not prelude.startswith("@"):
                    out.append((prelude, stripped[body_start:index]))
                start = index + 1
    return out


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
    core_rules = [sel for sel, _ in _top_level_rules(CORE_CSS.read_text()) if sel == PRIMITIVE]
    assert len(core_rules) == 1, f"expected exactly one bare {PRIMITIVE} rule, found {core_rules}"

    for plugin_css in PLUGIN_CSS:
        for selector, _body in _rules(plugin_css.read_text()):
            assert not re.search(rf"(^|[\s,]){re.escape(PRIMITIVE)}(\[|[\s,]|$)", selector), (
                f"{plugin_css.name} restyles {PRIMITIVE}; the primitive belongs to core"
            )


def test_primitive_uses_the_surface_fill() -> None:
    """White, not a status tint.

    Blue carries an established meaning elsewhere, and neither a partial load
    nor a render failure is an informational aside.
    """
    body = next(body for sel, body in _rules(CORE_CSS.read_text()) if sel == PRIMITIVE)
    assert "background: var(--bg)" in body, "the notice fill is the ordinary surface"
    for tint in STATUS_TINTS:
        assert tint not in body, f"{tint} is a status fill; severity belongs on the border"


def test_severity_is_carried_by_the_border() -> None:
    """Each severity is one border-color override and nothing else.

    If a severity ever changed the fill too, the "one tone per box" rule would
    be gone and the next notice would have two things to copy.
    """
    rules = dict(_rules(CORE_CSS.read_text()))
    for severity, token in (("warning", "--status-warning"), ("error", "--status-error")):
        selector = f'{PRIMITIVE}[data-severity="{severity}"]'
        assert selector in rules, f"no rule for {selector}"
        body = rules[selector]
        assert _declared_properties(body) == {"border-color"}, (
            f"{selector} may only set border-color, found {sorted(_declared_properties(body))}"
        )
        assert f"var({token})" in body


def test_no_use_site_restyles_the_primitive() -> None:
    """Use sites lay out and position; they do not repaint."""
    offenders: list[str] = []
    for css_path in (CORE_CSS, *PLUGIN_CSS):
        for selector, body in _rules(css_path.read_text()):
            if not any(cls in selector for cls in USE_SITE_CLASSES):
                continue
            for prop in sorted(_declared_properties(body) & set(OWNED_PROPERTIES)):
                offenders.append(f"{css_path.name}: `{selector}` sets {prop}")
    assert not offenders, (
        "notice use sites must carry .notice rather than restating it:\n  " + "\n  ".join(offenders)
    )


def test_no_status_tint_is_used_as_a_box_fill_anywhere() -> None:
    """The trap that produced both drifts, closed for good.

    A tint token exists for surfaces that genuinely mean "informational" or
    "succeeded". Using one as the fill of a message box is what made an error
    look like an aside.
    """
    offenders: list[str] = []
    for css_path in (CORE_CSS, *PLUGIN_CSS):
        for selector, body in _rules(css_path.read_text()):
            if selector.startswith((":root", "[data-theme", "@")):
                continue
            for tint in STATUS_TINTS:
                if re.search(rf"background(-color)?\s*:[^;]*{re.escape(tint)}", body):
                    offenders.append(f"{css_path.name}: `{selector}` fills with {tint}")
    assert not offenders, "\n  ".join(["status tints are not box fills:", *offenders])


def test_every_notice_the_sdk_emits_carries_the_primitive() -> None:
    """One builder, so markup cannot drift even if a caller is careless."""
    src = SDK_JS.read_text()
    assert "function partialNoticeHtml" in src
    assert 'class="notice partial-notice' in src
    assert 'data-severity="warning"' in src
    for fn in ("renderTextTruncationWarning", "renderTextLoadMoreFooter"):
        assert fn in src
    assert src.count('<div class="notice') == 1, "the notice box is built in exactly one place"


def test_plugin_views_carry_the_primitive_and_declare_a_severity() -> None:
    """A plugin drawing a notice uses the shell's box and names its severity."""
    for source_js in sorted(PLUGINS_DIR.glob("*/*.js")):
        source = source_js.read_text()
        for cls in USE_SITE_CLASSES:
            if f'class="{cls}' in source or f' {cls}"' in source:
                where = source_js.relative_to(REPO_ROOT)
                assert 'class="notice ' in source, f"{where} draws a notice without .notice"
                assert "data-severity=" in source, f"{where} draws a notice without a severity"
        if "partial-notice" in source and "partialNoticeHtml" not in source:
            raise AssertionError(
                f"{source_js.relative_to(REPO_ROOT)} names the notice class without "
                "going through mb.partialNoticeHtml"
            )
