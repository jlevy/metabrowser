"""The pull request header's reserved box, laid out by headless Chrome.

The header keeps one height from first paint whatever its record holds, and that is
layout: no browserless DOM computes it, and the stylesheet text passed while the state
badge hung below its line (PR 370 review A3). This mounts the production page module on
recorded records in a real engine, with the shell's stylesheets and KPress's faces, and
compares each row with the empty record's (tests/dom/github-pull-header-chrome.mjs).

Chrome is not a prerequisite of this repository, so without one this skips; strict mode
turns that skip into a failure in CI, whose runners have Chrome. ``CHROME_BIN`` names one.
The lookup is the one the transition instrument's tests use (``require_chrome``, on its
own branch); one of the two goes when both are on main.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from metabrowser import kpress_adapter
from tests.required_tools import require_node

SESSION = Path(__file__).resolve().parent / "dom" / "github-pull-header-chrome.mjs"
MAC_CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
CHROME_NAMES = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser")


def _chrome() -> str:
    named = os.environ.get("CHROME_BIN")
    if named:
        return named
    if os.path.exists(MAC_CHROME):
        return MAC_CHROME
    for name in CHROME_NAMES:
        found = shutil.which(name)
        if found is not None:
            return found
    pytest.skip("Chrome is not installed")


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
    chrome = _chrome()
    result = subprocess.run(
        [require_node(), str(SESSION)],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
        env={
            **os.environ,
            "CHROME_BIN": chrome,
            "KPRESS_STATIC": str(_kpress_faces(tmp_path / "kpress")),
        },
    )
    assert result.returncode == 0, result.stderr or result.stdout
    assert re.fullmatch(r"pull header in Chrome: \d+ checks passed\n", result.stdout), result.stdout
