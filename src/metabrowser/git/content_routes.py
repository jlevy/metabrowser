"""GitPath adapters for ``/api/tree``, ``/api/file``, ``/raw``, KPress, rollup, catalog, and index status.

These honor a pinned ``GitRevisionSubject`` without a checkout, index, or
invented filesystem fact. ``/view/`` accepts a GitPath wire, optionally plus
a host container inner, and refuses a filesystem spelling. ``/api/tree`` keeps
Git-native ``entries`` and also projects a SPA ``tree`` array so navigation
can paint; ``depth`` nests SPA children the way filesystem listings do (default 2)
and emits a lazy sentinel past the cap. Gitlinks are files, and listings omit mtime
and ignore. Blob and symlink entries carry ``cat-file`` sizes; trees and
gitlinks stay unsized, so ``min_size`` can filter without ``ls-tree -l``.
Directory ``total_files`` / ``total_size`` come from recursive ``ls-tree -r``
plus ``cat-file`` info; a truncated listing or missing blob omits the
incomplete dimension. ``/api/tree`` also carries whole-tree ``extensions``,
``canonical_extensions``, ``type_families``, and ``type_presets`` rows plus
``tally_cache_status`` from that index so the type filter and truncation
banner do not wait on a filesystem walker. A complete blob-size tally also
fills the whole-tree ``summary`` (``files``, ``size``, ignored 0/0) so the
nav header has honest counts; incomplete sizes omit ``summary`` rather than
inventing 0. ``types`` and ``min_size`` keep ancestor trees of matching blobs
and emit subtree ``filtered`` totals; empty filter dirs are omitted. File nav
nodes include ``ext`` from the same bounded compound-tail helper as
filesystem inventory, so type filters match ``bundle.min.js`` as ``.min.js``
and do not treat a basename ending in ``md`` as ``.md``.
Blob ``/api/file`` envelopes instead carry the name's last extension as ``ext``,
as a folder's do (``blob_logical_ext``, so ``run.codex.jsonl`` is ``.jsonl``):
it is what a kind is chosen from, and plugin-sdk ``langForPath`` and ``ctx.ext``
read it rather than fall back to a GitPath wire. They omit compressed identity
because blobs are stored bytes with no gzip smudge.
Markdown blob envelopes include parsed YAML ``frontmatter`` and
``frontmatter_error`` the way filesystem ``/api/file`` does; KPress on a pin
uses that parse of the blob's own bytes rather than an empty mapping, also when
the page sends prepared text to render in the blob's place.
Text blobs use the same first-window and highlight bound as filesystem
listings, and advertise ``bytes_read`` plus preview limits so Load more and
``fetchText`` can continue a truncated Git envelope.
A Git image blob is SPA ``image`` chrome (preview view, no inline content);
``/raw`` serves the stored bytes so the
image plugin can paint. Alternative text uses the display name, not the
GitPath wire.
``/api/file``, ``/raw``, KPress, and plugin sidekicks follow in-tree relative
symlink blobs to the target object; the requested GitPath stays the route
identity. Kind checks (JSONL, structured, patch) use the leaf path.
Listings still show the symlink node. Absolute, dangling, and cyclic
targets 404.
``logical_ext`` is only the inner extension of a compressed name.
``include_ignored=0`` is a no-op because ignore is absent.
A revision's file times are the committer times of the last commits that changed them
(``git/file_ages.py``): where the Git can read them the SPA offers Modified within and By age,
and where it cannot it hides both, because recency has no honest mtime.
A Git tree ``/api/file`` envelope is SPA ``folder`` chrome (``git_kind`` stays
``tree``) with no invented mtime or ignore. Omitted mtime leaves
SPA age chrome empty rather than pending. A direct-child README blob sets
``readme_path`` to its GitPath wire and mounts the Overview view. A complete
blob-size tally also mounts treemap and File Overview; ``/api/rollup`` answers
from the same index and omits mtime. A missing blob size 404s rollup rather
than emitting a partial sum. ``/api/catalog`` lists those blob names as
Quick File rows (``p`` GitPath wire, ``e`` display suffix, ``n`` display
basename) and is complete at once; a truncated index is an empty truncated
snapshot rather than a partial list. ``/api/index/progress``, ``/api/index/meta``,
and ``/api/capabilities`` report that same complete-at-once index without a
watcher or invented mtime. SPA path chrome and copy-path
decode GitPath wires to display names; C0 and invalid UTF-8 become U+FFFD.
Navigation identities stay wires. KPress ``source_path``
is the GitPath wire so Markdown rewrite cannot emit a filesystem spelling.
Patch-file container inners use a GitPath prefix plus a host inner path. Blob
kinds use extension, basename, sniffed adapter, and JSON/YAML/frontmatter
mappings parsed from blob bytes. ``path_glob`` stays filesystem-only. Serving
acquired Git over a listening port remains a later bead. The CLI can
``--show`` / ``--api`` a ``file://`` pin in-process.
"""

from __future__ import annotations

import asyncio
import functools
import heapq
import logging
import mimetypes
import time
from array import array
from bisect import bisect_left, bisect_right
from collections import Counter
from collections.abc import Awaitable, Callable, Iterator
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from itertools import compress
from pathlib import Path
from typing import Any, Literal

from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, Response

from metabrowser import kpress_adapter
from metabrowser.capabilities import UNTRUSTED_CAPABILITIES
from metabrowser.client_disconnect import CLIENT_CLOSED, unless_disconnected
from metabrowser.content_sniff import (
    SNIFF_PREFIX_BYTES,
    ContentClass,
    classify_prefix,
    media_type_from_prefix,
)
from metabrowser.diff.markdown_projection_worker import (
    InertRender,
    InertRenderRefused,
    kpress_refusal_payload,
    shared_worker,
    text_identity,
)
from metabrowser.file_extensions import (
    BROWSER_IMAGE_EXTS,
    BROWSER_TEXT_EXTS,
    syntax_language_for_path,
)
from metabrowser.file_kinds import classify_by_ext
from metabrowser.file_type_filters import FILTER_TYPE_PRESETS
from metabrowser.file_type_legend import build_file_type_legend
from metabrowser.file_type_match import name_matches_types, semantic_extension_tokens, type_tally
from metabrowser.file_type_registry import load_file_type_registry
from metabrowser.folder_discovery import choose_readme_name
from metabrowser.frontmatter_yaml import frontmatter_error_fields
from metabrowser.fs_paths import derive_ext
from metabrowser.git.file_ages import (
    UNDATED,
    RevisionAges,
    file_ages_availability,
    file_ages_version_label,
)
from metabrowser.git.file_ages_service import AgesStatus, file_ages_service
from metabrowser.git.process import GitError, GitTimeoutError, failure_detail
from metabrowser.git.tree_source import (
    GitBlobIndex,
    GitBlobTallies,
    GitBlobTooLargeError,
    GitObjectCorruptError,
    GitObjectUnavailableError,
    GitPath,
    GitPathError,
    GitRevisionSubject,
    GitTreeEntry,
    GitTreeSource,
    GitTreeTally,
    blob_logical_ext,
    follow_git_symlinks,
    resolve_git_blob_entry,
    split_git_container_wire,
)
from metabrowser.gz_io import ArtifactPath
from metabrowser.inventory_engine.contract import ascii_casefold
from metabrowser.inventory_rollup import RollupOptions, build_rollup, group_rollup_children
from metabrowser.invisible_chars import display_segment
from metabrowser.keymap import live_view_keys
from metabrowser.kpress_fences import read_fence_origin
from metabrowser.plugin_loader.classify import CONTENT_PREDICATE_MAX_BYTES
from metabrowser.settings import (
    FOLDER_DISCOVERY_MAX_ENTRIES,
    INVENTORY_MAX_FILES,
    RECENT_WINDOW_SECONDS,
    SYNTAX_HIGHLIGHT_MAX_BYTES,
    TEXT_PREVIEW_CHUNK_BYTES,
    TEXT_PREVIEW_REQUEST_MAX_BYTES,
)
from metabrowser.source import MAX_CONTAINER_INNER_DEPTH, UnsupportedSourceCapabilityError
from metabrowser.tree import _tree_depth_from_query
from metabrowser.tree_filter import TreeFilter
from metabrowser.tree_groups import (
    UNDATED_GROUP_ID,
    GroupBy,
    age_band,
    age_group_index,
    age_windows,
    group_row,
    groups_for,
    groups_payload,
)
from metabrowser.view_routes import decode_view_logical_path

log = logging.getLogger(__name__)

_NOT_FOUND = {"error": "Not found"}
_PATCH_EXTS = (".patch", ".diff")


def _git_path_from_query(request: Request) -> GitPath:
    return GitPath.from_wire(request.query_params.get("path", ""))


def decode_git_view_path(raw_path: bytes) -> str | None:
    """Decode ``/view/`` as a GitPath wire, optionally plus a container inner.

    Filesystem spellings are not GitPath identities. Missing Git objects stay
    valid shell destinations, matching missing files under a served root.
    """

    logical = decode_view_logical_path(raw_path)
    if logical is None:
        return None
    try:
        split_git_container_wire(logical)
    except GitPathError:
        return None
    return logical


def _listing_entry(entry: GitTreeEntry) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "path": entry.path.to_wire(),
        "display": entry.path.display(),
        "mode": entry.mode,
        "kind": entry.kind,
        "symlink": entry.is_symlink,
        "gitlink": entry.is_gitlink,
        "oid": entry.oid,
    }
    if entry.size is not None:
        payload["size"] = entry.size
    return payload


def _nav_tree_type(entry: GitTreeEntry) -> Literal["dir", "file", "symlink"]:
    if entry.is_tree:
        return "dir"
    if entry.is_symlink:
        return "symlink"
    return "file"


def _join_git_prefix(prefix: bytes, name: bytes) -> bytes:
    return name if not prefix else prefix + b"/" + name


def _nav_tree_node(
    entry: GitTreeEntry,
    *,
    tally: GitTreeTally | None = None,
    children: list[dict[str, Any]] | None = None,
    loaded: bool = False,
    ages: RevisionAges | None = None,
    kept_time: tuple[int | None] | None = None,
) -> dict[str, Any]:
    """SPA nav node. Omit inventory aggregates rather than invent zeros.

    With *ages*, a file carries ``mtime``, its last commit's time in seconds, and a
    directory the newest of its files'; a name the answer leaves undated carries none.
    *kept_time* is a directory's newest time among only the files a time filter kept under
    it, which is what puts it in its group (``(None,)`` when none has one): a grouped or
    windowed answer dates a folder by those, as it counts them.
    """

    node: dict[str, Any] = {
        "name": _display_basename(entry.path),
        "path": entry.path.to_wire(),
        "type": _nav_tree_type(entry),
    }
    if entry.is_tree:
        if loaded:
            nested = children if children is not None else []
            node["children"] = nested
            node["has_children"] = bool(nested)
        else:
            node["children"] = None
            node["has_children"] = True
        if tally is not None:
            node["total_files"] = tally.total_files
            if tally.total_size is not None:
                node["total_size"] = tally.total_size
    else:
        if not entry.is_symlink and not entry.is_gitlink:
            name = _display_basename(entry.path)
            ext = derive_ext(name)
            if ext:
                node["ext"] = ext
            artifact = ArtifactPath(Path(name))
            if artifact.is_compressed:
                inner = artifact.logical_ext
                if inner:
                    node["logical_ext"] = inner
                node["compressed"] = True
                compression = artifact.compression
                if compression is not None:
                    node["compression"] = compression
    if ages is not None:
        stamp = kept_time[0] if kept_time is not None and entry.is_tree else _age_of(entry, ages)
        if stamp is not None:
            node["mtime"] = stamp
    if entry.size is not None:
        node["size"] = entry.size
    return node


def _age_of(entry: GitTreeEntry, ages: RevisionAges) -> int | None:
    """*entry*'s time in the revision's answer: a file's own, a directory's newest, in
    seconds, or ``None`` when the answer leaves it undated. A gitlink is not a name the
    answer dates."""

    if entry.is_gitlink:
        return None
    name = b"/".join(entry.path.segments)
    if entry.is_tree:
        return ages.newest_under(name)
    return ages.time_of(name)


def _identity_fields(entry: GitTreeEntry, *, path: GitPath | None = None) -> dict[str, Any]:
    ident = entry.path if path is None else path
    return {
        "path": ident.to_wire(),
        "display": ident.display(),
        "mode": entry.mode,
        "git_kind": entry.kind,
        "symlink": entry.is_symlink,
        "gitlink": entry.is_gitlink,
        "oid": entry.oid,
    }


def _display_basename(path: GitPath) -> str:
    if not path.segments:
        return ""
    return path.display().rsplit("/", 1)[-1]


def _filter_tail_ext(path: GitPath) -> str:
    """The compound tail the type filter keys on; a kind is chosen by ``blob_logical_ext``."""

    return derive_ext(_display_basename(path))


def _plugin_kind_for_git_path(
    path: GitPath,
    *,
    adapter: str | None = None,
    json_top_level: dict[str, Any] | None = None,
    yaml_top_level: dict[str, Any] | None = None,
    frontmatter: dict[str, Any] | None = None,
    prefix: bytes | None = None,
) -> str | None:
    from metabrowser.plugin_loader.classify import classify_identity
    from metabrowser.server import _PLUGIN_KIND_RULES

    return classify_identity(
        _PLUGIN_KIND_RULES,
        ext=blob_logical_ext(path),
        basename=_display_basename(path),
        adapter=adapter,
        json_top_level=json_top_level,
        yaml_top_level=yaml_top_level,
        frontmatter=frontmatter,
        prefix=prefix,
    )


async def _blob_container_kind(subject: GitRevisionSubject, entry: GitTreeEntry) -> str | None:
    """The container kind a blob is by its magic number, such as a SQLite database's
    whatever its name, or None for a blob no container kind claims."""

    from metabrowser.server import _container_kinds

    head, _size = await subject.tree_source.read_blob_window(
        entry.oid, offset=0, max_bytes=SNIFF_PREFIX_BYTES
    )
    if classify_prefix(head) is not ContentClass.BINARY:
        return None
    kind = plugin_magic_kind(head)
    return kind if kind in _container_kinds() else None


def plugin_magic_kind(prefix: bytes) -> str:
    """The kind of a blob whose bytes sniff as binary: a plugin kind whose ``magic``
    bytes *prefix* holds, or ``binary``. A stored blob is never decompressed, so its
    bytes are the ones a magic number is checked against."""

    from metabrowser.plugin_loader.classify import classify_magic
    from metabrowser.server import _PLUGIN_KIND_RULES

    return classify_magic(_PLUGIN_KIND_RULES, prefix) or "binary"


def plugin_kind_for_git_wire(wire: str) -> str | None:
    """The plugin kind a blob's GitPath wire matches by extension and basename alone."""

    try:
        path = GitPath.from_wire(wire)
    except GitPathError:
        return None
    return _plugin_kind_for_git_path(path)


def _git_blob_content_predicates(
    ext: str, body: bytes
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, dict[str, Any] | None, str | None]:
    from metabrowser.plugin_loader.classify import (
        json_mapping_from_bytes,
        parse_frontmatter_bytes,
        yaml_mapping_from_bytes,
    )

    json_top = json_mapping_from_bytes(body) if ext == ".json" else None
    yaml_top = yaml_mapping_from_bytes(body) if ext in {".yaml", ".yml"} else None
    frontmatter = None
    frontmatter_error = None
    if ext == ".md":
        frontmatter, frontmatter_error = parse_frontmatter_bytes(body)
    return json_top, yaml_top, frontmatter, frontmatter_error


# The extensions `_git_blob_content_predicates` parses anything for.
_CONTENT_PREDICATE_EXTS = frozenset({".json", ".yaml", ".yml", ".md"})


async def _blob_predicates_off_loop(
    ext: str, body: bytes
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, dict[str, Any] | None, str | None]:
    """The predicates on a worker thread, where a parse of a bounded prefix can take
    seconds; a blob no predicate reads skips the thread."""

    if ext not in _CONTENT_PREDICATE_EXTS:
        return None, None, None, None
    return await asyncio.to_thread(_git_blob_content_predicates, ext, body)


def _git_frontmatter_envelope(
    *,
    mapping: dict[str, Any] | None,
    error: str | None,
) -> dict[str, Any]:
    # parse_frontmatter_bytes answers the bounded, JSON-safe copy
    # (metabrowser.frontmatter_yaml), so the mapping goes on the wire as it is.
    fields: dict[str, Any] = {}
    if mapping is not None:
        fields["frontmatter"] = mapping
    return fields | frontmatter_error_fields(error)


# A pinned revision is never trusted, whatever the process's block: every route here was
# handed the pin its request resolved, so the profile is fixed before anything is awaited
# (capabilities.capabilities_for).
_PIN_CAPABILITIES = UNTRUSTED_CAPABILITIES


def _views_for_kind(kind: str, *, prefix: tuple[bytes, str] | None = None) -> list[dict[str, Any]]:
    # Plugin kinds such as diff live in manifests, not VIEW_REGISTRY.
    from metabrowser.server import _views_for_kind as merged_views_for_kind

    return merged_views_for_kind(
        kind, prefix=prefix, active_content=_PIN_CAPABILITIES.active_content
    )


async def _text_views_off_loop(kind: str, ext: str, body: bytes) -> list[dict[str, Any]]:
    """A text blob's views, its kind's offered views decided from its leading bytes on a
    worker thread, since an offer may parse a bounded prefix; a kind with none is listed
    on the loop."""

    from metabrowser.server import _FILE_OFFER_KINDS

    prefix = (body[:_PREDICATE_PREFIX_BYTES], ext)
    if kind not in _FILE_OFFER_KINDS:
        return _views_for_kind(kind, prefix=prefix)
    return await asyncio.to_thread(_views_for_kind, kind, prefix=prefix)


def _passes_min_size(entry: GitTreeEntry, floor: int) -> bool:
    """Unsized blobs and gitlinks drop. Trees are decided by descendants."""

    if entry.is_tree:
        return True
    return entry.size is not None and entry.size >= floor


def _git_filter_active(tree_filter: TreeFilter) -> bool:
    return bool(
        tree_filter.types
        or tree_filter.min_size
        or tree_filter.group is not None
        or tree_filter.recency_seconds
    )


# What a file is when a request asks "which time is it in": a number a request's bands and
# windows decide once per file and every group of the answer then reads (`_GitTimes`). A band
# is the index of an age group, from `age_group_index`; the last two values name no group.
_BUCKET_OUTSIDE = 254  # dated outside the recency window, or undated while a window is set
_BUCKET_UNDATED = 255  # no time known, and no window asks for one


@dataclass(frozen=True, slots=True)
class _GitTimes:
    """What one request knows of a revision's file times: the answer, when there is one, the
    instant its windows and bands are cut at, and which of those it keeps.

    A file the answer does not date (no answer yet, a shallow boundary, a cut read) is in no
    window and no band: it is in Undated, and nowhere else. Every group of a grouped answer
    shares one instance's memo, so the file times are looked up once and each file is
    bucketed once, and the groups partition the times because they cut one bucketing.

    Measured 2026-11-20 on a synthetic index of 40,000 files whose times spread over a year
    (the seven groups' matches and tallies, no other filter, load average 21 to 23, one run
    of five after a warm-up): 296 ms when each group looked up and compared every file's
    time and summed every size in Python, and 32 ms with one bucketing and the sums done at
    C speed. The cost follows the files: 200,000 took 166 ms. Review A of #652 measured
    246 of a 322 ms response in those passes on 40,000 files.
    """

    ages: RevisionAges | None
    as_of: float
    recency: int
    wanted: frozenset[int] | None
    """The buckets that are members, or ``None`` when no time filter is set."""
    cutoffs: tuple[float, ...]
    """The instants the age windows begin at, ascending: a time at or after the Nth latest
    is no older than the Nth window."""
    memo: dict[object, Any] = field(default_factory=dict, compare=False)

    @property
    def active(self) -> bool:
        return self.wanted is not None

    def bucket(self, stamp: int | None) -> int:
        """The bucket of one time: the age group it is in, or one of the two that name none."""

        if stamp is None:
            return _BUCKET_OUTSIDE if self.recency else _BUCKET_UNDATED
        if self.recency and stamp < self.as_of - self.recency:
            return _BUCKET_OUTSIDE
        return len(self.cutoffs) - bisect_right(self.cutoffs, stamp)

    def keeps(self, full: bytes) -> bool:
        """Whether the file at *full*, its path from the revision's root, is a member."""

        if self.wanted is None:
            return True
        stamp = self.ages.time_of(full) if self.ages is not None else None
        return self.bucket(stamp) in self.wanted

    def stamps(self, index: GitBlobIndex, prefix: bytes = b"") -> array[int]:
        """Each of *index*'s blobs' times, in index order (`UNDATED` for none). *prefix* is the
        listed path, which the index's names are relative to."""

        key = ("stamps", id(index), prefix)
        found = self.memo.get(key)
        if found is None:
            found = self.memo[key] = _blob_stamps(index, self.ages, prefix)
        return found

    def buckets(self, index: GitBlobIndex, prefix: bytes = b"") -> bytes:
        """Each of *index*'s blobs' bucket, in index order: the one definition `bucket` gives,
        for every file at once."""

        key = ("buckets", id(index), prefix)
        found = self.memo.get(key)
        if found is None:
            found = self.memo[key] = self._bucket_all(self.stamps(index, prefix))
        return found

    def mask(self, index: GitBlobIndex, prefix: bytes = b"") -> bytes:
        """One byte per blob of *index*: 1 for a member of this request's time filter."""

        assert self.wanted is not None
        key = ("mask", id(index), prefix, self.wanted)
        found = self.memo.get(key)
        if found is None:
            table = bytes(int(value in self.wanted) for value in range(256))
            found = self.memo[key] = self.buckets(index, prefix).translate(table)
        return found

    def _bucket_all(self, stamps: array[int]) -> bytes:
        cutoffs = self.cutoffs
        windows = len(cutoffs)
        outside = self.as_of - self.recency if self.recency else None
        absent = _BUCKET_OUTSIDE if self.recency else _BUCKET_UNDATED
        buckets = bytearray(len(stamps))
        for position, stamp in enumerate(stamps):
            if stamp == UNDATED:
                buckets[position] = absent
            elif outside is not None and stamp < outside:
                buckets[position] = _BUCKET_OUTSIDE
            else:
                buckets[position] = windows - bisect_right(cutoffs, stamp)
        return bytes(buckets)


def _blob_stamps(index: GitBlobIndex, ages: RevisionAges | None, prefix: bytes) -> array[int]:
    """The times of *index*'s blobs, aligned to them: a slice of the answer's own when it names
    the same files in the same order (a revision's root index, always, and a folder's, which
    is that run of its names), and a lookup of each otherwise."""

    count = len(index.blobs)
    if ages is None:
        return array("q", [UNDATED]) * count
    if prefix:
        start = bisect_left(ages.names, prefix + b"/")
        stop = bisect_left(ages.names, prefix + b"0")
        cut = len(prefix) + 1
    else:
        start, stop, cut = 0, len(ages.names), 0
    if stop - start == count:
        named = ages.names[start:stop]
        if cut:
            named = tuple(name[cut:] for name in named)
        if named == tuple(rel for rel, _oid in index.blobs):
            return ages.times[start:stop]
    base = prefix + b"/" if prefix else b""
    stamps = array("q", [UNDATED]) * count
    for position, (rel, _oid) in enumerate(index.blobs):
        found = ages.time_of(base + rel)
        if found is not None:
            stamps[position] = found
    return stamps


def _git_times(
    ages: RevisionAges | None,
    tree_filter: TreeFilter,
    as_of: float,
    memo: dict[object, Any] | None = None,
) -> _GitTimes:
    """The time filter *tree_filter* asks of a revision at the instant *as_of*, and the memo
    its groups share (a fresh one when a request is one group)."""

    group = tree_filter.group
    windows = age_windows()
    wanted: frozenset[int] | None = None
    if group is not None and group.by == "age":
        wanted = frozenset(
            {_BUCKET_UNDATED if group.id == UNDATED_GROUP_ID else age_group_index(group)}
        )
    elif tree_filter.recency_seconds:
        wanted = frozenset(range(len(windows) + 1))
    return _GitTimes(
        ages=ages,
        as_of=as_of,
        recency=tree_filter.recency_seconds,
        wanted=wanted,
        cutoffs=tuple(sorted(as_of - seconds for seconds in windows)),
        memo={} if memo is None else memo,
    )


def _request_instant() -> float:
    """The instant a request cuts its age windows at; tests fix it."""

    return time.time()


def _git_type_group(name: str, ext: str, by_extension: dict[str, str]) -> str:
    """The display group a blob classifies into, as the inventory provider decides it: by
    its name when the registry knows the name, else by its extension, once per extension."""

    registry = load_file_type_registry()
    if registry.classifies_by_name(name):
        return registry.classify(name, ext).group_id
    group = by_extension.get(ext)
    if group is None:
        group = registry.classify("", ext).group_id
        by_extension[ext] = group
    return group


def _git_group_keeps(name: str, ext: str, tree_filter: TreeFilter, memo: dict[str, str]) -> bool:
    """Whether a blob is a member of the filter's File type group. An age group is decided
    by the file's time (`_GitTimes`), not its name."""

    group = tree_filter.group
    if group is None or group.by != "type":
        return True
    return _git_type_group(name, ext, memo) == group.id


def _blob_display_name(rel: bytes) -> str:
    return display_segment(rel.rsplit(b"/", 1)[-1])


def _git_blob_exts(index: GitBlobIndex) -> tuple[str, ...]:
    """Logical extension of every blob, aligned with ``index.blobs``.

    Derived once per tree: chrome tallies, index facts, and every filter read
    it instead of decoding each name again. Equal extensions share one string.
    """

    interned: dict[str, str] = {}
    exts: list[str] = []
    for rel, _oid in index.blobs:
        ext = derive_ext(_blob_display_name(rel))
        exts.append(interned.setdefault(ext, ext))
    return tuple(exts)


def _both(first: bytes | bytearray, second: bytes | bytearray) -> bytearray:
    """The bytes (each 0 or 1) that are 1 in both, as one integer AND."""

    size = len(first)
    return bytearray(
        (int.from_bytes(first, "little") & int.from_bytes(second, "little")).to_bytes(
            size, "little"
        )
    )


def _git_base_matches(
    index: GitBlobIndex,
    exts: tuple[str, ...],
    tree_filter: TreeFilter,
    semantic: frozenset[str],
) -> bytearray:
    """Which of the index's blobs the filter's types, File type group, and size floor keep,
    one byte each in index order. Same rules as ``file_type_match.name_matches_types``;
    the time filter is `_git_filter_matches`'s.

    A name is decoded only for what reads it: a type token that names a file, or a File type
    group. An age group, a window, and a size floor read none.
    """

    folded_types = tuple(ascii_casefold(token) for token in tree_filter.types)
    group = tree_filter.group
    type_group = group if group is not None and group.by == "type" else None
    floor = tree_filter.min_size
    if not folded_types and type_group is None and not floor:
        return bytearray(b"\x01") * len(index.blobs)
    ext_tokens = frozenset(token for token in folded_types if token.startswith("."))
    name_tokens = frozenset(token for token in folded_types if not token.startswith("."))
    suffix_tokens = tuple(token for token in ext_tokens if token in semantic)
    ext_verdicts: dict[str, bool] = {}
    group_memo: dict[str, str] = {}
    matches = bytearray(len(index.blobs))
    for position, ((rel, oid), ext) in enumerate(zip(index.blobs, exts, strict=True)):
        keep = True
        if folded_types:
            verdict = ext_verdicts.get(ext)
            if verdict is None:
                verdict = bool(ext) and (
                    ext in ext_tokens or any(ext.endswith(token) for token in suffix_tokens)
                )
                ext_verdicts[ext] = verdict
            keep = verdict or (
                bool(name_tokens) and ascii_casefold(_blob_display_name(rel)) in name_tokens
            )
        if keep and type_group is not None:
            keep = _git_group_keeps(_blob_display_name(rel), ext, tree_filter, group_memo)
        if keep and floor:
            size = index.sizes.get(oid)
            keep = size is not None and size >= floor
        matches[position] = keep
    return matches


def _git_filter_matches(
    index: GitBlobIndex,
    exts: tuple[str, ...],
    tree_filter: TreeFilter,
    semantic: frozenset[str],
    times: _GitTimes | None = None,
    prefix: bytes = b"",
) -> bytearray:
    """Which of the index's blobs *tree_filter* keeps, one byte each in index order.

    *prefix* is the listed path, which the index's names are relative to, so a file's time
    is looked up under its whole path. The time filter is one lookup in *times*, whose memo
    the groups of a grouped answer share, and the types and size floor are read once for all
    of them.
    """

    if times is None:
        return _git_base_matches(index, exts, tree_filter, semantic)
    key = ("base", id(index), tree_filter.types, tree_filter.min_size, _group_key(tree_filter))
    base = times.memo.get(key)
    if base is None:
        base = times.memo[key] = _git_base_matches(index, exts, tree_filter, semantic)
    if not times.active:
        return bytearray(base)
    return _both(base, times.mask(index, prefix))


def _group_key(tree_filter: TreeFilter) -> str | None:
    """The part of a group that the types and size floor depend on: a File type group's key,
    and nothing for an age group, whose members the time filter decides."""

    group = tree_filter.group
    return group.key if group is not None and group.by == "type" else None


def _git_filter_tallies(
    index: GitBlobIndex,
    exts: tuple[str, ...],
    tree_filter: TreeFilter,
    semantic: frozenset[str],
    times: _GitTimes | None = None,
    prefix: bytes = b"",
) -> GitBlobTallies:
    """Running totals of the blobs *tree_filter* keeps (`_git_filter_matches`)."""

    return index.tallies.select(
        _git_filter_matches(index, exts, tree_filter, semantic, times, prefix)
    )


@dataclass(frozen=True, slots=True)
class _GitTallyView:
    """Subtree totals for one request: the whole index, or one filter's matches.

    A request that filters by time also keeps the blobs' times and which of them it kept, so
    a folder row can be dated by the files that put it in the group (`newest`).
    """

    index: GitBlobIndex
    tallies: GitBlobTallies
    stamps: array[int] | None = None
    matches: bytearray | None = None

    def tally(self, prefix: bytes = b"") -> GitTreeTally:
        return self.tallies.tally(self.index.prefix_spans(prefix))

    def newest(self, prefix: bytes) -> int | None:
        """The newest time among the files kept under *prefix*, or ``None`` when this view
        has none, or only files without a time."""

        if self.stamps is None or self.matches is None:
            return None
        newest = max(
            (
                max(compress(self.stamps[start:stop], self.matches[start:stop]), default=UNDATED)
                for start, stop in self.index.prefix_spans(prefix)
            ),
            default=UNDATED,
        )
        return None if newest == UNDATED else newest


async def _git_tally_view(
    source: GitTreeSource,
    index: GitBlobIndex | None,
    *,
    tree_oid: str,
    tree_filter: TreeFilter,
    semantic: frozenset[str],
    times: _GitTimes | None = None,
    prefix: bytes = b"",
) -> _GitTallyView | None:
    """Totals for the tree at *tree_oid*. A filter's matches are memoized per filter, except
    one that reads file times, which depend on the instant of the request: its groups share
    the request's memo instead."""

    if index is None:
        return None
    if not _git_filter_active(tree_filter):
        return _GitTallyView(index, index.tallies)
    exts = await source.derived(("blob-exts", tree_oid), lambda: _git_blob_exts(index))
    if times is not None and times.active:

        def timed() -> _GitTallyView:
            matches = _git_filter_matches(index, exts, tree_filter, semantic, times, prefix)
            return _GitTallyView(
                index, index.tallies.select(matches), times.stamps(index, prefix), matches
            )

        return await asyncio.to_thread(timed)
    tallies = await source.derived(
        (
            "filter-tallies",
            tree_oid,
            tree_filter.types,
            tree_filter.min_size,
            tree_filter.group.key if tree_filter.group is not None else None,
        ),
        lambda: _git_filter_tallies(index, exts, tree_filter, semantic),
    )
    return _GitTallyView(index, tallies)


def _git_entry_visible(
    entry: GitTreeEntry,
    tree_filter: TreeFilter,
    view: _GitTallyView | None,
    *,
    index_prefix: bytes = b"",
    semantic: frozenset[str] | None = None,
    times: _GitTimes | None = None,
) -> bool:
    """Keep trees that have a matching descendant; drop empty filter dirs."""

    if not _git_filter_active(tree_filter):
        return True
    if entry.is_tree:
        if view is None:
            return True
        prefix = _join_git_prefix(index_prefix, entry.path.segments[-1])
        return view.tally(prefix).total_files > 0
    if tree_filter.types and not name_matches_types(
        _display_basename(entry.path), tree_filter.types, semantic=semantic
    ):
        return False
    if not _git_group_keeps(
        _display_basename(entry.path), _filter_tail_ext(entry.path), tree_filter, {}
    ):
        return False
    if times is not None and times.active and not times.keeps(b"/".join(entry.path.segments)):
        return False
    if tree_filter.min_size:
        return _passes_min_size(entry, tree_filter.min_size)
    return True


def _git_visible_entries(
    entries: tuple[GitTreeEntry, ...],
    tree_filter: TreeFilter,
    view: _GitTallyView | None,
    *,
    index_prefix: bytes,
    semantic: frozenset[str] | None,
    times: _GitTimes | None = None,
) -> tuple[GitTreeEntry, ...]:
    if not _git_filter_active(tree_filter):
        return entries
    return tuple(
        entry
        for entry in entries
        if _git_entry_visible(
            entry, tree_filter, view, index_prefix=index_prefix, semantic=semantic, times=times
        )
    )


# Nodes one ``/api/tree`` response may nest below the listed directory. ``depth``
# is accepted up to MAX_TREE_DEPTH, so without a bound one request could
# materialize a whole repository. Direct children are always listed; a
# directory whose children no longer fit is emitted as the same lazy sentinel
# the depth cap uses, and the SPA loads it on expansion.
#
# The filesystem tree has no cost-derived node bound to mirror: its page
# assembly stops only at the engine's MAX_ASSEMBLED_ROWS consistency guard and
# answers with an error. Measured on a synthetic 100,000-blob pin, on a heavily
# loaded machine: a warm build costs about 19 us per node (8,000 nodes in
# 149 ms), and a response at this bound took 0.4 to 0.6 s end to end for a
# 2.4 MiB body, against about 104,000 nodes unbounded. The default ``depth=2``
# listing of a 4,000-directory tree (8,000 nodes) stays whole.
GIT_NAV_TREE_MAX_NODES = 20_000


@dataclass(slots=True)
class _NavNodeBudget:
    remaining: int


async def _git_nav_tree(
    subject: GitRevisionSubject,
    entries: tuple[GitTreeEntry, ...],
    *,
    remaining_depth: int,
    tree_filter: TreeFilter,
    view: _GitTallyView | None,
    index_prefix: bytes,
    semantic: frozenset[str] | None,
    budget: _NavNodeBudget,
    ages: RevisionAges | None = None,
    times: _GitTimes | None = None,
) -> list[dict[str, Any]]:
    """SPA ``tree`` nodes. Nest while depth and the node budget allow; else a lazy sentinel."""

    if remaining_depth <= 0:
        return []
    nodes: list[dict[str, Any]] = []
    nest = remaining_depth > 1
    # Directories first, matching the filesystem tree contract the SPA renders in
    # server order; ``sorted`` is stable, so names keep the source's byte order.
    for entry in sorted(entries, key=lambda item: not item.is_tree):
        prefix = _join_git_prefix(index_prefix, entry.path.segments[-1]) if entry.is_tree else b""
        tally = view.tally(prefix) if entry.is_tree and view is not None else None
        kept = (
            (view.newest(prefix),)
            if entry.is_tree and view is not None and view.stamps is not None
            else None
        )
        if entry.is_tree and nest and budget.remaining > 0:
            try:
                nested = await subject.tree_source.list_tree_entry(entry)
            except GitObjectUnavailableError:
                nodes.append(_nav_tree_node(entry, tally=tally, ages=ages, kept_time=kept))
                continue
            nested = _git_visible_entries(
                nested, tree_filter, view, index_prefix=prefix, semantic=semantic, times=times
            )
            if len(nested) <= budget.remaining:
                budget.remaining -= len(nested)
                children = await _git_nav_tree(
                    subject,
                    nested,
                    remaining_depth=remaining_depth - 1,
                    tree_filter=tree_filter,
                    view=view,
                    index_prefix=prefix,
                    semantic=semantic,
                    budget=budget,
                    ages=ages,
                    times=times,
                )
                nodes.append(
                    _nav_tree_node(
                        entry,
                        tally=tally,
                        children=children,
                        loaded=True,
                        ages=ages,
                        kept_time=kept,
                    )
                )
                continue
        nodes.append(_nav_tree_node(entry, tally=tally, ages=ages, kept_time=kept))
    return nodes


def _git_tree_filtered(
    view: _GitTallyView | None, tree_filter: TreeFilter
) -> dict[str, int] | None:
    """Subtree filter totals. Omit when sizes are incomplete."""

    if view is None or not _git_filter_active(tree_filter):
        return None
    tally = view.tally()
    if tally.total_size is None:
        return None
    return {
        "files": tally.total_files,
        "size": tally.total_size,
        "entries": tally.total_files,
    }


def _query_int(request: Request, name: str, default: int) -> int:
    raw = request.query_params.get(name, "")
    if raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _with_requested_path(
    payload: dict[str, Any],
    entry: GitTreeEntry,
    requested: GitPath,
    ages: RevisionAges | None,
) -> dict[str, Any]:
    """Name the envelope by the path that was asked for, and date it from *ages*, the answer
    for the revision when one is already kept (a file read starts none)."""

    payload.update(_identity_fields(entry, path=requested))
    folder = payload.get("type") == "folder"
    if folder:
        payload["name"] = _display_basename(requested)
    if ages is not None and not entry.is_gitlink:
        # The time of the last commit that changed it, as the tree's rows say, so the
        # preview header shows the age beside the name; none when it is not known.
        name = b"/".join(requested.segments)
        stamp = ages.newest_under(name) if folder else ages.time_of(name)
        if stamp is not None:
            payload["mtime"] = stamp
    return payload


def _git_text_window(request: Request, entry: GitTreeEntry, ext: str) -> tuple[int, int]:
    """The requested text window's offset and limit, under the filesystem's policy."""

    offset = max(0, _query_int(request, "offset", 0))
    default_limit = TEXT_PREVIEW_CHUNK_BYTES
    if (
        offset == 0
        and syntax_language_for_path(_display_basename(entry.path), ext)
        and SYNTAX_HIGHLIGHT_MAX_BYTES > 0
    ):
        default_limit = min(default_limit, SYNTAX_HIGHLIGHT_MAX_BYTES)
    limit = max(
        1,
        min(_query_int(request, "limit", default_limit), TEXT_PREVIEW_REQUEST_MAX_BYTES),
    )
    return offset, limit


def _git_text_preview_fields(
    request: Request, entry: GitTreeEntry, ext: str, body: bytes
) -> dict[str, Any]:
    """Bounded text window matching filesystem /api/file preview policy."""

    offset, limit = _git_text_window(request, entry, ext)
    return _git_text_fields(offset, limit, body[offset : offset + limit], len(body))


def _git_text_fields(offset: int, limit: int, window: bytes, size: int) -> dict[str, Any]:
    # `bytes_read` is the cursor past this window, as the filesystem route reports it,
    # not the window's length: Load more reads it as the next offset and as the
    # notice's "Showing" figure. Reporting the length left a pin's notice at the first
    # window's size after every Load more, and the next request re-read from there.
    bytes_read = offset + len(window)
    return {
        "content": window.decode("utf-8", "replace"),
        "content_offset": offset,
        "content_bytes": len(window),
        "bytes_read": bytes_read,
        "content_truncated": bytes_read < size,
        "content_preview_limit": limit,
        "content_max_preview_limit": TEXT_PREVIEW_REQUEST_MAX_BYTES,
        "highlight_disabled": (
            SYNTAX_HIGHLIGHT_MAX_BYTES <= 0 or bytes_read > SYNTAX_HIGHLIGHT_MAX_BYTES
        ),
    }


def _blob_too_large_payload(exc: GitBlobTooLargeError) -> dict[str, Any]:
    return {
        "error": exc.reader_message,
        "detail": str(exc),
        "code": exc.code,
        "oid": exc.oid,
        "size": exc.size,
        "max_bytes": exc.max_bytes,
    }


def _object_unavailable_payload(
    exc: GitObjectUnavailableError | GitObjectCorruptError,
) -> dict[str, Any]:
    return {"error": exc.reader_message, "detail": str(exc), "code": exc.code, "oid": exc.oid}


def _json(payload: dict[str, Any], *, status_code: int = 200) -> JSONResponse:
    return JSONResponse(payload, status_code=status_code, headers={"cache-control": "no-store"})


def git_content_failure_response(exc: GitError) -> JSONResponse:
    """Typed envelope for a Git failure on a pin. No git text, so no local paths.

    Statuses match ``/api/git/*``: a timeout is 504 because a retry can
    plausibly fix it, and any other failure is 500. An object the store lacks
    and an oversized blob keep their own 404 and 413 envelopes; a corrupt object is 409.
    """

    if isinstance(exc, (GitObjectUnavailableError, GitObjectCorruptError)):
        return _json(_object_unavailable_payload(exc), status_code=exc.http_status)
    if isinstance(exc, GitBlobTooLargeError):
        return _json(_blob_too_large_payload(exc), status_code=413)
    if isinstance(exc, GitTimeoutError):
        return _json(
            {"error": exc.reader_message, "detail": "git command timed out", "code": "git_timeout"},
            status_code=504,
        )
    return _json(
        {"error": exc.reader_message, "detail": "git command failed", "code": "git_failed"},
        status_code=500,
    )


def _typed_git_failures[**P, R: Response](
    handler: Callable[P, Awaitable[R]],
) -> Callable[P, Awaitable[R | JSONResponse]]:
    """The one place a pin route turns an escaped ``GitError`` into a response.

    Handlers still answer the failures they give a route-specific shape, such
    as a plain 404 on ``/raw``. Everything else in the family lands here instead
    of becoming a bare 500.
    """

    @functools.wraps(handler)
    async def guarded(*args: P.args, **kwargs: P.kwargs) -> R | JSONResponse:
        try:
            return await handler(*args, **kwargs)
        except GitError as exc:
            log.warning("git pin %s failed: %s", handler.__name__, failure_detail(exc))
            return git_content_failure_response(exc)

    return guarded


@dataclass(frozen=True, slots=True)
class _GitRollupEntry:
    path: str
    parent: str
    name: str
    type: str
    ext: str
    size: int
    mtime_ns: int
    gitignored: bool
    total_files: int | None


def _dir_rollup_entry(path: GitPath, parent: GitPath, *, total_files: int) -> _GitRollupEntry:
    wire = path.to_wire()
    return _GitRollupEntry(
        path=wire,
        parent=parent.to_wire() if path.segments else wire,
        name=_display_basename(path),
        type="dir",
        ext="",
        size=0,
        mtime_ns=0,
        gitignored=False,
        total_files=total_files,
    )


def _rollup_entries_from_index(
    index: GitBlobIndex, tree_path: GitPath
) -> dict[str, _GitRollupEntry] | None:
    """Map one blob index to rollup entries. ``None`` when any blob size is missing."""

    root_tally = index.tally()
    if root_tally.total_size is None:
        return None
    root_wire = tree_path.to_wire()
    entries: dict[str, _GitRollupEntry] = {
        root_wire: _GitRollupEntry(
            path=root_wire,
            parent=root_wire,
            name=_display_basename(tree_path),
            type="dir",
            ext="",
            size=0,
            mtime_ns=0,
            gitignored=False,
            total_files=root_tally.total_files,
        )
    }
    for rel, oid in index.blobs:
        size = index.sizes.get(oid)
        if size is None:
            return None
        parts = rel.split(b"/")
        cursor = tree_path
        parent_wire = root_wire
        for index_part, segment in enumerate(parts):
            cursor = cursor.child(segment)
            wire = cursor.to_wire()
            last = index_part == len(parts) - 1
            if last:
                display = display_segment(segment)
                entries[wire] = _GitRollupEntry(
                    path=wire,
                    parent=parent_wire,
                    name=display,
                    type="file",
                    ext=derive_ext(display),
                    size=size,
                    mtime_ns=0,
                    gitignored=False,
                    total_files=None,
                )
            elif wire not in entries:
                rel_prefix = b"/".join(parts[: index_part + 1])
                entries[wire] = _GitRollupEntry(
                    path=wire,
                    parent=parent_wire,
                    name=display_segment(segment),
                    type="dir",
                    ext="",
                    size=0,
                    mtime_ns=0,
                    gitignored=False,
                    total_files=index.tally(rel_prefix).total_files,
                )
            parent_wire = wire
    return entries


def _missing_blob_oid(index: GitBlobIndex) -> str:
    for _name, oid in index.blobs:
        if oid not in index.sizes:
            return oid
    raise RuntimeError("blob index reported incomplete sizes without a missing oid")


@_typed_git_failures
async def git_revision_rollup(
    request: Request,
    subject: GitRevisionSubject,
    options: RollupOptions,
) -> JSONResponse:
    """Bounded directory rollup from recursive blob names and sizes. No mtime."""

    try:
        path = _git_path_from_query(request)
    except GitPathError:
        return _json(_NOT_FOUND, status_code=404)
    try:
        located = await subject.tree_source.resolve_path(path)
        if located is None or not located.is_tree:
            return _json(_NOT_FOUND, status_code=404)
        index = await subject.tree_source.blob_index(path)
        children = await subject.tree_source.list_tree(path)
    except GitObjectUnavailableError as exc:
        return _json(_object_unavailable_payload(exc), status_code=404)
    wire = path.to_wire()
    if index is None:
        return _json(
            {
                "subject": "git_revision",
                "root": "",
                "path": wire,
                "node": None,
                "ext_tallies": [],
                "file_type_breakdown": None,
                "file_type_legend": None,
                "index_status": "truncated",
                "indexed_files": 0,
                "max_files": INVENTORY_MAX_FILES,
                "truncated": True,
            }
        )
    # The body is capped by ``options.max_nodes``, so the memo holds a small
    # response, not the per-blob entries it was reduced from.
    status_code, payload = await subject.tree_source.derived(
        ("rollup", wire, options),
        lambda: _git_rollup_payload(index, path, children, options),
    )
    return _json(payload, status_code=status_code)


def _git_rollup_payload(
    index: GitBlobIndex,
    path: GitPath,
    children: tuple[GitTreeEntry, ...],
    options: RollupOptions,
) -> tuple[int, dict[str, Any]]:
    wire = path.to_wire()
    entries = _rollup_entries_from_index(index, path)
    if entries is None:
        missing_oid = _missing_blob_oid(index)
        return 404, {
            "error": f"object_unavailable: {missing_oid}",
            "code": "object_unavailable",
            "oid": missing_oid,
        }
    for child in children:
        if not child.is_tree:
            continue
        child_wire = child.path.to_wire()
        if child_wire in entries:
            continue
        child_tally = index.tally(child.path.segments[-1])
        entries[child_wire] = _dir_rollup_entry(
            child.path, path, total_files=child_tally.total_files
        )
    built = build_rollup(
        entries,
        group_rollup_children(entries),
        wire,
        options,
        False,
    )
    if built is None:
        return 404, _NOT_FOUND
    node = built["node"]
    return 200, {
        "subject": "git_revision",
        "root": "",
        "path": wire,
        "node": node,
        "ext_tallies": built["ext_tallies"],
        "file_type_breakdown": built["file_type_breakdown"],
        "file_type_legend": build_file_type_legend(built["file_type_breakdown"]),
        "index_status": "done",
        "indexed_files": node["total_files"],
        "max_files": INVENTORY_MAX_FILES,
        "truncated": False,
    }


def _git_catalog_body(index: GitBlobIndex, exts: tuple[str, ...]) -> bytes:
    files: list[dict[str, str]] = []
    for (rel, _oid), ext in zip(index.blobs, exts, strict=True):
        path = _git_path_from_relative(rel)
        files.append({"p": path.to_wire(), "e": ext, "n": _blob_display_name(rel)})
    payload = {"complete": True, "truncated": False, "revision": 1, "files": files}
    return bytes(JSONResponse(payload).body)


@_typed_git_failures
async def git_revision_catalog(request: Request, subject: GitRevisionSubject) -> Response:
    """One-shot Quick File catalog from recursive blob names. No watcher."""

    del request
    source = subject.tree_source
    try:
        index = await source.blob_index()
    except GitObjectUnavailableError as exc:
        return _json(_object_unavailable_payload(exc), status_code=404)
    if index is None:
        return _json({"complete": True, "truncated": True, "revision": 1, "files": []})
    exts = await _git_root_blob_exts(subject, index)
    # The rendered body is kept, not the row dicts: it is the smaller form, and
    # a repeat request skips serialization as well as the scan.
    body = await source.derived(
        ("catalog-body", subject.tree_oid), lambda: _git_catalog_body(index, exts)
    )
    return Response(
        content=body, media_type="application/json", headers={"cache-control": "no-store"}
    )


async def _git_root_blob_exts(subject: GitRevisionSubject, index: GitBlobIndex) -> tuple[str, ...]:
    return await subject.tree_source.derived(
        ("blob-exts", subject.tree_oid), lambda: _git_blob_exts(index)
    )


def _git_path_from_relative(name: bytes) -> GitPath:
    return GitPath.from_segments(*name.split(b"/"))


_GIT_INDEX_PROVIDER = "git"
_GIT_INDEX_CONTRACT = "git-revision"


@dataclass(frozen=True, slots=True)
class _GitIndexFacts:
    truncated: bool
    indexed_files: int
    indexed_dirs: int
    suffixes: tuple[tuple[str, int], ...]


def _git_extension_counts(exts: tuple[str, ...]) -> Counter[str]:
    counts = Counter(exts)
    del counts[""]
    return counts


def _git_tree_summary(index: GitBlobIndex | None) -> dict[str, int] | None:
    """Whole-tree tracked/ignored split. Omit when sizes are incomplete."""

    if index is None:
        return None
    tally = index.tally()
    if tally.total_size is None:
        return None
    return {
        "files": tally.total_files,
        "size": tally.total_size,
        "ignored_files": 0,
        "ignored_size": 0,
    }


def _git_tree_index_chrome(
    index: GitBlobIndex | None, exts: tuple[str, ...] = ()
) -> dict[str, Any]:
    """Whole-tree filter tallies and summary. Ignore is absent, so ignored is 0.

    *exts* is ``_git_blob_exts(index)``. The caller memoizes the result per pin.
    """

    truncated = index is None
    preset_rows = [[preset["id"], 0, 0] for preset in FILTER_TYPE_PRESETS]
    payload: dict[str, Any] = {
        "tally_cache_status": "truncated" if truncated else "done",
        "tally_cache_max_files": INVENTORY_MAX_FILES,
    }
    summary = _git_tree_summary(index)
    if summary is not None:
        payload["summary"] = summary
    payload["extensions"] = []
    payload["canonical_extensions"] = []
    payload["type_families"] = []
    payload["type_presets"] = preset_rows
    if index is None:
        return payload
    payload.update(
        type_tally(
            ((_blob_display_name(rel), ext),)
            for (rel, _oid), ext in zip(index.blobs, exts, strict=True)
        )
    )
    return payload


async def _git_index_facts(subject: GitRevisionSubject) -> _GitIndexFacts:
    index = await subject.tree_source.blob_index()
    if index is None:
        return _GitIndexFacts(True, 0, 0, ())
    exts = await _git_root_blob_exts(subject, index)
    return await subject.tree_source.derived(
        ("index-facts", subject.tree_oid), lambda: _git_index_facts_from(index, exts)
    )


def _git_index_facts_from(index: GitBlobIndex, exts: tuple[str, ...]) -> _GitIndexFacts:
    dirs: set[bytes] = set()
    for rel, _oid in index.blobs:
        parts = rel.split(b"/")
        for depth in range(len(parts) - 1):
            dirs.add(b"/".join(parts[: depth + 1]))
    suffixes = tuple(
        sorted(_git_extension_counts(exts).items(), key=lambda item: (-item[1], item[0]))
    )
    return _GitIndexFacts(False, len(index.blobs), len(dirs), suffixes)


def _git_index_common(facts: _GitIndexFacts) -> dict[str, Any]:
    return {
        "status": "truncated" if facts.truncated else "done",
        "indexed_files": facts.indexed_files,
        "max_files": INVENTORY_MAX_FILES,
        "truncated": facts.truncated,
        "complete": True,
        "provider": _GIT_INDEX_PROVIDER,
        "contract": _GIT_INDEX_CONTRACT,
    }


async def _git_ages_status(subject: GitRevisionSubject) -> AgesStatus:
    """The revision's file ages, asking for them when nothing has: never waits on Git.

    The service reads them in the background; a page shows what is here and asks again
    (`/api/index/progress`) until the state is no longer `dating`.
    """

    source = subject.tree_source

    async def names() -> tuple[bytes, ...] | None:
        index = await source.blob_index()
        if index is None:
            return None
        return await source.derived(
            ("ages-names", subject.tree_oid), lambda: tuple(rel for rel, _oid in index.blobs)
        )

    return file_ages_service().request(subject.command_target, subject.commit_oid, names)


@_typed_git_failures
async def git_revision_index_progress(
    subject: GitRevisionSubject, *, ages: bool = True
) -> JSONResponse:
    """Terminal crawl footer for a pin. There is no walker.

    It also asks for the revision's file ages and says how that stands, which is what a
    page polls; `ages=0` leaves them alone, for a command that only waits for the index
    (`wait_for_index`) and would otherwise start a read of a large history it never prints.
    """

    try:
        facts = await _git_index_facts(subject)
    except GitObjectUnavailableError as exc:
        return _json(_object_unavailable_payload(exc), status_code=404)
    payload = {**_git_index_common(facts), "active": False}
    if ages:
        status = await _git_ages_status(subject)
        if status.state != "unavailable":
            payload["ages"] = status.wire(files=facts.indexed_files)
    return _json(payload)


@_typed_git_failures
async def git_revision_index_meta(subject: GitRevisionSubject) -> JSONResponse:
    """Index summary from blob names. No mtime or watcher facts."""

    try:
        facts = await _git_index_facts(subject)
    except GitObjectUnavailableError as exc:
        return _json(_object_unavailable_payload(exc), status_code=404)
    return _json(
        {
            **_git_index_common(facts),
            "indexed_dirs": facts.indexed_dirs,
            "suffixes": [{"ext": ext, "count": count} for ext, count in facts.suffixes],
        }
    )


def _file_ages_capability() -> dict[str, Any]:
    """Whether this Git can date a revision's files, and the sentence for a page and
    `metab --doctor` to say when it cannot (`git/file_ages.py`)."""

    availability = file_ages_availability()
    return {
        "available": availability.available,
        "minimum_git": file_ages_version_label(),
        "hint": availability.hint,
    }


@_typed_git_failures
async def git_revision_capabilities(subject: GitRevisionSubject) -> JSONResponse:
    """Observation surface for a pin: complete, no watcher, events off.

    The content-trust block is the same process-wide answer the filesystem
    route publishes. It is what the shell reads to decide whether a document
    gets its executing view, and a pinned blob is browsed the same way, so
    leaving it out would hide the profile exactly where it applies.
    """

    try:
        facts = await _git_index_facts(subject)
    except GitObjectUnavailableError as exc:
        return _json(_object_unavailable_payload(exc), status_code=404)
    return _json(
        {
            "backends": [
                {
                    "prefix": ".",
                    "mode": "none",
                    "reason": "git-revision-immutable",
                    "state": "idle",
                }
            ],
            "index": {
                "complete": True,
                "indexed_files": facts.indexed_files,
                "max_files": INVENTORY_MAX_FILES,
                "truncated": facts.truncated,
                "provider": _GIT_INDEX_PROVIDER,
                "contract": _GIT_INDEX_CONTRACT,
            },
            "events": {"stream": "off", "reason": "git-revision-no-watcher"},
            "file_ages": _file_ages_capability(),
            "capabilities": _PIN_CAPABILITIES.as_wire(),
        }
    )


def _recent_dir_names(rel: bytes) -> dict[str, list[str]]:
    """The folders above a Recent row, by name as a person reads them: a row's path is a
    GitPath wire, whose folders the page draws from this, and not from the wire."""

    folders = rel.split(b"/")[:-1]
    return {"dir_names": [display_segment(folder) for folder in folders]} if folders else {}


@_typed_git_failures
async def git_revision_recent(
    subject: GitRevisionSubject,
    *,
    window: str,
    limit: int,
    types: tuple[str, ...],
    min_size: int,
    prefix: str,
) -> JSONResponse:
    """`/api/recent` on a Git revision: the files the last commits changed inside *window*,
    newest first, as a folder's Recent view lists them.

    Only a file with a time can be inside a window, so the answer says how many files that
    pass the other filters it could not date (`undated`, whatever the window: a window
    cannot place them, and they may be inside it) and how the read of the times stands
    (`ages`): a page that gets `dating` asks again when it lands. The same filters a tree
    takes (`types`, `min_size`) apply, and *prefix* is a directory's GitPath wire.
    """

    try:
        prefix_bytes = b"/".join(GitPath.from_wire(prefix).segments) if prefix else b""
    except GitPathError:
        return _json(dict(_NOT_FOUND), status_code=404)
    try:
        index = await subject.tree_source.blob_index()
    except GitObjectUnavailableError as exc:
        return _json(_object_unavailable_payload(exc), status_code=404)
    status = await _git_ages_status(subject)
    payload: dict[str, Any] = {
        "root": "",
        "gitignored_dirs": [],
        "window": window,
        "limit": limit,
        "tally_cache_status": "truncated" if index is None else "done",
    }
    if status.state != "unavailable":
        payload["ages"] = status.wire(files=len(index.blobs) if index is not None else None)
    if index is None or status.ages is None:
        return _json(
            {
                **payload,
                "entries_flat": [],
                "total_matching": 0,
                "total_matching_exact": index is not None,
                "truncated": False,
                "undated": 0,
            }
        )
    ages = status.ages
    exts = await subject.tree_source.derived(
        ("blob-exts", subject.tree_oid), lambda: _git_blob_exts(index)
    )
    seconds = RECENT_WINDOW_SECONDS[window]
    tree_filter = TreeFilter(
        recency_seconds=int(seconds or 0), types=types, min_size=min_size, include_ignored=True
    )
    times = _git_times(ages, tree_filter, _request_instant())
    semantic = semantic_extension_tokens(types)

    def build() -> tuple[list[dict[str, Any]], int, int]:
        stamps = times.stamps(index)
        passing = _git_filter_matches(
            index, exts, replace(tree_filter, recency_seconds=0), semantic
        )
        inside = times.mask(index) if times.active else None
        spans = index.prefix_spans(prefix_bytes) if prefix_bytes else ((0, len(index.blobs)),)
        undated = total = 0

        def candidates() -> Iterator[tuple[int, bytes, int]]:
            nonlocal undated, total
            for start, stop in spans:
                for position in range(start, stop):
                    if not passing[position]:
                        continue
                    stamp = stamps[position]
                    if stamp == UNDATED:
                        undated += 1
                    elif inside is None or inside[position]:
                        total += 1
                        yield (-stamp, index.blobs[position][0], position)

        # The newest `limit`, not a sort of every match: the same order (newest first, then
        # by name) at a cost that follows the files and not their number times log.
        newest = heapq.nsmallest(limit, candidates())
        rows = [
            {
                "name": _blob_display_name(rel),
                "path": GitPath.from_segments(*rel.split(b"/")).to_wire(),
                "type": "file",
                "size": index.sizes.get(index.blobs[position][1]) or 0,
                "mtime": float(-negated),
                "ext": exts[position],
                **_recent_dir_names(rel),
            }
            for negated, rel, position in newest
        ]
        return rows, total, undated

    rows, total, undated = await asyncio.to_thread(build)
    return _json(
        {
            **payload,
            "entries_flat": rows,
            "total_matching": total,
            "total_matching_exact": True,
            "truncated": total > len(rows),
            "undated": undated,
        }
    )


@_typed_git_failures
async def git_revision_tree(
    request: Request,
    subject: GitRevisionSubject,
    tree_filter: TreeFilter,
) -> JSONResponse:
    """List one Git tree. ``entries`` are Git facts; ``tree`` is the SPA nav."""

    payload, status = await _git_revision_tree_payload(request, subject, tree_filter)
    return _json(payload, status_code=status)


@_typed_git_failures
async def git_revision_tree_groups(
    request: Request,
    subject: GitRevisionSubject,
    tree_filter: TreeFilter,
    group_by: GroupBy,
) -> JSONResponse:
    """`group_by` on a Git revision: each group's tree, as `git_revision_tree` lists it.

    An age split cuts every band at one instant, so the bands partition the file times, and
    ends in Undated: the files whose time the answer does not know. Where the answer says
    why (`older_than`, a shallow boundary or a cut read), the group says so in its name.

    The state of the read of the times is asked once, and every file is bucketed once at that
    instant (`_GitTimes.memo`), so the groups are cut from one state of one answer and the
    split costs one pass over the files and not one per group.
    """

    groups: list[dict[str, Any]] = []
    envelope: dict[str, Any] | None = None
    as_of = _request_instant()
    status = await _git_ages_status(subject)
    memo: dict[object, Any] = {}
    for group in groups_for(group_by, undated=True):
        if (
            group.by == "age"
            and group.id != UNDATED_GROUP_ID
            and age_band(group, tree_filter.recency_seconds).empty
        ):
            continue
        payload, code = await _git_revision_tree_payload(
            request,
            subject,
            replace(tree_filter, group=group),
            as_of=as_of,
            ages_status=status,
            memo=memo,
            tallies=False,
        )
        if code != 200:
            return _json(payload, status_code=code)
        envelope = envelope or payload
        row = group_row(group, payload)
        if group.id == UNDATED_GROUP_ID:
            row["label"] = _undated_label(payload.get("ages"))
        groups.append(row)
    grouped = groups_payload(group_by, groups, envelope)
    # A revision has no served root folder; its envelope names the path it lists.
    grouped["root"] = envelope.get("display") if envelope is not None else None
    if envelope is not None and "ages" in envelope:
        grouped["ages"] = envelope["ages"]
    if status.ages is not None:
        # The Modified within counts, as the ungrouped tree carries them, so a page that
        # draws the groups when the answer lands has them with the rows.
        grouped["recency_tallies"] = await _git_recency_tallies(status.ages, as_of)
    return _json(grouped)


def _undated_label(ages: object) -> str:
    """What the Undated group is called: with the time it is known to be older than, when the
    answer has one (a shallow boundary, or a read cut at the oldest commit it reached)."""

    state = ages.get("state") if isinstance(ages, dict) else None
    if state == "dating":
        return "Undated, reading file ages…"
    if state == "failed":
        return "Undated, file ages could not be read"
    older_than = ages.get("older_than") if isinstance(ages, dict) else None
    if not isinstance(older_than, int):
        return "Undated"
    day = datetime.fromtimestamp(older_than, tz=UTC).strftime("%Y-%m-%d")
    return f"Undated, older than {day}"


async def _git_recency_tallies(ages: RevisionAges, as_of: float) -> list[list[object]]:
    """``[window, files, 0]`` for each recency window, as the Modified within menu counts: how
    many dated files changed inside it. Ignore is absent, so the second count is 0.

    The sorted times belong to the answer (`RevisionAges.sorted_times`), so a replaced answer
    is counted afresh."""

    ordered = await asyncio.to_thread(ages.sorted_times)
    rows: list[list[object]] = []
    for key, seconds in RECENT_WINDOW_SECONDS.items():
        if not seconds:
            continue
        inside = len(ordered) - bisect_left(ordered, as_of - seconds)
        rows.append([key, inside, 0])
    return rows


async def _git_revision_tree_payload(
    request: Request,
    subject: GitRevisionSubject,
    tree_filter: TreeFilter,
    *,
    as_of: float | None = None,
    ages_status: AgesStatus | None = None,
    memo: dict[object, Any] | None = None,
    tallies: bool = True,
) -> tuple[dict[str, Any], int]:
    """One tree's payload. A grouped answer passes the *as_of* instant, the *ages_status* it
    asked once, and the *memo* its groups share, and leaves the Modified within *tallies* to
    itself."""

    remaining_depth = _tree_depth_from_query(request.query_params.get("depth", ""))
    try:
        path = _git_path_from_query(request)
    except GitPathError:
        return dict(_NOT_FOUND), 404
    instant = _request_instant() if as_of is None else as_of
    try:
        located = await subject.tree_source.resolve_path(path)
        if located is None or not located.is_tree:
            return dict(_NOT_FOUND), 404
        source = subject.tree_source
        index = await source.blob_index(path)
        semantic = semantic_extension_tokens(tree_filter.types)
        if ages_status is None:
            ages_status = await _git_ages_status(subject)
        times = _git_times(ages_status.ages, tree_filter, instant, memo)
        view = await _git_tally_view(
            source,
            index,
            tree_oid=located.oid,
            tree_filter=tree_filter,
            semantic=semantic,
            times=times,
            prefix=b"/".join(path.segments),
        )
        if remaining_depth <= 0:
            entries: tuple[GitTreeEntry, ...] = ()
            tree_nodes: list[dict[str, Any]] = []
        else:
            entries = await source.list_tree(path)
            entries = _git_visible_entries(
                entries, tree_filter, view, index_prefix=b"", semantic=semantic, times=times
            )
            tree_nodes = await _git_nav_tree(
                subject,
                entries,
                remaining_depth=remaining_depth,
                tree_filter=tree_filter,
                view=view,
                index_prefix=b"",
                semantic=semantic,
                budget=_NavNodeBudget(GIT_NAV_TREE_MAX_NODES - len(entries)),
                ages=ages_status.ages,
                times=times,
            )
        root_index = index if not path.segments else await source.blob_index()
    except GitObjectUnavailableError as exc:
        return (_object_unavailable_payload(exc), 404)
    assert located is not None
    chrome = await _git_root_index_chrome(subject, root_index)
    filtered = _git_tree_filtered(view, tree_filter)
    payload: dict[str, Any] = {
        "subject": "git_revision",
        "path": path.to_wire(),
        "display": path.display(),
        "oid": located.oid,
        "kind": "tree",
        "entries": [_listing_entry(entry) for entry in entries],
        "tree": tree_nodes,
        **chrome,
    }
    if ages_status.state != "unavailable":
        # Where the Git cannot read file ages the key is absent and nothing else changes;
        # `/api/capabilities` says why.
        payload["ages"] = ages_status.wire(
            files=len(root_index.blobs) if root_index is not None else None
        )
    if tallies and ages_status.ages is not None:
        payload["recency_tallies"] = await _git_recency_tallies(ages_status.ages, instant)
    if filtered is None and tree_filter.group is not None:
        # A group's answer always says what it holds: its files when blob sizes are
        # incomplete, and nothing it cannot count when the index is truncated, so the
        # grouped answer keeps every group that shows anything (tree_groups.groups_payload).
        counted = view.tally().total_files if view is not None else None
        filtered = {"files": counted, "size": None, "entries": counted}
    if filtered is not None:
        payload["filtered"] = filtered
    return payload, 200


async def _git_root_index_chrome(
    subject: GitRevisionSubject, root_index: GitBlobIndex | None
) -> dict[str, Any]:
    if root_index is None:
        return _git_tree_index_chrome(None)
    exts = await _git_root_blob_exts(subject, root_index)
    return await subject.tree_source.derived(
        ("index-chrome", subject.tree_oid), lambda: _git_tree_index_chrome(root_index, exts)
    )


def _git_readme_child(
    children: tuple[GitTreeEntry, ...],
) -> tuple[GitTreeEntry | None, bool]:
    """Pick a direct-child README blob. Symlinks and gitlinks are not READMEs."""

    truncated = len(children) > FOLDER_DISCOVERY_MAX_ENTRIES
    scanned = children[:FOLDER_DISCOVERY_MAX_ENTRIES]
    by_name: dict[str, GitTreeEntry] = {}
    for child in scanned:
        if child.is_symlink or child.is_gitlink or not child.is_blob:
            continue
        name = _display_basename(child.path)
        if name.casefold() != "readme.md":
            continue
        by_name[name] = child
    chosen = choose_readme_name(list(by_name))
    return by_name.get(chosen), truncated


def _folder_views(*, readme: bool, tally: GitTreeTally | None) -> list[dict[str, Any]]:
    """Overview when a README or complete tally exists; treemap needs sizes.

    Overview alone has no other tab to switch to, so it is served without its key.
    """

    complete = tally is not None and tally.total_size is not None
    wanted: set[str] = set()
    if readme or complete:
        wanted.add("overview")
    if complete:
        wanted.add("treemap")
    return live_view_keys([view for view in _views_for_kind("folder") if view.get("id") in wanted])


def _dir_tally_payload(tally: GitTreeTally | None) -> dict[str, Any]:
    if tally is None:
        return {}
    payload: dict[str, Any] = {"total_files": tally.total_files}
    if tally.total_size is not None:
        payload["total_size"] = tally.total_size
    return {"dir": payload}


def _tree_file_payload(
    entry: GitTreeEntry,
    children: tuple[GitTreeEntry, ...],
    *,
    tally: GitTreeTally | None,
) -> dict[str, Any]:
    """SPA folder chrome. Keep Git ``tree`` identity; omit mtime and ignore."""

    readme, truncated = _git_readme_child(children)
    return {
        "subject": "git_revision",
        "type": "folder",
        "kind": "folder",
        "name": _display_basename(entry.path),
        "views": _folder_views(readme=readme is not None, tally=tally),
        "readme_path": readme.path.to_wire() if readme else "",
        "readme_search_truncated": truncated,
        **_dir_tally_payload(tally),
        **_identity_fields(entry),
    }


def _gitlink_file_payload(entry: GitTreeEntry) -> dict[str, Any]:
    return {
        "subject": "git_revision",
        "type": "gitlink",
        "kind": "commit",
        "views": [],
        **_identity_fields(entry),
    }


async def _blob_file_payload(entry: GitTreeEntry, body: bytes, request: Request) -> dict[str, Any]:
    ext = blob_logical_ext(entry.path)
    payload: dict[str, Any] = {
        "subject": "git_revision",
        "size": len(body),
        **_identity_fields(entry),
    }
    if ext:
        payload["ext"] = ext
    if entry.is_symlink:
        payload.update(
            {
                "type": "symlink",
                "kind": "symlink",
                "views": [],
                "content": body.decode("utf-8", "replace"),
                "content_offset": 0,
                "content_bytes": len(body),
                "content_truncated": False,
            }
        )
        return payload
    content_class = classify_prefix(body)
    if ext in BROWSER_IMAGE_EXTS:
        payload.update(
            {
                "type": "image",
                "kind": "image",
                "views": _views_for_kind("image"),
            }
        )
        return payload
    if content_class is ContentClass.BINARY or (
        ext not in BROWSER_TEXT_EXTS and content_class is not ContentClass.TEXT
    ):
        kind = plugin_magic_kind(body[:SNIFF_PREFIX_BYTES])
        payload.update({"type": "binary", "kind": kind, "views": _views_for_kind(kind)})
        return payload
    if ext == ".jsonl":
        from metabrowser.jsonl_view import parse_jsonl_bytes

        # Off the loop, as the filesystem envelope does: a blob can be as large as
        # the preview bound, and parsing it is synchronous.
        parsed = await asyncio.to_thread(parse_jsonl_bytes, body)
        adapter = parsed.get("summary", {}).get("adapter")
        adapter_name = adapter if isinstance(adapter, str) else None
        kind = _plugin_kind_for_git_path(entry.path, adapter=adapter_name) or classify_by_ext(
            ext, adapter_name
        )
        payload.update(
            {
                "type": "jsonl",
                "kind": kind,
                "views": _views_for_kind(kind),
                **parsed,
            }
        )
        return payload
    json_top, yaml_top, frontmatter, frontmatter_error = await _blob_predicates_off_loop(ext, body)
    kind = _plugin_kind_for_git_path(
        entry.path,
        json_top_level=json_top,
        yaml_top_level=yaml_top,
        frontmatter=frontmatter,
        prefix=body[:SNIFF_PREFIX_BYTES],
    ) or (classify_by_ext(ext) if ext else "text")
    payload.update(
        {
            "type": "text",
            "kind": kind,
            "views": await _text_views_off_loop(kind, ext, body),
            **_git_text_preview_fields(request, entry, ext, body),
            **_git_frontmatter_envelope(mapping=frontmatter, error=frontmatter_error),
        }
    )
    return payload


# Every content predicate reads a bounded prefix (`CONTENT_PREDICATE_MAX_BYTES`). One
# byte past the largest gives each the answer the whole blob would: a JSON document past
# its cap is refused, and a front-matter fence it does not close is reported as not
# closed within the bound.
_PREDICATE_PREFIX_BYTES = CONTENT_PREDICATE_MAX_BYTES + 1


async def _windowed_blob_file_response(
    request: Request,
    source: GitTreeSource,
    entry: GitTreeEntry,
    size: int,
    *,
    requested: GitPath,
    wire: str,
    ages: RevisionAges | None,
) -> JSONResponse:
    """``/api/file`` for a blob larger than the pin reads whole.

    The filesystem types a large file from its extension and a bounded sniff, then
    serves the requested text window. A pin does the same from a streamed window, so
    the blob is never held whole and nothing is refused for its size before it is
    classified. Like a compressed artifact, a blob streams from its start, so reaching
    an offset costs reading up to it: a text window is clipped to end within the pin's
    ceiling, and one that would start past it is 416, as a compressed file is past its
    decompression budget.
    """

    ext = blob_logical_ext(entry.path)
    payload: dict[str, Any] = {"subject": "git_revision", "size": size, **_identity_fields(entry)}
    if ext:
        payload["ext"] = ext
    if ext in BROWSER_IMAGE_EXTS:
        payload.update({"type": "image", "kind": "image", "views": _views_for_kind("image")})
        return _json(_with_requested_path(payload, entry, requested, ages))
    offset, limit = _git_text_window(request, entry, ext)
    limit = min(limit, source.max_blob_bytes - offset)
    head, _size = await source.read_blob_window(
        entry.oid,
        offset=0,
        max_bytes=max(_PREDICATE_PREFIX_BYTES, offset + limit if limit > 0 else 0),
    )
    content_class = classify_prefix(head[:SNIFF_PREFIX_BYTES])
    if content_class is ContentClass.BINARY or (
        ext not in BROWSER_TEXT_EXTS and content_class is not ContentClass.TEXT
    ):
        kind = plugin_magic_kind(head[:SNIFF_PREFIX_BYTES])
        payload.update({"type": "binary", "kind": kind, "views": _views_for_kind(kind)})
        return _json(_with_requested_path(payload, entry, requested, ages))
    if ext == ".jsonl":
        return await _windowed_jsonl_response(source, entry, size, payload, requested, wire, ages)
    if limit <= 0:
        return _json(
            {
                "type": "error",
                "path": wire,
                "error": "This part of the file is past what can be shown here.",
                "detail": "Requested preview window exceeds the stream budget for this blob",
                "max_offset": source.max_blob_bytes,
            },
            status_code=416,
        )
    json_top, yaml_top, frontmatter, frontmatter_error = await _blob_predicates_off_loop(
        ext, head[:_PREDICATE_PREFIX_BYTES]
    )
    kind = _plugin_kind_for_git_path(
        entry.path,
        json_top_level=json_top,
        yaml_top_level=yaml_top,
        frontmatter=frontmatter,
        prefix=head[:SNIFF_PREFIX_BYTES],
    ) or (classify_by_ext(ext) if ext else "text")
    payload.update(
        {
            "type": "text",
            "kind": kind,
            "views": await _text_views_off_loop(kind, ext, head),
            **_git_text_fields(offset, limit, head[offset : offset + limit], size),
            **_git_frontmatter_envelope(mapping=frontmatter, error=frontmatter_error),
        }
    )
    return _json(_with_requested_path(payload, entry, requested, ages))


async def _windowed_jsonl_response(
    source: GitTreeSource,
    entry: GitTreeEntry,
    size: int,
    payload: dict[str, Any],
    requested: GitPath,
    wire: str,
    ages: RevisionAges | None,
) -> JSONResponse:
    """Parse a JSONL blob under the filesystem's parser ceiling, or say it is too large."""

    from metabrowser.jsonl_view import _JSONL_PARSE_MAX_BYTES, parse_jsonl_bytes

    if size > _JSONL_PARSE_MAX_BYTES:
        # The filesystem refuses an uncompressed file this size before reading it.
        return _json(
            {
                "type": "error",
                "kind": "error",
                "views": [],
                "path": wire,
                "error": "This log is too large to show here.",
                "detail": f"JSONL content exceeds {_JSONL_PARSE_MAX_BYTES} decompressed bytes",
            }
        )
    body, _size = await source.read_blob_window(entry.oid, offset=0, max_bytes=size)
    parsed = await asyncio.to_thread(parse_jsonl_bytes, body)
    adapter = parsed.get("summary", {}).get("adapter")
    adapter_name = adapter if isinstance(adapter, str) else None
    kind = _plugin_kind_for_git_path(entry.path, adapter=adapter_name) or classify_by_ext(
        ".jsonl", adapter_name
    )
    payload.update({"type": "jsonl", "kind": kind, "views": _views_for_kind(kind), **parsed})
    return _json(_with_requested_path(payload, entry, requested, ages))


def _container_child_payload(
    entry: GitTreeEntry, *, wire: str, inner: str, path: GitPath, kind: str = "diff"
) -> dict[str, Any]:
    ext = blob_logical_ext(entry.path)
    return {
        "subject": "git_revision",
        "type": "text",
        "kind": kind,
        "views": _views_for_kind(kind),
        "path": wire,
        "display": path.display(),
        "container": path.to_wire(),
        "container_inner": inner,
        "ext": ext,
        "size": 0,
        "mode": entry.mode,
        "git_kind": entry.kind,
        "symlink": False,
        "gitlink": False,
        "oid": entry.oid,
        "content": "",
        "content_offset": 0,
        "content_bytes": 0,
        "bytes_read": 0,
        "content_truncated": False,
    }


@_typed_git_failures
async def git_revision_file(request: Request, subject: GitRevisionSubject) -> JSONResponse:
    """File or folder envelope for one GitPath. No ignore state; the time
    of its last commit when the answer for the revision has it (`_with_requested_path`)."""

    # Only an answer that is already there: a file read starts no read of the history (a
    # command that prints the time asks `?ages=1`, which makes `--api` wait for one).
    ages = file_ages_service().peek(subject.command_target, subject.commit_oid)
    wire = request.query_params.get("path", "")
    try:
        path, inner = split_git_container_wire(wire)
    except GitPathError:
        return _json(_NOT_FOUND, status_code=404)
    if inner:
        if inner.count("/") + 1 > MAX_CONTAINER_INNER_DEPTH:
            return _json(_NOT_FOUND, status_code=404)
        try:
            entry = await resolve_git_blob_entry(subject.tree_source, path)
            if entry is None:
                return _json(_NOT_FOUND, status_code=404)
            kind = (
                "diff"
                if blob_logical_ext(entry.path) in _PATCH_EXTS
                else await _blob_container_kind(subject, entry)
            )
        except GitObjectUnavailableError:
            return _json(_NOT_FOUND, status_code=404)
        if kind is None:
            return _json(_NOT_FOUND, status_code=404)
        return _json(_container_child_payload(entry, wire=wire, inner=inner, path=path, kind=kind))
    try:
        entry = await subject.tree_source.resolve_path(path)
        if entry is None:
            return _json(_NOT_FOUND, status_code=404)
        if entry.is_symlink:
            followed = await follow_git_symlinks(subject.tree_source, entry)
            if followed is None:
                return _json(_NOT_FOUND, status_code=404)
            entry = followed
        if entry.is_tree:
            children = await subject.tree_source.list_tree(entry.path)
            index = await subject.tree_source.blob_index(entry.path)
            payload = _tree_file_payload(
                entry, children, tally=None if index is None else index.tally()
            )
            return _json(_with_requested_path(payload, entry, path, ages))
        if entry.is_gitlink:
            return _json(_with_requested_path(_gitlink_file_payload(entry), entry, path, ages))
        if not entry.is_blob:
            return _json(_NOT_FOUND, status_code=404)
        source = subject.tree_source
        size = entry.size if entry.size is not None else (await source.object_info(entry.oid)).size
        if size > source.max_blob_bytes:
            return await _windowed_blob_file_response(
                request, source, entry, size, requested=path, wire=wire, ages=ages
            )
        body = await source.read_blob(entry.path)
    except GitObjectUnavailableError as exc:
        return _json(_object_unavailable_payload(exc), status_code=404)
    except GitBlobTooLargeError as exc:
        return _json(_blob_too_large_payload(exc), status_code=413)
    payload = await _blob_file_payload(entry, body, request)
    return _json(_with_requested_path(payload, entry, path, ages))


@_typed_git_failures
async def git_revision_kpress_render(
    subject: GitRevisionSubject,
    *,
    request: Request,
    subpath: str,
    view: str,
    profile: str | None,
    source_override: str | None,
    include_toc: Literal["auto", "on", "off"],
    max_bytes: int,
) -> JSONResponse:
    """Render one Git blob through KPress. No mtime; the cache key is the OID."""

    try:
        path = GitPath.from_wire(subpath)
    except GitPathError:
        return _json(_NOT_FOUND, status_code=404)
    try:
        entry = await subject.tree_source.resolve_path(path)
        if entry is None:
            return _json(_NOT_FOUND, status_code=404)
        if entry.is_symlink:
            followed = await follow_git_symlinks(subject.tree_source, entry)
            if followed is None:
                return _json(_NOT_FOUND, status_code=404)
            entry = followed
        if not entry.is_blob or entry.is_symlink or entry.is_gitlink:
            return _json(_NOT_FOUND, status_code=404)
        ext = blob_logical_ext(entry.path)
        body = (
            b"" if source_override is not None else await subject.tree_source.read_blob(entry.path)
        )
        # Front matter is the blob's own, as the filesystem route reads it from the file:
        # text a page sends in the blob's place is what it renders, prepared for the page
        # (the wiki preprocessor writes anchors into it), never what the file says.
        head = body
        if source_override is not None and ext == ".md":
            head, _size = await subject.tree_source.read_blob_window(
                entry.oid, offset=0, max_bytes=_PREDICATE_PREFIX_BYTES
            )
    except GitObjectUnavailableError:
        return _json(_NOT_FOUND, status_code=404)
    except GitBlobTooLargeError as exc:
        return _json(_blob_too_large_payload(exc), status_code=413)

    if source_override is not None:
        content = source_override
        logical_size = len(source_override.encode())
    else:
        if len(body) > max_bytes:
            return JSONResponse(
                {
                    "type": "kpress_render_error",
                    "error": kpress_adapter.RENDER_TOO_LARGE_MESSAGE,
                    "detail": "File is too large for full document rendering",
                    "path": path.to_wire(),
                    "size": len(body),
                    "max_size": max_bytes,
                },
                status_code=413,
            )
        content_class = classify_prefix(body)
        if ext not in BROWSER_TEXT_EXTS and content_class is not ContentClass.TEXT:
            return JSONResponse(
                {
                    "type": "kpress_render_error",
                    "error": kpress_adapter.RENDER_TEXT_ONLY_MESSAGE,
                    "detail": "KPress render supports text-like files only",
                    "path": path.to_wire(),
                    "ext": ext,
                    "size": len(body),
                },
                status_code=415,
            )
        content = body.decode("utf-8", "replace")
        logical_size = len(body)

    kind = classify_by_ext(ext) if ext else "text"
    frontmatter = None
    frontmatter_error = None
    if ext == ".md":
        _, _, frontmatter, frontmatter_error = await _blob_predicates_off_loop(
            ext, head[:_PREDICATE_PREFIX_BYTES]
        )
    envelope = _git_frontmatter_envelope(mapping=frontmatter, error=frontmatter_error)
    fence_origin = await read_fence_origin(
        entry.path.to_wire(),
        entry.oid,
        content,
        ext,
        view,
        profile,
        blob=body if source_override is None else None,
    )
    try:
        # A pin is never trusted (_PIN_CAPABILITIES), so its document renders inert, in the
        # Markdown child under its deadline, and is known by its blob, or by the text a
        # page sent in its place; display text is not a route identity, so the source path
        # stays on the wire. A client that goes away leaves the render to no one, and an
        # abandoned render must not hold the child. The child raises KPress's errors too.
        rendered = await unless_disconnected(
            request,
            shared_worker().render_inert(
                InertRender(
                    source_text=content,
                    fence_origin=fence_origin,
                    source_path=entry.path.to_wire(),
                    display_path=entry.path.display(),
                    identity=(
                        f"blob:{entry.oid}"
                        if source_override is None
                        else await asyncio.to_thread(text_identity, source_override)
                    ),
                    kind=kind,
                    view=view,
                    ext=ext,
                    mtime_hash=entry.oid,
                    size=logical_size,
                    frontmatter=envelope.get("frontmatter"),
                    frontmatter_error=envelope.get("frontmatter_error"),
                    profile=profile,
                    include_toc=include_toc,
                )
            ),
        )
        if rendered is None:
            return JSONResponse({}, status_code=CLIENT_CLOSED)
    except InertRenderRefused as refused:
        return JSONResponse(
            kpress_refusal_payload(refused, path.to_wire()),
            status_code=refused.http_status,
            headers={"cache-control": "no-cache"},
        )
    except kpress_adapter.KPressInvalidRequestError as exc:
        return JSONResponse(
            {
                "type": "kpress_render_error",
                "error": kpress_adapter.RENDER_FAILED_MESSAGE,
                "detail": str(exc),
                "diagnostics": [str(exc)],
            },
            status_code=400,
        )
    except kpress_adapter.KPressRenderError as exc:
        return JSONResponse(
            {
                "type": "kpress_render_error",
                "error": kpress_adapter.RENDER_FAILED_MESSAGE,
                "detail": str(exc),
                "diagnostics": [str(exc)],
            },
            status_code=502,
        )
    detail = envelope.get("frontmatter_error_detail")
    return JSONResponse(
        {**rendered, **({"frontmatter_error_detail": detail} if detail is not None else {})},
        headers={"cache-control": "no-cache"},
    )


@_typed_git_failures
async def git_revision_raw(request: Request, subject: GitRevisionSubject) -> Response:
    """Blob bytes for one GitPath. In-tree relative symlink blobs are followed.

    Only the query form answers. The path form, `/raw/<path>`, is the address of a
    document whose relative references resolve beside it, and its one consumer is
    the HTML preview frame, which a pin never offers: acquired content always runs
    under the untrusted profile. A reference inside a raw pinned document therefore
    reaches `unsupported_for_subject` rather than a 404 that would misreport a
    present file as missing. Markdown images need no path form: the link enhancer
    resolves them to GitPath wires in the pinned tree and requests the query form.
    """

    if "path" in getattr(request, "path_params", {}):
        raise UnsupportedSourceCapabilityError("raw_document_path")
    try:
        path = _git_path_from_query(request)
    except GitPathError:
        return PlainTextResponse("Not found", status_code=404)
    try:
        entry = await subject.tree_source.resolve_path(path)
        if entry is None or not entry.is_blob:
            return PlainTextResponse("Not found", status_code=404)
        if entry.is_symlink:
            followed = await follow_git_symlinks(subject.tree_source, entry)
            if followed is None or not followed.is_blob or followed.is_gitlink:
                return PlainTextResponse("Not found", status_code=404)
            entry = followed
        body = await subject.tree_source.read_blob(entry.path)
    except GitObjectUnavailableError:
        return PlainTextResponse("Not found", status_code=404)
    except GitBlobTooLargeError as exc:
        return _json(_blob_too_large_payload(exc), status_code=413)
    media_type, _ = mimetypes.guess_type(_display_basename(entry.path))
    return Response(
        content=body,
        # A name that gives no type: the blob's leading bytes may (media_type_from_prefix).
        media_type=media_type or media_type_from_prefix(body) or "application/octet-stream",
        headers={"cache-control": "no-store"},
    )


__all__ = [
    "decode_git_view_path",
    "git_content_failure_response",
    "git_revision_capabilities",
    "git_revision_catalog",
    "git_revision_file",
    "git_revision_index_meta",
    "git_revision_index_progress",
    "git_revision_kpress_render",
    "git_revision_raw",
    "git_revision_recent",
    "git_revision_rollup",
    "git_revision_tree",
    "resolve_git_blob_entry",
    "split_git_container_wire",
]
