"""What a link in rendered text opens agrees with the server's own reading of the same URL.

``static/repository-links.js`` decides in the browser what a ``github.com`` link into the
served repository opens; the server reads the same URLs for ``metab URL`` and the macOS
app's links (``builtin_plugins/github/urls.py``) and turns a selection into an address
(``cli/selection_href.py``). The browserless session (``tests/dom/repository-links-session.js``,
pinned whole by ``cli-ui-repository-links.tryscript.md``) runs the exact module over one
table of URLs, and these hold its answers to the server's: an in-app page is the one the
server opens the URL at, a pinned revision's address is the server's spelling of that
path, and a pull request text's file on github.com is that file at the text's commit.
"""

from __future__ import annotations

import functools
import json
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

from metabrowser.builtin_plugins.github.urls import GithubUrlReducer
from metabrowser.cache.urls import ReducerOutcome
from metabrowser.cli.selection_href import selection_view_href
from metabrowser.git.tree_source import GitPath
from metabrowser.view_routes import (
    decode_safe_commit_route,
    decode_safe_pull_route,
    decode_safe_stack_route,
)
from tests.required_tools import require_node

SESSION_JS = Path(__file__).resolve().parent / "dom" / "repository-links-session.js"
# The head each pull request text of the session describes.
TEXT_HEADS = {
    "text away from its head": "b" * 40,
    "a stack's note away from its head": "b" * 40,
    "text at the served head, from a subfolder": "a" * 40,
    "text beside a checkout of its head": "a" * 40,
}


@functools.cache
def _session(part: str | None = None) -> dict[str, Any]:
    """The session's transcript: with *part* ``localized``, the table ``localize`` reads."""

    require_node()
    result = subprocess.run(
        ["node", str(SESSION_JS), *([] if part is None else [part])],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    return json.loads(result.stdout)


def _rows(kind: str) -> list[tuple[str, dict[str, Any]]]:
    return [
        (context, row)
        for context, rows in _session("localized")["localized"].items()
        for row in rows
        if row["result"] is not None and row["result"]["kind"] == kind
    ]


def _reduced(url: str) -> ReducerOutcome:
    outcome = GithubUrlReducer().reduce(url)
    assert isinstance(outcome, ReducerOutcome), (url, outcome)
    assert outcome.clone_url == "https://github.com/example/docs", url
    return outcome


def test_an_in_app_page_is_the_one_the_server_opens_the_link_at() -> None:
    """A pull request, its tab, a commit, and the list open where ``metab URL`` opens them.

    The browser is stricter than the server, never looser: a fragment or query the page
    would lose leaves the link external, where the server drops it.
    """

    routes = _rows("route")
    assert {row["result"]["localization"] for _, row in routes} == {"pull", "commit", "pulls"}
    for context, row in routes:
        href = row["result"]["href"]
        if row["result"]["pull"] is not None and row["result"]["pull"]["file"]:
            continue  # A text's changed file: test_a_texts_changed_file_opens_in_changes.
        if href == "/pulls":
            assert urlsplit(row["url"]).path.endswith("/pulls"), row
            continue
        selection = _reduced(row["url"]).selection
        commit = selection.commit if selection.kind == "commit" else None
        assert selection_view_href(selection, (), commit=commit) == href, (context, row)
        assert (
            decode_safe_pull_route(href.encode()) is not None
            or decode_safe_commit_route(href.encode()) is not None
        ), href


def test_pr_and_diff_links_preserve_authored_destinations() -> None:
    localized = _session("localized")["localized"]
    checkout = {row["label"]: row["result"] for row in localized["checkout"]}
    away = {row["label"]: row["result"] for row in localized["text away from its head"]}
    assert checkout["its Changes, at one file and line"] is None
    assert checkout["a commit, at one file"] is None
    assert away["an authored absolute patch URL"] is None
    assert away["the same resolution from an authored relative file"]["url"].endswith(
        f"/blob/{TEXT_HEADS['text away from its head']}/7.patch"
    )
    assert away["an anchored changed file, on GitHub"]["url"].endswith("README.md#install")


def test_a_pinned_revisions_address_is_the_servers_spelling_of_the_path() -> None:
    """On a pin, a file or folder of the served branch or commit opens at the server's address."""

    pinned = [
        (context, row)
        for context, row in _rows("view")
        if context in {"pin", "text away from its head"}
    ]
    assert pinned
    for context, row in pinned:
        selection = _reduced(row["url"]).selection
        # The pinned branch, `main`, and a commit are one segment each.
        path = selection.ref_and_path[1:]
        target = row["result"]["target"]
        assert selection_view_href(selection, path) == f"/view/{target['path']}", (context, row)


def test_a_texts_path_off_its_head_is_that_file_at_the_head() -> None:
    """A pull request text's path-relative reference names the head's file on github.com,
    where Metabrowser cannot show it: at another commit, or outside a served folder."""

    external = _rows("external")
    assert external
    for context, row in external:
        assert context in TEXT_HEADS, row
        selection = _reduced(row["result"]["url"]).selection
        relative = unquote(urlsplit(row["url"]).path.split("/pull/", 1)[1])
        assert selection.kind == ("tree" if relative == "" or relative.endswith("/") else "blob")
        assert selection.ref_and_path[0] == TEXT_HEADS[context].encode(), row
        assert b"/".join(selection.ref_and_path[1:]) == relative.rstrip("/").encode(), row


def test_a_texts_changed_file_opens_in_changes() -> None:
    """A pull request text's path to a file its comparison changes opens in its Changes.

    The address is the one the server's route decoder reads back as that file of that pull
    request or stack, so the page's router and a new tab open the same file.
    """

    changed = [
        (context, row)
        for context, row in _rows("route")
        if row["result"]["pull"] is not None and row["result"]["pull"]["file"]
    ]
    assert {row["result"]["pull"]["stack"] for _, row in changed} == {False, True}
    for context, row in changed:
        pull = row["result"]["pull"]
        relative = unquote(urlsplit(row["url"]).path.split("/pull/", 1)[1])
        assert pull["file"] == relative, (context, row)
        raw = row["result"]["href"].encode()
        route = decode_safe_stack_route(raw) if pull["stack"] else decode_safe_pull_route(raw)
        assert route is not None, row
        assert (route.number, route.tab, route.file) == (pull["number"], pull["tab"], relative)


def test_a_rendered_diffs_head_link_on_github_is_the_file_its_wire_names() -> None:
    """A pin's ``/view/`` link off its head opens on github.com the file its wire names.

    The server reads the github.com address back as a blob at the head whose path is the
    one the server's GitPath codec decodes from the wire; a wire that names no text, or an
    address that is not a pin's, has no github.com address.
    """

    expected_files = {
        "a file",
        "a file, at a heading",
        "a name with a leading byte-order mark",
        "a name with a literal replacement character",
    }
    cases = _session()["viewFiles"]
    assert {label for label, case in cases.items() if case["url"] is not None} == expected_files
    for label in expected_files:
        href, url = cases[label]["href"], cases[label]["url"]
        wire = urlsplit(href).path.removeprefix("/view/")
        selection = _reduced(url).selection
        assert selection.kind == "blob", label
        head = TEXT_HEADS["text away from its head"].encode()
        assert selection.ref_and_path == (head, *GitPath.from_wire(wire).segments), label


def test_an_in_app_link_opens_what_its_address_says() -> None:
    """A plain click on an in-app link opens it in place; any other click is the browser's.

    So a new tab or a copied address opens what the click opens. A ``/view/`` link opens
    its target, and a route opens by the page's own opener when it takes it and otherwise
    by the shell's, which is asked only for what the page declined; a route neither opens,
    as before the shell's tabs have loaded, is followed as the link it is.
    """

    for name, run in _session()["enhanced"].items():
        for link, attributes in run["anchors"].items():
            in_app = "data-metabrowser-github-localization" in attributes
            assert ("target" in attributes) is not in_app, (name, link)
            assert not run["clicks"][link]["withMeta"], (name, link)
            # One click handler a link, however many times its text is read; a link restored
            # to what the text wrote keeps its handler, which leaves every click to the browser.
            listeners = run["clicks"][link]["listeners"]
            assert listeners == 1 if in_app else listeners in (0, 1), (name, link)
            assert in_app or not run["clicks"][link]["plain"], (name, link)
        opened = [f"/view/{target['path']}" for target in run["opened"]]
        followed = [
            attributes["href"]
            for link, attributes in run["anchors"].items()
            if run["clicks"][link]["plain"] and attributes["href"].startswith("/view/")
        ]
        assert opened == followed, name
        routes = [
            attributes["href"]
            for attributes in run["anchors"].values()
            if "data-metabrowser-github-localization" in attributes
            and not attributes["href"].startswith("/view/")
        ]
        routed = [
            attributes["href"]
            for link, attributes in run["anchors"].items()
            if run["clicks"][link]["plain"] and not attributes["href"].startswith("/view/")
        ]
        page = [entry.split(" ", 1)[0] for entry in run["routed"]]
        shell = run["shell"]["asked"]
        # Each route's plain click asks the page, then the shell for what the page declined.
        assert sorted(page + shell) == sorted(routes), name
        assert not set(page) & set(shell), name
        opened_in_place = page + (shell if run["shell"]["opens"] else [])
        assert sorted(opened_in_place) == sorted(routed), name


def test_each_in_app_link_has_the_card_of_what_it_opens() -> None:
    """A link ``enhance`` leaves in-app has its link card, for what its address opens, with
    the text it was given as the root; a link it restores or makes an outside one has none,
    and no link carries a tooltip of its own; the page's disposal of the text comes last.
    Without the cards loaded, the links open as they do with them."""

    runs = _session()["enhanced"]
    for name, run in runs.items():
        cards: dict[str, str] = {}
        for call in run["previews"][:-1]:
            verb, rest = call.split(" ", 1)
            if verb == "register":
                link, target = rest.split(" in the text: ", 1)
                cards[link] = target
            else:
                assert verb == "forget", (name, call)
                cards.pop(rest, None)
        assert run["previews"][-1:] in ([], ["dispose the text"]), name
        for link, attributes in run["anchors"].items():
            assert "data-tip-text" not in attributes, (name, link)
            localization = attributes.get("data-metabrowser-github-localization")
            if localization is None or not run["previews"]:
                assert link not in cards, (name, link)
                continue
            href = attributes["href"]
            kind = f"view {localization}" if href.startswith("/view/") else "route"
            assert cards[link] == f"{kind} {href}", (name, link)
    without = runs["a text on a page whose link cards have not loaded"]
    with_cards = runs["a commit's message, which has no text context"]
    assert without["previews"] == [] != with_cards["previews"]
    assert (without["changed"], without["anchors"]) == (
        with_cards["changed"],
        with_cards["anchors"],
    )
