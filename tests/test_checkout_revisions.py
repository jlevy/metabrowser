"""A folder's server shows its checkout's branches and tags, and never writes the checkout.

A folder that is a repository's root shows what a mirror does and more
(``docs/project/architecture/arch-source-sessions-and-pins.md``, "Revisions of a
Checkout"): any branch or tag of a served checkout is shown as a mirror shows one, a
pinned revision read from Git objects, and the working tree is a separate choice, the one
a folder opens on.
These tests run the real application over ``tests/source_checkout_fixture.py``'s checkout,
which has local branches, remote-tracking branches, tags, and a working tree that differs
from every commit: an edited file, a staged file, and an untracked one.

The rule they guard is the owner's: showing another revision never writes the working
tree, the index, ``HEAD``, a ref, or an object. :func:`snapshot` reads every entry under
the checkout, its ``.git`` included, with each file's inode and modification time, so a
rewrite to the same bytes shows too, and ``test_showing_revisions_leaves_the_checkout_byte_for_byte``
compares it across a whole session.
"""

from __future__ import annotations

import os
import subprocess
import time
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient

from metabrowser import server
from metabrowser.capabilities import (
    DEFAULT_CAPABILITIES,
    UNTRUSTED_CAPABILITIES,
    apply_capabilities,
    get_capabilities,
)
from metabrowser.checkout_revisions import NOT_A_CHECKOUT, open_on_ref
from metabrowser.source import SubjectOpenError, subject_open_failure
from metabrowser.source_routes import PIN_CHANGED_HEADER, PIN_HEADER, WORKING_TREE_PIN
from tests.required_tools import needs_git
from tests.source_checkout_fixture import (
    EDITED_README,
    STAGED_TEXT,
    UNTRACKED_TEXT,
    build_checkout,
    git,
    git_env,
    snapshot,
    view,
)

pytestmark = [
    pytest.mark.skipif(os.name != "posix", reason="the fixture's Git environment is POSIX"),
    needs_git,
]

_JSON = {"content-type": "application/json"}
FIRST = "fcb9d63c3c8533d1b929861f451a066e6d4f2d9e"
SECOND = "42382ea2303b733e1e21b4bd6ddb974ca4e775eb"
FEATURE = "c7ae2a331f546e6a2431ed7093e9e430a9d1269b"


@pytest.fixture
def checkout(tmp_path: Path) -> Path:
    return build_checkout(tmp_path.resolve())


@pytest.fixture
def served(checkout: Path) -> Generator[TestClient]:
    server._set_root_dir(checkout)
    with TestClient(server.app) as client:
        yield client


def _refs(client: TestClient, **params: str) -> dict[str, Any]:
    response = client.get("/api/source/refs", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def _pin(client: TestClient, **body: object) -> dict[str, Any]:
    response = client.post("/api/source/pin", json=body, headers=_JSON)
    assert response.status_code == 200, response.text
    return response.json()


def _names(listing: dict[str, Any]) -> list[str]:
    return [row["name"] for row in listing["refs"]]


def _wire(display: str) -> str:
    return view(display).removeprefix("/view/")


def _tree(client: TestClient) -> list[str]:
    return [node["name"] for node in client.get("/api/tree", params={"depth": "1"}).json()["tree"]]


def _live_tree(client: TestClient) -> list[str]:
    """The folder's listing once its walk has it: a server just started has not scanned yet."""

    deadline = time.monotonic() + 20
    while not (names := _tree(client)) and time.monotonic() < deadline:
        time.sleep(0.05)
    return names


# ── Listing ──────────────────────────────────────────────────


def test_a_checkout_lists_its_branches_tags_and_remotes(served: TestClient) -> None:
    branches = _refs(served)
    assert branches["kinds"] == ["branch", "tag", "remote"]
    # The working tree is what a folder opens on, and is no ref: no row is served.
    assert branches["working_tree"] == {
        "current": True,
        "head": "refs/heads/topic",
        "head_name": "topic",
    }
    assert (branches["pin"], branches["ref"]) == (None, None)
    # The checked-out branch lists first, as a mirror's default does, and is not "current":
    # picked as a ref it shows its commit, which is not the working tree.
    assert _names(branches) == ["topic", "feature", "local-work"]
    assert branches["refs"][0] == {
        "name": "topic",
        "ref": "refs/heads/topic",
        "commit": SECOND,
        "default": False,
        "checked_out": True,
        "current": False,
    }
    assert not any(row["current"] or row["default"] for row in branches["refs"])
    tags = _refs(served, kind="tag")
    assert sorted(_names(tags)) == ["local-tag", "v1"]
    # An annotated tag is peeled to the commit it names.
    assert {row["name"]: row["commit"] for row in tags["refs"]}["v1"] == FIRST
    remotes = _refs(served, kind="remote")
    # A remote-tracking branch keeps its remote's name; origin/HEAD names another row.
    assert _names(remotes) == ["origin/feature", "origin/topic"]
    assert [row["ref"] for row in remotes["refs"]] == [
        "refs/remotes/origin/feature",
        "refs/remotes/origin/topic",
    ]
    assert _names(_refs(served, kind="remote", q="FEAT")) == ["origin/feature"]


def test_a_detached_head_is_on_no_branch(checkout: Path) -> None:
    git(checkout, "stash", "-q", "--include-untracked")
    git(checkout, "checkout", "-q", "--detach", FIRST)
    server._set_root_dir(checkout)
    with TestClient(server.app) as client:
        listing = _refs(client)
        refused = client.post("/api/source/pin", json={"ref": "HEAD"}, headers=_JSON)
    assert listing["working_tree"] == {"current": True, "head": None, "head_name": None}
    assert not any(row["checked_out"] for row in listing["refs"])
    assert (refused.status_code, refused.json()["code"]) == (404, "selection_not_found")


def test_a_plain_folder_and_a_subdirectory_of_a_checkout_have_no_selector(
    checkout: Path, tmp_path: Path
) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    (plain / "README.md").write_text("# Plain\n", encoding="utf-8")
    inner = checkout / "docs"
    inner.mkdir()
    (inner / "note.md").write_text("inside\n", encoding="utf-8")
    for root in (plain, inner):
        server._set_root_dir(root)
        with TestClient(server.app) as client:
            shell = client.get("/view/").text
            refs = client.get("/api/source/refs")
            pin = client.post("/api/source/pin", json={"ref": "topic"}, headers=_JSON)
        assert 'id="source-ref-selector"' not in shell, root
        assert "METABROWSER_SOURCE_CHECKOUT" not in shell, root
        assert (refs.status_code, refs.json()["capability"]) == (409, "refs"), root
        assert (pin.status_code, pin.json()["capability"]) == (409, "pin"), root


# ── Showing a revision ───────────────────────────────────────


def test_a_branch_is_shown_from_its_commit_not_from_the_working_tree(
    served: TestClient, checkout: Path
) -> None:
    assert _live_tree(served) == ["NOTES.md", "README.md", "STAGED.md", "UNTRACKED.md"]
    answer = _pin(served, ref="refs/heads/feature", view="/view/README.md")
    status = answer["status"]
    assert answer["changed"] is True
    assert (status["subject"], status["pin"], status["ref"]) == (
        "git_revision",
        FEATURE,
        "refs/heads/feature",
    )
    # Named as the folder is, with no origin and nothing to refresh: Metabrowser fetches
    # nothing into a checkout.
    assert (status["name"], status["origin"], status["refreshable"]) == ("checkout", None, False)
    assert status["ref_name"] == "feature"
    # The page's file is in the revision, at the revision's address.
    assert answer["view_href"] == view("README.md")
    assert _tree(served) == ["FEATURE.md", "README.md"]
    readme = served.get("/api/file", params={"path": _wire("README.md")}).json()
    assert readme["content"] == "# Mirror\n"
    raw = served.get("/raw", params={"path": _wire("FEATURE.md")})
    assert raw.text == "Only on feature.\n"
    # The mode is still how the root was opened.
    identity = served.get("/api/identity").json()
    assert (identity["kind"], identity["short_name"]) == ("folder", "checkout")
    assert identity["full_name"].endswith("/checkout@feature")
    assert _refs(served)["working_tree"]["current"] is False
    assert [row["name"] for row in _refs(served)["refs"] if row["current"]] == ["feature"]


def test_the_checked_out_branch_is_its_commit_and_the_working_tree_is_a_separate_choice(
    served: TestClient,
) -> None:
    # STAGED.md is in the index and in no commit: the checked-out branch does not have it.
    answer = _pin(served, ref="topic", view="/view/STAGED.md")
    assert (answer["status"]["pin"], answer["status"]["ref"]) == (SECOND, "refs/heads/topic")
    assert answer["view_href"] == "/view/"
    assert _tree(served) == ["NOTES.md", "README.md"]
    committed = served.get("/api/file", params={"path": _wire("README.md")}).json()
    assert committed["content"] == "# Mirror\n"
    # Only the working-tree selection returns to the live files.
    back = _pin(served, working_tree=True, view=view("README.md"))
    assert (back["changed"], back["status"]["subject"], back["status"]["pin"]) == (
        True,
        "attached_filesystem",
        None,
    )
    assert back["view_href"] == "/view/README.md"
    assert _live_tree(served) == ["NOTES.md", "README.md", "STAGED.md", "UNTRACKED.md"]
    live = served.get("/api/file", params={"path": "README.md"}).json()
    assert live["content"] == EDITED_README
    assert _pin(served, working_tree=True)["changed"] is False


def test_a_tag_a_remote_branch_and_a_commit_are_shown_and_a_miss_fetches_nothing(
    served: TestClient,
) -> None:
    assert _pin(served, ref="v1")["status"]["ref"] == "refs/tags/v1"
    remote = _pin(served, ref="origin/feature")["status"]
    assert (remote["ref"], remote["ref_name"], remote["pin"]) == (
        "refs/remotes/origin/feature",
        "origin/feature",
        FEATURE,
    )
    assert served.get("/api/identity").json()["full_name"].endswith("@origin/feature")
    # A commit no remote has, by its abbreviated ID, under no ref.
    local = _refs(served)["refs"][2]
    assert local["name"] == "local-work"
    by_id = _pin(served, oid=local["commit"][:10])["status"]
    assert (by_id["pin"], by_id["ref"]) == (local["commit"], None)
    assert "LOCAL.md" in _tree(served)
    for body, status, code in (
        ({"ref": "refs/heads/gone"}, 404, "selection_not_found"),
        ({"oid": "0" * 40}, 404, "selection_not_found"),
        ({"ref": "topic~1"}, 400, "invalid_selection"),
        ({"ref": "refs/pull/7/head"}, 400, "invalid_selection"),
        ({"working_tree": True, "ref": "topic"}, 400, "invalid_selection"),
        ({"working_tree": False}, 400, "invalid_selection"),
    ):
        refused = served.post("/api/source/pin", json=body, headers=_JSON)
        assert (refused.status_code, refused.json()["code"]) == (status, code), body
    # Nothing was switched by a refusal.
    assert served.get("/api/source/status").json()["pin"] == local["commit"]


def test_an_address_crosses_between_the_folder_and_a_revision(served: TestClient) -> None:
    # NOTES.md is on topic and not on feature: the page goes to the root there.
    assert _pin(served, ref="feature", view="/view/NOTES.md")["view_href"] == "/view/"
    # A folder's address, kept by a tab or a history entry, is sent where a switch would
    # send it: to the same names in the revision, or to its root.
    kept = served.get("/view/README.md", follow_redirects=False)
    assert (kept.status_code, kept.headers["location"]) == (307, view("README.md"))
    gone = served.get("/view/NOTES.md", follow_redirects=False)
    assert (gone.status_code, gone.headers["location"]) == (307, "/view/")
    # Back on the working tree, a revision's address goes to the folder's entry, and one
    # the folder lacks is the folder's to answer as any missing path.
    assert _pin(served, working_tree=True, view=view("FEATURE.md"))["view_href"] == "/view/"
    crossed = served.get(view("README.md"), follow_redirects=False)
    assert (crossed.status_code, crossed.headers["location"]) == (307, "/view/README.md")
    assert served.get(view("FEATURE.md"), follow_redirects=False).status_code == 200


def test_a_folder_opens_on_a_named_ref_once(checkout: Path, tmp_path: Path) -> None:
    """``--ref``: the application's start makes the selector's switch, for that start only."""

    server._set_root_dir(checkout)
    open_on_ref("origin/feature")
    with TestClient(server.app) as client:
        status = client.get("/api/source/status").json()
        assert (status["subject"], status["ref"], status["pin"]) == (
            "git_revision",
            "refs/remotes/origin/feature",
            FEATURE,
        )
        assert _tree(client) == ["FEATURE.md", "README.md"]
        # The page's selector can still return to the working tree.
        assert _pin(client, working_tree=True)["status"]["pin"] is None
    # The next start says nothing, and opens on the files.
    with TestClient(server.app) as client:
        assert client.get("/api/source/status").json()["subject"] == "attached_filesystem"
    # A ref the checkout lacks, and a root with no checkout, stop the start with a message
    # that names no path, and leave nothing for the start after.
    plain = tmp_path / "plain"
    plain.mkdir()
    for root, ref, said in (
        (checkout, "gone", "--ref gone: no branch or tag with that name is in the checkout"),
        (checkout, "topic~1", "--ref topic~1: the ref is not a valid Git ref name"),
        (plain, "topic", NOT_A_CHECKOUT),
    ):
        server._set_root_dir(root)
        open_on_ref(ref)
        with pytest.raises(SubjectOpenError) as refused, TestClient(server.app):
            pass
        assert str(refused.value) == said
        assert str(subject_open_failure()) == said
        assert str(tmp_path) not in said
        with TestClient(server.app) as client:
            assert client.get("/api/source/status").json()["subject"] == "attached_filesystem"
        assert subject_open_failure() is None


# ── Trust ────────────────────────────────────────────────────


def _answered_under(client: TestClient) -> dict[str, bool]:
    """The trust block the served subject's routes answer under."""

    answer: dict[str, bool] = client.get("/api/capabilities").json()["capabilities"]
    return answer


def test_a_revision_runs_under_the_untrusted_profile_and_the_folder_gets_its_own_back(
    served: TestClient,
) -> None:
    trusted = DEFAULT_CAPABILITIES.as_wire()
    untrusted = UNTRUSTED_CAPABILITIES.as_wire()
    assert _answered_under(served) == trusted
    assert "content-security-policy" not in served.get("/view/").headers
    _pin(served, ref="feature")
    # The process's block is the folder's and does not move: a revision's profile is its
    # subject's, so nothing has to be set, or cleared, for it to hold.
    assert get_capabilities() == DEFAULT_CAPABILITIES
    assert _answered_under(served) == untrusted
    page = served.get("/view/")
    assert "script-src 'nonce-" in page.headers["content-security-policy"]
    assert '"CAPABILITIES": {"active_content": false, "mutations": false}' in page.text
    # /raw never hands a revision's file to the page as a script.
    raw = served.get("/raw", params={"path": _wire("README.md")})
    assert raw.status_code == 200
    assert "allow-scripts" not in raw.headers["content-security-policy"]
    _pin(served, ref="topic")
    assert _answered_under(served) == untrusted
    _pin(served, working_tree=True)
    assert _answered_under(served) == trusted
    assert "content-security-policy" not in served.get("/view/").headers
    assert "allow-scripts" in served.get("/raw/README.md").headers["content-security-policy"]


def test_the_folders_own_flags_return_exactly_and_a_revision_never_gains_them(
    checkout: Path,
) -> None:
    chosen = apply_capabilities(allow_edits=True)
    assert chosen.mutations and chosen.active_content
    server._set_root_dir(checkout)
    with TestClient(server.app) as client:
        _pin(client, ref="feature")
        assert _answered_under(client) == UNTRUSTED_CAPABILITIES.as_wire()
        _pin(client, working_tree=True)
        assert _answered_under(client) == chosen.as_wire()
        _pin(client, ref="feature")
    assert get_capabilities() == chosen


# A commit whose files would run if anything served them as active content.
_SCRIPT = "<script>window.ran = true</script>"
_HOSTILE_FILES = {
    "page.html": f"<!doctype html><title>t</title>{_SCRIPT}<img src=x onerror=alert(1)>\n",
    "doc.md": f'# Doc\n\n{_SCRIPT}\n\n<a href="javascript:alert(1)">link</a>\n',
    "pic.svg": "<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>\n",
    "code.js": "window.ran = true;\n",
}


def _hostile_branch(checkout: Path) -> None:
    """Write ``refs/heads/hostile`` with fast-import, leaving the working tree as it is."""

    stream = b"commit refs/heads/hostile\n"
    stream += b"committer Hostile <hostile@example.invalid> 1767225600 +0000\n"
    stream += b"data 8\nhostile\n"
    for name, body in _HOSTILE_FILES.items():
        payload = body.encode()
        stream += f"M 100644 inline {name}\ndata {len(payload)}\n".encode() + payload + b"\n"
    subprocess.run(
        ["git", "-C", str(checkout), "fast-import", "--quiet", "--done"],
        check=True,
        input=stream + b"done\n",
        capture_output=True,
        env=git_env(checkout.parent),
    )


def _assert_no_active_content(address: str, response: Any) -> None:
    """One answer of a pinned revision carries nothing a page would run."""

    kind = response.headers.get("content-type", "")
    policy = response.headers.get("content-security-policy", "")
    if address.startswith("/raw"):
        assert policy.startswith("sandbox"), address
        assert "allow-scripts" not in policy, address
        assert not kind.startswith(("text/javascript", "application/javascript")), address
        return
    if kind.startswith("text/html"):
        # The application's own page: every script it runs is the server's, by nonce.
        assert "script-src 'nonce-" in policy, address
        return
    if kind.startswith("application/json"):
        body = response.json()
        if not isinstance(body, dict):
            return
        capabilities = body.get("capabilities")
        if isinstance(capabilities, dict) and "active_content" in capabilities:
            assert capabilities == UNTRUSTED_CAPABILITIES.as_wire(), address
        # No Preview tab for an HTML file, the only view that frames a file's own page. An
        # image's Preview draws it in an <img>, which runs nothing.
        if body.get("kind") == "html":
            assert "preview" not in [view.get("id") for view in body.get("views") or []], address
        # A render is inert: no script element, handler, or script address survives it.
        rendered = str(body.get("html", ""))
        for hostile in ("<script", "onerror", "javascript:"):
            assert hostile not in rendered.lower(), (address, hostile)


def _sweep_a_hostile_revision(checkout: Path) -> int:
    """Ask every GET route of a revision holding hostile files; return how many were asked."""

    _hostile_branch(checkout)
    chosen = apply_capabilities(allow_edits=True)
    assert chosen.active_content and chosen.mutations
    server._set_root_dir(checkout)
    asked = 0
    with TestClient(server.app) as client:
        _pin(client, ref="hostile")
        wires = {name: _wire(name) for name in _HOSTILE_FILES}
        for route in server.app.routes:
            path = getattr(route, "path", "")
            if "GET" not in (getattr(route, "methods", None) or set()) or "{" in path:
                continue
            if path.startswith("/_debug"):
                continue
            for wire in ("", *wires.values()):
                address = path if not wire else f"{path}?path={wire}&view=rendered"
                _assert_no_active_content(address, client.get(address))
                asked += 1
        for name, wire in wires.items():
            shell = client.get(f"/view/{wire}")
            _assert_no_active_content(f"/view/{name}", shell)
        # The document did render, so the checks above read a real render.
        document = client.get(
            "/api/kpress/render", params={"path": wires["doc.md"], "view": "rendered"}
        )
        assert document.status_code == 200 and "Doc" in document.json()["html"]
        page = client.get("/api/file", params={"path": wires["page.html"]}).json()
        assert page["kind"] == "html" and [view["id"] for view in page["views"]] == ["source"]
        # And the folder's own block is still the process's.
        _pin(client, working_tree=True)
        assert _answered_under(client) == chosen.as_wire()
    return asked


def test_no_revision_response_is_under_active_content_with_a_trusted_process(
    checkout: Path,
) -> None:
    """A pin is never trusted: every route answers a revision without active content.

    The process's block is as trusting as it gets, as a reader's own folder may be. The
    revision is of that folder's checkout, and its commit holds a page, a document, an
    image, and a script that would each run under that block.
    """

    assert _sweep_a_hostile_revision(checkout) > 150


def test_the_sweep_sees_a_revision_answered_under_the_process_block(
    checkout: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The sweep above fails if a pin's routes take the process's block, as they once did."""

    from metabrowser.git import content_routes

    monkeypatch.setattr(content_routes, "_PIN_CAPABILITIES", DEFAULT_CAPABILITIES)
    with pytest.raises(AssertionError):
        _sweep_a_hostile_revision(checkout)


def test_raw_answers_as_a_pin_when_the_revision_arrived_after_the_request(
    served: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The profile is the subject's that the handler resolved, not what was served before.

    A request can arrive while the folder is served and be answered after a revision
    replaced it. The arrival is stood in for here: the middleware is told a folder was
    served when the request came, and the handler resolves the revision.
    """

    _pin(served, ref="feature")
    monkeypatch.setattr(server, "_pin_is_served", lambda: False)
    raw = served.get("/raw", params={"path": _wire("README.md")})
    assert raw.status_code == 200 and raw.text == "# Mirror\n"
    assert "allow-scripts" not in raw.headers["content-security-policy"]


def test_a_revision_serves_nothing_of_the_working_tree(served: TestClient) -> None:
    """No registered GET route answers a revision with what only the disk holds."""

    _pin(served, ref="feature")
    names = ("UNTRACKED.md", "STAGED.md")
    contents = (UNTRACKED_TEXT.strip(), STAGED_TEXT.strip(), "Edited in the working tree")
    asked = 0
    for route in server.app.routes:
        path = getattr(route, "path", "")
        methods = getattr(route, "methods", None) or set()
        if "GET" not in methods or "{" in path or path.startswith("/_debug"):
            continue
        # Asked for nothing, a route lists no file that is only on disk. Asked for one by
        # the folder's path, it may say the name back in its refusal, and never its bytes.
        bare = served.get(path)
        asked += 1
        assert not any(text in bare.text for text in (*names, *contents)), path
        for address in (f"{path}?path=UNTRACKED.md", f"{path}?path=STAGED.md", "/raw/README.md"):
            response = served.get(address)
            asked += 1
            assert not any(text in response.text for text in contents), address
    assert asked > 60


# ── A tab left behind ────────────────────────────────────────


def test_a_working_tree_page_is_refused_while_a_revision_is_served(served: TestClient) -> None:
    on_tree = {PIN_HEADER: WORKING_TREE_PIN}
    shell = served.get("/view/").text
    assert 'window.METABROWSER_SOURCE_CHECKOUT={"working_tree": true}' in shell
    # The guard comes with the selector's bundle, not inline: a folder's first paint
    # carries none of it.
    assert "MetabrowserSourcePinGuard" not in shell
    assert '"source-ref-selector": [{"src": "/static/source-pin-guard.js' in shell
    assert served.get("/api/tree", headers=on_tree).status_code == 200
    pinned = _pin(served, ref="feature")["status"]["pin"]
    refused = served.get("/api/tree", headers=on_tree)
    assert (refused.status_code, refused.json()["code"]) == (409, "pin_changed")
    assert refused.headers[PIN_CHANGED_HEADER] == pinned
    # The routes a page learns and switches through are exempt, and a caller that names
    # nothing, as `metab --api` and curl do, is never refused.
    assert served.get("/api/source/status", headers=on_tree).status_code == 200
    assert served.get("/api/tree").status_code == 200
    revision_shell = served.get("/view/").text
    assert 'window.METABROWSER_SOURCE_CHECKOUT={"working_tree": false}' in revision_shell
    assert "MetabrowserSourcePinGuard" in revision_shell
    assert 'data-mirror-note="committed revision of"' in revision_shell
    # And the other way: the revision's page, once the working tree is served again.
    _pin(served, working_tree=True)
    stale = served.get("/api/tree", headers={PIN_HEADER: pinned})
    assert (stale.status_code, stale.headers[PIN_CHANGED_HEADER]) == (409, "")
    assert served.get("/api/tree", headers=on_tree).status_code == 200


def test_a_page_that_names_nothing_is_refused_while_a_revision_is_served(
    served: TestClient,
) -> None:
    """The moment before a working-tree page has its guard is covered by the server.

    The page takes the guard with the selector's bundle, after its first requests. Until
    then its ``fetch`` names nothing, and a browser's own headers say it is a page's.
    """

    page_fetch = {"sec-fetch-site": "same-origin", "sec-fetch-dest": "empty"}
    assert served.get("/api/tree", headers=page_fetch).status_code == 200
    pinned = _pin(served, ref="feature")["status"]["pin"]
    refused = served.get("/api/tree", headers=page_fetch)
    assert (refused.status_code, refused.json()["code"]) == (409, "pin_changed")
    assert refused.headers[PIN_CHANGED_HEADER] == pinned
    # The pin's own page names its commit, and is answered.
    assert served.get("/api/tree", headers={**page_fetch, PIN_HEADER: pinned}).status_code == 200
    # A client that is no browser, a navigation, and an image are not a page's fetch.
    assert served.get("/api/tree").status_code == 200
    for other in (
        {"sec-fetch-site": "same-origin", "sec-fetch-dest": "image"},
        {"sec-fetch-site": "none", "sec-fetch-dest": "empty"},
    ):
        assert served.get("/api/tree", headers=other).status_code == 200, other
    # The routes a page learns and switches through stay open to it.
    assert served.get("/api/source/status", headers=page_fetch).status_code == 200
    _pin(served, working_tree=True)
    assert served.get("/api/tree", headers=page_fetch).status_code == 200


# ── The checkout is never written ────────────────────────────


def _status(checkout: Path) -> str:
    """What ``git status`` and ``HEAD`` say, read without refreshing the index."""

    env = {**git_env(checkout.parent), "GIT_OPTIONAL_LOCKS": "0"}

    def run(*args: str) -> str:
        return subprocess.run(
            ["git", "--no-optional-locks", "-C", str(checkout), *args],
            check=True,
            capture_output=True,
            text=True,
            env=env,
        ).stdout

    return "\n".join(
        (
            run("status", "--porcelain=v2", "--branch", "--untracked-files=all"),
            run("rev-parse", "HEAD"),
            run("symbolic-ref", "HEAD"),
            run("for-each-ref", "--format=%(refname) %(objectname)"),
            run("stash", "list"),
        )
    )


def test_showing_revisions_leaves_the_checkout_byte_for_byte(checkout: Path) -> None:
    said = _status(checkout)
    # The fixture is dirty in each way a careless command would show: an edit not staged,
    # a file staged and not committed, and a file on disk only.
    assert "1 .M N... 100644 100644 100644" in said and "README.md" in said
    assert "1 A. N... 000000 100644 100644" in said and "STAGED.md" in said
    assert "? UNTRACKED.md" in said
    before = snapshot(checkout)
    assert ".git/index" in before and ".git/HEAD" in before and "UNTRACKED.md" in before
    server._set_root_dir(checkout)
    with TestClient(server.app) as client:
        for kind in ("branch", "tag", "remote"):
            _refs(client, kind=kind)
        for selection in (
            {"ref": "refs/heads/feature", "view": "/view/README.md"},
            {"ref": "topic"},
            {"ref": "v1"},
            {"ref": "origin/topic"},
            {"oid": FEATURE},
            {"ref": "local-work"},
        ):
            _pin(client, **selection)
            assert client.get("/view/").status_code == 200
            tree = client.get("/api/tree", params={"depth": "2"}).json()
            for node in tree["tree"]:
                assert client.get("/api/file", params={"path": node["path"]}).status_code == 200
                assert client.get("/raw", params={"path": node["path"]}).status_code == 200
            # The revision's history and one commit's diff, which the Commits tab reads.
            assert client.get("/api/git/repo").status_code == 200
            log = client.get("/api/git/log", params={"limit": "5"})
            assert log.status_code == 200, log.text
        _pin(client, working_tree=True, view=view("README.md"))
        assert client.get("/api/file", params={"path": "README.md"}).json()["content"] == (
            EDITED_README
        )
        _pin(client, ref="feature")
        # The server stops while a revision is served.
    after = snapshot(checkout)
    changed = sorted(
        key for key in before.keys() | after.keys() if before.get(key) != after.get(key)
    )
    assert changed == []
    assert _status(checkout) == said
    # Reading the status did not write either: the comparison above ran before it.
    assert snapshot(checkout) == before


def test_the_snapshot_sees_an_index_rewritten_with_the_same_entries(checkout: Path) -> None:
    """The comparison above would catch a careless ``git status``, not only a checkout."""

    before = snapshot(checkout)
    subprocess.run(
        ["git", "-C", str(checkout), "status", "--porcelain"],
        check=True,
        capture_output=True,
        env=git_env(checkout.parent),
    )
    after = snapshot(checkout)
    # The index, replaced by rename, and the directory the lock file was made in.
    assert [key for key in before if before[key] != after.get(key)] == [".git", ".git/index"]


def test_a_linked_worktree_shows_its_repositorys_refs_and_is_not_written(
    checkout: Path, tmp_path: Path
) -> None:
    linked = tmp_path / "linked"
    git(checkout, "worktree", "add", "-q", str(linked), "feature")
    (linked / "DRAFT.md").write_text("Only in the linked worktree.\n", encoding="utf-8")
    before = (snapshot(checkout), snapshot(linked))
    server._set_root_dir(linked.resolve())
    with TestClient(server.app) as client:
        listing = _refs(client)
        # Its own HEAD's branch is the one checked out, and the refs are the repository's.
        assert listing["working_tree"]["head"] == "refs/heads/feature"
        assert _names(listing) == ["feature", "local-work", "topic"]
        assert _pin(client, ref="topic")["status"]["pin"] == SECOND
        assert _tree(client) == ["NOTES.md", "README.md"]
        _pin(client, working_tree=True)
        assert "DRAFT.md" in _live_tree(client)
    assert (snapshot(checkout), snapshot(linked)) == before


def test_a_hostile_checkout_configuration_runs_nothing_for_a_revision(
    checkout: Path, tmp_path: Path
) -> None:
    """What a revision's own reads run, with a checkout whose configuration names programs.

    The checkout's configuration is the reader's, and its Commits tab already reads it;
    this holds that listing refs, switching, and reading a revision's tree and files run
    none of the programs it names, and fetch nothing a promisor remote would.
    """

    marker = tmp_path / "marker"
    script = tmp_path / "planted.sh"
    script.write_text(f"#!/bin/sh\necho ran >> '{marker}'\n", encoding="utf-8")
    script.chmod(0o755)
    for key, value in (
        ("core.fsmonitor", str(script)),
        ("core.hooksPath", str(tmp_path)),
        ("core.sshCommand", str(script)),
        ("core.pager", str(script)),
        ("core.alternateRefsCommand", str(script)),
        ("credential.helper", f"!{script}"),
        ("uploadpack.packObjectsHook", str(script)),
        ("remote.origin.promisor", "true"),
        ("remote.origin.partialclonefilter", "blob:none"),
        ("remote.origin.url", f"ext::{script}"),
    ):
        git(checkout, "config", key, value)
    for hook in ("post-checkout", "reference-transaction", "post-index-change"):
        (tmp_path / hook).symlink_to(script)
    marker.unlink(missing_ok=True)
    before = snapshot(checkout)
    server._set_root_dir(checkout)
    with TestClient(server.app) as client:
        for kind in ("branch", "tag", "remote"):
            _refs(client, kind=kind)
        for ref in ("feature", "v1", "origin/topic"):
            _pin(client, ref=ref)
            for node in client.get("/api/tree", params={"depth": "2"}).json()["tree"]:
                assert client.get("/api/file", params={"path": node["path"]}).status_code == 200
        _pin(client, working_tree=True)
    assert not marker.exists(), marker.read_text(encoding="utf-8")
    assert snapshot(checkout) == before


@pytest.mark.parametrize(
    "selected_by", ["info/attributes", "core.attributesFile", ".gitattributes"]
)
def test_a_revisions_commit_view_runs_no_driver_and_writes_nothing(
    checkout: Path, tmp_path: Path, selected_by: str
) -> None:
    """A revision's history, commit view, and diff run no driver a checkout's configuration names.

    The store policies leave a checkout's local configuration in effect, and it can name
    a textconv driver, cached, and an external diff, which the repository's own
    ``info/attributes`` or a local ``core.attributesFile`` selects for every path. Run,
    each is a program started by a page of fetched content, and the cache is a
    ``refs/notes/textconv/`` ref written into the reader's ``.git``. Every ``diff`` and
    ``show`` at a store target says ``--no-textconv --no-ext-diff``
    (``GitLocation.diff_driver_args``), so none runs and nothing is written.
    """

    marker = tmp_path / "marker"
    script = tmp_path / "driver.sh"
    script.write_text(f"#!/bin/sh\necho ran >> '{marker}'\ncat \"$1\"\n", encoding="utf-8")
    script.chmod(0o755)
    for key, value in (
        ("diff.external", str(script)),
        ("diff.planted.textconv", str(script)),
        ("diff.planted.cachetextconv", "true"),
        ("diff.planted.command", str(script)),
    ):
        git(checkout, "config", key, value)
    if selected_by == "info/attributes":
        (checkout / ".git" / "info").mkdir(exist_ok=True)
        (checkout / ".git" / "info" / "attributes").write_text("* diff=planted\n", "utf-8")
    elif selected_by == "core.attributesFile":
        attributes = tmp_path / "attributes"
        attributes.write_text("* diff=planted\n", encoding="utf-8")
        git(checkout, "config", "core.attributesFile", str(attributes))
    else:
        (checkout / ".gitattributes").write_text("* diff=planted\n", encoding="utf-8")
    commit_view = (
        "/api/git/repo",
        "/api/git/refs",
        "/api/git/log?limit=5",
        f"/api/git/commit/{FEATURE}",
        f"/api/git/summary?rev={FEATURE}",
        f"/api/plugin/diff/comparison?revision={FEATURE}",
        f"/api/plugin/diff/comparison?revision={FEATURE}&file=FEATURE.md",
        f"/api/plugin/diff/comparison?revision={SECOND}&file=NOTES.md",
    )
    marker.unlink(missing_ok=True)
    before = snapshot(checkout)
    server._set_root_dir(checkout)
    with TestClient(server.app) as client:
        for ref in ("feature", "topic"):
            _pin(client, ref=ref)
            for address in commit_view:
                assert client.get(address).status_code == 200, address
        _pin(client, working_tree=True)
    assert not marker.exists(), marker.read_text(encoding="utf-8")
    after = snapshot(checkout)
    assert (
        sorted(key for key in before.keys() | after.keys() if before.get(key) != after.get(key))
        == []
    )
    # The fixture is live: the folder's own Commits tab honors its drivers, as before, so
    # the same diff asked of the working tree's server runs the one planted here.
    server._set_root_dir(checkout)
    with TestClient(server.app) as client:
        assert client.get(commit_view[-2]).status_code == 200
    assert marker.exists()
