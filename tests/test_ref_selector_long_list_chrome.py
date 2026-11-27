"""The branch chooser over thousands of branches in headless Chrome, on a real server (mb-dcp2).

The owner, 2026-11-19: "the branch selector shows: Showing 100 of 1292 branches; filter to
narrow. 1. We should not truncate at such an arbitrarily low number as 1,000. We can show
all the branches. 2. We should sort them by recency, with most recently modified branches
first". The listing has every ref, with primary branches first (``tests/test_source_refs.py``), and
the list draws only the rows near its view and the row that takes Tab (``drawWindow`` in
``static/source-ref-selector.js``), which ``tests/dom/source-ref-selector-session.js``
holds as a pure range (``rowWindow``). How tall a row is, where each is placed, which
rows a scroll position puts in view, and where focus lands are layout and the browser's,
so this serves a checkout of :data:`BRANCHES` branches with ``metab`` and reads, in one
Chrome (``tests/dom/ref-selector-long-list-chrome.mjs``):

- the open list: every branch counted, the primary one first and the rest newest
  first, no note, the list's role, and no more rows drawn than the view and the overscan;
- a scroll to the middle, after which the row under the list's center is drawn where its
  index puts it;
- End, which focuses the last branch, in view, where a redraw of the Files toolbar around
  the list leaves it, and Home the first;
- a row given focus by the keys, which keeps it when the list scrolls far from it, and
  which Tab from the filter box reaches, and ArrowDown, which brings the next into view;
- a filter, which narrows the list to its matches, newest first;
- the oldest branch's page, whose list and first Tab stop start at the top. End still
  reaches the marked current row, and reopening the list returns to the top.

It prints how long opening, End, and the filter took, and bounds them loosely
(``STEP_BOUND_MS``). Without Chrome this skips (``require_chrome`` in
``tests/required_tools.py``), and CI runs it.
"""

from __future__ import annotations

import json
import math
import os
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any, Final

import pytest

from metabrowser.git.process import acquisition_allowed, detect_git_version
from tests.process_group import GROUP_STOP_S, PROFILE_TEARDOWN_S, run_in_own_group
from tests.required_tools import needs_git, require_chrome, require_node
from tests.source_checkout_fixture import git, git_env

SESSION = Path(__file__).resolve().parent / "dom" / "ref-selector-long-list-chrome.mjs"
_METAB = Path(sys.executable).with_name("metab")
# More than the 100 rows the list once stopped at, and more than one view's overscan
# many times over, so a list that drew every row would show here.
BRANCHES: Final = 2000
# One server start, one Chrome, and one document, bounded as the checkout session's
# seven are (tests/test_checkout_ref_selector_chrome.py): a cold Chrome start in CI has
# taken 28.2 s, the server's start is bounded at 30 s inside the session, and each wait
# at 20 s. The whole test took 30 and 34 s on a 10-core Mac at a load average of 17 to 35.
SESSION_TIMEOUT_S = 150
LIFECYCLE_S = SESSION_TIMEOUT_S + GROUP_STOP_S + PROFILE_TEARDOWN_S
# Loose on purpose: here to catch a step that draws every row or waits on something, not
# to rank machines. The times are printed with a failure. Measured 2026-11-19 in headless
# Chrome 152 on a 10-core Mac at a load average of 17 to 35: opening, the server's first
# listing since it started, took 535 and 540 ms; End 35 and 48 ms; and the filter 391 ms
# from its last key, of which FILTER_DELAY_MS in static/source-ref-selector.js is the
# pause before it asks.
STEP_BOUND_MS = 5000
pytestmark = [
    pytest.mark.timeout(LIFECYCLE_S + 10),
    pytest.mark.skipif(os.name != "posix", reason="the fixture's Git environment is POSIX"),
    needs_git,
]
# The first branch's commit, an hour before the next one's.
_FIRST_AT: Final = 1_767_225_600


def _free_port() -> int:
    """A port to start the server's search from; the banner says where it went."""

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _branch(at: int) -> str:
    return f"b-{at:04d}"


def build_long_checkout(directory: Path, branches: int) -> Path:
    """A checkout on ``main`` with *branches* more, ``b-0000`` up, each its own commit.

    ``main`` is the oldest commit; each branch's is an hour newer than the one before it,
    so newest first reads from the last branch down. Written by ``git fast-import``.
    """

    checkout = directory / "long"
    checkout.mkdir(parents=True)
    git(checkout, "init", "-q", "-b", "main")
    lines = [
        "blob",
        "mark :1",
        "data 7",
        "# Long",
        "",
        "commit refs/heads/main",
        "mark :2",
        f"committer Fixture <fixture@example.invalid> {_FIRST_AT - 86_400} +0000",
        "data 4",
        "main",
        "M 100644 :1 README.md",
        "",
    ]
    for at in range(branches):
        lines += [
            f"commit refs/heads/{_branch(at)}",
            f"committer Fixture <fixture@example.invalid> {_FIRST_AT + at * 3600} +0000",
            "data 6",
            f"{at:06d}",
            "from :2",
            "",
        ]
    lines.append("done")
    subprocess.run(
        ["git", "-C", str(checkout), "fast-import", "--quiet", "--done"],
        input="\n".join(lines) + "\n",
        check=True,
        capture_output=True,
        text=True,
        env=git_env(directory),
    )
    git(checkout, "reset", "-q", "--hard", "main")
    return checkout


def test_a_list_of_every_branch_draws_only_its_view_in_chrome(
    tmp_path: Path, chrome_profile: Path
) -> None:
    chrome = require_chrome()
    # A checkout's revisions are read only with a Git the acquisition floor admits, and
    # nothing can admit an older one for another process (checkout_revisions.py).
    version, raw = detect_git_version()
    if not acquisition_allowed(version):
        pytest.skip(f"needs a Git the acquisition floor admits; found {raw or 'no git'!r}")
    checkout = build_long_checkout(tmp_path.resolve(), BRANCHES)
    state = tmp_path / "state"
    for part in ("cache", "config"):
        (state / part).mkdir(mode=0o700, parents=True)
    run = run_in_own_group(
        [require_node(), str(SESSION), str(_METAB), str(checkout), str(_free_port()), str(state)],
        timeout_s=SESSION_TIMEOUT_S,
        env={**os.environ, "CHROME_BIN": chrome, "CHROME_PROFILES": str(chrome_profile)},
    )
    assert not run.timed_out, f"the session ran past {SESSION_TIMEOUT_S} s: {run.stderr}"
    assert run.returncode == 0, run.stderr or run.stdout
    # Shown with a failure: what each step saw, and how long each took.
    print(run.stdout, run.stderr)
    result: dict[str, Any] = json.loads(run.stdout.strip().splitlines()[-1])
    newest = [_branch(at) for at in range(BRANCHES - 1, -1, -1)]

    opened = result["opened"]
    # Every branch is in the list, the primary one first and then newest first, and
    # nothing says the list stops short.
    assert opened["setSize"] == BRANCHES + 1
    assert opened["names"] == ["main", *newest[: len(opened["names"]) - 1]]
    assert opened["note"] == ""
    assert opened["listHeight"] > 0 and opened["rowHeight"] > 0
    assert math.isclose(opened["sizerHeight"], (BRANCHES + 1) * opened["rowHeight"], abs_tol=1)
    # Every row is as tall as the first, the badged one, and the rows abut: placed at one
    # row's height, a taller first row left a gap under every other (mb-dcp2).
    for step in ("opened", "end", "home", "filtered"):
        assert result[step]["heights"] == [result[step]["rowHeight"]], (step, result[step])
        assert result[step]["abutting"] is True, (step, result[step])
    # Drawn: the rows in view and the overscan below them, at the top of the list.
    in_view = math.ceil(opened["listHeight"] / opened["rowHeight"])
    overscan = result["overscan"]
    assert in_view <= opened["drawn"] <= in_view + overscan + 1

    middle = result["middle"]
    # The row under the list's center is the one its index puts there, and is drawn
    # with the rows around it, no more than the view and the overscan either side.
    assert middle["centerIndex"] == middle["expectedIndex"]
    assert middle["drawn"] <= in_view + 2 * overscan + 2

    # A scroll made in the same task as a redraw of the Files toolbar, or of the list's own
    # rows, is where the scroll put the list: no scroll event has come for it, so the page
    # reads the position before it rebuilds the toolbar and sets it after (the nightly
    # soak's 6 for 1001: the list came back at its top).
    for step in ("scrollThenToolbar", "scrollThenToolbarTwice", "scrollThenRender"):
        moved = result[step]
        assert moved["got"] == moved["want"], (step, moved)
        assert moved["centerIndex"] == moved["expectedIndex"], (step, moved)
        assert moved["drawn"] <= in_view + 2 * overscan + 2, (step, moved)

    end = result["end"]
    # End reaches the last branch, never drawn until then, and brings it into view.
    assert (end["focusedIndex"], end["focusedName"]) == (BRANCHES + 1, newest[-1])
    assert end["inView"] is True
    assert end["drawn"] <= in_view + 2 * overscan + 2
    # The Files toolbar drawn again around the list, as a tally refresh does, leaves it
    # where End put it, with its row focused and in view: the toolbar takes the list out
    # of the page and puts it back, which once left it scrolled to its top (mb-y1k0).
    redrawn = result["redrawn"]
    assert (redrawn["focusedIndex"], redrawn["inView"]) == (BRANCHES + 1, True)
    assert redrawn["scrollTop"] == end["scrollTop"] > 0
    assert redrawn["positions"] == end["positions"]
    assert result["home"]["focusedIndex"] == 1

    # A row with focus stays drawn, and focused, however far the list scrolls from it;
    # Tab from the filter box reaches it, and ArrowDown brings the next row into view
    # (review A of #614).
    kept_at = result["keptIndex"] + 1
    assert (result["kept"]["focusedIndex"], result["kept"]["inView"]) == (kept_at, False)
    assert result["kept"]["drawn"] <= in_view + 2 * overscan + 2
    assert result["tabbed"]["focusedIndex"] == kept_at
    assert (result["next"]["focusedIndex"], result["next"]["inView"]) == (kept_at + 1, True)
    # A list to assistive technology, whatever its style says (WebKit drops the role of a
    # list drawn without markers).
    assert opened["role"] == "list"

    filtered = result["filtered"]
    # b-19 matches b-1900 to b-1999 and nothing else; newest first.
    assert filtered["setSize"] == 100
    assert filtered["names"] == newest[: len(filtered["names"])]
    assert filtered["note"] == ""

    # The oldest branch is still current. Opening and tabbing keep primary branches visible.
    for step in ("switched", "switchedTab", "reopened"):
        view = result[step]
        assert view["setSize"] == BRANCHES + 1
        assert view["scrollTop"] == 0
        assert view["names"][0] == "main"
    assert result["switchedTab"]["focusedName"] == "main"
    assert result["switchedEnd"]["served"] == {
        "index": BRANCHES + 1,
        "name": newest[-1],
        "inView": True,
    }

    for step in ("openMs", "endMs", "filterMs"):
        assert result[step] < STEP_BOUND_MS, (step, result[step])
