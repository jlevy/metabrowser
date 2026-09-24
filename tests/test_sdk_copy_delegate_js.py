"""Behavioral checks for the SDK-owned copy delegate and the shell's delegated controls."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

COPY_DELEGATE_TEST_JS = Path(__file__).resolve().parent / "dom" / "sdk-copy-delegate-behavior.js"


def test_sdk_copy_delegate_behavior() -> None:
    if shutil.which("node") is None:
        pytest.skip("node not available")
    result = subprocess.run(
        ["node", str(COPY_DELEGATE_TEST_JS)],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, (
        f"copy delegate behavior failed:\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    assert "sdk copy delegate OK" in result.stdout


SHELL_DELEGATE_SESSION = Path(__file__).resolve().parent / "dom" / "shell-delegate-owner-session.js"


def test_shell_delegates_act_only_on_controls_the_page_created() -> None:
    """A trusted document's copy of a crumb, print, or tooltip control does nothing.

    KPress keeps class, id, and data-* in a trusted folder, so Markdown can spell the
    shell's control markup. The address crumbs, parent button, and print button act only
    with the SDK's per-page owner mark, and the tooltip ignores a rendered document.
    """

    if shutil.which("node") is None:
        pytest.skip("node not available")
    result = subprocess.run(
        ["node", str(SHELL_DELEGATE_SESSION)],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    transcript = json.loads(result.stdout)
    assert transcript["failures"] == []
    assert transcript["authoredCalls"] == []
    assert "print" in transcript["pageCalls"]
