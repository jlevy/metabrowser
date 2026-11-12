"""The Chrome for tests whose behavior is layout or paint, or a skip.

Chrome is not a prerequisite of this repository, so its absence skips with the reason
"Chrome is not installed"; strict mode turns that skip into a failure in CI, whose runners
have Chrome. ``CHROME_BIN`` names one. The lookup is the one the transition instrument's
tests use (``require_chrome``, on its own branch); one of the two goes when both are on
main.
"""

from __future__ import annotations

import os
import shutil

import pytest

MAC_CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
CHROME_NAMES = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser")


def find_chrome() -> str:
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
