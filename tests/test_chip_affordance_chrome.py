"""Whether each chip says it is clickable, in the running app and a real Chrome.

docs/design-system.md, "Clickable and Static Chips": a chip that is a control, or the
whole content of one, shows the pointer, is never underlined, paints another ground under
the pointer, keeps its text's contrast there, and draws the one focus ring; a static chip
shows nothing under the pointer. ``tests/dom/chip-affordance-chrome.mjs`` finds every chip
by its shape on the surfaces that draw chips and holds each to its side of that rule, in
the light theme and the dark, each a test of its own: a pull request's header, its Checks and Changes tabs, the
Pulls tab, and a stack's page, served from the GitHub stand-in with native stacks (as
``tests/test_github_stack_page_chrome.py`` serves it), and the Files tab, the revision
chooser, the Commits tab, a commit's page, a table whose rows reference another's, the same
table filtered, a document whose images the page does not load, and a compressed file's
header, from a checkout this test writes, served untrusted. Whether a chip paints another
ground, and what that ground is, is paint, which no browserless DOM computes. Before the
rule, the pull request header's readiness badge underlined under the pointer and painted
no ground of its own, nor did a branch chip, and 62 of the session's 582 checks failed
(2026-11-26).

Without Chrome this skips (``require_chrome`` in ``tests/required_tools.py``). The test
owns everything it starts: the stand-in's server stops when its stdin closes, and the
measuring Node process leads a process group of its own, which Chrome and the folder's
server join, so a run stopped at its bound stops all of it (tests/process_group.py).
"""

from __future__ import annotations

import gzip
import json
import os
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from tests.process_group import GROUP_STOP_S, PROFILE_TEARDOWN_S, run_in_own_group
from tests.required_tools import require_chrome, require_git, require_node
from tests.test_github_stack_page_chrome import FIXTURE, with_stacks
from tests.test_nav_metadata_chrome import (
    _SERVER_STOP_S,
    _SERVING_BUDGET_S,
    _free_port,
    _log_tail,
    _private,
    _stop_server,
    _wait_until_serving,
)

SESSION = Path(__file__).resolve().parent / "dom" / "chip-affordance-chrome.mjs"
_METAB = Path(sys.executable).with_name("metab")
# The stand-in's home, its mirror and the records of 7 to 10 fetched through the production
# CLI path, as tests/test_github_stack_page_chrome.py builds it.
_BUILD_BUDGET_S = 60.0
# A cold Chrome start, which tests/dom/chrome-session.mjs bounds at 30 s, the folder's
# server's start, bounded at 30 s in the session, and thirteen surfaces in two themes, each
# of about 130 chips a pointer move, four one-pixel screenshots, and a forced focus. On a
# 4-core Linux container shared with two other test runs the session took 75 s
# (2026-11-26); this is that three times over, as a loaded CI runner's slower start needs.
_MEASUREMENT_BUDGET_S = 240.0
LIFECYCLE_S = (
    _BUILD_BUDGET_S
    + _SERVING_BUDGET_S
    + _MEASUREMENT_BUDGET_S
    + GROUP_STOP_S
    + 2 * _SERVER_STOP_S
    + PROFILE_TEARDOWN_S
)
pytestmark = pytest.mark.timeout(LIFECYCLE_S + 10)


def _write_folder(root: Path) -> None:
    """A table whose rows reference another's, a document of image chips, and a gzip."""

    root.mkdir()
    with sqlite3.connect(root / "shop.sqlite") as db:
        db.executescript(
            "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL);"
            "CREATE TABLE orders (id INTEGER PRIMARY KEY, item TEXT NOT NULL,"
            " user_id INTEGER NOT NULL REFERENCES users(id));"
            "INSERT INTO users VALUES (1, 'Ada'), (2, 'Grace');"
            "INSERT INTO orders VALUES (1, 'pen', 1), (2, 'ink', 2), (3, 'pencil', 1);"
        )
    db.close()
    # An `http` image is never loaded, so each is its alt text in a chip: one in a link, a
    # badge's, and one in no link, which the page puts in a link to the image.
    (root / "badges.md").write_text(
        "# Badges\n\n"
        "[![build passing](http://img.example.test/build.svg)](https://example.test/ci)\n\n"
        "A diagram: ![the architecture](http://img.example.test/architecture.png)\n",
        encoding="utf-8",
    )
    (root / "notes.txt.gz").write_bytes(gzip.compress(b"a compressed note\n", mtime=0))
    # A checkout, so the Commits tab draws its history's ref chips, trunk, a branch, and a
    # tag, and the Files tab its revision row's chip.
    git = require_git()
    env = {
        **{name: value for name, value in os.environ.items() if not name.startswith("GIT_")},
        "GIT_AUTHOR_NAME": "Ada",
        "GIT_AUTHOR_EMAIL": "ada@example.test",
        "GIT_COMMITTER_NAME": "Ada",
        "GIT_COMMITTER_EMAIL": "ada@example.test",
        "GIT_AUTHOR_DATE": "2026-09-17T12:00:00Z",
        "GIT_COMMITTER_DATE": "2026-09-17T12:00:00Z",
    }
    for command in (
        ["init", "--quiet", "--initial-branch=main"],
        ["add", "."],
        ["commit", "--quiet", "--message", "Add the shop"],
        ["tag", "v1.0"],
        ["branch", "topic"],
    ):
        subprocess.run([git, *command], cwd=root, env=env, check=True, capture_output=True)


# Each theme is a test of its own: the two together took 86 to 90 s in CI's Chrome tier
# (run 45916053261), more than a shard's room beside its other tests, and two halves let the
# tier's dealer put them in different parts (devtools/shard_weights.py).
@pytest.mark.parametrize("theme", ["light", "dark"])
def test_every_chip_says_whether_it_is_clickable_in_chrome(
    tmp_path: Path, chrome_profile: Path, theme: str
) -> None:
    chrome = require_chrome()
    node = require_node()
    env = {name: value for name, value in os.environ.items() if not name.startswith("GIT_")}
    env["METABROWSER_CONFIG_DIR"] = str(_private(tmp_path / "config"))
    env["METABROWSER_LOG_LEVEL"] = "WARNING"
    stand_in = tmp_path / "stand-in"
    stand_in.mkdir()
    built = subprocess.run(
        [sys.executable, str(FIXTURE), str(stand_in)],
        capture_output=True,
        text=True,
        env=env,
        timeout=_BUILD_BUDGET_S,
        check=False,
    )
    assert built.returncode == 0, built.stderr[-4000:]
    answers = stand_in / "fake-gh-scenario.json"
    answers.write_text(
        json.dumps(with_stacks(json.loads(answers.read_text(encoding="utf-8")))),
        encoding="utf-8",
    )
    folder = tmp_path / "folder"
    _write_folder(folder)
    folder_state = _private(tmp_path / "folder-state")
    port = _free_port()
    log = tmp_path / "server.log"
    with log.open("w", encoding="utf-8") as output:
        # --exit-on-eof: closing stdin stops the server however this test ends.
        server = subprocess.Popen(
            [
                sys.executable,
                str(FIXTURE),
                str(stand_in),
                "--serve",
                "7",
                str(port),
                "--exit-on-eof",
            ],
            stdin=subprocess.PIPE,
            stdout=output,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
            start_new_session=True,
        )
    try:
        _wait_until_serving(server, port, log)
        run = run_in_own_group(
            [
                node,
                str(SESSION),
                f"http://127.0.0.1:{port}",
                str(_METAB),
                str(folder),
                str(_free_port()),
                str(folder_state),
                theme,
            ],
            timeout_s=_MEASUREMENT_BUDGET_S,
            env={**os.environ, "CHROME_BIN": chrome, "CHROME_PROFILES": str(chrome_profile)},
        )
    finally:
        _stop_server(server)
    if run.timed_out:
        pytest.fail(f"ran past {_MEASUREMENT_BUDGET_S:g} s; its steps:\n{run.stderr}")
    # Each step's time and the chips each surface drew, shown with the output when it fails.
    print(run.stderr)
    assert run.returncode == 0, f"{run.stderr[-8000:]}\nserver: {_log_tail(log)}"
    passed = re.fullmatch(r"chips in Chrome: (\d+) checks passed\n", run.stdout)
    assert passed is not None and int(passed.group(1)) > 0, run.stdout
