"""Exact browserless file-navigation lazy-asset contracts."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SHIM = Path(__file__).resolve().parent / "dom" / "file-navigation-lazy-asset-session.js"
APP_JS = REPO_ROOT / "src" / "metabrowser" / "static" / "app.js"


def test_navigation_assets_share_ownership_and_failure_semantics() -> None:
    if shutil.which("node") is None:
        pytest.skip("node not available; skipping file-navigation browserless session")
    result = subprocess.run(
        ["node", str(SHIM), str(REPO_ROOT)],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)

    assert payload["dependencyFailure"] == {
        "error": "compositor unavailable",
        "status": "error",
    }
    assert payload["samePathRevalidation"] == {
        "cachedRevision": "B",
        "dirty": False,
        "etag": '"B"',
        "lateOlderCommit": "cancelled",
        "markerSharedByPendingRequests": True,
        "newerCommit": "file",
        "newerSettled": True,
        "olderAbort": {"status": "cancelled"},
        "replacementSawDirty": True,
    }
    assert payload["fileToFolderEventRace"] == {
        "cacheRetained": False,
        "dirty": True,
        "etagRetained": False,
        "folderCommit": "folder",
        "olderMarkerSettled": False,
    }
    assert payload["missingValidatorResponse"] == {
        "cachedRevision": "fresh",
        "dirty": False,
        "noValidatorCommit": "file",
        "noValidatorSettled": True,
        "validatorRetained": False,
    }
    assert payload["boundedInvalidations"] == {
        "oldestRetained": False,
        "retained": ["two.md", "three.md"],
        "size": 2,
    }
    assert payload["authoritativeSnapshot"] == {
        "actions": [
            ["install", ["lazy/deep.md", "kept.jsonl", "new.jsonl"]],
            ["retire", "gone.jsonl", False],
            ["upsert", "kept.jsonl", True],
            ["upsert", "new.jsonl", True],
        ],
        "active": ["new.jsonl"],
        "lazyRows": ["lazy/deep.md"],
        "paths": ["lazy/deep.md", "kept.jsonl", "new.jsonl"],
    }


def test_shell_delegates_file_ownership_to_navigation_module() -> None:
    source = APP_JS.read_text()
    selection = source[
        source.index("async function selectFile(") : source.index("function openedFileOutcome(")
    ]

    assert "createFileRevalidationTracker(ETAG_REVALIDATE_MAX)" in source
    assert "fileNeedsRevalidate.capture(path)" in selection
    assert "fileNeedsRevalidate.delete(path)" not in selection
    assert selection.count("fileNeedsRevalidate.settle(path, revalidationMarker)") == 2
    assert "MetabrowserNavigationRoute.commitFreshFileResponse" in selection
    assert "MetabrowserNavigationRoute.settleFileSelectionFailure" in source
    assert "MetabrowserNavigationRoute.settleNavigationDependency" in source
    assert source.count("MetabrowserNavigationRoute.replaceFileSnapshot") == 2
