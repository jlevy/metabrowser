"""The metadata under each main tab's toolbar is one component, `.nav-metadata`.

Files' totals, Commits' tally, and Pulls' count and connection lines were three recipes:
13px text 6px under the Files filters, 13px text centred in the Commits toolbar slot,
and 12px muted text with no space above it under the Pulls filters. They are now one
shell component that owns the box, the type, and the spacing between items, and a use
site adds only what its own spans say. These checks hold the markup and the stylesheets
to that; ``tests/test_nav_metadata_chrome.py`` measures what it lays out to in Chrome.
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

# The classes that name a metadata line's role. Each element carrying one is a
# `.nav-metadata` line, so none of them may restate what the component owns.
LINE_ROLES = (
    "tree-summary",
    "tree-summary-split",
    "tree-summary-filtered",
    "tree-selection-note",
    "recent-stale-note",
    "git-history-summary",
    "github-pulls-status",
    "github-pulls-connection",
)
# What the component owns: its box, its type, and the spacing between its items.
OWNED = re.compile(
    r"^(padding|margin|border|font|line-height|color|min-height|height|gap|row-gap|"
    r"column-gap|background|letter-spacing|text-transform)(-|$)"
)
COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
RULE = re.compile(r"(?P<selectors>[^{}]+)\{(?P<body>[^{}]*)\}")


def _rules(css: str) -> list[tuple[str, str]]:
    return [
        (match.group("selectors").strip(), match.group("body"))
        for match in RULE.finditer(COMMENT.sub("", css))
    ]


def _rule(css: str, selector: str) -> str:
    bodies = [body for selectors, body in _rules(css) if selectors == selector]
    assert len(bodies) == 1, f"{selector}: {len(bodies)} rules"
    return bodies[0]


def _declarations(body: str) -> dict[str, str]:
    pairs = (part.split(":", 1) for part in body.split(";") if ":" in part)
    return {name.strip(): value.strip() for name, value in pairs}


def test_every_metadata_line_carries_the_one_component() -> None:
    server = (PACKAGE / "server.py").read_text(encoding="utf-8")
    assert "'<div class=\"git-history-summary nav-metadata\">{pending_tally}</div></div>'" in (
        server
    ), "the Commits tally the server ships before its count is a metadata line"
    git = (STATIC / "git-panel.js").read_text(encoding="utf-8")
    assert 'summary.className = "git-history-summary nav-metadata";' in git
    assert 'failed.className = "git-history-summary nav-metadata nav-metadata-note";' in git
    app = (STATIC / "app.js").read_text(encoding="utf-8")
    summary = app[app.index("function treeSummaryHtml(") :]
    summary = summary[: summary.index("\n}\n")]
    assert "'<div class=\"tree-summary nav-metadata\">'" in summary
    assert '<div class="tree-summary tree-summary-split nav-metadata">' in summary
    for role in ("tree-summary-filtered", "tree-selection-note", "recent-stale-note"):
        assert f'className = "{role} nav-metadata nav-metadata-note";' in app, role
    pulls = (GITHUB / "pulls-panel.js").read_text(encoding="utf-8")
    assert 'h("p", { class: "github-pulls-status nav-metadata" })' in pulls
    assert 'class: "github-pulls-connection nav-metadata nav-metadata-note"' in pulls


def test_no_use_site_restyles_what_the_component_owns() -> None:
    """A role class may lay out its own items, never the line's box, type, or spacing."""

    offenders = []
    for sheet in STYLESHEETS:
        for selectors, body in _rules(sheet.read_text(encoding="utf-8")):
            for selector in selectors.split(","):
                # The element the rule styles: the last compound selector.
                subject = re.split(r"\s+|>|\+|~", selector.strip())[-1]
                classes = set(re.findall(r"\.([\w-]+)", subject))
                if not classes & set(LINE_ROLES):
                    continue
                owned = [name for name in _declarations(body) if OWNED.match(name)]
                if owned:
                    offenders.append(f"{sheet.name}: {selector.strip()} sets {owned}")
    assert offenders == [], offenders


def test_the_component_is_built_from_tokens() -> None:
    css = (STATIC / "styles.css").read_text(encoding="utf-8")
    line = _declarations(_rule(css, ".nav-metadata"))
    assert line["padding"] == "var(--nav-metadata-padding-y) var(--pane-header-padding-x)"
    assert line["border-bottom"] == "1px solid var(--border)"
    assert line["font-size"] == "var(--nav-font-size)"
    assert line["font-weight"] == "var(--weight-normal)"
    assert line["color"] == "var(--text)"
    assert line["gap"] == "0 var(--nav-metadata-gap)"
    assert line["line-height"] == "1.5"
    # One line box, reserved before any content arrives, whatever padding a joined line keeps.
    assert line["min-height"] == "1lh" and line["box-sizing"] == "content-box"
    assert _declarations(_rule(css, ".nav-metadata-note")) == {"color": "var(--muted)"}
    # One line of it is the toolbar slot's height, so in the slot (Commits) the text sits
    # where it sits under a toolbar (Files, Pulls).
    token = css[css.index("--nav-metadata-padding-y:") :]
    token = " ".join(token[: token.index(";")].split())
    assert token == (
        "--nav-metadata-padding-y: calc( (var(--nav-toolbar-height) - 1px - 1.5 * "
        "var(--nav-font-size)) / 2 )"
    )
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


def test_the_component_is_documented_for_the_shell_and_for_plugins() -> None:
    design = (REPO / "docs" / "design-system.md").read_text(encoding="utf-8")
    assert "### Navigation Metadata Line" in design
    section = design[design.index("### Navigation Metadata Line") :]
    section = section[: section.index("\n### ")]
    for name in (".nav-metadata", ".nav-metadata-note", "--nav-metadata-padding-y"):
        assert name in section, name
    plugins = (REPO / "docs" / "plugins.md").read_text(encoding="utf-8")
    assert "`nav-metadata`" in plugins
