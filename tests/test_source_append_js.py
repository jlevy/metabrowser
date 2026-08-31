"""Incremental growth contracts for the source view's chunked loading."""

from __future__ import annotations

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
APP_JS = REPO_ROOT / "src" / "metabrowser" / "static" / "app.js"


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


def test_shell_appends_rather_than_rerendering() -> None:
    """Load more must not rebuild the pane.

    Re-rendering made each click cost the running total rather than the chunk
    it loaded, which is quadratic across a sequence of clicks.
    """
    js = APP_JS.read_text()

    assert "MetabrowserSourceAppend.appendSourceText" in js
    assert "MetabrowserSourceAppend.nextChunkBytes" in js
    # The full render survives only as the documented fallback for a view
    # shape the append cannot safely touch.
    append_call = js.index("MetabrowserSourceAppend.appendSourceText")
    following = js[append_call : append_call + 800]
    # The fallback also asserts pane ownership: the Git panel renders into this
    # same pane, so a late chunk must not repaint over it.
    assert "await renderFile(cached, undefined, previewClaim)" in following, (
        "the fallback render should remain reachable"
    )
    # Appending skips the plugin's render, so the partial-content banner has to
    # be brought back in line or it reports stale byte counts.
    assert "MetabrowserSourceAppend.syncTruncationWarning" in js
    assert "cached.highlight_disabled = !!chunk.highlight_disabled" in js


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
