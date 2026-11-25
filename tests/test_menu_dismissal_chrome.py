"""How every menu closes, in headless Chrome with real presses (mb-7uyy).

The owner, 2026-11-24: "some of the menus in the file view, such as the grouping menu and
the filter menus, do not close when I click outside the menu." The Files tab's dropdowns
held their whole filter bar as their inside, so a press on the bar beside them, on the
drawer's chevron, or on Show ignored left them open, and no menu closed on a press in a
preview's frame, whose presses never reach the page. Every menu now closes through one
helper (docs/design-system.md, "Every Menu Closes Alike"), which
``tests/dom/menu-dismissal-session.js`` walks without a browser.

What needs a browser is the press itself: where the browser delivers it, whether focus
moves with it, that a press in a frame reaches the page only as the window's blur, and
that a press which closes one menu still lands on, and acts on, what is under it after
the closing redraws. ``tests/dom/menu-dismissal-chrome.mjs`` serves a Git working tree
with an HTML page and, for the Files tab's Group by, Modified within, and File type, the
branch chooser, the gear, and the root details, presses each way; this judges it:

- a second press on the trigger, Escape, a press on a tree row, and a press in the HTML
  preview's frame close each menu, and Escape leaves focus on its trigger;
- a press on the filter bar beside a Files dropdown closes it;
- a press that closes one menu acts on what it lands on: the drawer's chevron opens the
  drawer, Show ignored turns off, and another dropdown, the branch chooser, the gear, and
  the root details open, with the first menu closed; from the branch chooser, whose list
  covers Group by's trigger, the first other trigger in sight opens.

Without Chrome this skips (``require_chrome`` in ``tests/required_tools.py``), and CI runs
it. The session leads a process group of its own, which Chrome and the server join, and
the whole group is stopped however it ends (``tests/process_group.py``).
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from metabrowser.git.process import acquisition_allowed, detect_git_version
from tests.process_group import GROUP_STOP_S, PROFILE_TEARDOWN_S, run_in_own_group
from tests.required_tools import needs_git, require_chrome, require_node

SESSION = Path(__file__).resolve().parent / "dom" / "menu-dismissal-chrome.mjs"
_METAB = Path(sys.executable).with_name("metab")
# One server start, one Chrome, and about 90 presses, each waiting two frames. A cold
# Chrome start in CI has taken 28.2 s (tests/dom/chrome-session.mjs), and the server's
# start is bounded at 30 s inside the session.
SESSION_TIMEOUT_S = 150
LIFECYCLE_S = SESSION_TIMEOUT_S + GROUP_STOP_S + PROFILE_TEARDOWN_S
pytestmark = [
    pytest.mark.timeout(LIFECYCLE_S + 10),
    pytest.mark.skipif(os.name != "posix", reason="the fixture's Git environment is POSIX"),
    needs_git,
]
MENUS = ("group", "recency", "types", "branch", "settings", "rootDetails")
DROPDOWNS = ("group", "recency", "types")


def _free_port() -> int:
    """A port to start the server's search from; the banner says where it went."""

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _working_tree(root: Path) -> None:
    """A Git working tree of one commit: a page to preview in a frame, and enough files
    that the tree runs on below the tallest open menu."""

    (root / "src").mkdir(parents=True)
    (root / "docs").mkdir()
    (root / "README.md").write_text("# Fixture\n", encoding="utf-8")
    (root / "page.html").write_text(
        "<!doctype html><title>Page</title><p>A page to press in.</p>\n", encoding="utf-8"
    )
    for n in range(1, 4):
        (root / "src" / f"m{n}.py").write_text(f"x = {n}\n", encoding="utf-8")
        (root / "docs" / f"d{n}.md").write_text(f"# d{n}\n", encoding="utf-8")
    for n in range(1, 31):
        (root / f"note{n:02}.txt").write_text(f"note {n}\n", encoding="utf-8")
    env = {name: value for name, value in os.environ.items() if not name.startswith("GIT_")}
    env.update(
        GIT_CONFIG_GLOBAL=str(root.parent / ".gitconfig-absent"),
        GIT_CONFIG_SYSTEM=str(root.parent / ".gitconfig-absent"),
        GIT_AUTHOR_NAME="T",
        GIT_AUTHOR_EMAIL="t@example.com",
        GIT_COMMITTER_NAME="T",
        GIT_COMMITTER_EMAIL="t@example.com",
        GIT_AUTHOR_DATE="2026-11-24T00:00:00Z",
        GIT_COMMITTER_DATE="2026-11-24T00:00:00Z",
    )
    for args in (
        ["init", "-q", "--template=", "-b", "main"],
        ["add", "."],
        ["commit", "-q", "-m", "init"],
    ):
        subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, env=env)


def test_every_menu_closes_alike_in_chrome(tmp_path: Path, chrome_profile: Path) -> None:
    chrome = require_chrome()
    # The branch chooser reads the working tree's refs only with a Git the acquisition
    # floor admits (checkout_revisions.py, "Which Git"); CI's Git is admitted.
    version, raw = detect_git_version()
    if not acquisition_allowed(version):
        pytest.skip(f"needs a Git the acquisition floor admits; found {raw or 'no git'!r}")
    root = (tmp_path / "served").resolve()
    _working_tree(root)
    state = tmp_path / "state"
    for part in ("cache", "config"):
        (state / part).mkdir(mode=0o700, parents=True)
    run = run_in_own_group(
        [require_node(), str(SESSION), str(_METAB), str(root), str(_free_port()), str(state)],
        timeout_s=SESSION_TIMEOUT_S,
        env={**os.environ, "CHROME_BIN": chrome, "CHROME_PROFILES": str(chrome_profile)},
    )
    assert not run.timed_out, f"the session ran past {SESSION_TIMEOUT_S} s: {run.stderr}"
    assert run.returncode == 0, run.stderr or run.stdout
    # Shown with a failure: what each menu did, and each phase's time.
    print(run.stdout, run.stderr)
    result: dict[str, Any] = json.loads(run.stdout.strip().splitlines()[-1])

    menus = result["menus"]
    assert sorted(menus) == sorted(MENUS)
    for name in MENUS:
        seen = menus[name]
        closes = {key: value for key, value in seen.items() if key.endswith("Closes")}
        assert all(closes.values()), (name, seen)
        expected = {"secondPressCloses", "escapeCloses", "treeRowCloses", "frameCloses"}
        if name in DROPDOWNS:
            expected.add("barGapCloses")
        assert set(closes) == expected, (name, seen)
        assert seen["focusAfterEscape"] == f"{name} trigger", (name, seen)

    acts = result["pressesAct"]
    # Each press landed on its control, not on the open menu drawn over it.
    assert all(case["landed"] for case in acts.values()), acts
    assert acts["drawerChevron"] == {"open": [], "landed": True, "before": False, "after": True}
    assert acts["showIgnored"] == {"open": [], "landed": True, "before": True, "after": False}
    for case, opened in (
        ("otherDropdown", "recency"),
        ("branchFromGroup", "branch"),
        ("gearFromGroup", "settings"),
        ("rootDetailsFromGear", "rootDetails"),
    ):
        assert acts[case]["open"] == [opened], (case, acts[case])
    # The branch chooser's list covers Group by's trigger, so the press goes to the first
    # other trigger it leaves in sight.
    from_branch = acts["otherFromBranch"]
    assert from_branch["pressed"] in ("group", "settings", "rootDetails"), from_branch
    assert from_branch["open"] == [from_branch["pressed"]], from_branch
