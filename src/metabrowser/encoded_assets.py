"""The application's own assets at a stamped address, held in memory and compressed once.

A stamped address names its content (:mod:`metabrowser.asset_stamps`): while the stamp is
current, the bytes behind ``/static/<file>?v=<digest>``,
``/plugin-static/<plugin>/@<digest>/<file>``, and ``/kpress-static/@<digest>/…`` are the
ones the digest was taken from. Read from disk and gzipped on every request, a landing's
few dozen assets cost the server the same work each time, on the event loop, for bytes
that cannot have changed (H115). Here they are kept by a key that names their content:
read once, gzipped once, in a thread, and sent from memory after that.

**What a client receives does not change.** The same answers are sent at the same
addresses with the same headers; an answer is gzipped exactly when the middleware would
gzip it (:func:`metabrowser.delivery.gzip_wanted`, and not under
:data:`~metabrowser.delivery.GZIP_MINIMUM_SIZE`), its decoded bytes are the file's, and
it now carries a ``Content-Length`` where a streamed one did not. A ``HEAD`` for a static
file is the file response's, as before, and reads nothing. Only an answer the
server would mark ``immutable`` is held, so a page from before an edit, which asks with
an old stamp and is answered ``no-cache``, still reads the file.

**Invalidation is the key.** A file is kept under the content digest its stamp recorded,
and read only when the stamp is current for it, which for a static or plugin file also
means it has the stat it was read with. An edited file therefore has a new key, and its
old bytes are never served for it; they wait in the bound until they are the least
recently used. The bytes read are hashed again before they are kept, so a file rewritten
between the stat and the read is sent as an ordinary revalidated answer, not kept.

**The bound** is in bytes, over both encodings: :data:`MAX_ENCODED_ASSET_BYTES`.

**What a cold request pays.** The first request for an asset waits for the whole read,
the digest check, and, for a client sent gzip, the whole compression before its headers
leave, where a streamed file response sent each 64 KiB chunk as soon as it was read and
compressed. For the largest static file, 318 KB, that wait is on the order of 10 ms
(gzip-6 of all 2.2 MB of the static directory took 61 ms of CPU on a loaded host). On
loopback it matters little; over a slow link a far server's cold landing loses the
overlap of compression with transfer. It is also why a stamped ``/static`` stylesheet's ``srv`` in
``Server-Timing`` now includes its read and compression (review B of #455, B5 and B8).

**Phases.** The ``read`` and ``encode`` a load costs are timed in the coroutine that runs
it, around the await of its thread, as every other route times a phase
(:mod:`metabrowser.server_timing`), so they include the wait for a pool thread. A load
runs in a task started by the request that found nothing held, in that request's
context, so only that request reports them; a request that joins the load waits and
reports nothing.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, override

from starlette.responses import Response

from metabrowser import delivery, server_timing
from metabrowser.loading_cache import LoadingCache

if TYPE_CHECKING:
    from pathlib import Path

    from starlette.types import Receive, Scope, Send

# Measured 2026-11-14 at this branch's base (ff50fbad0), every file the server stamps:
# the static directory, 64 files of 2,146 KB, 626 KB gzipped at level 6; the built-in
# plugins, 91 files of 1,301 KB, 386 KB gzipped; KPress's static tree, 57 files of 991 KB,
# 595 KB gzipped. What the store can hold of them is less than both encodings of all of
# them, since a KPress asset arrives with its bytes and keeps only its gzip encoding: at
# most about 5.0 MB on the compressed path (2,146 + 626 + 1,301 + 386 + 595 KB), and
# 3.4 MB on the macOS app's start, which keeps identity bytes alone (2,146 + 1,301 KB).
# One landing on a Markdown document asked for 81 of them
# (explorations/performance-loop/server-time.mjs, untimed) and left about 2.6 MB held on
# the compressed path and 1.85 MB on the app's start, summed from the logged bytes of the
# encodings each family keeps (review B of #455, B6); `EncodedAssets.held_bytes` is the
# reading that measures it. The server's 106.7-109.0 MB resident after those landings
# is the whole process's, and the three builds read within noise of each other. The
# bound holds the most the built-ins can occupy three times over, so an operator's
# plugin directory of the built-ins' size still fits, and a process holds at most what
# its pages asked for. Past the bound the least recently used go first and are read again when next
# asked for: a cost, not an error. Reads and compressions still running are not counted
# until they finish (loading_cache), so for as long as a landing's misses run, the store
# can hold their bytes past the bound.
MAX_ENCODED_ASSET_BYTES = 16 * 1024 * 1024
# The byte bound is the one that binds; this bounds the index alone. The built-in trees
# stamp 212 files (64 static, 91 in the built-in plugins, one tree each, and 57 of
# KPress's), at most 367 entries in both encodings. 16,000 is far above that; it binds
# only for operator plugin directories of thousands of small files, whose least recently
# used then go first, as they do past the byte bound.
_MAX_ENCODED_ASSET_ENTRIES = 16_000

IDENTITY = "identity"
GZIP = "gzip"


class AssetChanged(Exception):
    """The bytes read do not have the digest the stamp recorded: the file was rewritten."""

    def __init__(self, body: bytes) -> None:
        super().__init__("an asset's bytes changed after its stamp was taken")
        self.body = body


class EncodedAssets:
    """Assets by content key, each in the encodings asked for so far, under a byte bound."""

    def __init__(self, *, max_bytes: int = MAX_ENCODED_ASSET_BYTES) -> None:
        self._cache = LoadingCache[tuple[str, str], bytes](
            max_values=_MAX_ENCODED_ASSET_ENTRIES, max_weight=max_bytes, weigh=len
        )

    @property
    def held_bytes(self) -> int:
        """The bytes held now, in every encoding."""
        return self._cache.weight

    def holds(self, key: str, encoding: str) -> bool:
        """Whether *key* is held in *encoding*. Starts nothing."""
        return self._cache.kept((key, encoding)) is not None

    async def identity(self, key: str, load: Callable[[], bytes]) -> bytes:
        """*key*'s bytes, loaded once with *load*, in a thread, as the request's ``read``."""

        async def produce() -> bytes:
            with server_timing.phase("read"):
                return await asyncio.to_thread(load)

        return await self._cache.get((key, IDENTITY), produce)

    async def gzipped(self, key: str, identity: bytes) -> bytes:
        """*identity*, *key*'s bytes, gzipped once, in a thread, as the request's ``encode``."""

        async def produce() -> bytes:
            with server_timing.phase("encode"):
                return await asyncio.to_thread(delivery.gzip_bytes, identity)

        return await self._cache.get((key, GZIP), produce)


# The one store every asset route shares: a key names content, whichever route sent it.
ENCODED_ASSETS = EncodedAssets()


def file_loader(path: Path, digest: str, digest_of: Callable[[bytes], str]) -> Callable[[], bytes]:
    """Read *path*, refusing bytes whose ``digest_of`` is not *digest* (:class:`AssetChanged`)."""

    def load() -> bytes:
        body = path.read_bytes()
        if digest_of(body) != digest:
            raise AssetChanged(body)
        return body

    return load


class EncodedAssetResponse(Response):
    """An asset at a current stamped address, sent from :data:`ENCODED_ASSETS`.

    The bytes are *identity*, when the route holds them already, as KPress's does, or what
    *load* reads the first time. *headers* are the ones the route would send with the
    file; ``Content-Length``, ``Content-Encoding``, and ``Vary`` are set here, as the gzip
    middleware sets them. An answer sent identity is left for the middleware to pass on,
    and its ``Vary`` with it, because the middleware makes the same decision
    (:func:`delivery.gzip_wanted`).
    """

    def __init__(
        self,
        *,
        key: str,
        headers: Mapping[str, str],
        media_type: str | None,
        load: Callable[[], bytes] | None = None,
        identity: bytes | None = None,
        store: EncodedAssets | None = None,
    ) -> None:
        if (load is None) == (identity is None):
            raise ValueError("an encoded asset is given its bytes or a way to read them")
        super().__init__(content=identity or b"", headers=dict(headers), media_type=media_type)
        self._key = key
        self._load = load
        self._identity = identity
        self._store = store if store is not None else ENCODED_ASSETS

    @override
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        try:
            if self._load is None:
                identity = self._identity or b""
            else:
                identity = await self._store.identity(self._key, self._load)
        except AssetChanged as changed:
            # Not the bytes the address names: an ordinary answer, revalidated next time,
            # which the middleware compresses as it compresses any other.
            body = changed.body
            self.headers["cache-control"] = "no-cache"
        else:
            if len(identity) >= delivery.GZIP_MINIMUM_SIZE and delivery.gzip_wanted(scope):
                body = await self._store.gzipped(self._key, identity)
                self.headers["content-encoding"] = GZIP
                self.headers.add_vary_header("Accept-Encoding")
            else:
                body = identity
        self.body = body
        self.headers["content-length"] = str(len(body))
        await super().__call__(scope, receive, send)


__all__ = [
    "ENCODED_ASSETS",
    "MAX_ENCODED_ASSET_BYTES",
    "AssetChanged",
    "EncodedAssetResponse",
    "EncodedAssets",
    "file_loader",
]
