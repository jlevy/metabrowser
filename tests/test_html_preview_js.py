"""Production HTML-preview registration, sandbox tokens, and lifecycle."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SESSION_JS = Path(__file__).resolve().parent / "dom" / "html-preview-session.js"
PLUGIN_ROOT = REPO_ROOT / "src" / "metabrowser" / "builtin_plugins" / "html"


def test_html_preview_session() -> None:
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
        f"HTML preview session failed:\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    assert json.loads(result.stdout) == {
        "cancellation": {
            "cancelledBeforeSettle": True,
            "lateHandleDisposed": True,
            "status": "cancelled",
        },
        "composition": {
            "assetRequests": ["html", "html", "html"],
            "cancelledPreparation": "cancelled",
            "initialView": "preview",
            "missingRenderer": True,
            "registeredAfterAssets": True,
            "sourceRegistered": True,
        },
        "disposal": {
            "activeContainerCount": 1,
            "idempotent": True,
            "secondDetached": True,
            "secondSrcCleared": True,
        },
        "error": {
            "accessible": True,
            "committed": True,
            "logged": ["broken renderer"],
            "status": "error",
        },
        "firstMount": {
            "childCount": 1,
            "className": "file-html-preview",
            "committed": True,
            "hasAllowSameOrigin": False,
            "hasAllowTopNavigation": False,
            "hasInlineHandler": False,
            "rawUrl": "/raw/docs/%3Cunsafe%20%22quoted%22%20%26%20file%3E.html",
            "referrerPolicy": "no-referrer",
            "sandbox": "allow-scripts allow-popups allow-forms allow-downloads",
            "status": "mounted",
            "tagName": "IFRAME",
            "title": 'docs/<unsafe "quoted" & file>.html',
        },
        "innerHtmlWrites": 0,
        "replacement": {
            "committed": True,
            "firstDetached": True,
            "secondRawUrl": "/raw/docs/100%25.html",
            "staleCommitRejected": True,
            "staleCommitPreservedReplacement": True,
            "status": "mounted",
        },
    }


def test_html_preview_styles_and_rendering_are_plugin_owned() -> None:
    core_app = (REPO_ROOT / "src/metabrowser/static/app.js").read_text(encoding="utf-8")
    core_css = (REPO_ROOT / "src/metabrowser/static/styles.css").read_text(encoding="utf-8")
    plugin_css = PLUGIN_ROOT.joinpath("styles.css").read_text(encoding="utf-8")
    plugin_js = PLUGIN_ROOT.joinpath("index.js").read_text(encoding="utf-8")

    assert "file-html-preview" not in core_app
    assert "file-html-preview" not in core_css
    assert ".metabrowser-html-host .file-html-preview" in plugin_css
    assert 'PREVIEW_SANDBOX = "allow-scripts allow-popups allow-forms allow-downloads"' in plugin_js
