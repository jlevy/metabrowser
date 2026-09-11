"""Browserless coverage for the persisted document reading-width setting."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

SESSION_JS = Path(__file__).resolve().parent / "dom" / "document-width-session.js"


def test_document_width_session() -> None:
    if shutil.which("node") is None:
        pytest.skip("node not available")
    result = subprocess.run(
        ["node", str(SESSION_JS)],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, (
        f"Document-width session failed:\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    payload = json.loads(result.stdout)
    assert payload["authority"]["default"] == 102
    assert payload["storedProfiles"] == {"existing": 118, "fresh": 102, "malformed": 102}
    assert payload["committedApply"]["persisted"] == "102"
