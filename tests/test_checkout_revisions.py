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

import asyncio
import os
import re
import subprocess
import time
from collections.abc import Generator
from html import escape
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from starlette.testclient import TestClient

from metabrowser import checkout_revisions, server
from metabrowser.capabilities import (
    DEFAULT_CAPABILITIES,
    UNTRUSTED_CAPABILITIES,
    apply_capabilities,
    get_capabilities,
)
from metabrowser.checkout_revisions import (
    CHECKOUT_REFS_FLOOR_S,
    CHECKOUT_REFS_POLL_S,
    NOT_A_CHECKOUT,
    PARTIAL_CLONE_GIT_MINIMUM,
    CheckoutGitUnsupportedError,
    open_on_ref,
)
from metabrowser.commit_ids import short_commit
from metabrowser.git import repo as git_repo
from metabrowser.git.process import (
    GIT_NO_CONFIGURED_FORMAT_ARGS,
    GIT_NO_DRIVER_ARGS,
    GIT_NO_SIGNATURE_ARGS,
    GIT_NO_SUBMODULE_DIFF_ARGS,
    GitLocation,
    UnsupportedGitVersionError,
    detect_git_version,
    repository_store_target,
    run_git,
    run_git_at,
)
from metabrowser.settings import GIT_REPO_INFO_TTL_S
from metabrowser.source import (
    SubjectOpenError,
    attach_subject,
    get_source_session,
    subject_open_failure,
)
from metabrowser.source_routes import PIN_CHANGED_HEADER, PIN_HEADER, WORKING_TREE_PIN
from tests.required_tools import needs_git
from tests.source_checkout_fixture import (
    EDITED_README,
    STAGED_TEXT,
    UNTRACKED_TEXT,
    admit_installed_git,
    build_checkout,
    build_partial_clone,
    git,
    git_env,
    read_refs_at_every_ask,
    signed_branch,
    snapshot,
    view,
)
from tests.source_mirror_fixture import build_origin

pytestmark = [
    pytest.mark.skipif(os.name != "posix", reason="the fixture's Git environment is POSIX"),
    needs_git,
]

_JSON = {"content-type": "application/json"}
# What a page shows for a Git too old for a checkout's revisions; the release it needs
# is the answer's detail.
TOO_OLD = CheckoutGitUnsupportedError.reader_message
FIRST = "fcb9d63c3c8533d1b929861f451a066e6d4f2d9e"
SECOND = "42382ea2303b733e1e21b4bd6ddb974ca4e775eb"
FEATURE = "c7ae2a331f546e6a2431ed7093e9e430a9d1269b"


@pytest.fixture(autouse=True)
def _installed_git(monkeypatch: pytest.MonkeyPatch) -> None:  # pyright: ignore[reportUnusedFunction]
    """A checkout's revisions are read with an admitted Git; see ``admit_installed_git``."""

    admit_installed_git(monkeypatch)


@pytest.fixture(autouse=True)
def _reads_at_every_ask(monkeypatch: pytest.MonkeyPatch) -> None:  # pyright: ignore[reportUnusedFunction]
    """Each page ask here reads the refs; see ``read_refs_at_every_ask``."""

    read_refs_at_every_ask(monkeypatch)


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


def test_a_checkout_lists_its_branches_tags_and_remotes(served: TestClient, checkout: Path) -> None:
    branches = _refs(served)
    assert branches["kinds"] == ["working_tree", "branch", "remote", "tag"]
    # The working tree is what a folder opens on, and is no ref: no row is served. It is
    # named as the folder's page names it, the folder and its path, which is not under the
    # test's home directory and so is shown whole.
    assert branches["working_tree"] == {
        "current": True,
        "head": "refs/heads/topic",
        "head_name": "topic",
        "head_commit": SECOND,
        "name": "checkout",
        "location": str(checkout),
    }
    assert (branches["pin"], branches["ref"]) == (None, None)
    # The checked-out branch lists first, as a mirror's default does, and is not "current":
    # picked as a ref it shows its commit, which is not the working tree. The rest read
    # newest first: local-work's commit was made here a month after feature's.
    assert _names(branches) == ["topic", "local-work", "feature"]
    # Each row's commit and the date it was committed, read in the same for-each-ref. The
    # page shortens the ID as every line does (`shortCommit` in static/formatters.js).
    assert branches["refs"][0] == {
        "name": "topic",
        "ref": "refs/heads/topic",
        "commit": SECOND,
        "committed_at": float(git(checkout, "log", "-1", "--format=%ct", SECOND)),
        "default": False,
        "checked_out": True,
        "current": False,
    }
    assert not any(row["current"] or row["default"] for row in branches["refs"])
    tags = _refs(served, kind="tag")
    assert sorted(_names(tags)) == ["local-tag", "v1"]
    # An annotated tag is peeled to the commit it names, and has that commit's date.
    v1 = {row["name"]: row for row in tags["refs"]}["v1"]
    assert v1["commit"] == FIRST
    assert v1["committed_at"] == float(git(checkout, "log", "-1", "--format=%ct", FIRST))
    remotes = _refs(served, kind="remote")
    # A remote-tracking branch keeps its remote's name; origin/HEAD names another row.
    assert _names(remotes) == ["origin/feature", "origin/topic"]
    assert [row["ref"] for row in remotes["refs"]] == [
        "refs/remotes/origin/feature",
        "refs/remotes/origin/topic",
    ]
    assert _names(_refs(served, kind="remote", q="FEAT")) == ["origin/feature"]


def test_a_kept_listing_follows_head_to_another_branch(
    served: TestClient, checkout: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A listing names the branch ``HEAD`` is on now, however lately it moved.

    The listing reads ``HEAD`` through ``repo_info``, which keeps it for
    ``GIT_REPO_INFO_TTL_S``, while the refs' state reads it afresh. Keyed on the state
    alone, the listing made within the TTL of a switch, from the ``HEAD`` kept before it,
    was kept under the new state and served past the TTL, until some ref moved (review A
    of #614). A page now asks for a listing the moment its watch says ``HEAD`` moved, so
    the listing reads ``HEAD`` from the checkout's files too, and drops an identity they
    contradict. Here the identity cache's clock stands still, well inside the TTL.
    """

    standing = time.monotonic()
    clock = {"offset": 0.0}
    monkeypatch.setattr(
        git_repo,
        "time",
        SimpleNamespace(monotonic=lambda: standing + clock["offset"]),
    )
    git_repo.clear_repo_cache()
    assert _refs(served)["working_tree"]["head"] == "refs/heads/topic"
    git(checkout, "symbolic-ref", "HEAD", "refs/heads/feature")
    # Within the TTL, with the clock where it was: the working tree's own list, which
    # runs no Git, and the list of branches, which marks and lists first the one checked
    # out, both name the branch HEAD is on now.
    tree = _refs(served, kind="working_tree")
    assert (tree["refs"], tree["working_tree"]["head"]) == ([], "refs/heads/feature")
    after = _refs(served)
    assert after["working_tree"] == tree["working_tree"]
    assert _names(after)[0] == "feature"
    assert [row["name"] for row in after["refs"] if row["checked_out"]] == ["feature"]
    # Past the TTL it says the same.
    clock["offset"] = GIT_REPO_INFO_TTL_S + 1
    assert _refs(served) == after


def test_a_detached_head_is_on_no_branch(checkout: Path) -> None:
    git(checkout, "stash", "-q", "--include-untracked")
    git(checkout, "checkout", "-q", "--detach", FIRST)
    server._set_root_dir(checkout)
    with TestClient(server.app) as client:
        listing = _refs(client)
        refused = client.post("/api/source/pin", json={"ref": "HEAD"}, headers=_JSON)
    assert listing["working_tree"] == {
        "current": True,
        "head": None,
        "head_name": None,
        "head_commit": FIRST,
        "name": "checkout",
        "location": str(checkout),
    }
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


def test_a_revision_of_a_checkout_keeps_the_mark_and_the_repository_the_route_names(
    checkout: Path,
) -> None:
    """The shell's mark and `/api/identity` say the same on the working tree and on a revision.

    A revision has no mirror session, so the page's own repository context is empty for it;
    the sentence still names the repository the checkout's `origin` is on github.com.
    """

    git(checkout, "remote", "set-url", "origin", "git@github.com:Octo/Demo.git")
    server._set_root_dir(checkout)
    tip = "Local Git checkout (GitHub: Octo/Demo)"
    with TestClient(server.app) as client:
        for shown in ("working tree", "revision"):
            if shown == "revision":
                _pin(client, ref="refs/heads/feature", view="/view/README.md")
            identity = client.get("/api/identity").json()
            assert (identity["kind"], identity["kind_tip"]) == ("git", tip), shown
            for address in ("/view/", "/pulls", "/commit/0123456789abcdef"):
                page = client.get(address).text
                assert 'data-root-kind="git"' in page, (shown, address)
                assert f'data-tip-text="{tip}"' in page, (shown, address)


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
    # The kind is still how the root was opened: a checkout, whichever revision it shows.
    identity = served.get("/api/identity").json()
    assert (identity["kind"], identity["short_name"]) == ("git", "checkout")
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


_SELECTOR_ROW = re.compile(r'<div class="source-ref-selector" id="source-ref-selector".*?</div>')


def _selector_row(client: TestClient) -> str:
    """The revision row the server draws at first paint, before the selector mounts."""

    found = _SELECTOR_ROW.search(client.get("/view/").text)
    assert found is not None
    return found.group(0)


def test_the_row_tells_the_working_tree_from_the_checked_out_branchs_revision(
    served: TestClient, checkout: Path
) -> None:
    """The working tree and its branch's own revision never read the same (mb-cxpq).

    Both name the branch topic, so the working tree's row says "Working tree" first, and
    the revision's names the branch alone. The row is otherwise the same on both: its
    label and the chooser's button, and nothing else, so it is one shape whatever the
    page shows. ``tests/golden/cli-ui-source-ref-selector.tryscript.md`` pins what the
    mounted selector then paints from the same attributes.
    """

    def shape(row: str) -> list[str]:
        """The row's elements outside its label: what could move it."""

        outside = re.sub(
            r'<span class="source-ref-selector-label">.*?</span>(?=<button)', "", row, flags=re.S
        )
        return re.findall(r"<(\w+)[^>]*? class=\"([^\"]+)\"", outside)

    tree = _selector_row(served)
    assert ' data-working-branch="topic"' in tree
    assert f' data-working-commit="{SECOND}">' in tree
    assert 'data-source-mode="working-tree"' in tree
    assert f'data-source-path="{escape(str(checkout.resolve()))}"' in tree
    assert (
        '<span class="source-ref-selector-label"><span class="source-ref-selector-view">'
        'Working tree</span><span class="source-ref-selector-sep" aria-hidden="true"> · </span>'
        '<span class="git-ref git-ref-local"><span class="git-ref-label">topic</span></span>'
        "</span>"
    ) in tree
    _pin(served, ref="refs/heads/topic")
    revision = _selector_row(served)
    assert "data-working-" not in revision
    assert 'data-source-mode="checkout-revision"' in revision
    assert f'data-source-path="{escape(str(checkout.resolve()))}"' in revision
    assert "data-source-synced-at" not in revision
    assert (
        '<span class="source-ref-selector-label">'
        '<span class="git-ref git-ref-local"><span class="git-ref-label">topic</span></span>'
        "</span>"
    ) in revision
    assert revision != tree and shape(revision) == shape(tree)
    assert len(shape(tree)) == 3, "the row, its button's host, and the chooser's button"
    _pin(served, working_tree=True)
    assert _selector_row(served) == tree
    # A detached HEAD's working tree names its commit, in the commit-ID face.
    git(checkout, "checkout", "-q", "--detach", "topic")
    detached = _selector_row(served)
    assert f' data-working-commit="{SECOND}">' in detached
    assert (
        'Working tree</span><span class="source-ref-selector-sep" aria-hidden="true"> · </span>'
        f'<span class="git-commit-sha">{short_commit(SECOND)}</span></span>'
    ) in detached
    assert shape(detached) == shape(tree)


def test_a_github_checkouts_row_names_its_head_from_the_pages_repository_context(
    checkout: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A checkout whose origin is on github.com has a repository context, read for the page,
    which already holds its ``HEAD``: the row names the branch or commit from it, and the
    server does not read ``HEAD`` a second time."""

    git(checkout, "remote", "set-url", "origin", "git@github.com:Octo/Demo.git")
    server._set_root_dir(checkout)

    def read_again(root: Path) -> None:
        raise AssertionError(f"HEAD of {root} was read again")

    monkeypatch.setattr(server, "checked_out_head", read_again)
    with TestClient(server.app) as client:
        tree = _selector_row(client)
        assert ' data-working-branch="topic"' in tree
        assert f' data-working-commit="{SECOND}">' in tree
        assert '<span class="git-ref-label">topic</span>' in tree
        git(checkout, "checkout", "-q", "--detach", "topic")
        detached = _selector_row(client)
        assert f' data-working-commit="{SECOND}">' in detached
        assert f'<span class="git-commit-sha">{short_commit(SECOND)}</span>' in detached


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
    local = next(row for row in _refs(served)["refs"] if row["name"] == "local-work")
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


def _page_ask(client: TestClient) -> dict[str, Any]:
    """A visible page's own ask, which reads where the served ref is in the checkout."""

    response = client.post("/api/source/refresh", json={"for": "page"}, headers=_JSON)
    assert response.status_code == 200, response.text
    return response.json()


def test_a_branch_follows_the_checkout_when_the_reader_commits(
    served: TestClient, checkout: Path
) -> None:
    """A page on a branch reads that branch, not one commit of it: when the reader's
    commit moves it, the server serves the new commit, and the page's address is found
    there, or the root when the new commit lacks it."""

    answer = _pin(served, ref="refs/heads/feature", view="/view/FEATURE.md")
    status = answer["status"]
    assert (status["pin"], status["follows"], status["latest"]) == (FEATURE, True, FEATURE)
    assert status["probe_every_s"] == CHECKOUT_REFS_POLL_S
    # Nothing is fetched into a checkout, so nothing is refreshable; the ask is a read.
    assert status["refreshable"] is False
    asked = _page_ask(served)
    assert (asked["refresh"], asked["status"]["pin"]) == ("probed", FEATURE)
    assert asked["status"]["generation"] == status["generation"]

    # A commit on the branch, as `git commit` there makes one: the ref names a new commit.
    git(checkout, "branch", "-f", "feature", "local-work")
    local_work = git(checkout, "rev-parse", "local-work")
    moved = _page_ask(served)["status"]
    assert (moved["pin"], moved["ref"], moved["latest"]) == (
        local_work,
        "refs/heads/feature",
        local_work,
    )
    assert moved["generation"] > status["generation"] and moved["follows"] is True
    assert _tree(served) == ["LOCAL.md", "NOTES.md", "README.md"]
    # The page asks the pin route for its ref with its own address, as a mirror's does:
    # nothing changes, and the answer says where the page is on the new commit.
    kept = _pin(served, ref="refs/heads/feature", view=view("README.md"))
    assert (kept["changed"], kept["view_href"]) == (False, view("README.md"))
    gone = _pin(served, ref="refs/heads/feature", view=view("FEATURE.md"))
    assert (gone["changed"], gone["view_href"]) == (False, "/view/")
    # The status route reads nothing: it reports what the ask found.
    assert served.get("/api/source/status").json()["pin"] == local_work


def test_a_remote_tracking_branch_and_a_tag_follow_the_readers_own_fetch(
    served: TestClient, checkout: Path
) -> None:
    """`origin/feature` is where the reader's last fetch left it, and moves when theirs
    does; Metabrowser fetches nothing into the checkout to move it."""

    remote = _pin(served, ref="refs/remotes/origin/feature")["status"]
    assert (remote["pin"], remote["follows"]) == (FEATURE, True)
    # What `git fetch` does to a remote-tracking ref, without a network.
    git(checkout, "update-ref", "refs/remotes/origin/feature", SECOND)
    assert _page_ask(served)["status"]["pin"] == SECOND
    tag = _pin(served, ref="refs/tags/local-tag")["status"]
    assert (tag["pin"], tag["follows"]) == (FEATURE, True)
    git(checkout, "tag", "-f", "local-tag", SECOND)
    assert _page_ask(served)["status"]["pin"] == SECOND


def test_a_commit_id_and_the_working_tree_never_move(served: TestClient, checkout: Path) -> None:
    """What the reader opened decides whether the view moves: a commit stays that commit
    and the working tree is the files on disk, so neither is asked about."""

    status = _pin(served, oid=FEATURE)["status"]
    assert (status["pin"], status["ref"]) == (FEATURE, None)
    assert (status["follows"], status["probe_every_s"], status["latest"]) == (False, None, None)
    git(checkout, "branch", "-f", "feature", "local-work")
    # No store and nothing that follows: the ask is refused as a folder's refresh is.
    refused = served.post("/api/source/refresh", json={"for": "page"}, headers=_JSON)
    assert (refused.status_code, refused.json()["code"]) == (409, "unsupported_for_subject")
    assert served.get("/api/source/status").json()["pin"] == FEATURE
    back = _pin(served, working_tree=True)["status"]
    assert (back["follows"], back["probe_every_s"], back["pin"]) == (False, None, None)
    refused = served.post("/api/source/refresh", json={"for": "page"}, headers=_JSON)
    assert refused.status_code == 409


def test_a_commit_opened_by_its_id_at_a_branchs_tip_stays_that_commit(
    served: TestClient, checkout: Path
) -> None:
    """A commit opened by its ID while it is the tip of the branch the page was on is
    served under that branch, so the selector still names it, and never follows it: only
    a selection that names a ref does. Choosing the branch again makes it follow."""

    _pin(served, ref="refs/heads/feature")
    by_id = _pin(served, oid=FEATURE)
    assert by_id["changed"] is False
    status = by_id["status"]
    assert (status["pin"], status["ref"]) == (FEATURE, "refs/heads/feature")
    assert (status["follows"], status["probe_every_s"], status["latest"]) == (False, None, None)
    git(checkout, "branch", "-f", "feature", "local-work")
    local_work = git(checkout, "rev-parse", "local-work")
    # Nothing that follows is served, and with no store there is nothing else to ask.
    refused = served.post("/api/source/refresh", json={"for": "page"}, headers=_JSON)
    assert (refused.status_code, refused.json()["code"]) == (409, "unsupported_for_subject")
    assert served.get("/api/source/status").json()["pin"] == FEATURE

    # Chosen by its name, the branch is served at its tip and follows from there.
    named = _pin(served, ref="refs/heads/feature")
    assert named["changed"] is True
    assert (named["status"]["pin"], named["status"]["follows"]) == (local_work, True)
    # Opened by ID while it is the very revision served, it stops following; named again
    # while the branch has not moved, it follows again. Neither changes what is served.
    still = _pin(served, oid=local_work)
    assert (still["changed"], still["status"]["follows"]) == (False, False)
    again = _pin(served, ref="refs/heads/feature")
    assert (again["changed"], again["status"]["follows"]) == (False, True)
    assert again["status"]["latest"] == local_work
    git(checkout, "branch", "-f", "feature", FEATURE)
    assert _page_ask(served)["status"]["pin"] == FEATURE


def test_a_commit_opened_by_its_id_under_a_named_ref_follows_it(
    served: TestClient, checkout: Path
) -> None:
    """A selection that names the ref a commit is served under, as View on branch's does
    with ``under``, names a ref, so the pin follows it."""

    under = _pin(served, oid=FEATURE, under="refs/heads/feature")["status"]
    assert (under["pin"], under["ref"], under["follows"]) == (FEATURE, "refs/heads/feature", True)
    git(checkout, "branch", "-f", "feature", "local-work")
    assert _page_ask(served)["status"]["pin"] == git(checkout, "rev-parse", "local-work")


def test_following_reads_the_ref_only_when_the_checkouts_refs_changed(
    served: TestClient, checkout: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The ask names the checkout's ref state from the filesystem; Git reads the ref
    only when that state is not the one it was last read under."""

    from metabrowser.cache import resolve

    read: list[str] = []
    ref_tip = resolve.ref_tip

    async def counted(target: Any, ref: str) -> str | None:
        read.append(ref)
        return await ref_tip(target, ref)

    _pin(served, ref="refs/heads/feature")
    monkeypatch.setattr(resolve, "ref_tip", counted)
    for _ask in range(3):
        assert _page_ask(served)["status"]["pin"] == FEATURE
    assert read == []
    # Another ref moved: the state changed, the served ref is read, and it is where it was.
    git(checkout, "update-ref", "refs/heads/other", SECOND)
    assert _page_ask(served)["status"]["pin"] == FEATURE
    assert read == ["refs/heads/feature"]
    assert _page_ask(served)["status"]["pin"] == FEATURE
    assert read == ["refs/heads/feature"]


def test_a_branch_the_reader_deleted_keeps_its_last_commit_served(
    served: TestClient, checkout: Path
) -> None:
    _pin(served, ref="refs/heads/feature")
    git(checkout, "branch", "-D", "feature")
    status = _page_ask(served)["status"]
    assert (status["pin"], status["ref"], status["latest"]) == (FEATURE, "refs/heads/feature", None)
    assert _tree(served) == ["FEATURE.md", "README.md"]


class _Clock:
    """The monotonic clock the floor between two readings is kept on, moved by the test."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


class _CountedLock:
    """A switch's lock that counts how often it is taken."""

    def __init__(self, lock: asyncio.Lock) -> None:
        self._lock = lock
        self.taken = 0

    async def __aenter__(self) -> None:
        self.taken += 1
        await self._lock.acquire()

    async def __aexit__(self, *_exc: object) -> None:
        self._lock.release()


def _counted(monkeypatch: pytest.MonkeyPatch, module: Any, name: str) -> list[str]:
    """Each call of *module*'s async *name*, by its last argument, in order."""

    calls: list[str] = []
    real = getattr(module, name)

    async def counted(*args: Any) -> Any:
        calls.append(str(args[-1]))
        return await real(*args)

    monkeypatch.setattr(module, name, counted)
    return calls


def test_an_ask_whose_refs_did_not_move_takes_no_switch_lock(
    served: TestClient, checkout: Path
) -> None:
    """An ask names the ref state before taking the locks a switch is made under, and
    takes them only when it changed, so it waits for no switch and holds none up."""

    _pin(served, ref="refs/heads/feature")
    revisions = checkout_revisions.checkout_revisions()
    assert revisions is not None
    lock = _CountedLock(revisions._switching)
    revisions._switching = lock  # type: ignore[assignment]
    for _ask in range(3):
        assert _page_ask(served)["status"]["pin"] == FEATURE
    assert lock.taken == 0
    git(checkout, "branch", "-f", "feature", "local-work")
    assert _page_ask(served)["status"]["pin"] == git(checkout, "rev-parse", "local-work")
    assert lock.taken == 1


def test_asks_inside_the_floor_are_answered_from_memory(
    served: TestClient, checkout: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """However many visible pages ask, the refs are read at most once a floor: an ask
    under half an interval after the last reading reads nothing, and the next is read."""

    from metabrowser.git import ref_state

    monkeypatch.setattr(checkout_revisions, "CHECKOUT_REFS_FLOOR_S", CHECKOUT_REFS_FLOOR_S)
    clock = _Clock()
    monkeypatch.setattr(checkout_revisions, "_monotonic", clock)
    # The switch reads the ref, which is a reading.
    _pin(served, ref="refs/heads/feature")
    named = _counted(monkeypatch, ref_state, "ref_state")
    git(checkout, "branch", "-f", "feature", "local-work")
    clock.now += CHECKOUT_REFS_FLOOR_S - 0.1
    early = _page_ask(served)
    assert (early["refresh"], early["status"]["pin"]) == ("probed", FEATURE)
    assert named == []
    clock.now += 0.1
    assert _page_ask(served)["status"]["pin"] == git(checkout, "rev-parse", "local-work")
    assert len(named) == 1
    # A second page asking at once is answered by that reading.
    assert _page_ask(served)["status"]["pin"] == git(checkout, "rev-parse", "local-work")
    assert len(named) == 1


def test_a_ref_that_cannot_be_read_is_warned_of_once_a_streak(
    served: TestClient,
    checkout: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A reading that keeps failing, as when the Git directory is removed under an open
    page, warns once, and again only after a reading has succeeded."""

    from metabrowser.cache import resolve
    from metabrowser.git.process import GitCommandError

    real = resolve.ref_tip
    failing = [True]

    async def ref_tip(target: Any, ref: str) -> str | None:
        if failing[0]:
            raise GitCommandError(["for-each-ref"], 128, "fatal: not a git repository")
        return await real(target, ref)

    _pin(served, ref="refs/heads/feature")
    monkeypatch.setattr(resolve, "ref_tip", ref_tip)

    def warned() -> int:
        return sum(
            1
            for record in caplog.records
            if record.levelname == "WARNING" and "could not be read" in record.getMessage()
        )

    caplog.set_level("DEBUG", logger="metabrowser.checkout_revisions")
    for number in range(3):
        # Each ask finds the refs changed, so each reads the ref, and each reading fails.
        git(checkout, "update-ref", f"refs/heads/other-{number}", SECOND)
        assert _page_ask(served)["status"]["pin"] == FEATURE
    assert warned() == 1
    failing[0] = False
    git(checkout, "update-ref", "refs/heads/other-read", SECOND)
    assert _page_ask(served)["status"]["pin"] == FEATURE
    failing[0] = True
    git(checkout, "update-ref", "refs/heads/other-again", SECOND)
    assert _page_ask(served)["status"]["pin"] == FEATURE
    assert warned() == 2


def test_a_followed_revision_is_the_checkouts_before_it_is_attached(
    served: TestClient, checkout: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The follow records the new revision as this checkout's before attaching it, as a
    switch does, so no request can find it served and not the checkout's."""

    from metabrowser import mirror_refresh

    _pin(served, ref="refs/heads/feature")
    revisions = checkout_revisions.checkout_revisions()
    assert revisions is not None
    real = mirror_refresh.replace_owned_subject
    seen: list[bool] = []

    async def replace(subject: Any) -> Any:
        seen.append(revisions.serves(subject))
        return await real(subject)

    monkeypatch.setattr(mirror_refresh, "replace_owned_subject", replace)
    git(checkout, "branch", "-f", "feature", "local-work")
    assert _page_ask(served)["status"]["pin"] == git(checkout, "rev-parse", "local-work")
    assert seen == [True]


def test_following_a_branch_writes_nothing_into_the_checkout(checkout: Path) -> None:
    """The move is read from the refs: after the reader's own commit, an ask, the follow,
    and the new commit's files leave every entry under the checkout as it was."""

    server._set_root_dir(checkout)
    with TestClient(server.app) as client:
        _pin(client, ref="refs/heads/feature")
        _page_ask(client)
        git(checkout, "branch", "-f", "feature", "local-work")
        before = snapshot(checkout)
        assert _page_ask(client)["status"]["pin"] == git(checkout, "rev-parse", "local-work")
        for node in client.get("/api/tree", params={"depth": "2"}).json()["tree"]:
            assert client.get("/api/file", params={"path": node["path"]}).status_code == 200
        _page_ask(client)
        after = snapshot(checkout)
    changed = sorted(
        key for key in before.keys() | after.keys() if before.get(key) != after.get(key)
    )
    assert changed == []
    assert snapshot(checkout) == before


def test_the_commits_tab_shows_the_revision_the_files_tab_shows(
    checkout: Path, served: TestClient
) -> None:
    """One choice for both tabs: the history is the served revision's, as the files are.

    On the working tree it walks the checkout's ``HEAD``, its upstream, and its trunk
    refs. On a branch, tag, remote-tracking branch, or commit it is that commit's own
    history, Git's walk from the commit the Files tab shows, which is its first row. Back
    on the working tree, every answer is what it was.
    """

    routes = (
        "/api/git/repo",
        "/api/git/refs",
        "/api/git/summary",
        "/api/git/summary?scope=all",
        "/api/git/log?limit=50",
        "/api/git/log?limit=50&scope=all",
    )

    def answers() -> dict[str, Any]:
        replies = {route: served.get(route) for route in routes}
        assert all(reply.status_code == 200 for reply in replies.values()), replies
        return {route: reply.json() for route, reply in replies.items()}

    def walked(answer: dict[str, Any]) -> list[str]:
        return [commit["id"] for commit in answer["/api/git/log?limit=50"]["commits"]]

    on_the_folder = answers()
    assert on_the_folder["/api/git/repo"]["head"]["ref"] == "refs/heads/topic"
    assert walked(on_the_folder)[0] == git(checkout, "rev-parse", "HEAD")
    for selection in ({"ref": "feature"}, {"ref": "v1"}, {"ref": "origin/topic"}, {"oid": FIRST}):
        shown = _pin(served, **selection)["status"]["pin"]
        on_revision = answers()
        assert on_revision["/api/git/repo"]["head"]["revision"] == shown, selection
        history = git(checkout, "rev-list", "--date-order", shown).split()
        assert walked(on_revision) == history, selection
        assert on_revision["/api/git/summary"]["commit_count"] == len(history), selection
    _pin(served, working_tree=True)
    assert answers() == on_the_folder


def test_an_address_crosses_between_the_folder_and_a_revision(served: TestClient) -> None:
    # NOTES.md is on topic and not on feature: the page goes to the root there.
    assert _pin(served, ref="feature", view="/view/NOTES.md")["view_href"] == "/view/"
    # A folder's address, kept by a tab or a history entry, is sent where a switch would
    # send it: to the same names in the revision, or to its root.
    kept = served.get("/view/README.md", follow_redirects=False)
    assert (kept.status_code, kept.headers["location"]) == (307, view("README.md"))
    gone = served.get("/view/NOTES.md", follow_redirects=False)
    assert (gone.status_code, gone.headers["location"]) == (307, "/view/")
    # Back on the working tree, a revision's address goes to the folder's entry, or to its
    # root when the folder has none by those names. A name that only begins as a wire
    # does is the folder's own missing path, and a file really so named is served.
    assert _pin(served, working_tree=True, view=view("FEATURE.md"))["view_href"] == "/view/"
    crossed = served.get(view("README.md"), follow_redirects=False)
    assert (crossed.status_code, crossed.headers["location"]) == (307, "/view/README.md")
    absent = served.get(view("FEATURE.md"), follow_redirects=False)
    assert (absent.status_code, absent.headers["location"]) == (307, "/view/")
    assert served.get("/view/g1-not_a_wire!", follow_redirects=False).status_code == 200


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
    # So are the event log's, which are about the server whichever revision it shows: a
    # page left behind still reports what it saw, and its Details read the log (A4, review
    # A of #629). Without a log they answer that, never that the pin changed.
    report = {"page": "k3v9q2zx", "reports": [], "dropped": 0}
    for answer in (
        served.get("/api/event-log", headers=on_tree),
        served.get("/api/event-log/failures", headers=on_tree),
        served.post("/api/event-log/client", json=report, headers={**_JSON, **on_tree}),
    ):
        assert PIN_CHANGED_HEADER not in answer.headers, answer.text
        assert answer.status_code in {200, 409}, answer.text
        assert answer.json().get("code") != "pin_changed", answer.text
    assert served.get("/api/event-logs", headers=on_tree).status_code == 409
    revision_shell = served.get("/view/").text
    assert 'window.METABROWSER_SOURCE_CHECKOUT={"working_tree": false}' in revision_shell
    assert "MetabrowserSourcePinGuard" in revision_shell
    assert 'data-mirror-note="committed revision of"' in revision_shell
    # The root menu describes the pinned source beside its local checkout path.
    assert 'data-mirror-tip="Files come from a committed revision of this checkout."' in (
        revision_shell
    )
    assert "window.MetabrowserMirrorHeading" in revision_shell
    assert "window.MetabrowserMirrorHeading" not in shell
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


def test_a_commits_tab_left_behind_is_refused_as_files_is(served: TestClient) -> None:
    """A switch made in another tab is a reload for this page's Commits tab too.

    Its history is the revision the page was drawn for, so once another is served, the
    guard refuses its history and its commits as it refuses its tree, for the working
    tree's page and a revision's, and for a page whose guard has not arrived. The page's
    freshness row then offers the reload on every tab.
    """

    page_fetch = {"sec-fetch-site": "same-origin", "sec-fetch-dest": "empty"}
    routes = (
        "/api/tree",
        "/api/git/repo",
        "/api/git/refs",
        "/api/git/summary",
        "/api/git/log?limit=5",
        "/api/git/log?limit=5&scope=all",
        f"/api/git/commit/{FIRST}",
    )
    on_tree = {**page_fetch, PIN_HEADER: WORKING_TREE_PIN}
    for route in routes:
        assert served.get(route, headers=on_tree).status_code == 200, route
    pinned = _pin(served, ref="feature")["status"]["pin"]
    on_revision = {**page_fetch, PIN_HEADER: pinned}
    for headers in (on_tree, page_fetch):
        for route in routes:
            reply = served.get(route, headers=headers)
            assert (reply.status_code, reply.json()["code"]) == (409, "pin_changed"), route
            assert reply.headers[PIN_CHANGED_HEADER] == pinned, route
    for route in routes:
        assert served.get(route, headers=on_revision).status_code == 200, route
    # And the revision's page, once another tab has gone back to the working tree.
    _pin(served, working_tree=True)
    for route in routes:
        reply = served.get(route, headers=on_revision)
        assert (reply.status_code, reply.headers[PIN_CHANGED_HEADER]) == (409, ""), route


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

    # ``git status`` rewrites the index only when it has stat data to refresh, so a bare
    # run sometimes leaves it alone (a run on main did, mb-c8hi). Give it some: a tracked
    # file's modification time moves with its bytes unchanged, which Git finds out of date
    # with the index and refreshes, deterministically. The file is touched before the
    # snapshot, so what differs after is only what ``git status`` wrote.
    tracked = checkout / "STAGED.md"
    later = tracked.stat().st_mtime_ns + 5_000_000_000
    os.utime(tracked, ns=(later, later))
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


# The reads that honor a repository's configuration: the Commits tab's history, a commit's
# view, and its diffs, whole and one file. While a revision is served, each is read at its
# store target (`session_git_location` in git/routes.py), under the store policies.
def _commit_views(*commits: str) -> tuple[str, ...]:
    views = [
        "/api/git/repo",
        "/api/git/refs",
        "/api/git/log?limit=5",
        "/api/git/log?limit=5&scope=all",
    ]
    for commit in commits:
        views += [
            f"/api/git/commit/{commit}",
            f"/api/git/summary?rev={commit}",
            f"/api/plugin/diff/comparison?revision={commit}",
        ]
    return tuple(views)


def _plant(
    checkout: Path, tmp_path: Path, *, selected_by: str = "info/attributes"
) -> dict[str, Path]:
    """Give *checkout* a configuration that names a program for everything Git can run.

    Each program leaves its own marker, so a test says which ran: a diff driver (external,
    textconv with its cache, and per-driver command, selected for every path the way
    *selected_by* says), a signature program for each format with ``log.showSignature``,
    and the rest (fsmonitor, hooks, pager, ssh, credential and upload-pack helpers).
    """

    markers = {name: tmp_path / f"ran-{name}" for name in ("driver", "signature", "other")}
    scripts: dict[str, Path] = {}
    for name, marker in markers.items():
        script = tmp_path / f"{name}.sh"
        body = 'cat "$1" 2>/dev/null\n' if name == "driver" else ""
        script.write_text(f"#!/bin/sh\necho ran >> '{marker}'\n{body}", encoding="utf-8")
        script.chmod(0o755)
        scripts[name] = script
    settings = [
        ("diff.external", scripts["driver"]),
        ("diff.planted.textconv", scripts["driver"]),
        ("diff.planted.cachetextconv", "true"),
        ("diff.planted.command", scripts["driver"]),
        ("log.showSignature", "true"),
        ("gpg.program", scripts["signature"]),
        ("gpg.ssh.program", scripts["signature"]),
        ("gpg.x509.program", scripts["signature"]),
        ("core.fsmonitor", scripts["other"]),
        ("core.hooksPath", tmp_path),
        ("core.sshCommand", scripts["other"]),
        ("core.pager", scripts["other"]),
        ("core.alternateRefsCommand", scripts["other"]),
        ("credential.helper", f"!{scripts['other']}"),
        ("uploadpack.packObjectsHook", scripts["other"]),
    ]
    for key, value in settings:
        git(checkout, "config", key, str(value))
    for hook in ("post-checkout", "reference-transaction", "post-index-change"):
        (tmp_path / hook).unlink(missing_ok=True)
        (tmp_path / hook).symlink_to(scripts["other"])
    common = Path(git(checkout, "rev-parse", "--path-format=absolute", "--git-common-dir"))
    if selected_by == "info/attributes":
        (common / "info").mkdir(exist_ok=True)
        (common / "info" / "attributes").write_text("* diff=planted\n", encoding="utf-8")
    elif selected_by == "core.attributesFile":
        attributes = tmp_path / "attributes"
        attributes.write_text("* diff=planted\n", encoding="utf-8")
        git(checkout, "config", "core.attributesFile", str(attributes))
    else:
        (checkout / ".gitattributes").write_text("* diff=planted\n", encoding="utf-8")
    for marker in markers.values():
        marker.unlink(missing_ok=True)
    return markers


def _differing(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    return sorted(key for key in before.keys() | after.keys() if before.get(key) != after.get(key))


def _read_revisions(client: TestClient, refs: tuple[str, ...], views: tuple[str, ...]) -> None:
    """Show each of *refs* and read its tree, its files, and each of *views*."""

    for kind in ("branch", "tag", "remote"):
        _refs(client, kind=kind)
    for ref in refs:
        _pin(client, ref=ref)
        for node in client.get("/api/tree", params={"depth": "2"}).json()["tree"]:
            assert client.get("/api/file", params={"path": node["path"]}).status_code == 200
            assert client.get("/raw", params={"path": node["path"]}).status_code == 200
        for address in views:
            assert client.get(address).status_code == 200, (ref, address)
    _pin(client, working_tree=True)


@pytest.mark.parametrize(
    "selected_by", ["info/attributes", "core.attributesFile", ".gitattributes"]
)
def test_a_hostile_checkout_configuration_runs_nothing_for_a_revision(
    checkout: Path, tmp_path: Path, selected_by: str
) -> None:
    """No program a checkout's configuration names runs for a revision, and nothing is written.

    The store policies leave a checkout's local configuration in effect. It can name a
    diff driver, cached, which would run for a commit's view and write a
    ``refs/notes/textconv/`` ref into the reader's ``.git``, and a signature program,
    which would run for every signed commit of a history and, by what it prints, take
    that commit out of it. Every ``diff`` and ``show`` at a store target says
    ``--no-textconv --no-ext-diff``, and every command says ``log.showSignature=false``
    (``git/process.py``). So across a revision's files, its commit views, and its diffs,
    and the Commits tab beside it, which is the revision's history read at the same store
    target: no marker, the signed commit is in the history and opens, and every entry
    under the checkout is what it was.
    """

    signed = signed_branch(checkout)
    markers = _plant(checkout, tmp_path, selected_by=selected_by)
    views = _commit_views(FEATURE, SECOND, signed)
    before = snapshot(checkout)
    server._set_root_dir(checkout)
    with TestClient(server.app) as client:
        _read_revisions(client, ("feature", "topic", "signed", "v1", "origin/topic"), views)
        _pin(client, ref="signed")
        # The Commits tab shows the revision the Files tab shows: its history starts at the
        # signed commit, which a signature program's lines would have taken out of it, and
        # every ref's walk has it too.
        log = client.get("/api/git/log", params={"limit": "5"}).json()
        assert log["commits"][0]["id"] == signed
        every = client.get("/api/git/log", params={"limit": "50", "scope": "all"}).json()
        assert signed in [commit["id"] for commit in every["commits"]]
        assert client.get(f"/api/git/commit/{signed}").json()["commit"]["id"] == signed
        _pin(client, working_tree=True)
    assert [name for name, marker in markers.items() if marker.exists()] == []
    assert _differing(before, snapshot(checkout)) == []
    # The fixture is live. The folder's own Commits tab honors its diff drivers, as
    # before, so the same diff asked of the working tree's server runs the one planted.
    # It verifies no signature either: that option is on every command, a folder's too,
    # where a signature program's lines took a signed commit out of the history.
    server._set_root_dir(checkout)
    with TestClient(server.app) as client:
        for address in _commit_views(signed):
            assert client.get(address).status_code == 200, address
        assert client.get(f"/api/git/commit/{signed}").json()["commit"]["id"] == signed
    assert markers["driver"].exists()
    assert not markers["signature"].exists()
    # And the signature program is live: Git asked without the option runs it.
    assert git(checkout, "log", "-1", "--format=%H", signed) == signed
    assert markers["signature"].exists()


def test_a_linked_worktree_shows_its_repositorys_refs_and_neither_is_written(
    checkout: Path, tmp_path: Path
) -> None:
    """The three places differ here: the worktree, its Git directory, and the common one.

    The worktree's refs and objects are its main repository's, so the driver's cache
    would be written there. With the hostile configuration planted, a revision's files,
    history, commit views, and diffs leave the worktree and the main repository, each
    with its ``.git``, as they were, and run nothing.
    """

    linked = tmp_path / "linked"
    git(checkout, "worktree", "add", "-q", str(linked), "feature")
    (linked / "DRAFT.md").write_text("Only in the linked worktree.\n", encoding="utf-8")
    markers = _plant(linked, tmp_path)
    before = (snapshot(checkout), snapshot(linked))
    server._set_root_dir(linked.resolve())
    with TestClient(server.app) as client:
        listing = _refs(client)
        # Its own HEAD's branch is the one checked out, and the refs are the repository's.
        assert listing["working_tree"]["head"] == "refs/heads/feature"
        assert _names(listing) == ["feature", "local-work", "topic"]
        assert _pin(client, ref="topic")["status"]["pin"] == SECOND
        assert _tree(client) == ["NOTES.md", "README.md"]
        _read_revisions(client, ("topic", "feature", "v1"), _commit_views(FEATURE, SECOND))
        assert "DRAFT.md" in _live_tree(client)
    assert [name for name, marker in markers.items() if marker.exists()] == []
    after = (snapshot(checkout), snapshot(linked))
    assert (_differing(before[0], after[0]), _differing(before[1], after[1])) == ([], [])


def _superproject(tmp_path: Path) -> tuple[Path, Path]:
    """A superproject on ``main`` whose submodule ``sub`` is the fixture origin on ``topic``."""

    origin = build_origin(tmp_path)
    superproject = tmp_path / "super"
    env = git_env(tmp_path)
    subprocess.run(
        ["git", "init", "-q", "--template=", "-b", "main", str(superproject)], check=True, env=env
    )
    subprocess.run(
        [
            *("git", "-C", str(superproject), "-c", "protocol.file.allow=always"),
            *("submodule", "add", "-q", str(origin), "sub"),
        ],
        check=True,
        capture_output=True,
        env=env,
    )
    git(superproject, "commit", "-q", "-m", "add sub")
    module = (superproject / "sub").resolve()
    assert (module / ".git").is_file()
    return superproject.resolve(), module


def test_a_submodule_served_as_the_root_is_read_from_its_own_git_directory(
    tmp_path: Path,
) -> None:
    """A submodule's Git directory is under its superproject's, and neither is written."""

    superproject, module = _superproject(tmp_path)
    markers = _plant(module, tmp_path)
    before = snapshot(superproject)
    server._set_root_dir(module)
    with TestClient(server.app) as client:
        assert _refs(client)["working_tree"]["head"] == "refs/heads/topic"
        _read_revisions(client, ("origin/feature", "v1"), _commit_views(FEATURE))
    assert [name for name, marker in markers.items() if marker.exists()] == []
    assert _differing(before, snapshot(superproject)) == []


def test_a_superprojects_comparison_runs_no_driver_of_its_submodule(tmp_path: Path) -> None:
    """A moved submodule is diffed by name only, so its own drivers never run.

    With ``diff.submodule=diff`` in the superproject's configuration, ``git diff -p`` diffs
    a changed submodule in a child ``git diff`` in the submodule's Git directory, with
    that directory's configuration and ``info/attributes``; ``--no-textconv`` and
    ``--no-ext-diff`` stay with the parent. The submodule's driver ran for a revision's
    comparison, and its cache wrote ``refs/notes/textconv/`` under ``.git/modules/sub``
    (review B1 on #559). Every read at a store target says ``diff.submodule=short``.
    """

    superproject, module = _superproject(tmp_path)
    # A branch whose one commit moves the submodule from topic's tip to feature's.
    git(superproject, "checkout", "-q", "-b", "moved")
    git(module, "checkout", "-q", FEATURE)
    git(superproject, "add", "sub")
    git(superproject, "commit", "-q", "-m", "move sub")
    moved = git(superproject, "rev-parse", "HEAD")
    git(superproject, "checkout", "-q", "main")
    git(module, "checkout", "-q", "topic")
    markers = _plant(module, tmp_path)
    git(superproject, "config", "diff.submodule", "diff")
    before = snapshot(superproject)
    server._set_root_dir(superproject)
    with TestClient(server.app) as client:
        assert _pin(client, ref="moved")["status"]["pin"] == moved
        for address in _commit_views(moved):
            assert client.get(address).status_code == 200, address
        _pin(client, working_tree=True)
    assert [name for name, marker in markers.items() if marker.exists()] == []
    assert _differing(before, snapshot(superproject)) == []
    # The fixture is live: Git asked for the same patch without the setting runs the
    # submodule's driver.
    git(superproject, "diff", "-p", f"{moved}~1", moved)
    assert markers["driver"].exists()


def test_a_partial_clone_answers_object_unavailable_and_fetches_nothing(tmp_path: Path) -> None:
    """A blobless clone names blobs it does not hold, and a revision's read fetches none.

    A file, a commit's view, and its diff each answer a typed ``object_unavailable``;
    the tree and the history, which need no blob, answer. No pack arrives and the clone,
    its ``.git`` included, is what it was: ``GIT_NO_LAZY_FETCH`` on a Git the floor
    admits, which is why this module is in the admitted-git list. On an admitted Git
    before :data:`PARTIAL_CLONE_GIT_MINIMUM`, the CI job's 2.43.7, that variable refuses
    the fetch and ends the process, so the revision is refused by name instead, and
    nothing arrives either.
    """

    clone = build_partial_clone(tmp_path.resolve())
    packs = sorted(path.name for path in (clone / ".git" / "objects" / "pack").iterdir())
    before = snapshot(clone)
    server._set_root_dir(clone)
    version, _raw = detect_git_version()
    assert version is not None
    with TestClient(server.app, raise_server_exceptions=False) as client:
        if version < PARTIAL_CLONE_GIT_MINIMUM:
            refused = client.post("/api/source/pin", json={"ref": "origin/feature"}, headers=_JSON)
            assert (refused.status_code, refused.json()["code"]) == (409, "unsupported_git")
            assert "partial clone" in refused.json()["detail"]
            assert client.get("/api/source/status").json()["subject"] == "attached_filesystem"
            _the_clone_is_unchanged(clone, packs, before)
            return
        assert _pin(client, ref="origin/feature")["status"]["pin"] == FEATURE
        assert _tree(client) == ["FEATURE.md", "README.md"]
        assert client.get("/api/git/log", params={"limit": "5"}).status_code == 200
        blob = client.get("/api/file", params={"path": _wire("FEATURE.md")})
        assert (blob.status_code, blob.json()["code"]) == (404, "object_unavailable")
        commit = client.get(f"/api/git/commit/{FEATURE}")
        assert (commit.status_code, commit.json()["code"]) == (404, "object_unavailable")
        assert commit.json()["oid"] == blob.json()["oid"]
        # A commit the clone does not have at all is still not found, and not unavailable.
        unknown = client.get(f"/api/git/commit/{'0123456789abcdef' * 2}01234567")
        assert (unknown.status_code, unknown.json()["code"]) == (404, "commit_not_found")
        for address in (
            f"/api/plugin/diff/comparison?revision={FEATURE}",
            f"/api/plugin/diff/comparison?revision={FEATURE}&file=FEATURE.md",
        ):
            diff = client.get(address)
            assert (diff.status_code, diff.json()["error"]) == (409, "object_unavailable"), address
            assert diff.json()["message"] == "Part of this comparison is not in this checkout."
            assert "nothing is fetched into it" in diff.json()["detail"]
        _pin(client, working_tree=True)
    _the_clone_is_unchanged(clone, packs, before)


def _the_clone_is_unchanged(clone: Path, packs: list[str], before: dict[str, Any]) -> None:
    assert sorted(path.name for path in (clone / ".git" / "objects" / "pack").iterdir()) == packs
    assert _differing(before, snapshot(clone)) == []


def test_a_partial_clone_on_a_git_that_ends_at_a_missing_object_is_refused_by_name(
    checkout: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Before 2.45, ``GIT_NO_LAZY_FETCH`` refuses the fetch and ends the process.

    So an admitted 2.43.7 or 2.44.4 is refused for a partial clone with the release it
    needs, before anything is listed or served, and still serves an ordinary checkout.
    Held on any Git by naming 2.43.7 as the host's.
    """

    monkeypatch.setattr(
        "metabrowser.checkout_revisions.require_acquisition_git", lambda: (2, 43, 7)
    )
    clone = build_partial_clone(tmp_path.resolve())
    before = snapshot(clone)
    said = (
        "showing a branch or tag of a partial clone needs Git 2.45.4 or a patched release "
        "at least 2.50.1 on a newer track, which reads an object the clone lacks as "
        "missing and never fetches it; this is git version 2.43.7"
    )
    server._set_root_dir(clone)
    with TestClient(server.app) as client:
        for refused in (
            client.get("/api/source/refs"),
            client.post("/api/source/pin", json={"ref": "origin/feature"}, headers=_JSON),
        ):
            assert (refused.status_code, refused.json()) == (
                409,
                {"error": TOO_OLD, "detail": said, "code": "unsupported_git"},
            )
        assert client.get("/api/source/status").json()["subject"] == "attached_filesystem"
    assert _differing(before, snapshot(clone)) == []
    # The other ways Git makes a remote a promisor (review C2 on #559): a
    # partialCloneFilter alone, and promisor as an integer other than 0. Zero is false.
    env = git_env(tmp_path)
    for unset, setting, refuses in (
        (("remote.origin.promisor", "extensions.partialclone"), (), True),
        (("remote.origin.partialclonefilter",), ("remote.origin.promisor", "2"), True),
        ((), ("remote.origin.promisor", "0"), False),
    ):
        for key in unset:
            subprocess.run(
                ["git", "-C", str(clone), "config", "--unset-all", key], env=env, check=False
            )
        if setting:
            git(clone, "config", *setting)
        before = snapshot(clone)
        server._set_root_dir(clone)
        with TestClient(server.app) as client:
            answer = client.get("/api/source/refs")
        if refuses:
            assert (answer.status_code, answer.json()) == (
                409,
                {"error": TOO_OLD, "detail": said, "code": "unsupported_git"},
            ), setting
        else:
            assert answer.status_code == 200, answer.text
        assert _differing(before, snapshot(clone)) == []
    # The same Git reads a checkout that names no promisor remote.
    server._set_root_dir(checkout)
    with TestClient(server.app) as client:
        assert _pin(client, ref="feature")["status"]["pin"] == FEATURE
        assert _tree(client) == ["FEATURE.md", "README.md"]
        _pin(client, working_tree=True)


# ── Which Git, which directory, and which folders ────────────


def test_an_older_git_is_refused_by_name_and_the_working_tree_is_still_served(
    checkout: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only a Git the acquisition floor admits is known never to fetch into a checkout."""

    def below_the_floor() -> tuple[int, int, int]:
        raise UnsupportedGitVersionError("git version 2.39.2", "2.43.7 or newer")

    monkeypatch.setattr("metabrowser.checkout_revisions.require_acquisition_git", below_the_floor)
    said = (
        "showing a branch or tag of a checkout needs Git 2.43.7 or newer, which is known "
        "never to fetch into it; this is git version 2.39.2"
    )
    server._set_root_dir(checkout)
    with TestClient(server.app) as client:
        for refused in (
            client.get("/api/source/refs"),
            client.post("/api/source/pin", json={"ref": "feature"}, headers=_JSON),
        ):
            assert (refused.status_code, refused.json()) == (
                409,
                {"error": TOO_OLD, "detail": said, "code": "unsupported_git"},
            )
        assert client.get("/api/source/status").json()["subject"] == "attached_filesystem"
        assert _live_tree(client) == ["NOTES.md", "README.md", "STAGED.md", "UNTRACKED.md"]
    open_on_ref("feature")
    with pytest.raises(SubjectOpenError) as stopped, TestClient(server.app):
        pass
    assert str(stopped.value) == f"--ref: {said}"


def test_the_directory_read_is_the_one_git_names(tmp_path: Path) -> None:
    """A ``.git`` pointer Git and another parser read differently is read as Git reads it.

    ``gitdir:`` followed by two spaces and an absolute path: Git keeps the second space
    and reads a directory of that name inside the folder; a parser that strips it reads
    the absolute path, a repository the reader did not open and Git did not check.
    """

    outside = build_checkout((tmp_path / "outside").resolve())
    served_root = (tmp_path / "served").resolve()
    inner = served_root / " " / str(outside).lstrip("/")
    inner.mkdir(parents=True)
    env = git_env(tmp_path)
    scratch = tmp_path / "scratch"
    subprocess.run(
        ["git", "init", "-q", "--template=", "-b", "inside", str(scratch)], check=True, env=env
    )
    (scratch / "INSIDE.md").write_text("inside\n", encoding="utf-8")
    git(scratch, "add", "INSIDE.md")
    git(scratch, "commit", "-q", "-m", "inside")
    (scratch / ".git").rename(inner / ".git")
    (served_root / ".git").write_text(f"gitdir:  {outside / '.git'}\n", encoding="utf-8")
    (served_root / "INSIDE.md").write_text("inside\n", encoding="utf-8")
    server._set_root_dir(served_root)
    with TestClient(server.app) as client:
        history = [ref["name"] for ref in client.get("/api/git/refs").json()["refs"]]
        chosen = client.get("/api/source/refs")
        assert chosen.status_code == 200, chosen.text
        assert _names(chosen.json()) == ["inside"] == [name for name in history if name == "inside"]
        assert "topic" not in _names(chosen.json())


def test_a_git_entry_that_is_no_repository_has_its_row_removed_by_the_page(
    tmp_path: Path,
) -> None:
    """The row is drawn from a ``.git`` entry, and Git's answer takes it away again."""

    hollow = tmp_path / "hollow"
    (hollow / ".git").mkdir(parents=True)
    (hollow / "README.md").write_text("# Hollow\n", encoding="utf-8")
    server._set_root_dir(hollow)
    with TestClient(server.app) as client:
        assert 'id="source-ref-selector"' in client.get("/view/").text
        refused = client.get("/api/source/refs")
        # The code the selector removes its row for (static/source-ref-selector.js).
        assert (refused.status_code, refused.json()["code"]) == (409, "unsupported_for_subject")
        pin = client.post("/api/source/pin", json={"ref": "main"}, headers=_JSON)
        assert (pin.status_code, pin.json()["code"]) == (409, "unsupported_for_subject")


def test_a_repository_git_refuses_for_its_owner_is_not_read(
    checkout: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Git's ownership check decides, and ``--git-dir`` is never used to step around it.

    The served folder's Git reads no configuration from outside the test: GitHub's Ubuntu
    runner images put ``safe.directory = *`` in ``/etc/gitconfig``, under which Git
    accepts every repository whatever its owner, as ``tests/test_git_repo_identity.py``
    notes too.
    """

    before = snapshot(checkout)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    for name in ("GIT_CONFIG_PARAMETERS", "GIT_CONFIG_COUNT"):
        monkeypatch.delenv(name, raising=False)
    # What Git's own tests set to have every repository belong to someone else.
    monkeypatch.setenv("GIT_TEST_ASSUME_DIFFERENT_OWNER", "1")
    server._set_root_dir(checkout)
    with TestClient(server.app) as client:
        for refused in (
            client.get("/api/source/refs"),
            client.post("/api/source/pin", json={"ref": "feature"}, headers=_JSON),
        ):
            assert (refused.status_code, refused.json()["code"]) == (
                409,
                "unsupported_for_subject",
            )
        assert client.get("/api/source/status").json()["subject"] == "attached_filesystem"
    monkeypatch.delenv("GIT_TEST_ASSUME_DIFFERENT_OWNER")
    assert _differing(before, snapshot(checkout)) == []


def test_a_repository_made_in_a_served_folder_gets_its_selector_without_a_restart(
    tmp_path: Path,
) -> None:
    plain = tmp_path / "later"
    plain.mkdir()
    (plain / "README.md").write_text("# Later\n", encoding="utf-8")
    server._set_root_dir(plain)
    with TestClient(server.app) as client:
        assert 'id="source-ref-selector"' not in client.get("/view/").text
        assert client.get("/api/source/refs").status_code == 409
        env = git_env(tmp_path)
        subprocess.run(
            ["git", "init", "-q", "--template=", "-b", "main", str(plain)], check=True, env=env
        )
        git(plain, "add", "README.md")
        git(plain, "commit", "-q", "-m", "first")
        assert 'id="source-ref-selector"' in client.get("/view/").text
        assert _names(_refs(client)) == ["main"]


def test_a_shell_rendered_while_the_server_switches_is_still_its_folders(
    served: TestClient, checkout: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The shell reads its folder once, with its subject, and not again after an await."""

    _pin(served, ref="feature")
    revision = get_source_session().subject
    _pin(served, working_tree=True)
    discover = server.discover_repository_context

    def switched_meanwhile(root: Path) -> Any:
        # Another request attached a revision while this shell was being rendered.
        attach_subject(revision)
        return discover(root)

    monkeypatch.setattr(server, "discover_repository_context", switched_meanwhile)
    shell = served.get("/view/")
    monkeypatch.undo()
    server._set_root_dir(checkout)
    assert shell.status_code == 200
    assert 'window.METABROWSER_SOURCE_KIND="filesystem"' in shell.text
    assert "content-security-policy" not in shell.headers


def test_a_store_read_that_could_run_a_configured_program_is_refused_at_the_spawn(
    checkout: Path,
) -> None:
    """The options are held where every store spawn passes, not by each caller remembering."""

    target = repository_store_target(git_dir=checkout / ".git")

    async def run(*args: str) -> bytes:
        return await run_git(list(args), target=target)

    settings = (*GIT_NO_SIGNATURE_ARGS, *GIT_NO_SUBMODULE_DIFF_ARGS, *GIT_NO_CONFIGURED_FORMAT_ARGS)
    for args, refused in (
        (("show", FEATURE), "--no-textconv --no-ext-diff"),
        (("diff", FIRST, FEATURE), "--no-textconv --no-ext-diff"),
        (("log", "-1", FEATURE), "--no-textconv --no-ext-diff"),
        (("--literal-pathspecs", "log", "--stat", "-1", FEATURE), "--no-textconv --no-ext-diff"),
        # The driver options name the diff's own, so they come after the command.
        ((*settings, *GIT_NO_DRIVER_ARGS, "log", "-1", FEATURE), "--no-textconv --no-ext-diff"),
        (("log", *GIT_NO_DRIVER_ARGS, "-1", FEATURE), "-c log.showSignature=false"),
        (
            ("-C", ".", *GIT_NO_SIGNATURE_ARGS, "show", *GIT_NO_DRIVER_ARGS, FEATURE),
            "-c diff.submodule=short",
        ),
        (
            (*GIT_NO_SIGNATURE_ARGS, *GIT_NO_SUBMODULE_DIFF_ARGS, "show", *GIT_NO_DRIVER_ARGS),
            "-c format.pretty=medium",
        ),
        (
            (*settings, "-c", "log.showSignature=true", "log", *GIT_NO_DRIVER_ARGS, FEATURE),
            "must not set log.showSignature=true",
        ),
        (
            (*settings, "-c", "log.showsignature", "log", *GIT_NO_DRIVER_ARGS, FEATURE),
            "must not set log.showsignature",
        ),
        (
            (*settings, "-c", "diff.submodule=diff", "diff", *GIT_NO_DRIVER_ARGS, FIRST, FEATURE),
            "must not set diff.submodule=diff",
        ),
        (
            (
                *settings,
                "--config-env=diff.submodule=MB_SUBMODULE",
                *("diff", *GIT_NO_DRIVER_ARGS, FIRST, FEATURE),
            ),
            "must not set --config-env=diff.submodule=MB_SUBMODULE",
        ),
        (
            (*settings, "log", *GIT_NO_DRIVER_ARGS, "--show-signature", "-1", FEATURE),
            "--show-signature",
        ),
        (
            (*settings, "diff", *GIT_NO_DRIVER_ARGS, "--submodule=diff", FIRST, FEATURE),
            "--submodule=diff",
        ),
        (
            (*settings, "log", *GIT_NO_DRIVER_ARGS, "-1", "--format=%G?", FEATURE),
            "must not verify a signature",
        ),
        (
            (*settings, "log", *GIT_NO_DRIVER_ARGS, "-1", "--pretty", "%GS", FEATURE),
            "must not verify a signature",
        ),
        (("cat-file", "--textconv", f"{FEATURE}:README.md"), "must not run a configured filter"),
        (("cat-file", "--filters", f"{FEATURE}:README.md"), "must not run a configured filter"),
        (("rev-list", "-Sneedle", FEATURE), "must not search content"),
        (("rev-list", "--find-object", FEATURE, FEATURE), "must not search content"),
        # Git takes the last of --no-textconv and --textconv.
        (
            (*settings, "show", *GIT_NO_DRIVER_ARGS, "--textconv", FEATURE),
            "must not pass --textconv",
        ),
        (
            (*settings, "diff", *GIT_NO_DRIVER_ARGS, "--ext-diff", FIRST, FEATURE),
            "must not pass --ext-diff",
        ),
        (("hash-object", "README.md"), "must pass --no-filters"),
        (("config", "--edit"), "must not start an editor"),
        # A command no store read uses could start a program its configuration names.
        (("blame", FEATURE, "--", "README.md"), "git blame is not a read of a repository store"),
        (("grep", "x", FEATURE), "git grep is not a read of a repository store"),
        # ``--shallow-file`` takes the next word, so the command is ``log``.
        (
            ("--shallow-file", "x", "log", "-p", FEATURE),
            "git log at a repository store must pass --no-textconv --no-ext-diff",
        ),
        (
            ("for-each-ref", "--format=%(signature:grade)", "refs/heads"),
            "must not verify a signature",
        ),
        # Review C1 on #559: what configuration can make of an option an allowed command
        # takes. A setting the location holds, given another value.
        (
            (*settings, "-c", "format.pretty=%G?", "show", *GIT_NO_DRIVER_ARGS, "-s", FEATURE),
            "must not set format.pretty=%G?",
        ),
        (("-c", "core.fsmonitor=true", "cat-file", "-t", FEATURE), "core.fsmonitor=true"),
        (("-c", "core.hooksPath=hooks", "rev-parse", FEATURE), "core.hooksPath=hooks"),
        # The refs an alternate's core.alternateRefsCommand lists.
        (
            (*settings, "log", *GIT_NO_DRIVER_ARGS, "--alternate-refs", FEATURE),
            "--alternate-refs",
        ),
        (("rev-list", "--alternate-refs", FEATURE), "--alternate-refs"),
        # A signature as a sort key, and a format by name, which pretty.<name> can define.
        (("for-each-ref", "--sort=signature", "refs/heads"), "must not sort by signature"),
        (("for-each-ref", "--sort", "-signature:grade"), "must not sort by signature"),
        (
            (*settings, "show", *GIT_NO_DRIVER_ARGS, "-s", "--pretty=planted", FEATURE),
            "must not name a format: --pretty=planted",
        ),
        (
            (*settings, "log", *GIT_NO_DRIVER_ARGS, "--format=oneline", FEATURE),
            "must not name a format: --format=oneline",
        ),
        # A read writes no ref, so no reference-transaction hook runs, and no configuration.
        (("symbolic-ref", "HEAD", "refs/heads/feature"), "git symbolic-ref at a repository"),
        (("symbolic-ref", "--delete", "HEAD"), "git symbolic-ref at a repository"),
        (("symbolic-ref", "-m", "why", "HEAD"), "git symbolic-ref at a repository"),
        (("config", "core.bare", "true"), "git config at a repository store must only read"),
        (("config", "--unset", "core.bare"), "git config at a repository store must only read"),
        (
            ("config", "--get", "--add", "core.bare", "true"),
            "git config at a repository store must only read",
        ),
    ):
        with pytest.raises(ValueError, match=re.escape(refused)):
            asyncio.run(run(*args))
    listed = asyncio.run(run(*settings, "log", *GIT_NO_DRIVER_ARGS, "-1", "--format=%H", FEATURE))
    assert listed.decode().strip() == FEATURE
    # After ``--`` each word is a path: a file named --show-signature is no option, and
    # the commit changes no such file.
    shown = asyncio.run(
        run(*settings, "show", *GIT_NO_DRIVER_ARGS, "--stat", FEATURE, "--", "--show-signature")
    )
    assert shown == b""
    shown = asyncio.run(run(*settings, "show", *GIT_NO_DRIVER_ARGS, "--stat", FEATURE))
    assert FEATURE in shown.decode()
    assert asyncio.run(run("rev-parse", FEATURE)).decode().strip() == FEATURE
    # The read forms of the commands whose writes are refused.
    assert (
        asyncio.run(run("symbolic-ref", "--quiet", "HEAD")).decode().strip() == "refs/heads/topic"
    )
    assert asyncio.run(run("config", "--get", "core.bare")).decode().strip() == "false"


def test_a_store_location_takes_no_format_fsmonitor_or_hook_from_the_checkout(
    checkout: Path, tmp_path: Path
) -> None:
    """What a location sets for a read that no argument shows (review C1 on #559).

    A ``show`` with no format of its own prints the one ``format.pretty`` names, which
    can hold ``%G?`` and so verify a signature, and a read of an index path runs
    ``core.fsmonitor``. A read through a store target's :class:`GitLocation` sets
    ``format.pretty=medium``, ``core.fsmonitor=false``, and no hooks, so neither runs and
    nothing is written.
    """

    signed = signed_branch(checkout)
    markers = _plant(checkout, tmp_path)
    git(checkout, "config", "format.pretty", "%G? %H")
    before = snapshot(checkout)
    location = GitLocation.revision(repository_store_target(git_dir=checkout / ".git"), signed)

    async def read() -> tuple[bytes, bytes]:
        shown = await run_git_at(["show", *location.diff_driver_args, "-s", signed], location)
        indexed = await run_git_at(["cat-file", "-p", ":README.md"], location)
        return shown, indexed

    shown, indexed = asyncio.run(read())
    assert shown.decode().startswith(f"commit {signed}\n")
    assert indexed
    assert [name for name, marker in markers.items() if marker.exists()] == []
    assert _differing(before, snapshot(checkout)) == []
    # The fixture is live: Git asked the same without those settings runs each program.
    git(checkout, "-c", "log.showSignature=false", "show", "-s", signed)
    assert markers["signature"].exists()
    git(checkout, "cat-file", "-p", ":README.md")
    assert markers["other"].exists()
