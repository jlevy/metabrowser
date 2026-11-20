"""The agents home, the session list, and the Session view in headless Chrome.

``tests/dom/agents-views-chrome.mjs`` drives the production pages against a live ``metab``
that serves the synthetic homes of ``tests/agents_synthetic_home.py``, plus sixty small
Claude Code sessions so the list has a second page, a plain folder, and an exported
transcript that is in no home. It checks what only a browser can: that a folder holding a
home opens on its home and a plain folder does not, that the views' stylesheet is not in a
plain folder's load, that the list pages, sorts, and filters through clicks, that a session
page and a compressed rollout render with the kind colors in both themes, and that leaving
the home stops its poll. The state machines are pinned without a browser in
``tests/dom/agents-views-session.js``.

Measured on a 10-core Mac, 2026-11-20, load average near 10: the server's banner in about
2 s, the six synthetic sessions' summaries in under a second, and the whole session in about
20 s, of which the wait for a left view's poll to stay silent is ``LIVE_POLL_MS`` plus 1.5 s.
Cold Chrome starts took 28 s in CI (tests/test_folder_overview_alignment.py), which the
bound leaves room for.

Without Chrome this skips (``require_chrome`` in ``tests/required_tools.py``).
"""

from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import sys
from pathlib import Path

import pytest

from metabrowser.cli.http_readiness import wait_for_http_ok_then
from tests import agents_synthetic_home as synthetic
from tests.process_group import GROUP_STOP_S, PROFILE_TEARDOWN_S, run_in_own_group
from tests.required_tools import require_chrome, require_node

SESSION = Path(__file__).resolve().parent / "dom" / "agents-views-chrome.mjs"
PLUGIN = Path(__file__).resolve().parents[1] / "src/metabrowser/builtin_plugins/agents"
_METAB = Path(sys.executable).with_name("metab")
_SERVING_LINE = re.compile(r"^Serving .* at http://127\.0\.0\.1:(\d+)/view/", re.MULTILINE)

# Sessions added to the synthetic homes so the list has a second page.
BULK = 60
BANNER_BUDGET_S = 30.0
SERVING_BUDGET_S = 15.0
# The session's own bound: one cold Chrome start, the pages, and the silent wait.
SESSION_TIMEOUT_S = 120
SERVER_STOP_S = 5.0
LIFECYCLE_S = (
    BANNER_BUDGET_S
    + SERVING_BUDGET_S
    + SESSION_TIMEOUT_S
    + GROUP_STOP_S
    + 2 * SERVER_STOP_S
    + PROFILE_TEARDOWN_S
)
pytestmark = pytest.mark.timeout(LIFECYCLE_S + 10)


def _constant(path: str, name: str) -> int:
    """A number a module in the plugin defines, so this test never restates it."""

    match = re.search(rf"export const {name} = ([\d_]+);", (PLUGIN / path).read_text())
    assert match is not None, f"{path} no longer exports {name}"
    return int(match.group(1).replace("_", ""))


def _serve_root(root: Path) -> None:
    synthetic.build(root)
    bulk = root / ".claude" / "projects" / "-work-bulk"
    for number in range(BULK):
        session = f"bbbbbbbb-0000-4000-8000-{number:012d}"
        records: list[object] = [
            {
                "type": "user",
                **synthetic._env(session, 100 + number, cwd="/work/bulk"),  # pyright: ignore[reportPrivateUsage]
                "message": {"role": "user", "content": f"bulk {number}"},
            }
        ]
        synthetic._write_jsonl(  # pyright: ignore[reportPrivateUsage]
            bulk / f"{session}.jsonl", records, mtime=synthetic.T0 + 100 + number
        )
    (root / "plain").mkdir()
    (root / "plain" / "notes.txt").write_text("a folder that is no home\n", encoding="utf-8")
    synthetic._write_jsonl(  # pyright: ignore[reportPrivateUsage]
        root / "loose" / "export.jsonl", synthetic.claude_s1_records()
    )


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _stop(server: subprocess.Popen[str]) -> None:
    assert server.stdin is not None
    server.stdin.close()
    try:
        server.wait(timeout=SERVER_STOP_S)
    except subprocess.TimeoutExpired:
        server.kill()
        server.wait(timeout=SERVER_STOP_S)


def test_the_agents_views_in_chrome(tmp_path: Path, chrome_profile: Path) -> None:
    chrome = require_chrome()
    node = require_node()
    root = tmp_path / "served"
    _serve_root(root)
    env = {name: value for name, value in os.environ.items() if not name.startswith("GIT_")}
    env["METABROWSER_CACHE_DIR"] = str(tmp_path / "cache")
    env["METABROWSER_CONFIG_DIR"] = str(tmp_path / "config")
    env["METABROWSER_LOG_LEVEL"] = "WARNING"
    log = tmp_path / "server.log"
    with log.open("w", encoding="utf-8") as output:
        server = subprocess.Popen(
            [str(_METAB), str(root), "--no-open", "--port", str(_free_port()), "--exit-on-eof"],
            stdin=subprocess.PIPE,
            stdout=output,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
            start_new_session=True,
        )
    try:
        port = _await_banner(server, log)
        _await_serving(server, port, log)
        reviews = 1
        listed = 12 + BULK
        expectations = {
            "plain": "plain",
            "sessions": 13 + BULK,
            "listed": listed,
            "reviews": reviews,
            "codex": 7,
            "pageSize": _constant("session-list-state.js", "PAGE_SIZE"),
            "livePollMs": _constant("poller.js", "LIVE_POLL_MS"),
            "claude": f".claude/projects/-work-alpha/{synthetic.S1}.jsonl",
            "claudeTitle": "Synthetic session",
            # S1's two resumed lines yield three events (agents_synthetic_home.py).
            "claudeReplayed": 3,
            "claudeChild": (
                f".claude/projects/-work-alpha/{synthetic.S1}/subagents/{synthetic.AGENT_A}.jsonl"
            ),
            "loose": "loose/export.jsonl",
            "rollout": (
                f".codex/sessions/2026/11/18/rollout-2026-11-18T00-00-00-{synthetic.T1}.jsonl.zst"
            ),
            "rolloutTitle": "Gamma thread",
        }
        run = run_in_own_group(
            [node, str(SESSION), f"http://127.0.0.1:{port}", json.dumps(expectations)],
            timeout_s=SESSION_TIMEOUT_S,
            env={**os.environ, "CHROME_BIN": chrome, "CHROME_PROFILES": str(chrome_profile)},
        )
    finally:
        _stop(server)
    if run.timed_out:
        pytest.fail(f"the session ran past {SESSION_TIMEOUT_S} s; its steps:\n{run.stderr}")
    print(run.stderr)
    assert run.returncode == 0, run.stderr or run.stdout
    passed = re.fullmatch(r"agents views in Chrome: (\d+) checks passed\n", run.stdout)
    assert passed is not None and int(passed.group(1)) > 0, run.stdout


def _await_banner(server: subprocess.Popen[str], log: Path) -> int:
    import time

    deadline = time.monotonic() + BANNER_BUDGET_S
    while time.monotonic() < deadline:
        if match := _SERVING_LINE.search(log.read_text(encoding="utf-8", errors="replace")):
            return int(match.group(1))
        if server.poll() is not None:
            pytest.fail(f"the server exited before its banner: {log.read_text()[-2000:]!r}")
        time.sleep(0.05)
    pytest.fail(f"no banner within {BANNER_BUDGET_S:g} s: {log.read_text()[-2000:]!r}")


def _await_serving(server: subprocess.Popen[str], port: int, log: Path) -> None:
    outcome: list[str] = []
    wait_for_http_ok_then(
        "127.0.0.1",
        port,
        f"http://127.0.0.1:{port}/view/",
        on_ready=lambda: outcome.append("ready"),
        on_error=outcome.append,
        is_cancelled=lambda: server.poll() is not None,
        timeout_s=SERVING_BUDGET_S,
    )
    if outcome != ["ready"]:
        pytest.fail(f"the server did not serve: {outcome} {log.read_text()[-2000:]!r}")
