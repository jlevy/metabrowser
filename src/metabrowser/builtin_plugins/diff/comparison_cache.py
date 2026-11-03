"""What a comparison of two commit IDs answers, kept in memory.

A comparison names its two ends by commit ID, so the answer is not going to change, and
the route computes it from a Git process and a parse every time it is asked otherwise: a
second tab, a reload, each deferred file of a large pull request. This module keeps two
things for a store, and nothing for a folder:

- each comparison's resolution and manifest, the one part that grows with the size of the
  comparison, so that one deferred file costs one path-limited diff;
- each encoded answer, gzipped as the server would send it, so a repeat costs no parse, no
  serialization and no compression.

What the answer depends on, other than the two commit IDs:

- ``base_policy``, ``revision`` and ``file``: they are the key, as the request's own words
  are, because ``resolved.left.symbolic`` repeats them in the body.
- The build: its options (``-M50 -C``, three lines of context), its parser, and
  ``MAX_HYDRATED_FILES``. A process holds one build, and a browser's copy is scoped to it by
  the entity tag and by the ``build`` a request names.
- The store. Its Git directory and its token are the first parts of the key in memory, and
  a browser's copy is scoped to it by the entity tag and by the ``store`` a request names,
  the token ``http_caching.store_tag`` makes, which the shell gives the page beside the
  build. A folder has no token, so its answers are never kept by the browser either.
- A store's Git configuration and attributes. Its reads ignore user and system
  configuration and the reader's attributes files (``STORE_READ_POLICY``: ``HOME`` and
  ``XDG_CONFIG_HOME`` hold nothing, ``GIT_ATTR_NOSYSTEM`` is set), and read no commit's
  ``.gitattributes`` (``GIT_ATTR_SOURCE`` names the store's empty tree: Git 2.43 reads a
  bare repository's from ``HEAD``, which a fetch moves, and 2.50 reads none); the store's
  own configuration holds no ``diff.*``; and its ``info/attributes``, which a store is made
  without and which Git reads whatever else is isolated, is folded into the store's token,
  and so into the key, so an edit to it is answered afresh by a running server.
  ``tests/test_diff_comparison_cache.py`` holds that a ``.gitattributes`` at its HEAD
  changes nothing, on each Git the Makefile admits, and that an edit to
  ``info/attributes`` moves the token, the key and the answer.
- The commit graph, for ``merge_base``: fixed for a commit unless the store is shallow, and
  no store is. ``git/process.py`` fetches with no ``--depth``.

A folder has inputs of its own beyond those, so it is never cached this way: its working
tree's ``.gitattributes``, which an edit changes, ``.git/config``, and the reader's Git
configuration, which can name a diff driver.

Only an answer is kept: a refusal is computed again, since fetching can answer it.
"""

from __future__ import annotations

import asyncio
import functools
import gzip
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from metabrowser.diff.format import ChangeSetManifest, ResolvedComparison

# Comparisons whose manifest stays in memory. Measured 2026-11-02 at load 15 with tracemalloc on
# real pull requests of 42, 101, 663 and 1,183 files: 3.1 to 4.1 KB a file, 4.9 MB at 1,183. So
# the manifest's own cap of 2,000 files would retain 8.2 MB, and sixteen of those 131 MB, which
# an ordinary session comes nowhere near. A reader moving between recent pull requests keeps
# every one of them.
MAX_CACHED_MANIFESTS = 16

# Encoded answers kept in memory, in compressed bytes. Measured the same day: a first page is 144
# KB at 42 files, 197 KB at 1,183, and 339 KB for fifty files of a +442,186-line pull request
# whose decoded answer is 13.5 MB, and one deferred file a median of 3 to 5 KB. So this holds
# about three hundred first pages, or thirteen thousand deferred files.
MAX_CACHED_BODY_BYTES = 64 * 1024 * 1024

# An answer larger than this is served and not kept: one must not push out everything else.
MAX_CACHED_BODY_ENTRY_BYTES = MAX_CACHED_BODY_BYTES // 4

# The level the server's own compression uses, GZipMiddleware in server.py, so the answer is
# the bytes the route sent before it kept any.
_GZIP_LEVEL = 6


@dataclass(frozen=True, slots=True)
class ResolvedManifest:
    """A comparison's resolution and its manifest."""

    resolved: ResolvedComparison
    manifest: ChangeSetManifest


def encode_body(body: bytes) -> bytes:
    """Compress one answer, with no timestamp, so its bytes are the same each time."""
    return gzip.compress(body, compresslevel=_GZIP_LEVEL, mtime=0)


class ComparisonCache:
    """Two bounded least-recently-used maps, and one computation per comparison at a time."""

    def __init__(
        self,
        *,
        max_manifests: int = MAX_CACHED_MANIFESTS,
        max_body_bytes: int = MAX_CACHED_BODY_BYTES,
        max_body_entry_bytes: int = MAX_CACHED_BODY_ENTRY_BYTES,
    ) -> None:
        self._max_manifests = max_manifests
        self._max_body_bytes = max_body_bytes
        self._max_body_entry_bytes = max_body_entry_bytes
        self._manifests: OrderedDict[tuple[str, ...], ResolvedManifest] = OrderedDict()
        self._bodies: OrderedDict[tuple[str, ...], bytes] = OrderedDict()
        self._body_bytes = 0
        self._computing: dict[tuple[str, ...], asyncio.Task[ResolvedManifest]] = {}

    async def manifest(
        self, key: tuple[str, ...], compute: Callable[[], Awaitable[ResolvedManifest]]
    ) -> ResolvedManifest:
        """The comparison's manifest, computing it once however many ask together.

        The computation is a task of its own and each request waits through a shield, as
        the rollup's build does: a reader who goes back while a large comparison is being
        listed cancels their own wait, and the next request finds the work done.
        """
        kept = self._manifests.get(key)
        if kept is not None:
            self._manifests.move_to_end(key)
            return kept
        shared = self._computing.get(key)
        if shared is None:
            shared = asyncio.ensure_future(compute())
            self._computing[key] = shared
            shared.add_done_callback(functools.partial(self._finished, key))
        return await asyncio.shield(shared)

    def _finished(self, key: tuple[str, ...], task: asyncio.Task[ResolvedManifest]) -> None:
        if self._computing.get(key) is task:
            del self._computing[key]
        if task.cancelled():
            return
        # Every waiter raises on its own, so this only marks a failure as retrieved.
        if task.exception() is not None:
            return
        self._manifests[key] = task.result()
        while len(self._manifests) > self._max_manifests:
            self._manifests.popitem(last=False)

    def has_manifest(self, key: tuple[str, ...]) -> bool:
        """Whether this process computed the comparison, so a validator of it can be trusted."""
        return key in self._manifests

    def body(self, key: tuple[str, ...]) -> bytes | None:
        """One encoded answer, or None."""
        kept = self._bodies.get(key)
        if kept is not None:
            self._bodies.move_to_end(key)
        return kept

    def remember_body(self, key: tuple[str, ...], body: bytes) -> None:
        if len(body) > self._max_body_entry_bytes:
            return
        replaced = self._bodies.pop(key, None)
        if replaced is not None:
            self._body_bytes -= len(replaced)
        self._bodies[key] = body
        self._body_bytes += len(body)
        while self._body_bytes > self._max_body_bytes:
            _, oldest = self._bodies.popitem(last=False)
            self._body_bytes -= len(oldest)

    def sizes(self) -> dict[str, int]:
        """What it holds, for a test and a measurement."""
        return {
            "manifests": len(self._manifests),
            "bodies": len(self._bodies),
            "body_bytes": self._body_bytes,
        }
