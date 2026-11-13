"""The pull request header's reserved box, laid out by headless Chrome.

The header keeps one height from first paint whatever its record holds, and that is
layout: no browserless DOM computes it, and the stylesheet text passed while the state
badge hung below its line. This mounts the production page module on
recorded records in a real engine, with the shell's stylesheets and KPress's faces, and
compares each row with the empty record's (tests/dom/github-pull-header-chrome.mjs).

Without Chrome this skips (``require_chrome`` in ``tests/required_tools.py``).
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from metabrowser import kpress_adapter
from tests.required_tools import require_chrome, require_node

SESSION = Path(__file__).resolve().parent / "dom" / "github-pull-header-chrome.mjs"
# The session took 9 to 12 s on a Mac at a load average of 10 to 27 (the whole test 11.8 s
# at 9 to 13), so 45 s leaves it room on a loaded runner and fires before the suite's 60.
SESSION_TIMEOUT_S = 45


def _kpress_faces(into: Path) -> Path:
    text = kpress_adapter.get_kpress_static_asset("css/style-tokens.css").content.decode("utf-8")
    (into / "css").mkdir(parents=True)
    (into / "css" / "style-tokens.css").write_text(text, encoding="utf-8")
    for relative in sorted(set(re.findall(r'url\("\.\./([^"]+)"\)', text))):
        target = into / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(kpress_adapter.get_kpress_static_asset(relative).content)
    return into


def test_the_pull_header_keeps_its_box_in_chrome(tmp_path: Path) -> None:
    chrome = require_chrome()
    result = subprocess.run(
        [require_node(), str(SESSION)],
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
    assert re.fullmatch(r"pull header in Chrome: \d+ checks passed\n", result.stdout), result.stdout
