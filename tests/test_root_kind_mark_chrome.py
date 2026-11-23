"""The mark before the root's name, for each of three kinds of root, drawn in a real Chrome.

The owner asked, 2026-11-20, that the root's name at the top of the navigation lead with an
icon for what is open (a cloud mirror, a local Git checkout, or a local plain folder), that
its tooltip name the kind, and that none read as the folder icon of an ordinary subfolder
(docs/design-system.md, "Source Kind Marks"). Which kind a root is, its words, and its
sentence are ``/api/identity``'s, pinned by ``cli-api-shell.tryscript.md``, and the shell
writing the same into its first paint is ``tests/test_root_identity.py``'s. What only a
browser tells is the mark itself, so this serves a plain folder, a checkout, and a mirror
with ``metab`` and reads each page's mark in one Chrome (``tests/dom/root-kind-mark-chrome.mjs``):
its box, its place with the name inside the Home link, its glyph and ink, and its tooltip,
in both themes. It also exercises the Home link and adjacent details chevron with real clicks.

Without Chrome or Node this skips (``require_chrome``, ``require_node``), and a mirror
needs Git. The test owns everything it starts: each server stops when its stdin closes, and
the measuring Node process leads a process group of its own, which Chrome joins
(tests/process_group.py). ``METABROWSER_ROOT_KIND_SHOTS`` names a directory to keep its
screenshots in; unset, they are written under the test's temporary directory.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from tests.process_group import GROUP_STOP_S, PROFILE_TEARDOWN_S, run_in_own_group
from tests.required_tools import needs_git, require_chrome, require_git, require_node
from tests.source_checkout_fixture import git
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

SESSION = Path(__file__).resolve().parent / "dom" / "root-kind-mark-chrome.mjs"
GLYPH_FILE = (
    Path(__file__).resolve().parent.parent
    / "src"
    / "metabrowser"
    / "static"
    / "source-kind-glyphs.json"
)
MIRROR_FIXTURE = Path(__file__).resolve().parent / "source_mirror_fixture.py"
_METAB = Path(sys.executable).with_name("metab")
SHOTS_ENV = "METABROWSER_ROOT_KIND_SHOTS"
# A cold Chrome start, which tests/dom/chrome-session.mjs bounds at 30 s, then three pages in
# two themes, each with a tooltip waited for twice, and eighteen screenshots.
_MEASUREMENT_BUDGET_S = 120.0
_SERVERS = 3
LIFECYCLE_S = (
    _SERVERS * (_BANNER_BUDGET_S + _SERVING_BUDGET_S + _SERVER_STOP_S)
    + _MEASUREMENT_BUDGET_S
    + GROUP_STOP_S
    + PROFILE_TEARDOWN_S
)
pytestmark = [
    pytest.mark.timeout(LIFECYCLE_S + 60),
    pytest.mark.skipif(os.name != "posix", reason="the mirror fixture's Git environment is POSIX"),
    needs_git,
]


def _kind_glyphs() -> dict[str, dict[str, str]]:
    """What the server draws for each kind, from the file it reads."""

    return json.loads(GLYPH_FILE.read_text(encoding="utf-8"))


def _serve(
    argument: str, tmp_path: Path, name: str, env: dict[str, str]
) -> tuple[subprocess.Popen[str], Path, str]:
    """A server for *argument*, started and answering: the process, its log, and its address."""

    log = tmp_path / f"{name}.log"
    with log.open("w", encoding="utf-8") as output:
        # --exit-on-eof: closing stdin stops the server however this test ends.
        server = subprocess.Popen(
            [str(_METAB), argument, "--no-open", "--port", str(_free_port()), "--exit-on-eof"],
            stdin=subprocess.PIPE,
            stdout=output,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
            start_new_session=True,
        )
    port = _read_port(server, log)
    _wait_until_serving(server, port, log)
    return server, log, f"http://127.0.0.1:{port}/view/"


def test_each_kind_of_root_draws_its_mark_before_its_name_in_chrome(
    tmp_path: Path, chrome_profile: Path
) -> None:
    chrome = require_chrome()
    node = require_node()
    base_env = {name: value for name, value in os.environ.items() if not name.startswith("GIT_")}
    base_env["METABROWSER_LOG_LEVEL"] = "WARNING"
    base_env["METABROWSER_RECORD_RECENT"] = "0"
    base_env["METABROWSER_CONFIG_DIR"] = str(_private(tmp_path / "config"))
    # The servers' PATH holds Git and a `gh` that fails at once and nothing else: a checkout
    # of a GitHub repository asks `gh` for its pull requests, which no real one may answer,
    # and which the suite's own stand-in would count as a call a test made.
    tools = tmp_path / "tools"
    tools.mkdir()
    (tools / "git").symlink_to(require_git())
    (tools / "gh").write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    (tools / "gh").chmod(0o755)
    base_env["PATH"] = str(tools)

    plain = tmp_path / "plain"
    (plain / "docs").mkdir(parents=True)
    (plain / "README.md").write_text("# A plain folder\n", encoding="utf-8")
    (plain / "preview.html").write_text(
        "<!doctype html><html><body><p>Preview content</p>"
        "<script>parent.postMessage('root-kind-preview-ready', '*')</script>"
        "</body></html>\n",
        encoding="utf-8",
    )
    # A real checkout lets the branch chip offer a local pin without contacting GitHub.
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    branch = "topic/a-branch-name-that-stays-readable-when-the-nav-gets-narrow"
    git(checkout, "init", "-q", "--template=", "-b", branch)
    (checkout / "README.md").write_text("# A checkout\n", encoding="utf-8")
    git(checkout, "add", "README.md")
    git(checkout, "commit", "-q", "-m", "Checkout for the root details menu")
    git(checkout, "remote", "add", "origin", "git@github.com:Octo/Demo.git")
    git(checkout, "update-ref", f"refs/remotes/origin/{branch}", "HEAD")
    # A mirror that the cache already holds: a cache hit needs no clone, as the source golden's.
    mirror_home = tmp_path / "mirror"
    mirror_home.mkdir()
    built = subprocess.run(
        [sys.executable, str(MIRROR_FIXTURE), str(mirror_home)],
        check=False,
        capture_output=True,
        text=True,
        env=base_env,
    )
    assert built.returncode == 0, built.stderr or built.stdout

    servers: list[subprocess.Popen[str]] = []
    pages: dict[str, str] = {}
    logs: list[Path] = []
    try:
        for kind, argument, env in (
            ("folder", str(plain), {}),
            ("git", str(checkout), {}),
            (
                "mirror",
                f"file://{mirror_home / 'origin.git'}",
                {"METABROWSER_CACHE_DIR": str(mirror_home / "home")},
            ),
        ):
            server, log, url = _serve(argument, tmp_path, kind, {**base_env, **env})
            servers.append(server)
            logs.append(log)
            pages[kind] = url
        glyphs = {kind: entry["elements"] for kind, entry in _kind_glyphs().items()}
        shots = Path(os.environ.get(SHOTS_ENV) or tmp_path / "shots")
        shots.mkdir(parents=True, exist_ok=True)
        run = run_in_own_group(
            [node, str(SESSION), json.dumps(pages), json.dumps(glyphs), str(shots)],
            timeout_s=_MEASUREMENT_BUDGET_S,
            env={**os.environ, "CHROME_BIN": chrome, "CHROME_PROFILES": str(chrome_profile)},
        )
    finally:
        for server in servers:
            _stop_server(server)
    if run.timed_out:
        pytest.fail(f"ran past {_MEASUREMENT_BUDGET_S:g} s; its steps:\n{run.stderr}")
    print(run.stderr)
    assert run.returncode == 0, f"{run.stderr[-6000:]}\nservers: {[_log_tail(log) for log in logs]}"
    passed = re.fullmatch(r"root kind marks in Chrome: (\d+) checks passed\n", run.stdout)
    assert passed is not None and int(passed.group(1)) > 0, run.stdout
    # One screenshot of each kind's navigation heading in each theme, with its tooltip, with details open, and at rest.
    assert sorted(path.name for path in shots.glob("root-kind-*.png")) == sorted(
        f"root-kind-{kind}-{theme}{suffix}.png"
        for kind in pages
        for theme in ("light", "dark")
        for suffix in ("", "-tooltip", "-details")
    )
