"""The filesystem record the scanner produces and the inventory retains.

Split out of :mod:`metabrowser.events` so the scanner does not have to import the
browser-event layer to name the thing it produces. That dependency is what
`test_scanner_and_reducer_do_not_depend_on_browser_events` forbids, and routing the
walker through the provider contract's validated entry type to avoid it cost a second
construction and two path validations for every entry discovered -- about 6 us each, on
the one path that runs hundreds of thousands of times.

The record is genuinely shared: the scanner fills the filesystem facts, the browser layer
adds ``views``, ``labels``, and ``active``. Keeping it here says so, and lets both import
it without either importing the other.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

from metabrowser.fs_paths import derive_ext


@dataclass(slots=True, frozen=True)
class WriteToken:
    """Captured snapshot of the inventory's generation counter for a path.

    A producer that wants race-safety reads the counter at the moment it
    starts observing a path's filesystem state and writes the resulting
    entry with that token. If the retained Python provider bumps the counter
    before the write lands, it drops the write rather than overwriting a fresher
    observation.

    Producers that just observed the filesystem **now** can leave
    ``FsEntry.write_token = None``; the inventory treats the write as a
    fresh observation and stamps it with the current generation at write
    time. The ``None`` vs ``WriteToken`` distinction is type-level so the
    contract is un-confusable — a default ``int`` field cannot be
    accidentally interpreted as "stale snapshot N".
    """

    generation: int


@dataclass(slots=True, frozen=True)
class FsEntry:
    """One browser-event record for a file, directory, or symlink.

    Filesystem facts originate in the provider contract. This host record adds preview
    and activity decorations for browser delivery; providers never return it.

    Files always carry concrete ``size`` / ``mtime_ns``. Directories
    carry their immediate-child count via ``total_files`` (with the
    cumulative subtree count for the recent/tree decoration), but
    those aggregate fields are ``None`` while the walker is still
    finalizing the subtree below them. The walker writes the
    finalized values atomically (``dataclasses.replace``) once the
    subtree is complete.

    Symlinks are typed leaves: the inventory records the link itself
    without following its target or including it in file aggregates.
    ``empty`` reports whether a finalized directory subtree has no file or
    symlink leaves. It stays separate from file-only aggregates because
    symlinks are visible leaves but not files; ``None`` means unknown.

    ``views`` is the ordered list of preview-pane view ids (see
    :mod:`metabrowser.file_kinds`); empty for dirs and symlinks.
    ``labels`` is an open dict for run-state, pid-alive, errored,
    plugin badges; meaningful only for files.

    ``write_token`` carries a captured snapshot of the inventory's
    generation counter for race-safety; see :class:`WriteToken`.
    ``None`` means "freshly observed; stamp at write time"; a
    :class:`WriteToken` means the producer captured the counter at
    observation start and the inventory should drop the write if an
    invalidation has bumped the counter since.
    """

    path: str
    parent: str
    name: str
    type: Literal["file", "dir", "symlink"]
    ext: str
    kind: str
    size: int
    mtime_ns: int
    mtime_hash: str
    active: bool
    views: tuple[str, ...] = ()
    labels: tuple[tuple[str, str], ...] = ()
    # dir aggregates — None while the walker has not yet finalized
    total_files: int | None = None
    total_size: int | None = None
    unignored_files: int | None = None
    unignored_size: int | None = None
    newest_mtime_ns: int | None = None
    empty: bool | None = None
    gitignored: bool = False
    # walker bookkeeping (not part of the wire payload)
    write_token: WriteToken | None = None

    # `dataclasses.replace` reads all twenty fields back through string-keyed
    # `getattr` and then runs the generated `__init__` over them. The walker calls
    # it once per entry to stamp a write token, which on a 60,000-file tree is
    # 64,420 replaces and about 1.3 million of those attribute lookups.
    #
    # These build the copy positionally instead: the same generated `__init__`,
    # reached without the replace machinery or the by-name reads. 3.5 us to
    # 1.3 us. Safe because this class has no `__post_init__` -- there is no
    # validation being skipped, only reflection.
    #
    # They are written out rather than generated because a loop over field names
    # is the cost being removed. A field added to this class must be added here;
    # `test_fsentry_fast_copies_match_dataclasses_replace` fails if it is not.

    def with_write_token(self, write_token: WriteToken | None) -> FsEntry:
        """Copy carrying *write_token*, for the walker's per-entry stamp."""

        return FsEntry(
            self.path,
            self.parent,
            self.name,
            self.type,
            self.ext,
            self.kind,
            self.size,
            self.mtime_ns,
            self.mtime_hash,
            self.active,
            self.views,
            self.labels,
            self.total_files,
            self.total_size,
            self.unignored_files,
            self.unignored_size,
            self.newest_mtime_ns,
            self.empty,
            self.gitignored,
            write_token,
        )

    def with_empty(self, empty: bool | None) -> FsEntry:
        """Copy carrying *empty*, for a directory the walker has finalized."""

        return FsEntry(
            self.path,
            self.parent,
            self.name,
            self.type,
            self.ext,
            self.kind,
            self.size,
            self.mtime_ns,
            self.mtime_hash,
            self.active,
            self.views,
            self.labels,
            self.total_files,
            self.total_size,
            self.unignored_files,
            self.unignored_size,
            self.newest_mtime_ns,
            empty,
            self.gitignored,
            self.write_token,
        )

    @classmethod
    def for_observed_file(
        cls,
        *,
        path: str,
        parent: str,
        name: str,
        size: int,
        mtime_ns: int,
        gitignored: bool = False,
        existing: FsEntry | None = None,
    ) -> FsEntry:
        """Build a freshly-observed file entry.

        This is the single construction point for the walker and watcher,
        ensuring both use the bounded compound-tail extension rule in
        :func:`metabrowser.fs_paths.derive_ext`.

        Carries forward ``active`` and ``labels`` from *existing* when
        provided so the watcher's modify path preserves run-state and
        plugin badges across edits. Leaves ``write_token=None`` so the Python
        provider stamps the entry with the current generation at write time.
        """

        return cls(
            path=path,
            parent=parent,
            name=name,
            type="file",
            ext=derive_ext(name),
            kind="file",
            size=size,
            mtime_ns=mtime_ns,
            mtime_hash="",
            active=existing.active if existing else False,
            views=existing.views if existing else (),
            labels=existing.labels if existing else (),
            gitignored=gitignored,
        )

    @classmethod
    def for_observed_dir(
        cls,
        *,
        path: str,
        parent: str,
        name: str,
        gitignored: bool = False,
    ) -> FsEntry:
        """Build a freshly-observed directory placeholder.

        Aggregates (``total_files`` / ``total_size`` /
        ``newest_mtime_ns``) stay ``None`` until the walker finalizes
        the subtree via post-order replacement.
        """

        return cls(
            path=path,
            parent=parent,
            name=name,
            type="dir",
            ext="",
            kind="dir",
            size=0,
            mtime_ns=0,
            mtime_hash="",
            active=False,
            gitignored=gitignored,
        )

    @classmethod
    def for_observed_symlink(
        cls,
        *,
        path: str,
        parent: str,
        name: str,
        size: int,
        mtime_ns: int,
        gitignored: bool = False,
    ) -> FsEntry:
        """Build a symlink leaf without treating it as a regular file."""

        return cls(
            path=path,
            parent=parent,
            name=name,
            type="symlink",
            ext="",
            kind="symlink",
            size=size,
            mtime_ns=mtime_ns,
            mtime_hash="",
            active=False,
            gitignored=gitignored,
        )

    @classmethod
    def for_stat(
        cls,
        *,
        path: str,
        parent: str,
        name: str,
        stat: os.stat_result,
        gitignored: bool = False,
        existing: FsEntry | None = None,
    ) -> FsEntry:
        """Build a freshly-observed file entry from a ``stat_result``.

        Convenience wrapper for the watcher path where the producer
        already holds an ``os.stat_result``. Equivalent to
        :meth:`for_observed_file` but pulls ``size`` / ``mtime_ns``
        from the stat tuple.
        """

        return cls.for_observed_file(
            path=path,
            parent=parent,
            name=name,
            size=stat.st_size,
            mtime_ns=stat.st_mtime_ns,
            gitignored=gitignored,
            existing=existing,
        )


# ── fs.change ops ───────────────────────────────────────────────
#
# The discriminated union below is the unit of change in the
# inventory plane. Producers (watch backends, app-log backend,
# reconciliation) push ops into the shared queue; the inventory
# consumer batches ops and emits an ``FsChange`` event per drain.
