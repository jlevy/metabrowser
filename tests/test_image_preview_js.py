"""Production image-preview registration, DOM construction, and lifecycle."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SESSION_JS = Path(__file__).resolve().parent / "dom" / "image-preview-session.js"
PLUGIN_ROOT = REPO_ROOT / "src" / "metabrowser" / "builtin_plugins" / "image"


def test_image_preview_session() -> None:
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
        f"Image preview session failed:\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    assert json.loads(result.stdout) == {
        "cancellation": {
            "cancelledBeforeSettle": True,
            "lateHandleDisposed": True,
            "status": "cancelled",
        },
        "composition": {
            "assetRequests": ["image", "image", "image"],
            "cancelledPreparation": "cancelled",
            "initialView": "preview",
            "missingRenderer": True,
            "registeredAfterAssets": True,
        },
        "disposal": {
            "activeContainerCount": 1,
            "idempotent": True,
            "secondDetached": True,
        },
        "error": {
            "accessible": True,
            "committed": True,
            "logged": ["broken renderer"],
            "status": "error",
        },
        "firstMount": {
            "alt": 'images/<unsafe "quoted" & file>.png',
            "childCount": 1,
            "className": "file-image",
            "committed": True,
            "hasInlineHandler": False,
            "rawUrl": "/raw?path=images%2F%3Cunsafe%20%22quoted%22%20%26%20file%3E.png",
            "status": "mounted",
            "tagName": "IMG",
        },
        "innerHtmlWrites": 0,
        "replacement": {
            "committed": True,
            "firstDetached": True,
            "secondAlt": "next/diagram #2.svg",
            "secondRawUrl": "/raw?path=next%2Fdiagram%20%232.svg",
            "staleCommitRejected": True,
            "staleCommitPreservedReplacement": True,
            "status": "mounted",
        },
    }


def test_image_preview_styles_and_rendering_are_plugin_owned() -> None:
    core_app = (REPO_ROOT / "src/metabrowser/static/app.js").read_text(encoding="utf-8")
    core_css = (REPO_ROOT / "src/metabrowser/static/styles.css").read_text(encoding="utf-8")
    plugin_css = PLUGIN_ROOT.joinpath("styles.css").read_text(encoding="utf-8")

    assert 'data.type === "image"' not in core_app
    assert ".file-image" not in core_css
    assert ".metabrowser-image-host .file-image" in plugin_css
