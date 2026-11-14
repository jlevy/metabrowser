"""A /raw answer Chrome keeps under the trusted profile runs nothing after ``--untrusted``.

Reviews A and B of #426 (A1, B1): a versioned ``/raw`` answer kept for a year is replayed
without reaching the server, under whichever profile serves the origin by then. So one
kept while the trusted profile served an SVG, with its ``allow-scripts`` sandbox, would
run the SVG's script when a link to it is followed after the folder is served
``--untrusted`` on the same port, and an untrusted document keeps an absolute link to this
origin. Only a raster image, whose execution headers are the same under both profiles,
is kept (``SECURITY.md``).

``tests/dom/raw-profile-cache-chrome.mjs`` runs one headless Chrome across the two
servers. Before the fix the followed SVG came from the cache with ``allow-scripts`` and
its script ran; now it is asked for again, and the untrusted profile's answer runs
nothing. ``tests/test_raw_versions.py`` checks the headers without a browser. Without
Chrome this skips (``require_chrome`` in ``tests/required_tools.py``).
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest

from tests.required_tools import require_chrome, require_node

SESSION = Path(__file__).resolve().parent / "dom" / "raw-profile-cache-chrome.mjs"
# Two server starts, a Markdown view under each, and four documents opened with a 1 s wait
# after each for a script that may run took 31.2 s on a Mac at a load average near 8, more
# than half the suite's 60 s budget, so the test carries its own, and the session's bound
# fires before it.
SESSION_TIMEOUT_S = 100
_METAB = Path(sys.executable).with_name("metab")


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


@pytest.mark.timeout(120)
def test_a_trusted_answer_kept_by_chrome_runs_nothing_after_untrusted(tmp_path: Path) -> None:
    chrome = require_chrome()
    root = tmp_path / "served"
    root.mkdir()
    state = tmp_path / "state"
    state.mkdir()
    result = subprocess.run(
        [require_node(), str(SESSION), str(_METAB), str(root), str(_free_port()), str(state)],
        capture_output=True,
        text=True,
        timeout=SESSION_TIMEOUT_S,
        check=False,
        env={**os.environ, "CHROME_BIN": chrome},
    )
    assert result.returncode == 0, result.stderr or result.stdout
    record = json.loads(result.stdout.strip().splitlines()[-1])
    # The untrusted document keeps the absolute link to the trusted profile's address.
    assert record["linksKept"] is True
    trusted, untrusted = record["trusted"], record["untrusted"]
    # Under the trusted profile the SVG's script runs, and its answer is revalidated.
    assert trusted["svg"]["scriptRuns"] == 1
    assert "allow-scripts" in trusted["svg"]["sandbox"]
    assert trusted["svg"]["cacheControl"] == "no-cache"
    # After the switch, following the link asks again, and the answer runs nothing.
    assert untrusted["svg"]["fromCache"] is False
    assert untrusted["svg"]["status"] == 200
    assert "allow-scripts" not in untrusted["svg"]["sandbox"]
    assert untrusted["svg"]["scriptRuns"] == 0
    # A raster image is kept for a year under one execution policy, which both profiles
    # send, so its replay after the switch is the answer the untrusted profile gives.
    for answer in (trusted["png"], untrusted["png"]):
        assert answer["cacheControl"] == "private, max-age=31536000, immutable"
        assert "allow-scripts" not in answer["sandbox"]
        assert answer["scriptRuns"] == 0
    assert untrusted["png"]["fromCache"] is True
