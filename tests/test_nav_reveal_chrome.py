"""Navigating to an item reveals it in the navigation pane, in a real Chrome.

Which tab a route brings to the front, what each route asks a panel to reveal, and what a
panel says of an item it cannot show are browserless (``tests/dom/nav-reveal-session.js``).
What only a browser can tell is held here: that after each route the item's row is in the
tab in front, selected, and inside the navigation pane's scroller, and that focus stays
where the reader was (docs/design-system.md, "Navigation Reveals the Item").

So this serves a checkout of the GitHub stand-in with a fake ``gh`` whose ``gh stack``
answers two native stacks, #286 (pull requests 7 to 10) and #300 (5 and 10), and whose
pull request 106 has 250 changed files, with a deep folder, a document linking into it,
and a folder longer than the tree draws at once; and, on a second server, a repository
with 300 commits, for a commit's address. A step within the pull request shown, another
tab of its page or one of its changed files, is checked to move nothing, and a pull
request's address is loaded twice with the page's stacks held past the list's first
window, so that the regroup they bring comes after the reveal, as on a loaded machine:
once while the reader stays, and once while the reader goes to Files and back with the
tab buttons.
Every page has a Mac's navigator, on every host, so Control-N and Control-P are bound,
as they are only on macOS and iOS (``tests/dom/control-chords-chrome.mjs`` sets one too).
``tests/dom/nav-reveal-chrome.mjs`` drives each route in the running app.
``METABROWSER_NAV_REVEAL_SHOTS`` names a directory for its screenshots.

Without Chrome this skips (``require_chrome`` in ``tests/required_tools.py``). The test owns
everything it starts: the servers stop when their stdin closes, and the measuring Node
process leads a process group of its own, which Chrome joins, so a run stopped at its
bound stops all of it (tests/process_group.py).
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from tests.github_pull_fixture import (
    CANONICAL,
    Origin,
    clone_checkout,
    git_env,
    install_fake_gh,
)
from tests.process_group import GROUP_STOP_S, PROFILE_TEARDOWN_S, run_in_own_group
from tests.required_tools import require_chrome, require_git, require_node
from tests.test_github_pulls_stacks_chrome import stacks_scenario
from tests.test_nav_metadata_chrome import (
    _BANNER_BUDGET_S,
    _SERVER_STOP_S,
    _SERVING_BUDGET_S,
    _free_port,
    _log_tail,
    _private,
    _read_port,
    _stop_server,
    _wait_until_serving,
)

SESSION = Path(__file__).resolve().parent / "dom" / "nav-reveal-chrome.mjs"
_METAB = Path(sys.executable).with_name("metab")
# A cold Chrome start, which tests/dom/chrome-session.mjs bounds at 30 s, then its routes,
# each a page load, a search, or a fake gh refresh, each bounded at 30 s in the script.
_MEASUREMENT_BUDGET_S = 150.0
LIFECYCLE_S = (
    2 * (_BANNER_BUDGET_S + _SERVING_BUDGET_S)
    + _MEASUREMENT_BUDGET_S
    + GROUP_STOP_S
    + 4 * _SERVER_STOP_S
    + PROFILE_TEARDOWN_S
)
pytestmark = pytest.mark.timeout(LIFECYCLE_S + 10)

# Five of the pages a folder draws at a time (TREE_PAGE_SIZE in static/app.js): a reveal of
# a file in the fourth draws only that page, between "more" rows for the pages around it.
LONG_FOLDER_FILES = 1000
HISTORY_COMMITS = 300


def add_reveal_files(checkout: Path) -> None:
    """A deep folder, a document that links into it, and a long folder.

    The document also links the repository's pages on github.com that open in the app: the
    checkout's head commit, pull request 8, and the list of pull requests.
    """

    deeper = checkout / "docs" / "deep" / "deeper"
    deeper.mkdir(parents=True)
    (deeper / "leaf.md").write_text("# Leaf\n\nA file three folders down.\n", encoding="utf-8")
    head = subprocess.run(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        env=git_env(checkout.parent),
    ).stdout.strip()
    (checkout / "docs" / "links.md").write_text(
        "# Links\n\n- [The leaf](deep/deeper/leaf.md)\n"
        f"- [The head commit]({CANONICAL}/commit/{head})\n"
        f"- [Pull request 8]({CANONICAL}/pull/8)\n"
        f"- [The pull requests]({CANONICAL}/pulls)\n",
        encoding="utf-8",
    )
    long = checkout / "long"
    long.mkdir()
    for index in range(LONG_FOLDER_FILES):
        (long / f"f{index:03d}.txt").write_text(f"{index}\n", encoding="utf-8")


def build_history(directory: Path) -> tuple[Path, list[str]]:
    """A repository of HISTORY_COMMITS commits on one branch; its revisions, newest first."""

    repository = directory / "history"
    env = git_env(directory)
    subprocess.run(
        ["git", "init", "-q", "--template=", "-b", "main", str(repository)],
        check=True,
        capture_output=True,
        env=env,
    )
    stream = []
    for index in range(1, HISTORY_COMMITS + 1):
        message = f"commit {index}\n".encode()
        content = f"{index}\n".encode()
        stream.append(
            b"commit refs/heads/main\n"
            + f"mark :{index}\ncommitter T <t@example.com> {1_700_000_000 + index * 60} +0000\n".encode()
            + f"data {len(message)}\n".encode()
            + message
            + (f"from :{index - 1}\n".encode() if index > 1 else b"")
            + f"M 644 inline f{index % 7}.txt\ndata {len(content)}\n".encode()
            + content
            + b"\n"
        )
    stream.append(b"done\n")
    subprocess.run(
        ["git", "-C", str(repository), "fast-import", "--quiet", "--done"],
        check=True,
        capture_output=True,
        input=b"".join(stream),
        env=env,
    )
    subprocess.run(
        ["git", "-C", str(repository), "checkout", "-q", "main"],
        check=True,
        capture_output=True,
        env=env,
    )
    revisions = subprocess.run(
        ["git", "-C", str(repository), "log", "--format=%H"],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    ).stdout.split()
    return repository, revisions


def _serve(root: Path, env: dict[str, str], log: Path) -> subprocess.Popen[str]:
    with log.open("w", encoding="utf-8") as output:
        # --exit-on-eof: closing stdin stops the server however this test ends.
        return subprocess.Popen(
            [str(_METAB), str(root), "--no-open", "--port", str(_free_port()), "--exit-on-eof"],
            stdin=subprocess.PIPE,
            stdout=output,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
            start_new_session=True,
        )


def test_every_route_to_an_item_reveals_it_in_the_navigation_pane(
    tmp_path: Path, pull_origin: Origin, chrome_profile: Path
) -> None:
    chrome = require_chrome()
    node = require_node()
    checkout = clone_checkout(pull_origin, tmp_path / "checkout")
    add_reveal_files(checkout)
    history, revisions = build_history(tmp_path)
    fake = install_fake_gh(tmp_path, stacks_scenario(pull_origin))
    env = {name: value for name, value in os.environ.items() if not name.startswith("GIT_")}
    env.update(fake)
    tools = _private(tmp_path / "tools")
    (tools / "git").symlink_to(require_git())
    env["PATH"] = f"{tmp_path / 'fake-gh-bin'}{os.pathsep}{tools}"
    env["METABROWSER_CONFIG_DIR"] = str(_private(tmp_path / "config"))
    env["METABROWSER_LOG_LEVEL"] = "WARNING"
    pulls_log = tmp_path / "server.log"
    history_log = tmp_path / "history.log"
    servers: list[subprocess.Popen[str]] = []
    try:
        servers.append(
            _serve(
                checkout,
                {**env, "METABROWSER_CACHE_DIR": str(_private(tmp_path / "cache"))},
                pulls_log,
            )
        )
        servers.append(
            _serve(
                history,
                {**env, "METABROWSER_CACHE_DIR": str(_private(tmp_path / "history-cache"))},
                history_log,
            )
        )
        ports = []
        for server, log in zip(servers, (pulls_log, history_log), strict=True):
            port = _read_port(server, log)
            _wait_until_serving(server, port, log)
            ports.append(port)
        shots = os.environ.get("METABROWSER_NAV_REVEAL_SHOTS")
        # A commit halfway down the history: past the rows a first paint mounts.
        deep_commit = revisions[HISTORY_COMMITS // 2]
        run = run_in_own_group(
            [
                node,
                str(SESSION),
                f"http://127.0.0.1:{ports[0]}",
                f"http://127.0.0.1:{ports[1]}",
                deep_commit,
            ],
            timeout_s=_MEASUREMENT_BUDGET_S,
            env={
                **os.environ,
                "CHROME_BIN": chrome,
                "CHROME_PROFILES": str(chrome_profile),
                **({"SHOTS_DIR": shots} if shots else {}),
            },
        )
    finally:
        for server in servers:
            _stop_server(server)
    if run.timed_out:
        pytest.fail(f"ran past {_MEASUREMENT_BUDGET_S:g} s; its steps:\n{run.stderr}")
    # Each step's time, shown with the output when it fails.
    print(run.stderr)
    assert run.returncode == 0, (
        f"{run.stderr[-6000:]}\nserver: {_log_tail(pulls_log)}\nhistory: {_log_tail(history_log)}"
    )
    passed = re.fullmatch(r"nav reveal in Chrome: (\d+) checks passed\n", run.stdout)
    assert passed is not None and int(passed.group(1)) > 0, run.stdout
