"""One stack design, held by the source (docs/design-system.md, "Stacks").

The pull request page's stack button and menu, a Pulls row's place, and the
Pulls tab's stack groups name a stack one way. These checks hold the source to that
without a browser: one label class for the menu's heading and a stack row's header, read
from the shell's group heading and its label tokens and restyled nowhere; one function
for each stack word; and no surface writing "Stack #" itself.
``tests/test_github_pulls_stacks_chrome.py`` measures in Chrome that the two headers
resolve to the same tokens, and that the groups and the menu list a stack's members in
one order; ``tests/dom/github-pulls-stack-groups-session.js`` holds the order
browserlessly against the menu's own code.
"""

from __future__ import annotations

import re
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1] / "src" / "metabrowser"
GITHUB = PACKAGE / "builtin_plugins" / "github"
SHELL_CSS = PACKAGE / "static" / "styles.css"
LABEL_CLASS = '"group-heading github-pull-stack-label"'
# What the label register is: the properties the shell's label tokens set.
# `font` is the shorthand that sets the family, size, and weight at once.
REGISTER = (
    "color",
    "font",
    "font-family",
    "font-size",
    "font-weight",
    "letter-spacing",
    "text-transform",
)
COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
RULE = re.compile(r"(?P<selectors>[^{}]+)\{(?P<body>[^{}]*)\}")


def _rules(css: str) -> list[tuple[str, str]]:
    return [
        (match["selectors"].strip(), match["body"]) for match in RULE.finditer(COMMENT.sub("", css))
    ]


def test_the_menu_heading_and_a_stack_row_header_are_one_label_class() -> None:
    """Both headers are the shell's group heading with the stack's label class, so the
    two cannot be given two registers by their markup."""

    page = (GITHUB / "pull-page.js").read_text(encoding="utf-8")
    panel = (GITHUB / "pulls-panel.js").read_text(encoding="utf-8")
    assert page.count(LABEL_CLASS) == 1, "the stack menu's heading"
    assert panel.count(LABEL_CLASS) == 1, "a Pulls stack row's header"
    assert "stackLabel(stack.number)" in page


def test_the_label_reads_the_shells_label_tokens_and_nothing_restyles_it() -> None:
    """The register is the shell's `.group-heading`, from its `--label-*` tokens; no rule of
    the GitHub plugin sets a register property on the stack's label or on a group heading,
    so the menu's heading and a stack row's header resolve to the same tokens."""

    heading = dict(_rules(SHELL_CSS.read_text(encoding="utf-8")))[".group-heading"]
    for declaration in (
        "color: var(--label-color)",
        "font-family: var(--font-sans)",
        "font-size: var(--label-font-size)",
        "font-weight: var(--label-font-weight)",
        "letter-spacing: var(--label-letter-spacing)",
        "text-transform: var(--label-text-transform)",
    ):
        assert declaration in heading, declaration
    rules = _rules((GITHUB / "styles.css").read_text(encoding="utf-8"))
    for selectors, body in rules:
        if "github-pull-stack-label" in selectors or "group-heading" in selectors:
            declared = {line.split(":")[0].strip() for line in body.split(";") if ":" in line}
            assert not declared & set(REGISTER), f"{selectors} restyles the label: {declared}"
    # In a stack's row the label gives up only the menu's inset: the row's grid places it.
    row_label = dict(rules)[".github-pulls-stack-heading > .github-pull-stack-label"]
    assert "padding: 0;" in row_label


def test_a_stack_files_list_is_fresh_as_long_as_a_pull_requests_is() -> None:
    """``STACK_FILES_FRESH_S`` in stack-files.js is the server's ``FRESHNESS_WINDOW_S``.

    A pull request's list of changed files answers its freshness window in ``fresh_for_s``;
    the ``stack`` route answers none, so the Pulls tab's list of a stack's files states the
    window itself. This holds the two to one value.
    """

    from metabrowser.mirror_refresh import FRESHNESS_WINDOW_S

    stated = re.search(
        r"^export const STACK_FILES_FRESH_S = (\d+);$",
        (GITHUB / "stack-files.js").read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    assert stated is not None
    assert int(stated.group(1)) == FRESHNESS_WINDOW_S


def test_every_stack_word_comes_from_pull_stacks() -> None:
    """ "Stack #N", a position, and its tip are written once, in pull-stacks.js, and the
    order a stack's rows are listed in, its Stack Overview row among its members, is
    `stackEntries` over `stackMenuOrder`, in the stack menu and the Pulls tab's groups
    alike: no surface spells its own."""

    stacks = (GITHUB / "pull-stacks.js").read_text(encoding="utf-8")
    assert "export function stackLabel(" in stacks
    assert "export function stackPosition(" in stacks
    assert "export function stackPositionHint(" in stacks
    assert "export function stackMenuOrder(" in stacks
    assert "export function stackEntries(" in stacks
    for path in sorted(GITHUB.glob("*.js")):
        if path.name == "pull-stacks.js":
            continue
        text = path.read_text(encoding="utf-8")
        assert "Stack #${" not in text, f"{path.name} spells a stack's label itself"
        assert "position ${" not in text, f"{path.name} spells a position's tip itself"
    page = (GITHUB / "pull-page.js").read_text(encoding="utf-8")
    assert "for (const target of stackEntries(stackMenuOrder(stack)))" in page
