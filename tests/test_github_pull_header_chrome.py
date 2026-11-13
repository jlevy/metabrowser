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
# The parts the session runs in, each in a browser of its own (--part in the session).
PARTS = ("header-wide", "header-middle", "header-narrow", "pulls", "badges")
# Whole, the session took about 18 s on a Mac and ran past 45 s on a CI runner. In parts,
# on a Mac at a load average of 10 to 12, each header part took 9.8 to 10.0 s, the Pulls
# rows 6.1 s, and the run badge 6.1 s: with 4 checks, the badge part is mostly Chrome's
# launch and the page's load. 40 s gives a runner four times this machine's time for the
# largest part, and fires before the suite's 60.
SESSION_TIMEOUT_S = 40


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
    result = subprocess.run(
        [require_node(), str(SESSION), "--part", part],
        capture_output=True,
        text=True,
        timeout=SESSION_TIMEOUT_S,
        check=False,
        env={
            **os.environ,
            "CHROME_BIN": chrome,
            "KPRESS_STATIC": str(_kpress_faces(tmp_path / "kpress")),
        },
    )
    assert result.returncode == 0, result.stderr or result.stdout
    passed = re.fullmatch(rf"pull header in Chrome, {part}: (\d+) checks passed\n", result.stdout)
    assert passed is not None and int(passed.group(1)) > 0, result.stdout
