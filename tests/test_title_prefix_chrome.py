"""A title's conventional-commit prefix is regular and the rest keeps the title's weight.

A commit's or a pull request's title draws a prefix such as ``feat(ledger):`` at regular
weight and the rest of the title at the title's own weight, on every surface that shows
one (docs/design-system.md, "Titles"; mb-z57p). Which part is the prefix, and the markup
drawn from it, are browserless (``tests/dom/title-prefix-session.js`` and its golden).

Two things are held here. The first needs no browser: every surface draws its title
through the shared helper, only ``static/formatters.js`` writes the prefix's class, and one
rule in the shell's stylesheet sets its weight, so no surface keeps a weight or markup of
its own. The second is the cascade, which only a browser resolves:
``tests/dom/title-prefix-chrome.mjs`` draws each surface with its production code in
headless Chrome and reads the computed weight, face, size, and ink of a prefix and of the
rest of its title, and of a title with no prefix, on each.

Without Chrome the second skips (``require_chrome`` in ``tests/required_tools.py``).
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from tests.process_group import GROUP_STOP_S, PROFILE_TEARDOWN_S, run_in_own_group
from tests.required_tools import require_chrome, require_node
from tests.test_github_pull_header_chrome import (
    _kpress_faces,  # pyright: ignore[reportPrivateUsage]
)

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src" / "metabrowser" / "static"
PLUGINS = ROOT / "src" / "metabrowser" / "builtin_plugins"
SESSION = Path(__file__).resolve().parent / "dom" / "title-prefix-chrome.mjs"
# A cold Chrome start in CI has taken 28.2 s (tests/test_github_pull_header_chrome.py, whose
# launch bound this shares); every surface was drawn and read in under 2 s on a Mac.
SESSION_TIMEOUT_S = 48
# The bound, the session's process group stopped after it, and the profile's teardown
# (tests/process_group.py), with 10 s for the copy of KPress's faces;
# tests/test_process_group.py holds the sum under the module's timeout.
LIFECYCLE_S = SESSION_TIMEOUT_S + GROUP_STOP_S + PROFILE_TEARDOWN_S
pytestmark = pytest.mark.timeout(LIFECYCLE_S + 10)

# Each surface that shows a commit's or a pull request's title, and how its source draws
# the title: through the SDK's titleNodes, the shell's titleNodes, or titleHtml.
SURFACES = (
    # A Pulls row, drawn and patched by the member row's builder (stack-member-row.js, below).
    (
        PLUGINS / "github" / "pulls-panel.js",
        "stackMemberRow(heading, mb.titleNodes, rowAuthor, PULLS_RUN)",
    ),
    # The pull request page's title, the record's or, cold, its Pulls row's; the member row of
    # its stack menu and of a stack's page (stack-member-row.js); and its Conversation's
    # commits.
    (
        PLUGINS / "github" / "pull-page.js",
        "titleHeading(pullStateIcon(state, { named: false }), mb.titleNodes(title), number)",
    ),
    (
        PLUGINS / "github" / "stack-member-row.js",
        "title.replaceChildren(...titleNodes(words));",
    ),
    (PLUGINS / "github" / "pull-page.js", "titleNodes: mb.titleNodes,"),
    (
        PLUGINS / "github" / "pull-page.js",
        'h("span", { class: "github-pull-commit-subject" }, mb.titleNodes(event.subject || "Commit"))',
    ),
    # Quick Search's pull requests.
    (
        STATIC / "search-palette.js",
        "window.MetabrowserFormatters.titleNodes(hostDocument, result.label,",
    ),
    # The Commits tab's rows, a commit's page, and its tooltip.
    (
        STATIC / "git-panel.js",
        '`<span class="git-graph-subject">${subjectHtml(commit.subject)}</span>`',
    ),
    (STATIC / "git-panel.js", "${subjectHtml(commit.subject)}</${subjectTag}>`"),
    (STATIC / "git-panel.js", "return window.MetabrowserFormatters.titleHtml(subject);"),
)


def _shipped(pattern: str) -> list[Path]:
    """The app's own files matching *pattern*, in the shell and the built-in plugins."""

    vendor = STATIC / "vendor"
    return sorted(
        path
        for path in (*STATIC.rglob(pattern), *PLUGINS.rglob(pattern))
        if vendor not in path.parents
    )


def test_every_title_surface_draws_its_title_through_the_shared_helper() -> None:
    for source, drawn in SURFACES:
        assert drawn in source.read_text(encoding="utf-8"), f"{source.name}: {drawn}"
    # One markup: only formatters.js writes the prefix's class, as a string; a comment may
    # name it.
    literal = re.compile(r"[\"'`]title-prefix[\"'`]")
    writers = [
        path.name for path in _shipped("*.js") if literal.search(path.read_text(encoding="utf-8"))
    ]
    assert writers == ["formatters.js"], writers
    # One weight: a single rule names the class, in the shell's stylesheet, on the shell's
    # regular weight token, and sets nothing but the weight.
    rules = [
        (path.name, selectors.strip(), body.strip())
        for path in _shipped("*.css")
        for selectors, body in re.findall(
            r"([^{}]+)\{([^{}]*)\}",
            re.sub(r"/\*.*?\*/", "", path.read_text(encoding="utf-8"), flags=re.DOTALL),
        )
        if "title-prefix" in selectors
    ]
    assert rules == [("styles.css", ".title-prefix", "font-weight: var(--weight-normal);")], rules


def test_a_title_prefix_is_regular_and_the_rest_keeps_its_weight_in_chrome(
    tmp_path: Path, chrome_profile: Path
) -> None:
    chrome = require_chrome()
    # The session leads a process group of its own, which Chrome joins, and the whole group
    # is stopped however it ends; its profile is the fixture's to remove.
    result = run_in_own_group(
        [require_node(), str(SESSION)],
        timeout_s=SESSION_TIMEOUT_S,
        env={
            **os.environ,
            "CHROME_BIN": chrome,
            "CHROME_PROFILES": str(chrome_profile),
            "KPRESS_STATIC": str(_kpress_faces(tmp_path / "kpress")),
        },
    )
    if result.timed_out:
        pytest.fail(f"ran past {SESSION_TIMEOUT_S} s; its steps:\n{result.stderr}")
    # Each step's time, shown with the output when it fails.
    print(result.stderr)
    assert result.returncode == 0, result.stderr or result.stdout
    passed = re.fullmatch(r"title prefix in Chrome: (\d+) checks passed\n", result.stdout)
    assert passed is not None and int(passed.group(1)) > 0, result.stdout
