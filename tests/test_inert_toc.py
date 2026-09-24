"""The table of contents of an untrusted document: the server's half, and the session.

``kpress_adapter.inert_render`` takes KPress's table of contents out of the HTML (its
script cannot run under the untrusted profile), says whether KPress drew one, and points
KPress's entries at the ``user-content-`` anchors. ``builtin_plugins/markdown/
inert-toc.js`` draws and runs the page's own from them; ``tests/dom/
markdown-inert-toc-session.js`` plays that on the render recorded here.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Literal

import pytest

from metabrowser import kpress_adapter
from tests.github_pull_fixture import allowlist_violations, html_tree

REPO_ROOT = Path(__file__).resolve().parent.parent
RECORDED = REPO_ROOT / "tests" / "fixtures" / "inert-toc-render.json"
SESSION_JS = REPO_ROOT / "tests" / "dom" / "markdown-inert-toc-session.js"

# A document long enough for a table of contents, with a repeated heading, a heading
# named like the application's globals, a raw heading with its own id, and links to
# headings as github.com spells them.
GUIDE = "\n\n".join(
    [
        "# Guide",
        "Links: [install](#install) [usage again](#usage-1) [raw](#user-content-raw-heading).",
        "## Install",
        "Run the installer. " * 20,
        "## Usage",
        "Open a folder. " * 20,
        "### Usage",
        "A nested section with the same title. " * 10,
        "## `constructor`",
        "Named like a prototype member. " * 10,
        '<h2 id="metabrowser">Raw heading</h2>',
        "Written in HTML with an id of its own. " * 10,
        "## Troubleshooting",
        "When something fails. " * 20,
    ]
)


def _render(text: str, include_toc: Literal["on", "off"]) -> dict[str, Any]:
    return kpress_adapter.render_kpress_view(
        source_text=text,
        source_path="GUIDE.md",
        kind="markdown",
        view="document",
        ext=".md",
        mtime_hash="inert-toc-test",
        size=len(text.encode()),
        include_toc=include_toc,
    )


def test_an_inert_render_carries_kpress_entries_not_its_markup() -> None:
    trusted = _render(GUIDE, "on")
    assert "data-kpress-toc" in trusted["html"]
    inert = kpress_adapter.inert_render(trusted)
    assert inert["toc"] is True
    # KPress's nav, toggle, and title are gone, not flattened into the document.
    assert "Contents" not in inert["html"]
    assert "<ol>" not in inert["html"]
    assert allowlist_violations(inert["html"], images=True) == []
    entries = inert["model"]["headings"]
    assert [(entry["level"], entry["title"], entry["href"]) for entry in entries] == [
        (1, "Install", "#user-content-install"),
        (1, "Usage", "#user-content-usage"),
        (2, "Usage", "#user-content-usage-1"),
        (1, "constructor", "#user-content-constructor"),
        (1, "Troubleshooting", "#user-content-troubleshooting"),
    ]
    for entry in entries:
        assert f'id="{entry["href"][1:]}"' in inert["html"]
    # The raw heading is anchored too, though KPress lists only Markdown headings.
    assert 'id="user-content-raw-heading"' in inert["html"]
    assert 'id="metabrowser"' not in inert["html"]
    assert 'href="#user-content-usage-1"' in inert["html"]


def test_an_inert_render_without_a_table_of_contents_says_so() -> None:
    assert kpress_adapter.inert_render(_render(GUIDE, "off"))["toc"] is False
    # A document that writes KPress's markers itself keeps its text and draws no TOC.
    forged = (
        "<button data-kpress-toc-toggle>x</button><nav data-kpress-toc><p>kept</p></nav>\n\n"
        + GUIDE
    )
    inert = kpress_adapter.inert_render(_render(forged, "off"))
    assert inert["toc"] is False
    assert "kept" in inert["html"]


def test_an_entry_names_only_the_heading_kpress_gave_its_id() -> None:
    """A raw heading written with the id KPress gives a Markdown heading does not take
    that heading's entry: the id names no one heading, so the entry is left out. The
    first heading with an empty slug, which KPress gives ``id=""``, keeps its entry."""

    text = "\n\n".join(
        [
            "# Guide",
            "## \U0001f680",
            "## \U0001f389",
            '<h2 id="install">Evil</h2>',
            "## Install",
            "## Usage",
        ]
    )
    inert = kpress_adapter.inert_render(_render(text, "on"))
    assert [(entry["title"], entry["href"]) for entry in inert["model"]["headings"]] == [
        ("\U0001f680", "#user-content-"),
        ("\U0001f389", "#user-content--1"),
        ("Usage", "#user-content-usage"),
    ]
    assert 'id="user-content-evil"' in inert["html"]


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
def test_the_session_plays_the_recorded_inert_render() -> None:
    """``tests/dom/markdown-inert-toc-session.js`` runs on the inert render recorded in
    ``tests/fixtures/inert-toc-render.json``: whether KPress drew a TOC, its anchored
    entries, and Python's HTML parse of the inert HTML, so the session never runs on
    markup a test wrote by hand. Regenerate with GOLDEN_UPDATE=1, then update
    tests/golden/cli-ui-inert-toc.tryscript.md."""

    inert = kpress_adapter.inert_render(_render(GUIDE, "on"))
    recorded = (
        json.dumps(
            {
                "toc": inert["toc"],
                "headings": inert["model"]["headings"],
                "tree": html_tree(inert["html"]),
            },
            indent=1,
            ensure_ascii=False,
        )
        + "\n"
    )
    if os.environ.get("GOLDEN_UPDATE") == "1":
        RECORDED.write_text(recorded, encoding="utf-8")
    assert RECORDED.read_text(encoding="utf-8") == recorded
    result = subprocess.run(
        ["node", str(SESSION_JS)], capture_output=True, text=True, timeout=60, check=True
    )
    transcript = json.loads(result.stdout)
    assert transcript["entries"][0] == {
        "level": "kpress-toc-level-1 toc-h1",
        "href": "#user-content-install",
        "text": "Install",
    }
    assert transcript["scrolled"]["active"] == "#user-content-constructor"
    assert transcript["enhancerRoot"] == [{"className": "kpress-prose", "tocLinks": 0, "links": 3}]
    assert transcript["entryClicked"]["opened"] == ["user-content-troubleshooting"]
    assert transcript["modifiedClick"]["defaultPrevented"] is False
    assert transcript["disposed"]["listeners"] == 0
