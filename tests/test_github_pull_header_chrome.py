"""The pull request header's reserved box, laid out by headless Chrome.

The header keeps one height from first paint whatever its record holds, and that is
layout: no browserless DOM computes it, and the stylesheet text passed while the state
badge hung below its line. This mounts the production page module on
recorded records in a real engine, with the shell's stylesheets and KPress's faces, and
compares each row with the empty record's (tests/dom/github-pull-header-chrome.mjs). The
same session lays out Pulls rows as their stack positions arrive, and a file header as a
run's status badge changes its label in place, and checks that nothing moves. It runs in
parts, one case each, so each part has a bound of its own under the suite's.

Without Chrome this skips (``require_chrome`` in ``tests/required_tools.py``).
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

from metabrowser import kpress_adapter
from tests.required_tools import require_chrome, require_node

SESSION = Path(__file__).resolve().parent / "dom" / "github-pull-header-chrome.mjs"
# The parts the session runs in, each in a browser of its own (--part in the session),
# `launch` first: it takes the first Chrome start of the job. On a CI runner the first
# part took 10 to 20 s where the same part took 10 s elsewhere, and once ran to its 40 s
# bound (header-wide, run 43496743423). The launcher read Chrome's DevTools port before
# Chrome answered on it, and the throw left Chrome running, which held the session open
# until the bound; it reproduced here once under load, as "fetch failed" and a session
# that did not end. tests/dom/chrome-session.mjs now waits for the answer and stops
# Chrome on a failed start.
PARTS = (
    "launch",
    "header-wide",
    "header-middle",
    "header-narrow",
    "offers",
    "pulls",
    "badges",
)
# On a Mac at a load average of 10 to 16, each header part took 5.0 to 6.7 s, the Pulls
# rows 1.4 to 2.6 s, the offers and the run badge 1.4 to 1.7 s, and the launch 1.3 to
# 1.4 s, once Chrome's exit stopped holding each process open 5 s more. A CI runner took
# about as long as this machine once its first Chrome had started. 40 s leaves the
# largest part six times that, and fires before the suite's 60.
SESSION_TIMEOUT_S = 40
# The first start's own bound, as long as the suite's gates allow an inner one.
LAUNCH_TIMEOUT_S = 48


def _kpress_faces(into: Path) -> Path:
    text = kpress_adapter.get_kpress_static_asset("css/style-tokens.css").content.decode("utf-8")
    (into / "css").mkdir(parents=True)
    (into / "css" / "style-tokens.css").write_text(text, encoding="utf-8")
    for relative in sorted(set(re.findall(r'url\("\.\./([^"]+)"\)', text))):
        target = into / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(kpress_adapter.get_kpress_static_asset(relative).content)
    return into


@pytest.mark.parametrize("part", PARTS)
def test_the_pull_header_keeps_its_box_in_chrome(tmp_path: Path, part: str) -> None:
    chrome = require_chrome()
    bound = LAUNCH_TIMEOUT_S if part == "launch" else SESSION_TIMEOUT_S
    try:
        result = subprocess.run(
            [require_node(), str(SESSION), "--part", part],
            capture_output=True,
            text=True,
            timeout=bound,
            check=False,
            env={
                **os.environ,
                "CHROME_BIN": chrome,
                "KPRESS_STATIC": str(_kpress_faces(tmp_path / "kpress")),
            },
        )
    except subprocess.TimeoutExpired as expired:
        # The steps it finished, each with its time, say where the bound went.
        pytest.fail(f"{part} ran past {bound} s; its steps:\n{expired.stderr or ''}")
    # Each step's time, shown with the case's output when it fails.
    print(result.stderr)
    assert result.returncode == 0, result.stderr or result.stdout
    passed = re.fullmatch(rf"pull header in Chrome, {part}: (\d+) checks passed\n", result.stdout)
    assert passed is not None and int(passed.group(1)) > 0, result.stdout
