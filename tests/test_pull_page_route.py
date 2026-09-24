"""The served pull request's page: its route, its shell, and what its paint may parse.

The page's decisions run browserless in ``tests/dom/github-pull-page-session.js``. What is
left to the browser is the shell's route glue and the page's paint; this file pins what
of them can be pinned without one: the route grammar the server and ``--show`` share,
that ``/pull/`` serves the shell and loads the GitHub plugin for the ``pull-request``
kind, and that the paint parses no HTML but KPress's sanitized Markdown.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from metabrowser.server import app
from metabrowser.view_routes import decode_safe_pull_route, format_pull_href

PAGE_JS = (
    Path(__file__).resolve().parent.parent / "src/metabrowser/builtin_plugins/github/pull-page.js"
)


@pytest.mark.parametrize(
    ("raw", "decoded"),
    [
        (b"/pull/7", (7, "")),
        (b"/pull/7/", (7, "")),
        (b"/pull/7/files", (7, "files")),
        (b"/pull/7/files/", (7, "files")),
        (b"/pull/9999999999", (9999999999, "")),
        (b"/pull/0", None),
        (b"/pull/07", None),
        (b"/pull/7/commits", None),
        (b"/pull/7/files/x", None),
        (b"/pull/7//", None),
        (b"/pull/%37", None),
        (b"/pull/", None),
        (b"/pulls/7", None),
    ],
)
def test_the_pull_route_grammar(raw: bytes, decoded: tuple[int, str] | None) -> None:
    assert decode_safe_pull_route(raw) == decoded
    if decoded is not None:
        assert decode_safe_pull_route(format_pull_href(*decoded).encode()) == decoded


def test_format_pull_href_refuses_what_the_route_does_not_parse() -> None:
    for number, tab in ((0, ""), (7, "commits"), (10**10, "")):
        with pytest.raises(ValueError, match="pull route"):
            format_pull_href(number, tab)


def test_the_pull_route_serves_the_shell_and_the_plugin_for_its_kind() -> None:
    with TestClient(app) as client:
        shell = client.get("/pull/7/files")
        assert shell.status_code == 200
        assert 'id="preview-pane"' in shell.text
        # The shell loads a plugin's assets by the kinds its views consume.
        config = re.search(r"configureAssets\((\{.*?\})\);", shell.text)
        assert config is not None and '"pull-request": [{"name": "github"' in config.group(1)
        for refused in ("/pull/0", "/pull/7/commits"):
            answer = client.get(refused)
            assert (answer.status_code, answer.text) == (400, "Invalid pull-request route.")


def test_the_page_parses_no_html_but_sanitized_markdown() -> None:
    """Every text of the pull request is painted with textContent.

    The one ``innerHTML`` write is KPress's Markdown into an inert template, made inert by
    ``sanitizeNodes``, which rebuilds only allowlisted nodes; every outside link opens with
    no opener or referrer, and no KPress script or stylesheet is loaded for it.
    """

    source = PAGE_JS.read_text(encoding="utf-8")
    assert source.count("innerHTML") == 1
    assert "template.innerHTML = String(rendered.html);" in source
    assert "...sanitizeNodes(template.content.childNodes, document," in source
    assert "loadKpressAssets" not in source
    assert "insertAdjacentHTML" not in source and "outerHTML" not in source
    assert source.count('rel: "noopener noreferrer"') == 1
    assert source.count('["rel", "noopener noreferrer"]') == 1
    # GitHub's own rendering of the text is never read.
    assert ".body_html" not in source and '["body_html"]' not in source
