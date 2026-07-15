"""Filesystem-watcher backends for the inventory event plane.

Single entry point :func:`run_watcher` spawns a long-running task
that emits ``fs.change`` ops on the InventoryIndex whenever the
filesystem under the served root reports an mtime / create /
delete event.

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

Output: each detected change resolves to a path, runs through
the same :func:`metabrowser.activity.activity_tracker.poll`
fingerprinter, and pushes an ``fs.change`` op via
:meth:`InventoryIndex._apply_walker_entry`. New files trigger a
fresh ``FsEntry``; deletes emit ``FsRemove``.

The watcher is additive to (not a replacement for) the
inventory walker: the walker does the initial scan; the watcher
keeps it live thereafter.
"""

from __future__ import annotations

import asyncio
import logging
import os
import stat as stat_module
import subprocess
import sys
from pathlib import Path
from typing import Literal

from watchfiles import Change, awatch

from metabrowser.events import FsEntry, ProjectionInvalidate
from metabrowser.fs_paths import is_visible_segment as _is_visible_segment
from metabrowser.inventory import InventoryIndex
from metabrowser.inventory import get_instance as get_inventory
from metabrowser.projections import invalidate_path as projection_invalidate_path
from metabrowser.tree import build_gitignore_check

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
    inventory: InventoryIndex,
    root: Path,
    abs_path: str,
    change_type: Change,
) -> None:
    """Translate one watchfiles change into an inventory write."""

    rel = _abs_to_rel(root, abs_path)
    if rel is None:
        LOG.debug("watcher: drop (outside root) change=%s abs=%s", change_type.name, abs_path)
        return
    if not _is_visible_segment(rel):
        LOG.debug("watcher: drop (hidden segment) change=%s rel=%s", change_type.name, rel)
        return

    # Invalidate the path and every ancestor before observing the live state.
    # A boot-walker directory finalization carries the generation captured when
    # its placeholder was stored, so a pre-change aggregate is dropped and
    # repaired from the current inventory instead of overwriting this event.
    inventory.invalidate(rel)

    if change_type == Change.deleted:
        existing = inventory.get(rel)
        if existing is None:
            LOG.debug("watcher: delete-noop (not in index) rel=%s", rel)
            return
        # Real remove + emit an FsRemove op so subscribers can drop
        # the row(s) — the SPA, the bus's ring buffer, and any
        # downstream consumer. ``inventory.remove`` walks
        # descendants under a deleted directory and emits one batch
        # covering every path removed.
        inventory.remove(rel)
        LOG.debug("watcher: delete remove rel=%s", rel)
        return

    # Created / modified: stat and update the FsEntry. ``lstat`` so a
    # symlink is described by the link itself, not its target — the
    # boot walker uses ``follow_symlinks=False`` and records symlinks
    # as leaf entries, so following one here would diverge from the
    # boot tree (and, for a symlinked directory, trigger a rewalk that
    # grafts the link target's whole subtree under the link path).
    p = Path(abs_path)
    try:
        st = await asyncio.to_thread(os.lstat, p)
    except OSError as exc:
        LOG.debug("watcher: stat-failed rel=%s err=%s", rel, exc)
        return

    is_symlink = stat_module.S_ISLNK(st.st_mode)
    existing = inventory.get(rel)
    if p.is_dir() and not is_symlink:
        # Real directories: re-walk the subtree so every descendant
        # lands in the inventory. ``rewalk_subtree`` reuses the boot
        # walker's machinery, including the generation counters, so a
        # concurrent invalidate on this subtree drops stale writes the
        # same way as boot. ``rewalk_subtree`` also re-checks
        # containment and refuses to follow symlinks, so a link that
        # slips past the ``is_symlink`` check above (e.g. a symlinked
        # *ancestor* of ``rel``) still can't escape the served root.
        await inventory.rewalk_subtree(rel)
        LOG.debug("watcher: dir rewalk rel=%s", rel)
        return
    if is_symlink:
        # Symlink (to anything): record it as a leaf entry, matching
        # the boot walker, and never descend. This is the upstream
        # guard for the phantom-subtree bug.
        LOG.debug("watcher: symlink leaf rel=%s -> %s", rel, os.readlink(abs_path))

    name = p.name
    parent_rel = rel.rsplit("/", 1)[0] if "/" in rel else ""

    # Re-derive gitignored on every event — the watcher fires for
    # both new files (no existing entry) and edits (a `.gitignore`
    # change in between can flip the matching state).
    # ``build_gitignore_check`` is TTL-cached in
    # ``tree._IGNORE_CACHE``, so this is one dict lookup per event
    # past the first.
    try:
        gi_check, git_root = await asyncio.to_thread(build_gitignore_check, root)
    except Exception:
        gi_check, git_root = None, None
    gitignored = False
    if gi_check is not None and git_root is not None:
        try:
            gitignored = bool(gi_check(p, is_dir=False))
        except Exception:
            gitignored = False

    entry = FsEntry.for_stat(
        path=rel,
        parent=parent_rel,
        name=name,
        stat=st,
        gitignored=gitignored,
        existing=existing,
    )
    inventory.apply_live_entry(entry)
    # Drop the projection caches' entry for this path and tell
    # subscribers the derived view is stale. ``MtimeCache.read``
    # will re-stat lazily anyway, but the explicit invalidate is
    # symmetric with the fs.change op the bus just emitted, and
    # the ``projection.invalidate`` event lets client-side caches
    # stay in step with the same edge.
    try:
        projection_invalidate_path(p)
    except Exception:
        LOG.exception("watcher: projection invalidate failed for %s", p)
    inventory.emit_event(ProjectionInvalidate(path=rel, projection="*"))
    LOG.debug(
        "watcher: file %s rel=%s size=%d existing=%s",
        "modified" if existing else "created",
        rel,
        st.st_size,
        existing is not None,
    )


async def run_watcher(*, root: Path, mode: WatchMode | None = None) -> None:
    """Long-running watcher coroutine. Spawn from the lifespan
    hook; cancel on shutdown.

    Selects native vs polling automatically (override via *mode*
    for tests). All errors are logged; the loop keeps running.
    Terminating cleanly on cancellation is critical so the
    lifespan teardown completes.
    """

    inventory = get_inventory()
    if mode is None:
        mode, reason = await asyncio.to_thread(select_watch_mode, root)
        LOG.info("watcher starting at %s mode=%s reason=%s", root, mode, reason)
    else:
        LOG.info("watcher starting at %s mode=%s (override)", root, mode)

    force_polling = mode == "polling"
    poll_delay_ms = 2000 if force_polling else 50

    try:
        async for changes in awatch(
            str(root),
            force_polling=force_polling,
            poll_delay_ms=poll_delay_ms,
            recursive=True,
        ):
            LOG.debug("watcher: batch n=%d", len(changes))
            for change_type, abs_path in changes:
                try:
                    await _emit_for_path(inventory, root, abs_path, change_type)
                except Exception:
                    LOG.exception("watcher emit failed for %s", abs_path)
    except asyncio.CancelledError:
        LOG.info("watcher cancelled")
        raise


__all__ = [
    "WatchMode",
    "detect_fs_type",
    "run_watcher",
    "select_watch_mode",
]
