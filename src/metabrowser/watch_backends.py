"""Filesystem observation backends owned by an opened inventory provider.

Single entry point :func:`run_watcher` spawns a long-running task that submits
typed, bounded ``RefreshRequest`` values whenever the filesystem under the
served root reports an mtime, create, or delete event. The selected provider
verifies each hint and owns all retained-state mutation.

Debugging a "no live updates" report? See
``docs/realtime-debugging.md`` — it walks the
producer/consumer chain layer by layer and tells you which DEBUG
log line proves which layer is healthy.

Backend selection is by **filesystem type** at startup:

* Native-eligible (apfs, ext4, btrfs, xfs, zfs, hfs, hfsplus,
  tmpfs) → ``watchfiles.awatch`` with the platform's native
  inotify / FSEvents / kqueue driver. Sub-second update
  latency.
* Polling-required (nfs, nfs4, cifs, smbfs, fuse.gcsfuse, …) →
  ``watchfiles.awatch(force_polling=True, poll_delay_ms=2000)``.
  Slower but works on remote mounts where native watchers don't
  see remote writes, so polling is the correctness fallback.
* Unknown fs type → polling, with a ``log.warning`` naming the
  type so unrecognized mounts surface in logs.

We do not branch by OS; ``watchfiles`` handles the per-platform
native-driver choice. Only the local-vs-polling distinction
lives here.

Output: each detected batch resolves to bounded, deduplicated relative paths and
observation labels. Watch labels are hints, not truth: the owning provider must stat and
reconcile each path before publishing a change.

The watcher is additive to (not a replacement for) the
inventory walker: the walker does the initial scan; the watcher
keeps it live thereafter.
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
import sys
from collections.abc import Awaitable, Callable, Collection
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from watchfiles import Change, awatch

from metabrowser.fs_paths import is_visible_segment as _is_visible_segment
from metabrowser.inventory_engine.contract import (
    MAX_COMMAND_PATHS,
    ObservationKind,
    RefreshObservation,
    RefreshReceipt,
    RefreshRequest,
)

LOG = logging.getLogger(__name__)


# ── Capability detection by fs type ──────────────────────────


# fs types that work fine with native filesystem watchers.
_NATIVE_FS_TYPES: frozenset[str] = frozenset(
    {
        "apfs",
        "hfs",
        "hfsplus",
        "ext2",
        "ext3",
        "ext4",
        "btrfs",
        "xfs",
        "zfs",
        "tmpfs",
    }
)

# Known-bad fs types (remote mounts where native watchers either
# don't fire or only see local-process writes). We force polling
# on these AND log a warning so the operator knows the watcher is
# in fallback mode.
_POLLING_FS_TYPES: frozenset[str] = frozenset(
    {
        "nfs",
        "nfs4",
        "cifs",
        "smbfs",
        "smb3",
        "fuse",
        "fuse.gcsfuse",
        "fuse.sshfs",
        "fuse.mutagen-agent",
        "afpfs",
    }
)


WatchMode = Literal["native", "polling"]


@dataclass(frozen=True, slots=True)
class WatcherStatus:
    """Provider-facing observation health without application wire types."""

    mode: WatchMode
    state: Literal["running", "failed"]
    reason: str
    detail: str = ""


def _longest_prefix_fs(target: str, entries: list[tuple[str, str]]) -> str:
    best: tuple[int, str] = (-1, "")
    for mp, fs_type in entries:
        if (target == mp or target.startswith(mp.rstrip("/") + "/")) and len(mp) > best[0]:
            best = (len(mp), fs_type)
    return best[1]


def _read_linux_mountinfo() -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    with open("/proc/self/mountinfo", encoding="utf-8") as fh:
        for line in fh:
            # Format (per Linux man procfs):
            #   ...mount_point - fs_type source super_options
            if " - " not in line:
                continue
            left, _, right = line.partition(" - ")
            left_parts = left.split()
            right_parts = right.split()
            if len(left_parts) < 5 or not right_parts:
                continue
            entries.append((left_parts[4], right_parts[0]))
    return entries


def _read_darwin_mounts() -> list[tuple[str, str]]:
    # `mount` output: "/dev/disk3s1s1 on / (apfs, sealed, ...)".
    # Parse the mount point (between " on " and " (") and the fs
    # type (first token inside the parens).
    out = subprocess.run(
        ["/sbin/mount"],
        capture_output=True,
        text=True,
        check=True,
        timeout=5,
    ).stdout
    entries: list[tuple[str, str]] = []
    for line in out.splitlines():
        if " on " not in line or "(" not in line:
            continue
        _, _, rest = line.partition(" on ")
        mp, _, opts = rest.partition(" (")
        fs_type = opts.split(",", 1)[0].strip().rstrip(")").strip().lower()
        if mp and fs_type:
            entries.append((mp, fs_type))
    return entries


def detect_fs_type(path: Path) -> str:
    """Return the filesystem type underlying *path*, or empty
    string when undetermined.

    Linux: parse ``/proc/self/mountinfo``.
    macOS: parse ``mount(8)`` output (``stat -f`` doesn't expose
    the fs name; ``statfs(2)`` requires fragile ctypes against a
    versioned struct, and a one-shot subprocess at startup is
    cheap).
    """

    try:
        if sys.platform == "darwin":
            entries = _read_darwin_mounts()
        else:
            entries = _read_linux_mountinfo()
    except (OSError, subprocess.SubprocessError):
        return ""
    return _longest_prefix_fs(str(path.resolve()), entries)


def select_watch_mode(path: Path) -> tuple[WatchMode, str]:
    """Choose ``native`` vs ``polling`` for a watcher rooted at
    *path*. Returns ``(mode, reason)`` so the capabilities
    surface (``/api/capabilities``) can show the operator why
    the badge says what it does."""

    fs_type = detect_fs_type(path)
    if not fs_type:
        return "polling", "fs-type-unknown"
    if fs_type in _NATIVE_FS_TYPES:
        return "native", f"fs={fs_type}"
    if fs_type in _POLLING_FS_TYPES:
        return "polling", f"fs={fs_type}"
    LOG.warning(
        "watch_backends: unrecognized fs type %r at %s; defaulting to polling. "
        "If native watch should work here, add the type to _NATIVE_FS_TYPES.",
        fs_type,
        path,
    )
    return "polling", f"fs={fs_type}-unrecognized"


# ── The one watcher loop ────────────────────────────────────


def _abs_to_rel(root: Path, abs_path: str) -> str | None:
    """Convert an absolute path emitted by watchfiles to a
    posix-style relative path under *root*. Returns None when
    the path falls outside the root (shouldn't happen with a
    properly-rooted watcher but defensive)."""

    try:
        rel = Path(abs_path).resolve().relative_to(root.resolve())
    except ValueError:
        return None
    return rel.as_posix() if str(rel) != "." else ""


async def _emit_for_path(
    refresh: Callable[[RefreshRequest], Awaitable[RefreshReceipt]],
    root: Path,
    abs_path: str,
    change_type: Change,
    *,
    hidden_allowlist: Collection[str] | None = None,
) -> None:
    """Translate one watchfiles event into a verified provider refresh."""

    await _emit_batch(
        refresh,
        root,
        ((change_type, abs_path),),
        hidden_allowlist=hidden_allowlist,
    )


def _observations_for_batch(
    root: Path,
    changes: Collection[tuple[Change, str]],
    *,
    hidden_allowlist: Collection[str] | None = None,
) -> tuple[RefreshObservation, ...]:
    """Normalize and deduplicate one backend batch without reading the filesystem."""

    by_path: dict[str, ObservationKind] = {}
    for change_type, abs_path in sorted(changes, key=lambda item: (item[1], int(item[0]))):
        rel = _abs_to_rel(root, abs_path)
        if rel is None:
            LOG.debug("watcher: drop (outside root) change=%s abs=%s", change_type.name, abs_path)
            continue
        if not rel:
            LOG.debug("watcher: drop root metadata change=%s", change_type.name)
            continue
        if not _is_visible_segment(rel, hidden_allowlist):
            LOG.debug("watcher: drop (hidden segment) change=%s rel=%s", change_type.name, rel)
            continue
        by_path[rel] = {
            Change.added: ObservationKind.CREATED,
            Change.modified: ObservationKind.MODIFIED,
            Change.deleted: ObservationKind.DELETED,
        }[change_type]
    return tuple(RefreshObservation(path=path, kind=kind) for path, kind in sorted(by_path.items()))


async def _emit_batch(
    refresh: Callable[[RefreshRequest], Awaitable[RefreshReceipt]],
    root: Path,
    changes: Collection[tuple[Change, str]],
    *,
    hidden_allowlist: Collection[str] | None = None,
) -> None:
    """Submit one backend batch in contract-sized chunks."""

    observations = _observations_for_batch(
        root,
        changes,
        hidden_allowlist=hidden_allowlist,
    )
    for offset in range(0, len(observations), MAX_COMMAND_PATHS):
        chunk = observations[offset : offset + MAX_COMMAND_PATHS]
        receipt = await refresh(RefreshRequest(observations=chunk))
        accepted = frozenset(receipt.accepted_paths)
        expected = frozenset(observation.path for observation in chunk)
        reported = accepted | frozenset(receipt.rejected_paths)
        if reported != expected:
            raise RuntimeError(
                "provider returned an inconsistent watcher receipt "
                f"(expected={len(expected)}, reported={len(reported)})"
            )
        if accepted != expected:
            raise RuntimeError(
                f"provider rejected {len(expected - accepted)} watcher observation(s)"
            )
        for observation in chunk:
            rel = observation.path
            LOG.debug("watcher: submitted rel=%s kind=%s", rel, observation.kind)


async def run_watcher(
    *,
    root: Path,
    refresh: Callable[[RefreshRequest], Awaitable[RefreshReceipt]],
    on_status: Callable[[WatcherStatus], None] = lambda _status: None,
    mode: WatchMode | None = None,
    hidden_allowlist: Collection[str] | None = None,
) -> None:
    """Long-running watcher coroutine. Spawn from an opened provider
    handle; cancel and join it when the handle closes.

    Selects native vs polling automatically (override via *mode*
    for tests). A watch-backend failure or an incompletely submitted
    batch ends the watch: the backend cannot prove that later changes
    form a lossless suffix. The gap is announced rather than left silent, because
    everything downstream reads a still-answering index as a
    current one. Terminating cleanly on cancellation is critical
    so the lifespan teardown completes.
    """

    reason = "override"
    if mode is None:
        mode, reason = await asyncio.to_thread(select_watch_mode, root)
        LOG.debug("watcher starting at %s mode=%s reason=%s", root, mode, reason)
    else:
        LOG.debug("watcher starting at %s mode=%s (override)", root, mode)

    force_polling = mode == "polling"
    poll_delay_ms = 2000 if force_polling else 50
    on_status(WatcherStatus(mode=mode, state="running", reason=reason))

    try:
        async for changes in awatch(
            str(root),
            force_polling=force_polling,
            poll_delay_ms=poll_delay_ms,
            recursive=True,
        ):
            LOG.debug("watcher: batch n=%d", len(changes))
            await _emit_batch(
                refresh,
                root,
                changes,
                hidden_allowlist=hidden_allowlist,
            )
        raise RuntimeError("watch stream ended before provider close")
    except asyncio.CancelledError:
        LOG.debug("watcher cancelled")
        raise
    except Exception as error:
        # The index is only current because this loop keeps it current, and
        # nothing downstream can tell a quiet filesystem from a dead watch:
        # requests keep being answered, and conditional ones keep answering
        # "not modified" — truthfully about the index, which has stopped
        # being about the filesystem. Exhausting the inotify watch limit on
        # a large tree lands here. Say so loudly and on the event stream.
        LOG.exception("watcher stopped at %s mode=%s; live updates have ended", root, mode)
        on_status(
            WatcherStatus(
                mode=mode,
                state="failed",
                reason="watch-failed",
                detail=f"{type(error).__name__}: {error}",
            )
        )
        return


__all__ = [
    "WatchMode",
    "WatcherStatus",
    "detect_fs_type",
    "run_watcher",
    "select_watch_mode",
]
