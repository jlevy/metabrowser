"""Incremental growth contracts for the source view's chunked loading."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from metabrowser.settings import (
    TEXT_PREVIEW_CHUNK_BYTES,
    TEXT_PREVIEW_MAX_CHUNK_BYTES,
    TEXT_PREVIEW_REQUEST_MAX_BYTES,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SHIM = Path(__file__).resolve().parent / "dom" / "source-append-behavior.js"
NAVIGATION_SHIM = Path(__file__).resolve().parent / "dom" / "source-append-navigation-session.js"
APP_JS = REPO_ROOT / "src" / "metabrowser" / "static" / "app.js"
SOURCE_APPEND_JS = REPO_ROOT / "src" / "metabrowser" / "static" / "source-append.js"


def test_source_append_contracts() -> None:
    if shutil.which("node") is None:
        pytest.skip("node not available")
    result = subprocess.run(
        ["node", str(SHIM), str(REPO_ROOT)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, (
        f"source append contracts failed:\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    assert "source append OK" in result.stdout


def test_source_append_navigation_is_claimed_and_transactional() -> None:
    if shutil.which("node") is None:
        pytest.skip("node not available")
    result = subprocess.run(
        ["node", str(NAVIGATION_SHIM), str(REPO_ROOT)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)

    assert payload["afterFailedRender"] == {
        "cacheIsOriginal": True,
        "content": "old",
        "cursor": 3,
        "nextBytes": 128,
        "truncated": True,
    }
    assert payload["afterRetryCommit"] == {
        "cacheIsOriginal": False,
        "content": "oldnew",
        "cursor": 6,
        "nextBytes": 256,
        "truncated": False,
    }
    assert payload["samePathAba"] == {
        "committed": False,
        "content": "old",
        "nextBytes": None,
    }
    assert payload["cacheReplacement"] == {
        "committed": False,
        "content": "replacement",
        "nextBytes": None,
    }


def test_shell_appends_rather_than_rerendering() -> None:
    """Load more must not rebuild the pane.

    Re-rendering made each click cost the running total rather than the chunk
    it loaded, which is quadratic across a sequence of clicks.
    """
    js = APP_JS.read_text()
    load_more = js[
        js.index("async function loadMoreCurrentText()") : js.index(
            "var LOADING_INDICATOR_DELAY_MS"
        )
    ]

    assert "sourceAppend.nextCacheValue(cached, chunk)" in load_more
    assert "sourceAppend.appendSourceText(document, chunk.content" in load_more
    assert "commitTextChunkCache(path, previewClaim, cached, nextCached, requested)" in load_more
    assert 'assets.ensureAsset("source-append")' in load_more
    assert "await Promise.all([" in load_more
    # The full render survives only as the documented fallback for a view
    # shape the append cannot safely touch.
    append_call = load_more.index("sourceAppend.appendSourceText")
    following = load_more[append_call : append_call + 1_200]
    # The fallback also asserts pane ownership: the Git panel renders into this
    # same pane, so a late chunk must not repaint over it. It keeps the active
    # tab so a reader on the Source tab is not thrown back to the rendered view.
    assert "await renderFile(nextCached, activeView || undefined, previewClaim" in following, (
        "the fallback render should remain reachable"
    )
    assert "onCommit:" in following
    # Appending skips the plugin's render, so the partial-content banner has to
    # be brought back in line or it reports stale byte counts.
    assert "sourceAppend.syncTruncationWarning" in load_more
    assert "highlight_disabled: !!chunk.highlight_disabled" in SOURCE_APPEND_JS.read_text()


def test_chunk_size_is_not_duplicated_across_the_boundary() -> None:
    """The client reads the chunk size rather than restating it."""
    js = APP_JS.read_text()

    assert "METABROWSER_SETTINGS?.TEXT_PREVIEW_CHUNK_BYTES" in js
    assert "METABROWSER_SETTINGS?.TEXT_PREVIEW_MAX_CHUNK_BYTES" in js
    assert "const TEXT_PREVIEW_CHUNK_BYTES = 128 * 1024;" not in js


def test_text_preview_sizes_are_ordered() -> None:
    """A growth cap below the opening chunk would shrink on the first click."""
    assert TEXT_PREVIEW_CHUNK_BYTES <= TEXT_PREVIEW_MAX_CHUNK_BYTES
    assert TEXT_PREVIEW_MAX_CHUNK_BYTES <= TEXT_PREVIEW_REQUEST_MAX_BYTES
