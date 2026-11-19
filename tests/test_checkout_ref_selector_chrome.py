"""A checkout's branch and tag selector in headless Chrome, on a real server (mb-8ob8).

The owner, 2026-11-18, looking at a local checkout: "Why do I still not see a branch
chooser anymore?" A folder that is a repository's root now has the mirror's selector,
which shows any branch or tag as a pinned revision read from the checkout's own Git
objects, and the working tree as a separate choice. What the selector decides is
browserless (``tests/dom/source-ref-selector-session.js``). What needs a browser is that
the page a real ``metab`` writes for a checkout mounts it, that a click reaches the pin
route and the document that comes back is the other subject's, under that subject's
Content-Security-Policy, and where the panel sits. ``tests/dom/checkout-ref-selector-chrome.mjs``
serves ``tests/source_checkout_fixture.py``'s checkout, whose working tree differs from
every commit, and in one Chrome walks: the working tree's page and its panel, a branch,
its lists, a switch made outside the page and the reload the selector then offers, a tag,
the Working tree row, Back onto a revision's address while the working tree is served,
and a revision's Commits tab, which is the checkout's. This judges it, and then compares every file under the checkout, its ``.git``
included, with what it was before the server started.

It also measures, since nothing should be slow here: each switch from the click to the
new document's first tree rows, printed with a failure and bounded loosely
(``SWITCH_BOUND_MS``).

Without Chrome this skips (``require_chrome`` in ``tests/required_tools.py``), and CI runs
it. The session leads a process group of its own, which Chrome and the server join, and
the whole group is stopped however it ends (``tests/process_group.py``).
"""

from __future__ import annotations

import json
import os
import socket
import sys
from pathlib import Path
from typing import Any

import pytest

from metabrowser.commit_ids import SHORT_COMMIT_CHARS
from metabrowser.git.process import acquisition_allowed, detect_git_version
from metabrowser.paths_safe import tilde_path
from tests.process_group import GROUP_STOP_S, PROFILE_TEARDOWN_S, run_in_own_group
from tests.required_tools import needs_git, require_chrome, require_node
from tests.source_checkout_fixture import build_checkout, snapshot, view

SESSION = Path(__file__).resolve().parent / "dom" / "checkout-ref-selector-chrome.mjs"
_METAB = Path(sys.executable).with_name("metab")
# One server start, one Chrome, and seven documents. The session took 5 s on a 10-core Mac
# at a load average of 13; a cold Chrome start in CI has taken 28.2 s, the server's start is
# bounded at 30 s inside the session, and each wait for a document at 20 to 30 s.
SESSION_TIMEOUT_S = 150
LIFECYCLE_S = SESSION_TIMEOUT_S + GROUP_STOP_S + PROFILE_TEARDOWN_S
pytestmark = [
    pytest.mark.timeout(LIFECYCLE_S + 10),
    pytest.mark.skipif(os.name != "posix", reason="the fixture's Git environment is POSIX"),
    needs_git,
]
# A switch is one POST, which resolves a ref and opens a tree with a few Git commands, and
# one document. Measured 2026-11-18 in headless Chrome 152 on a 10-core Mac at a load
# average of 13 to 16, over three runs, from the click to the new document's first tree
# rows: 117 to 123 ms to a branch, 107 to 121 ms to a tag, and 34 to 41 ms back to the
# working tree, whose folder was never closed. The bound is loose on purpose: it is here
# to catch a switch that waits on something, not to rank machines.
SWITCH_BOUND_MS = 5000
WORKING_TREE = ["NOTES.md", "README.md", "STAGED.md", "UNTRACKED.md"]
FEATURE = "c7ae2a331f546e6a2431ed7093e9e430a9d1269b"
# Each ref's commit as every line names one (`short_commit` in commit_ids.py), in the
# fixture, whose IDs are literal (tests/source_checkout_fixture.py).
TOPIC, FEATURE_SHORT, LOCAL_WORK, V1 = ("42382ea", "c7ae2a3", "25e0a2a", "fcb9d63")
TRUSTED = {"active_content": True, "mutations": False}
UNTRUSTED = {"active_content": False, "mutations": False}


def _free_port() -> int:
    """A port to start the server's search from; the banner says where it went."""

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _rows(panel: dict[str, Any]) -> list[str]:
    return [row["text"] for row in panel["rows"]]


def _one_look(name: str, shown: dict[str, Any]) -> None:
    """Every short commit ID a page shows is one length, in the mono face, in the muted gray."""

    face = shown["face"]
    for entry in shown["ids"]:
        assert len(entry["text"]) == SHORT_COMMIT_CHARS, (name, entry)
        assert (entry["color"], entry["font"]) == (face["color"], face["font"]), (name, entry)


def test_a_checkout_switches_between_its_working_tree_and_its_revisions_in_chrome(
    tmp_path: Path, chrome_profile: Path
) -> None:
    chrome = require_chrome()
    # The server here is a real `metab`, which reads a checkout's revisions only with a Git
    # the acquisition floor admits and refuses by name otherwise (checkout_revisions.py,
    # "Which Git"). Nothing can admit an older Git for another process, so on one this
    # has no subject; CI's Git is admitted. tests/test_checkout_revisions.py holds the
    # same behavior in process on any Git.
    version, raw = detect_git_version()
    if not acquisition_allowed(version):
        pytest.skip(f"needs a Git the acquisition floor admits; found {raw or 'no git'!r}")
    checkout = build_checkout((tmp_path / "served").resolve())
    state = tmp_path / "state"
    for part in ("cache", "config"):
        (state / part).mkdir(mode=0o700, parents=True)
    before = snapshot(checkout)
    run = run_in_own_group(
        [require_node(), str(SESSION), str(_METAB), str(checkout), str(_free_port()), str(state)],
        timeout_s=SESSION_TIMEOUT_S,
        env={**os.environ, "CHROME_BIN": chrome, "CHROME_PROFILES": str(chrome_profile)},
    )
    assert not run.timed_out, f"the session ran past {SESSION_TIMEOUT_S} s: {run.stderr}"
    assert run.returncode == 0, run.stderr or run.stdout
    # Shown with a failure: what each page was, and how long each switch took.
    print(run.stdout, run.stderr)
    result: dict[str, Any] = json.loads(run.stdout.strip().splitlines()[-1])

    # The working tree's page: the folder's own profile, the live files, and the selector.
    tree = result["workingTree"]
    assert (tree["kind"], tree["button"], tree["heading"]) == (
        "filesystem",
        "Working tree",
        "checkout",
    )
    assert tree["checkout"] == {"working_tree": True} and tree["pin"] is None
    assert tree["tree"] == WORKING_TREE
    assert tree["capabilities"] == TRUSTED
    # The pin guard came with the selector's bundle, so the page says what it shows.
    assert tree["guard"] is True
    # The button chooses what the Files tab shows and nothing else, so it is in that tab's
    # toolbar, not above the tabs.
    assert tree["inFilesToolbar"] is True

    panel = result["workingTreePanel"]
    assert panel["open"] and panel["focused"]
    # The working tree is named by its folder, the path as the page names the folder, and
    # has no commit or age; the folder's own name is shown whole in the narrow pane.
    working_tree = panel["workingTree"]
    assert working_tree["text"].startswith("Working tree ")
    assert (working_tree["current"], working_tree["chip"]) == (True, None)
    assert (working_tree["commitFace"], working_tree["age"]) == (None, None)
    assert panel["location"] == tilde_path(checkout, Path.home().resolve())
    assert panel["folderWhole"] is True
    assert [(entry["label"], entry["chosen"]) for entry in panel["lists"]] == [
        ("Branches", True),
        ("Tags", False),
        ("Remotes", False),
    ]
    # The checked-out branch is badged, lists first, and is not the served row; the rest
    # are newest first, local-work committed in the checkout after feature (mb-dcp2).
    assert _rows(panel) == [
        f"topic checked out {TOPIC}",
        f"local-work {LOCAL_WORK}",
        f"feature {FEATURE_SHORT}",
    ]
    assert not any(row["current"] for row in panel["rows"])
    assert {row["chip"] for row in panel["rows"]} == {"local"}
    assert _rows(result["workingTreeRemotes"]) == [
        f"origin/feature {FEATURE_SHORT}",
        f"origin/topic {TOPIC}",
    ]
    assert {row["chip"] for row in result["workingTreeRemotes"]["rows"]} == {"remote"}
    assert sorted(_rows(result["workingTreeTags"])) == [
        f"local-tag {FEATURE_SHORT}",
        f"v1 {V1}",
    ]
    for name in ("workingTreePanel", "workingTreeRemotes", "workingTreeTags", "branchPanel"):
        assert result[name]["inside"], f"{name}: the panel leaves the navigation pane"
        assert result[name]["spansToolbar"], f"{name}: the panel does not span the toolbar"
        assert result[name]["overflowing"] == 0, f"{name}: a row is wider than the panel"
        assert result[name]["error"] == ""
        # Every ref's short ID is in the commit-ID face, and every ref has an age in a tier,
        # its date the tooltip. A tag's is its commit's.
        for row in result[name]["rows"]:
            assert row["commitFace"] is True, (name, row)
            assert row["age"]["text"] and row["age"]["tier"] and row["age"]["tip"], (name, row)
        # The ages end the rows in one column, so the IDs line up: the widest compact age
        # takes no more room than the narrowest.
        assert len(set(result[name]["ageColumn"])) == 1, (name, result[name]["ageColumn"])
        assert result[name]["commitColumns"] <= 1, name
        # Every ref's commit, in the list as in the heading beside it, is one short ID: one
        # length, the mono face, and the muted gray (docs/design-system.md, "Short Commit
        # IDs"), which the owner asked for after seeing longer IDs in this list.
        assert len(result[name]["commitIds"]["ids"]) >= len(result[name]["rows"]), name
        _one_look(name, result[name]["commitIds"])
    for name in ("workingTree", "branch", "tag", "reloaded", "back"):
        _one_look(name, result[name]["commitIds"])
    # A revision's heading names its commit the same way.
    assert [entry["text"] for entry in result["branch"]["commitIds"]["ids"]] == [FEATURE_SHORT]

    # A branch: a revision's page, under the untrusted profile, with no file of the disk's.
    branch = result["branch"]
    assert (branch["kind"], branch["path"]) == ("git_revision", view("README.md"))
    assert branch["pin"] == {"pin": FEATURE, "ref": "refs/heads/feature"}
    assert branch["checkout"] == {"working_tree": False}
    assert branch["button"] == "feature"
    assert branch["heading"] == f"checkoutfeature{FEATURE_SHORT}"
    assert branch["tree"] == ["FEATURE.md", "README.md"]
    assert branch["capabilities"] == UNTRUSTED
    assert branch["title"] == tree["title"] == "checkout • Metabrowser"
    on_branch = result["branchPanel"]
    assert on_branch["workingTree"]["current"] is False
    assert [row["text"] for row in on_branch["rows"] if row["current"]] == [
        f"feature {FEATURE_SHORT}"
    ]

    # The selector is drawn by the server with its button, leading the Files toolbar, so
    # mounting it moves nothing: one height for the selector and one place for the tree's
    # first row, from each document's start, on the working tree's page and on a revision's.
    for name in ("workingTreeLayout", "branchLayout"):
        layout = result[name]
        assert len(layout["rowHeights"]) == 1, f"{name}: the selector changed height: {layout}"
        assert len(layout["treeTops"]) == 1, f"{name}: the tree moved: {layout}"
        # The button the parser drew is the one the mounted module uses, so focus put on
        # it before the module arrived is not lost to a swap.
        assert (layout["toggles"], layout["adopted"]) == (1, True), f"{name}: {layout}"

    # A page that shows what the server serves is never refused: the working tree's page
    # before its guard arrived, and the revision's through a file and its history. The
    # server refuses a page's fetch that names no commit while a pin is served, so this
    # is also that every request of a pin's page does name it.
    for name in ("workingTreeBrowsing", "revisionRequests", "revisionBrowsing"):
        assert result[name]["asked"] > 0, name
        assert result[name]["refused"] == [], f"{name}: refused {result[name]['refused']}"
    # Nor is the page that asked to switch, which asks nothing more: it asked for its root's
    # tallies every few milliseconds through the switch, as its own refresh of them can,
    # and each waited for the answer and went with the page (mb-bio7).
    assert result["leftBehind"] == [], f"the page left behind asked: {result['leftBehind']}"

    # Another tab switched the server back: this page is refused, and offers a reload.
    assert (result["switchedOutside"], result["refused"]) == (200, 409)
    assert result["stale"]["stale"] == "The server now shows the working treeReload"
    # It sits at the pane's foot, after the indexing row and under the tree: outside the
    # Files toolbar and the metadata band under it, which hide with the Files tab.
    stale_at = {
        "after": "index-progress",
        "inToolbarOrBand": False,
        "shown": True,
        "underTree": True,
        "inPane": True,
    }
    assert result["staleAt"] == {**stale_at, "front": "files"}
    # The reload asks for the revision's address, which the server sends to the folder's.
    reloaded = result["reloaded"]
    assert (reloaded["kind"], reloaded["path"], reloaded["button"]) == (
        "filesystem",
        "/view/README.md",
        "Working tree",
    )
    assert reloaded["stale"] is None and reloaded["tree"] == WORKING_TREE

    # A tag, and the way back by the Working tree row.
    tag = result["tag"]
    assert (tag["kind"], tag["button"], tag["tree"]) == ("git_revision", "v1", ["README.md"])
    back = result["back"]
    assert (back["kind"], back["path"], back["button"]) == (
        "filesystem",
        "/view/README.md",
        "Working tree",
    )
    assert back["tree"] == WORKING_TREE and back["capabilities"] == TRUSTED

    # Back onto the tag's address while the working tree is served: the folder's page.
    after_back = result["afterBack"]
    assert (after_back["kind"], after_back["path"]) == ("filesystem", "/view/README.md")
    assert after_back["tree"] == WORKING_TREE
    assert (result["served"]["subject"], result["served"]["pin"]) == ("attached_filesystem", None)

    # Each document came under its subject's policy: a revision's has one, the folder's none.
    documents = [entry for entry in result["documents"] if entry["status"] == 200]
    assert documents, result["documents"]
    for entry in documents:
        assert entry["csp"] is entry["url"].startswith("/view/g1-"), entry

    # The Commits tab does not follow the Files tab: on feature's page, the history it shows
    # is the checkout's, whose HEAD chip is on the checked-out topic, and the button went
    # with the Files toolbar.
    assert result["revisionCommits"] == {"head": "topic", "button": False}
    # A switch from another tab with Commits in front: the history still answers, the
    # tree does not, and the offer to reload shows on the Commits tab, where it was.
    assert result["commitsSwitched"] == {
        "statuses": [409, 200],
        "at": {**stale_at, "front": "git"},
    }

    for name in ("toBranch", "toTag", "toWorkingTree"):
        assert result[name]["rowsMs"] < SWITCH_BOUND_MS, f"{name}: {result[name]}"

    # And none of it wrote the checkout: the working tree, the index, HEAD, every ref and
    # object, byte for byte, with each file's inode and modification time.
    after = snapshot(checkout)
    assert (
        sorted(key for key in before.keys() | after.keys() if before.get(key) != after.get(key))
        == []
    )
