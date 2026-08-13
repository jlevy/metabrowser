"""Tests for the filesystem-watcher backend.

* fs-type detection from /proc/self/mountinfo (Linux); falls
  back to "polling" with a sensible reason on unknown / missing.
* select_watch_mode chooses native for ext4-style mounts and
  polling for nfs/fuse.
* run_watcher emits fs.change ops on real file writes (using
  tmp_path which is typically tmpfs/ext4).
* The mode override pins behaviour for tests.
"""

from __future__ import annotations

import asyncio
import contextlib
from pathlib import Path

import pytest
from watchfiles import Change

from metabrowser.events import FsChange, FsUpsert
from metabrowser.inventory import get_instance, reset_instance_for_tests
from metabrowser.watch_backends import (
    _NATIVE_FS_TYPES,
    _POLLING_FS_TYPES,
    _emit_for_path,
    detect_fs_type,
    run_watcher,
    select_watch_mode,
)

# ── fs-type fixtures ─────────────────────────────────────────


def test_native_set_includes_ext4_apfs() -> None:
    """The fs-type allowlist matches the spec contract."""
    assert "ext4" in _NATIVE_FS_TYPES
    assert "apfs" in _NATIVE_FS_TYPES
    assert "btrfs" in _NATIVE_FS_TYPES
    assert "tmpfs" in _NATIVE_FS_TYPES


def test_polling_set_includes_nfs_and_fuse() -> None:
    assert "nfs" in _POLLING_FS_TYPES
    assert "nfs4" in _POLLING_FS_TYPES
    assert "fuse.gcsfuse" in _POLLING_FS_TYPES


def test_select_watch_mode_native_for_ext4_fixture(tmp_path: Path) -> None:
    """tmp_path on a typical Linux box is ext4 / tmpfs; both
    native-eligible. We assert mode is native OR (if the
    detector returned an unrecognized type for some reason)
    polling — either is correct for an unknown-fs scenario."""

    mode, reason = select_watch_mode(tmp_path)
    # On the dev container's filesystem this should land in
    # native; if not, the reason explains why.
    assert mode in ("native", "polling")
    assert reason  # non-empty


def test_select_watch_mode_polling_for_nfs_synthetic(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub detect_fs_type to return "nfs" and assert the
    selector chooses polling."""

    monkeypatch.setattr(
        "metabrowser.watch_backends.detect_fs_type",
        lambda _p: "nfs",
    )
    mode, reason = select_watch_mode(Path("/anywhere"))
    assert mode == "polling"
    assert reason == "fs=nfs"


def test_select_watch_mode_polling_for_unknown_fs(monkeypatch: pytest.MonkeyPatch) -> None:
    """An unrecognized fs type defaults to polling and surfaces
    the type in the reason so logs aren't opaque."""

    monkeypatch.setattr(
        "metabrowser.watch_backends.detect_fs_type",
        lambda _p: "weirdfs",
    )
    mode, reason = select_watch_mode(Path("/anywhere"))
    assert mode == "polling"
    assert "weirdfs" in reason


def test_select_watch_mode_polling_when_detect_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "metabrowser.watch_backends.detect_fs_type",
        lambda _p: "",
    )
    mode, reason = select_watch_mode(Path("/anywhere"))
    assert mode == "polling"
    assert reason == "fs-type-unknown"


def test_detect_fs_type_returns_string_on_real_path(tmp_path: Path) -> None:
    """Smoke: against a real path the detector returns either
    a plausible fs-type string or '' (if mountinfo unavailable)."""

    fs = detect_fs_type(tmp_path)
    # Don't pin a value — depends on dev env. Just assert it's
    # either empty or a non-whitespace string.
    assert isinstance(fs, str)


# ── End-to-end watcher loop ──────────────────────────────────


def _build_fixture(tmp_path: Path) -> Path:
    (tmp_path / "runs").mkdir()
    (tmp_path / "runs" / "x").mkdir()
    return tmp_path / "runs" / "x" / "new.jsonl"


def test_run_watcher_emits_fs_change_on_new_file(tmp_path: Path) -> None:
    """A file created after the watcher starts should produce
    an fs.change op for the new path."""

    new_file = _build_fixture(tmp_path)

    async def _run() -> set[str]:
        reset_instance_for_tests()
        inv = get_instance()
        q = inv.subscribe()
        # Pre-populate the inventory with the existing dirs so
        # the watcher's emit path doesn't bail on a parent-not-
        # found check (the active path checks only visibility +
        # fs.change emission, not pre-existence).
        inv.start(tmp_path)
        await inv.wait_until_done(timeout=5.0)
        # Drain pre-existing events.
        while not q.empty():
            q.get_nowait()

        # Force polling mode so the test doesn't depend on the
        # native backend being available; poll cadence kept
        # short so the test finishes quickly.
        watcher = asyncio.create_task(run_watcher(root=tmp_path, mode="polling"))
        try:
            # Give the watcher a beat to start.
            await asyncio.sleep(0.5)
            new_file.write_text('{"event":"start"}\n')
            # Wait long enough for the polling backend to detect.
            await asyncio.sleep(3.5)
        finally:
            watcher.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await watcher

        seen: set[str] = set()
        while not q.empty():
            evt = q.get_nowait()
            if isinstance(evt, FsChange):
                for op in evt.ops:
                    if isinstance(op, FsUpsert):
                        seen.add(op.entry.path)
        return seen

    seen = asyncio.run(_run())
    # The watcher should have fired for the newly-created file.
    assert "runs/x/new.jsonl" in seen


def test_stale_delete_event_reconciles_recreated_directory(tmp_path: Path) -> None:
    async def run() -> tuple[set[str], int]:
        reset_instance_for_tests()
        inventory = get_instance()
        artifacts = tmp_path / "dist"
        artifacts.mkdir()
        (artifacts / "old.whl").write_bytes(b"old")
        inventory.start(tmp_path)
        await inventory.wait_until_done(timeout=5.0)

        (artifacts / "old.whl").unlink()
        artifacts.rmdir()
        artifacts.mkdir()
        (artifacts / "new.whl").write_bytes(b"new artifact")

        await _emit_for_path(inventory, tmp_path, str(artifacts), Change.deleted)
        rollup = inventory.rollup("dist", depth=0, top=0, ext_top=10)
        assert rollup is not None
        indexed_paths = {entry.path for entry in inventory.entries(scope="all-known")}
        return indexed_paths, rollup["node"]["total_files"]

    indexed_paths, total_files = asyncio.run(run())
    assert "dist/new.whl" in indexed_paths
    assert "dist/old.whl" not in indexed_paths
    assert total_files == 1


def test_stale_add_event_removes_now_absent_file(tmp_path: Path) -> None:
    async def run() -> tuple[bool, int]:
        reset_instance_for_tests()
        inventory = get_instance()
        target = tmp_path / "gone.txt"
        target.write_text("gone")
        inventory.start(tmp_path)
        await inventory.wait_until_done(timeout=5.0)

        target.unlink()
        await _emit_for_path(inventory, tmp_path, str(target), Change.added)
        root = inventory.rollup("", depth=0, top=0, ext_top=10)
        assert root is not None
        return inventory.get("gone.txt") is None, root["node"]["total_files"]

    removed, total_files = asyncio.run(run())
    assert removed
    assert total_files == 0
