"""Browserless coverage for rendered-Markdown TOC scrollspy behavior."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SESSION_JS = Path(__file__).resolve().parent / "dom" / "markdown-toc-scrollspy-session.js"


def test_rendered_markdown_toc_scrollspy_session() -> None:
    if shutil.which("node") is None:
        pytest.skip("node not available")
    result = subprocess.run(
        ["node", str(SESSION_JS), str(REPO_ROOT)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, (
        f"Markdown TOC scrollspy session failed:\nstdout: {result.stdout!r}\n"
        f"stderr: {result.stderr!r}"
    )
    assert '"middle of long implementation plan"' in result.stdout
    assert '"active": "implementation-plan"' in result.stdout
    assert '"enhancedHref": "#implementation-plan"' in result.stdout
    assert '"fragment": "implementation-plan"' in result.stdout
    assert '"renderedMarkdownMount": true' in result.stdout
    assert '"enhancerHadRunAtTocMount": true' in result.stdout
    assert '"collapsedRows": 65' in result.stdout
    assert '"label": "Collapse TOC"' in result.stdout
