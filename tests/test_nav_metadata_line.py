"""The metadata under each main tab's toolbar is one component, `.nav-metadata`.

Files' totals, Commits' tally, and Pulls' count and connection lines were three recipes:
13px text 6px under the Files filters, 13px text centred in the Commits toolbar slot,
and 12px muted text with no space above it under the Pulls filters. They are now one
shell component that owns the box, the type, and the spacing between items, and a use
site adds only what its own spans say. These checks hold the markup and the stylesheets
to that; ``tests/test_nav_metadata_chrome.py`` measures what it lays out to in Chrome,
and ``tests/dom/tree-summary-line-session.js`` records what the Files line says.
The rule and its reasons are in docs/design-system.md, "Navigation Metadata Line".
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PACKAGE = REPO / "src" / "metabrowser"
STATIC = PACKAGE / "static"
GITHUB = PACKAGE / "builtin_plugins" / "github"
STYLESHEETS = (STATIC / "styles.css", *sorted((PACKAGE / "builtin_plugins").glob("*/*.css")))
SOURCES = (
    PACKAGE / "server.py",
    *sorted(STATIC.glob("*.js")),
    *sorted((PACKAGE / "builtin_plugins").glob("*/*.js")),
)
COMPONENT = frozenset({"nav-metadata", "nav-metadata-note"})
# The component's own rules, all in static/styles.css. A rule anywhere else whose element
# is a metadata line restyles the component, however it is scoped.
COMPONENT_SELECTORS = frozenset(
    {
        ".nav-metadata",
        ".nav-metadata[hidden]",
        ".nav-metadata-note",
        ".nav-metadata:has(+ .nav-metadata)",
        ".nav-metadata + .nav-metadata",
        ".nav-toolbar > .nav-metadata",
    }
)
# What a use site may still say of the line element itself, through its own role class:
# how a long word in it breaks. Its box, type, spacing, and layout are the component's.
ALLOWED_ON_A_LINE = frozenset({"overflow-wrap"})
# The role classes the markup is known to give metadata lines, so the derivation below
# cannot quietly find nothing.
KNOWN_ROLES = frozenset(
    {
        "tree-summary",
        "tree-summary-split",
        "tree-summary-filtered",
        "tree-selection-note",
        "recent-stale-note",
        "git-history-summary",
        "github-pulls-status",
        "github-pulls-connection",
    }
)
COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
RULE = re.compile(r"(?P<selectors>[^{}]+)\{(?P<body>[^{}]*)\}")
# A class attribute or property in markup a source builds: `class="…"` (also escaped, in
# a Python or JS string), `className = "…"`, and `class: "…"` in an element helper.
CLASS_STRING = re.compile(r"""class(?:Name)?\s*[:=]\s*\\?["'`]([^"'`\\]+)\\?["'`]""")
# Functional pseudo-classes whose argument the element itself must match.
MATCHING = frozenset({"is", "where", "matches"})


def _rules(css: str) -> list[tuple[str, str]]:
    """Every rule's selector list and body, nested ones (`@media`) included."""

    return [
        (match.group("selectors").strip(), match.group("body"))
        for match in RULE.finditer(COMMENT.sub("", css))
        if not match.group("selectors").strip().startswith("@")
    ]


def _rule(css: str, selector: str) -> str:
    bodies = [body for selectors, body in _rules(css) if selectors == selector]
    assert len(bodies) == 1, f"{selector}: {len(bodies)} rules"
    return bodies[0]


def _declarations(body: str) -> dict[str, str]:
    pairs = (part.split(":", 1) for part in body.split(";") if ":" in part)
    return {name.strip(): value.strip() for name, value in pairs}


def _split_top(text: str, separator: str) -> list[str]:
    """Split at each `separator` outside brackets and parentheses."""

    parts, depth, start = [], 0, 0
    for index, char in enumerate(text):
        if char in "([":
            depth += 1
        elif char in ")]":
            depth -= 1
        elif char == separator and depth == 0:
            parts.append(text[start:index])
            start = index + 1
    parts.append(text[start:])
    return [part.strip() for part in parts if part.strip()]


def _subject(selector: str) -> str:
    """The last compound selector: the element a rule styles."""

    depth, start = 0, 0
    for index, char in enumerate(selector):
        if char in "([":
            depth += 1
        elif char in ")]":
            depth -= 1
        elif depth == 0 and char in " \t\n>+~":
            start = index + 1
    return selector[start:].strip()


def _classes(compound: str) -> set[str]:
    """The classes an element must carry to match `compound`.

    A `:not()` or `:has()` argument says nothing of the element's own classes, and an
    `:is()` or `:where()` argument does, through each of its selectors' subjects.
    """

    classes: set[str] = set()
    index = 0
    while index < len(compound):
        char = compound[index]
        if char == ".":
            match = re.match(r"\.([\w-]+)", compound[index:])
            assert match is not None, compound
            classes.add(match.group(1))
            index += len(match.group(0))
        elif char == ":":
            match = re.match(r"::?([\w-]+)(\()?", compound[index:])
            assert match is not None, compound
            index += len(match.group(0))
            if match.group(2):
                depth, end = 1, index
                while depth:
                    depth += {"(": 1, ")": -1}.get(compound[end], 0)
                    end += 1
                argument = compound[index : end - 1]
                index = end
                if match.group(1) in MATCHING:
                    for part in _split_top(argument, ","):
                        classes |= _classes(_subject(part))
        elif char == "[":
            index = compound.index("]", index) + 1
        else:
            index += 1
    return classes


def _rules_by_subject() -> list[tuple[Path, str, set[str], dict[str, str]]]:
    found = []
    for sheet in STYLESHEETS:
        for selectors, body in _rules(sheet.read_text(encoding="utf-8")):
            for selector in _split_top(selectors, ","):
                selector = " ".join(selector.split())
                found.append((sheet, selector, _classes(_subject(selector)), _declarations(body)))
    return found


def _line_roles() -> set[str]:
    """Every class the markup puts beside `nav-metadata` on an element."""

    roles: set[str] = set()
    for source in SOURCES:
        for match in CLASS_STRING.finditer(source.read_text(encoding="utf-8")):
            tokens = set(match.group(1).split())
            if "nav-metadata" in tokens:
                roles |= tokens - COMPONENT
    return roles


def test_the_guard_reads_selectors_as_the_browser_matches_them() -> None:
    """Its own parsing, so a scoped or wrapped selector cannot slip past it."""

    assert _classes(_subject(".github-pulls .nav-metadata")) == {"nav-metadata"}
    assert _classes(_subject(".github-pulls-status:not(:has(> .x))")) == {"github-pulls-status"}
    assert _classes(_subject(":is(.a .github-pulls-status, .b)")) == {"github-pulls-status", "b"}
    assert _classes(_subject(".a:where(.nav-toolbar > *)")) == {"a"}
    assert _classes(_subject('.x[data-y="a > .b"]')) == {"x"}
    assert _split_top(":is(.a, .b), .c", ",") == [":is(.a, .b)", ".c"]


def test_every_metadata_line_carries_the_one_component() -> None:
    server = (PACKAGE / "server.py").read_text(encoding="utf-8")
    assert "'<div class=\"git-history-summary nav-metadata\">'" in server
    assert "f'<span class=\"git-history-summary-count\">{pending_tally}</span></div></div>'" in (
        server
    ), "the Commits tally ships pending in the count's own span, where the count will be"
    git = (STATIC / "git-panel.js").read_text(encoding="utf-8")
    assert 'summary.className = "git-history-summary nav-metadata";' in git
    assert 'failed.className = "git-history-summary nav-metadata nav-metadata-note";' in git
    navigation = (STATIC / "navigation.js").read_text(encoding="utf-8")
    summary = navigation[navigation.index("  function treeSummaryHtml(") :]
    summary = summary[: summary.index("\n  }\n")]
    assert "'<div class=\"tree-summary nav-metadata\">'" in summary
    assert '<div class="tree-summary tree-summary-split nav-metadata">' in summary
    app = (STATIC / "app.js").read_text(encoding="utf-8")
    for role in ("tree-summary-filtered", "tree-selection-note", "recent-stale-note"):
        assert f'className = "{role} nav-metadata nav-metadata-note";' in app, role
    pulls = (GITHUB / "pulls-panel.js").read_text(encoding="utf-8")
    assert 'h("p", { class: "github-pulls-status nav-metadata" })' in pulls
    assert 'class: "github-pulls-connection nav-metadata nav-metadata-note"' in pulls
    assert _line_roles() >= KNOWN_ROLES, KNOWN_ROLES - _line_roles()


def test_only_the_component_styles_a_metadata_line_by_its_class() -> None:
    """However a rule is scoped, one whose element is `.nav-metadata` is the component's."""

    offenders = [
        f"{sheet.name}: {selector}"
        for sheet, selector, classes, _ in _rules_by_subject()
        if classes & COMPONENT
        and (sheet != STATIC / "styles.css" or selector not in COMPONENT_SELECTORS)
    ]
    assert offenders == [], offenders


def test_no_use_site_restyles_a_metadata_line_by_its_role() -> None:
    """A role class may lay out the line's own spans, never the line itself."""

    roles = _line_roles()
    offenders = [
        f"{sheet.name}: {selector} sets {sorted(set(declarations) - ALLOWED_ON_A_LINE)}"
        for sheet, selector, classes, declarations in _rules_by_subject()
        if classes & roles and set(declarations) - ALLOWED_ON_A_LINE
    ]
    assert offenders == [], offenders


def test_the_component_is_built_from_tokens() -> None:
    css = (STATIC / "styles.css").read_text(encoding="utf-8")
    line = _declarations(_rule(css, ".nav-metadata"))
    assert line["padding"] == "var(--nav-metadata-padding-y) var(--pane-header-padding-x)"
    assert line["border-bottom"] == "var(--nav-metadata-rule-width) solid var(--border)"
    assert line["font-size"] == "var(--nav-font-size)"
    assert line["font-weight"] == "var(--weight-normal)"
    assert line["color"] == "var(--text)"
    assert line["gap"] == "0 var(--nav-metadata-gap)"
    assert line["line-height"] == "var(--nav-metadata-line-height)"
    # One line box, reserved before any content arrives, whatever padding a joined line keeps.
    assert line["min-height"] == "1lh" and line["box-sizing"] == "content-box"
    assert _declarations(_rule(css, ".nav-metadata-note")) == {"color": "var(--muted)"}
    # One line of it is the toolbar slot's height, so in the slot (Commits) the text sits
    # where it sits under a toolbar (Files, Pulls): the padding is derived, not restated.
    token = css[css.index("--nav-metadata-padding-y:") :]
    token = " ".join(token[: token.index(";")].split())
    assert token == (
        "--nav-metadata-padding-y: calc( ( var(--nav-toolbar-height) - "
        "var(--nav-metadata-rule-width) - var(--nav-metadata-line-height) * "
        "var(--nav-font-size) ) / 2 )"
    )
    assert "--nav-metadata-line-height: 1.5;" in css
    assert "--nav-metadata-rule-width: 1px;" in css
    slot = _declarations(_rule(css, ".nav-toolbar > .nav-metadata"))
    assert slot == {
        "flex": "1 1 auto",
        "flex-wrap": "nowrap",
        "min-width": "0",
        "padding-inline": "0",
        "border-bottom": "none",
    }
    # Consecutive lines are one band under one rule.
    joined = _declarations(_rule(css, ".nav-metadata:has(+ .nav-metadata)"))
    assert joined == {"padding-bottom": "0", "border-bottom": "none"}
    assert _declarations(_rule(css, ".nav-metadata + .nav-metadata")) == {"padding-top": "0"}


def test_items_built_of_spans_keep_the_lines_word_gap() -> None:
    css = (STATIC / "styles.css").read_text(encoding="utf-8")
    assert "--nav-metadata-gap: 4px;" in css
    for selector in (".tree-summary-ignored", ".git-history-summary-first"):
        assert _declarations(_rule(css, selector))["gap"] == "var(--nav-metadata-gap)", selector


def test_the_component_is_documented() -> None:
    design = (REPO / "docs" / "design-system.md").read_text(encoding="utf-8")
    assert "### Navigation Metadata Line" in design
    section = design[design.index("### Navigation Metadata Line") :]
    section = section[: section.index("\n### ")]
    for name in (".nav-metadata", ".nav-metadata-note", "--nav-metadata-padding-y"):
        assert name in section, name
