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
  build. A folder has no token, so the browser's HTTP cache never keeps its answers. The
  Commits panel does keep them in the page, until Refresh, by commit ID; that keep and
  what it does not notice are in ``static/git-panel.js`` and the architecture document
  ``arch-git-and-comparison-sources.md``.
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
- The commit graph, for ``merge_base`` and ``revision``. A store that borrows from a shallow
  checkout is shallow too, with a boundary that follows the checkout's (``cache/lender.py``).
  There a merge base is answered only when ``git/shallow.py`` shows it certain, which makes
  it the full graph's, and a commit at the boundary has its diff refused as
  ``parent_unavailable``. Both refusals are computed again, so a deepening of the store or
  of the checkout changes no answer that was kept.
- What a borrowing store can read, which neither the key nor the token names. Its objects
  are a full mirror's less what the checkout lacks or has since collected, so a comparison
  that needs one it cannot read fails, and is not kept, and one that succeeds is the answer
  any store holding those commits gives. A kept answer therefore stays true when the lender
  later loses the commits, as a browser's copy stays true across a restart, and a repair
  that names another checkout moves no address. The lender's own ``info/attributes`` is
  never read: Git reads the attributes of the repository it runs in.
  ``tests/test_checkout_overlay.py`` holds each of these on a replica.

A folder has inputs of its own beyond those, so this server never caches its answers: its
working tree's ``.gitattributes``, which an edit changes, ``.git/config``, the reader's Git
configuration, which can name a diff driver, and its replace refs and grafts, which can give
a commit another first parent. The page's own keep of them, which lasts until Refresh, is
the one place a folder's answer outlives a request.

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
# every one of them. What the reader's machine pays is RSS, which is more: filling the cache
# with twenty distinct comparisons of 1,325 to 2,000 files on one store, at load 8.1 to 8.6, took
# the server from 103 MB to 293 MB at the sixteenth and 296 MB after the twentieth, so the bound
# holds and plateaus there, at about 190 MB that includes the allocator's high-water mark from
# computing them (review of #284, E5).
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
        self._body_generation = object()
        self._computing: dict[tuple[str, ...], asyncio.Task[ResolvedManifest]] = {}

    async def manifest(
        self, key: tuple[str, ...], compute: Callable[[], Awaitable[ResolvedManifest]]
    ) -> ResolvedManifest:
        """The comparison's manifest, computing it once however many ask together.

        The computation is a task of its own and each request waits without cancelling it:
        a reader who goes back while a large comparison is being listed cancels their own
        wait, and the next request finds the work done.
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
        # wait() leaves shared work running when this reader leaves. Unlike shield()
        # on Python 3.14, it does not install an unconditional exception logger on a
        # cancelled waiter: _finished owns retrieval even after cache invalidation.
        await asyncio.wait((shared,))
        return shared.result()

    def _finished(self, key: tuple[str, ...], task: asyncio.Task[ResolvedManifest]) -> None:
        current = self._computing.get(key) is task
        if current:
            del self._computing[key]
        if task.cancelled():
            return
        # Every waiter raises on its own, so this only marks a failure as retrieved.
        if task.exception() is not None or not current:
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

    def body_generation(self) -> object:
        """Capture before asynchronous work; invalidation retires all older body writers."""
        return self._body_generation

    def remember_body(self, key: tuple[str, ...], body: bytes, *, generation: object) -> None:
        if generation is not self._body_generation or len(body) > self._max_body_entry_bytes:
            return
        replaced = self._bodies.pop(key, None)
        if replaced is not None:
            self._body_bytes -= len(replaced)
        self._bodies[key] = body
        self._body_bytes += len(body)
        while self._body_bytes > self._max_body_bytes:
            _, oldest = self._bodies.popitem(last=False)
            self._body_bytes -= len(oldest)

    def invalidate(self, key: tuple[str, ...]) -> None:
        """Drop answers after an observed corrupt object; in-flight results stay uncached."""
        # Invalidation is rare. Retire even unrelated in-flight encoders rather than
        # retain per-key generation history after eviction. Already-held unrelated
        # bodies stay valid. Object identity also rejects writers from replaced caches.
        self._body_generation = object()
        self._manifests.pop(key, None)
        self._computing.pop(key, None)
        for body_key in tuple(self._bodies):
            if body_key[: len(key)] == key:
                self._body_bytes -= len(self._bodies.pop(body_key))

    def sizes(self) -> dict[str, int]:
        """What it holds, for a test and a measurement."""
        return {
            "manifests": len(self._manifests),
            "bodies": len(self._bodies),
            "body_bytes": self._body_bytes,
        }
