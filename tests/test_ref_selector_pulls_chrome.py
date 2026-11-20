"""The branch chooser over branches that are the heads of pull requests, in headless Chrome (mb-tjbm).

The owner, 2026-11-20: "The branch chooser in the files view ... only shows the branch
names. If a branch corresponds to a pull request, we should show the pull request as
well." A row with a pull request is two lines and a row without one is one, so the list
places each row by its own height (``rowOffsets`` in ``static/source-ref-selector.js``).
Which rows a scroll position draws, as numbers, is browserless
(``tests/dom/source-ref-selector-session.js``), and the listing and the filter are the
server's (``tests/test_github_ref_pulls.py``, ``tests/test_source_refs.py``). What needs a
browser is layout, and this serves a checkout of :data:`BRANCHES` branches, half of them
the heads of pull requests, whose ``origin`` is a GitHub repository with its pull requests
cached, with ``metab`` and reads in one Chrome (``tests/dom/ref-selector-pulls-chrome.mjs``):

- that a row with a pull request is one height and a row without is another, that each
  row sits where the heights of the rows before it put it, that they abut, and that the
  list's box is as tall as all of them;
- that no more rows are drawn than the view and the overscan, at the top, at the middle,
  and after End, which draws a row never drawn before, with its row focused and in view;
- that a scroll to the middle puts at the list's center the row its index names;
- that a pull request's line holds its state's icon, which the GitHub plugin draws, its
  number and its title, bold, with a long title cut at the line's end and the line inside
  the row;
- that the filter finds a branch by its pull request's number and by a word of its title.

Without Chrome this skips (``require_chrome`` in ``tests/required_tools.py``), and CI runs
it.
"""

from __future__ import annotations

import json
import math
import os
import socket
import sys
from pathlib import Path
from typing import Any, Final

import pytest

from metabrowser.builtin_plugins.github.pull_list import ListedRepository
from metabrowser.git.process import acquisition_allowed, detect_git_version
from tests.cache_home_fixture import (  # pyright: ignore[reportPrivateUsage]
    FixtureSource,
    _stage_and_publish_source,
    build_empty_home,
)
from tests.github_pull_fixture import CANONICAL, head_item, seed_catalog
from tests.process_group import GROUP_STOP_S, PROFILE_TEARDOWN_S, run_in_own_group
from tests.required_tools import needs_git, require_chrome, require_node
from tests.source_checkout_fixture import git
from tests.test_ref_selector_long_list_chrome import _branch, build_long_checkout

SESSION = Path(__file__).resolve().parent / "dom" / "ref-selector-pulls-chrome.mjs"
_METAB = Path(sys.executable).with_name("metab")
# Far more rows than one view and its overscan hold, so a list that drew every row, or
# placed them at one height, would show.
BRANCHES: Final = 600
SESSION_TIMEOUT_S = 150
LIFECYCLE_S = SESSION_TIMEOUT_S + GROUP_STOP_S + PROFILE_TEARDOWN_S
pytestmark = [
    pytest.mark.timeout(LIFECYCLE_S + 10),
    pytest.mark.skipif(os.name != "posix", reason="the fixture's Git environment is POSIX"),
    needs_git,
]
_STATES: Final = ("open", "draft", "merged", "closed")
_NEEDLE: Final = "needlework"
# A title that goes past the end of any line the list has.
_LONG: Final = " and then a good deal more, past any line a list has, " * 3


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _pull_requests(branches: int) -> list[dict[str, Any]]:
    """Every second branch is the head of a pull request, and every tenth of two.

    Pull request ``at + 1`` is from branch ``b-<at>``, in a state that goes round the
    four; a tenth branch's earlier one, ``5000 + at``, was closed. Every fourteenth title
    is long, and two say :data:`_NEEDLE`, which no branch's name does.
    """

    items: list[dict[str, Any]] = []
    for at in range(0, branches, 2):
        state = _STATES[(at // 2) % 4]
        title = f"feat(chooser): row {at}"
        if at % 14 == 0:
            title += _LONG
        if at in (100, 300):
            title = f"Tidy the {_NEEDLE}"
        items.append(
            head_item(
                at + 1,
                _branch(at),
                title,
                state="open" if state in ("open", "draft") else "closed",
                draft=state == "draft",
                merged=state == "merged",
            )
        )
        if at % 10 == 0:
            items.append(
                head_item(5000 + at, _branch(at), f"An earlier try at {at}", state="closed")
            )
    return items


def _newest_first(names: list[str]) -> list[str]:
    """The names as a list shows them: newest first, which is the highest branch number."""

    return sorted(names, key=lambda name: -int(name.removeprefix("b-")))


def test_rows_with_a_pull_request_are_placed_by_their_own_height_in_chrome(
    tmp_path: Path, chrome_profile: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    chrome = require_chrome()
    version, raw = detect_git_version()
    if not acquisition_allowed(version):
        pytest.skip(f"needs a Git the acquisition floor admits; found {raw or 'no git'!r}")
    root = tmp_path.resolve()
    checkout = build_long_checkout(root, BRANCHES)
    # Its `origin` is the GitHub repository the cache holds the pull requests of; nothing
    # is fetched from it.
    git(checkout, "remote", "add", "origin", CANONICAL)
    state = root / "state"
    (state / "config").mkdir(mode=0o700, parents=True)
    home = state / "cache"
    build_empty_home(home)
    source = FixtureSource("https", CANONICAL)
    _stage_and_publish_source(home, source, opened=False)
    items = _pull_requests(BRANCHES)
    seed_catalog(
        ListedRepository(home, source.slug, "octo", "demo"),
        items,
        fetched_at="2026-10-01T12:00:00Z",
    )
    run = run_in_own_group(
        [require_node(), str(SESSION), str(_METAB), str(checkout), str(_free_port()), str(state)],
        timeout_s=SESSION_TIMEOUT_S,
        env={**os.environ, "CHROME_BIN": chrome, "CHROME_PROFILES": str(chrome_profile)},
    )
    assert not run.timed_out, f"the session ran past {SESSION_TIMEOUT_S} s: {run.stderr}"
    assert run.returncode == 0, run.stderr or run.stdout
    print(run.stdout, run.stderr)
    result: dict[str, Any] = json.loads(run.stdout.strip().splitlines()[-1])

    opened = result["opened"]
    heights = result["heights"]
    overscan = result["overscan"]
    # The filter finds pull requests too, once the server has them.
    assert result["placeholder"] == "Filter branches or pull requests"
    # Every branch and the checked-out one, and two heights: a row with a pull request is
    # taller by its line and the gap before it.
    assert opened["setSize"] == BRANCHES + 1
    assert opened["names"][0] == "main"
    assert heights["tall"] > heights["plain"] > 0
    heads = {item["head"]["ref"] for item in items}
    assert opened["rowsWithPulls"] == len(heads) and opened["rowsWithout"] == BRANCHES + 1 - len(
        heads
    )
    for step in ("opened", "end", "redrawn", "home", "byNumber", "byTitle"):
        seen = result[step]
        # Each kind of row is one height, whichever rows are drawn.
        assert len(seen["plainHeights"]) <= 1 and len(seen["tallHeights"]) <= 1, (step, seen)
        if seen["tallHeights"]:
            assert seen["tallHeights"] == [heights["tall"]], (step, seen)
        if seen["plainHeights"]:
            assert seen["plainHeights"] == [heights["plain"]], (step, seen)
        # Each row is where the rows before it put it, and each abuts the next.
        assert seen["placed"] is True and seen["abutting"] is True, (step, seen)
        expected = seen["rowsWithPulls"] * heights["tall"] + seen["rowsWithout"] * heights["plain"]
        assert math.isclose(seen["sizerHeight"], expected, abs_tol=1), (step, seen)
    # Drawn: the rows in view and the overscan, at the top of the list.
    in_view = math.ceil(opened["listHeight"] / heights["plain"])
    assert opened["drawn"] <= in_view + overscan + 1
    # The line: the icon, the plugin's, in the state's own hue; the number; the title, bold.
    assert opened["lines"], "no row drew a pull request"
    for line in opened["lines"]:
        assert line["iconDrawn"] is True and line["iconState"] == line["state"], line
        assert line["number"].startswith("#") and int(line["numberWeight"]) >= 600, line
        assert int(line["titleWeight"]) >= 600, line
        # A title that is cut ends at the line's end, and the line stays in its row.
        assert line["fits"] is True, line
    assert any(line["cut"] for line in opened["lines"]), "no long title was cut"
    # A branch of two pull requests shows the open one and counts the other.
    assert any(line["more"] == "+1" for line in opened["lines"]), opened["lines"]

    middle = result["middle"]
    # The row at the list's center is the one its index names, with the rows around it
    # drawn and no more than the view and the overscan either side.
    assert middle["centerIndex"] == middle["expectedIndex"]
    assert middle["drawn"] <= in_view + 2 * overscan + 2

    # End draws the last row, never drawn before the key, and brings it into view, where a
    # redraw of the Files toolbar around the list leaves it.
    for step in ("end", "redrawn"):
        assert (result[step]["focusedIndex"], result[step]["inView"]) == (BRANCHES + 1, True)
        assert result[step]["drawn"] <= in_view + 2 * overscan + 2
    assert result["home"]["focusedIndex"] == 1

    # `#12`: the branches whose pull requests' numbers start with 12, newest first.
    by_number = [item["head"]["ref"] for item in items if str(item["number"]).startswith("12")]
    assert result["byNumber"]["names"] == _newest_first(by_number)
    assert result["byNumber"]["setSize"] == len(by_number) > 0
    # A word of a title that no branch's name has.
    assert result["byTitle"]["names"] == _newest_first([_branch(100), _branch(300)])
