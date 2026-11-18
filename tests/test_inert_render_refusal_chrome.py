"""A Markdown document the server refuses to render shows its source and why, in Chrome.

``tests/dom/inert-render-refusal-chrome.mjs`` serves a folder ``--untrusted`` whose README
and one document take KPress seconds to render, past a deadline shortened to half a
second, beside a document that renders. In headless Chrome the folder Overview's README
panel and the document's Document tab each show one warning notice saying why, and the
source in the render's place, with no render-error box and no KPress document; reloading
the document is refused from the server's memory, and the fine document renders inert.
The notice and the source view are drawn by the browser's stylesheets and the shell's
view mounting, which only a browser runs; what each draws for each refusal is pinned
without one in ``tests/dom/markdown-render-refusal-session.js``, and the route's refusal
in ``tests/test_inert_render_deadline.py``, a served pin's among them.

Without Chrome this skips (``require_chrome`` in ``tests/required_tools.py``).
"""

from __future__ import annotations

import json
import os
import socket
import sys
from pathlib import Path

import pytest

from tests.process_group import GROUP_STOP_S, PROFILE_TEARDOWN_S, run_in_own_group
from tests.required_tools import require_chrome, require_node

SESSION = Path(__file__).resolve().parent / "dom" / "inert-render-refusal-chrome.mjs"
# A server start, one Chrome, and four pages, two of them waiting out the shortened
# deadline and a child's start, took 25.8 s on a Mac at a load average near 10. A cold
# Chrome start in CI has taken 28.2 s (the Overview alignment test, 2026-11-14), and the
# server's start is bounded at 60 s inside the session, so the bound leaves room for both.
SESSION_TIMEOUT_S = 100
# The longest the test can take: the session's bound, its process group stopped after it
# (Chrome and the server are in it), and the profile's teardown (tests/process_group.py),
# with 10 s more for the rest of the setup; tests/test_process_group.py holds the sum under
# the module's limit.
LIFECYCLE_S = SESSION_TIMEOUT_S + GROUP_STOP_S + PROFILE_TEARDOWN_S
pytestmark = pytest.mark.timeout(LIFECYCLE_S + 10)
_METAB = Path(sys.executable).with_name("metab")
# The shape the review of mb-273l timed at 23.1 s for 239 KB: seconds at this size, far
# past the session's deadline on any machine.
SLOW = "[" * 100 + "%" * (60 * 1024)
DEADLINE_MS = 500


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def test_a_refused_document_shows_its_source_under_one_notice_in_chrome(
    tmp_path: Path, chrome_profile: Path
) -> None:
    chrome = require_chrome()
    root = tmp_path / "served"
    (root / "docs").mkdir(parents=True)
    (root / "README.md").write_text(SLOW, encoding="utf-8")
    (root / "docs" / "slow.md").write_text(f"{SLOW}\nslow\n", encoding="utf-8")
    (root / "docs" / "fine.md").write_text("# Fine\n\nThis document renders.\n", encoding="utf-8")
    state = tmp_path / "state"
    state.mkdir()
    result = run_in_own_group(
        [
            require_node(),
            str(SESSION),
            str(_METAB),
            str(root),
            str(_free_port()),
            str(state),
            "docs/slow.md",
            "docs/fine.md",
            "--untrusted",
        ],
        timeout_s=SESSION_TIMEOUT_S,
        env={
            **os.environ,
            "CHROME_BIN": chrome,
            "CHROME_PROFILES": str(chrome_profile),
            "METABROWSER_INERT_RENDER_DEADLINE_MS": str(DEADLINE_MS),
        },
    )
    assert not result.timed_out, (
        f"the session ran past {SESSION_TIMEOUT_S} s: {result.stderr or result.stdout}"
    )
    assert result.returncode == 0, result.stderr or result.stdout
    record = json.loads(result.stdout.strip().splitlines()[-1])
    said = "This document took longer than 0.5 seconds to render, so its source is shown."
    readme, slow, reload = record["readme"], record["slow"], record["reload"]
    assert readme["inReadmePanel"] is True
    assert readme["notice"] == f"{said} Open the file"
    assert readme["link"] == "/view/README.md"
    assert slow["inReadmePanel"] is False
    assert slow["notice"] == said
    for page in (readme, slow, reload):
        assert page["code"] == "render_deadline"
        assert page["severity"] == "warning"
        assert page["sourceLines"] == 1
        assert page["sourceStart"] == "[" * 24
        assert page["renderError"] is False
        assert page["panelError"] is False
        assert page["kpressDocument"] is False
    fine = record["fine"]
    assert fine["kpressDocument"] is True
    assert fine["heading"] == "Fine"
    assert fine["notice"] is None
