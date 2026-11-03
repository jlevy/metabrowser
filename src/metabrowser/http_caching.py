"""Cache validators for responses whose body depends on this build.

Metabrowser answers file requests with a rendering of a file, not with the
file. The body is therefore a function of two things — the bytes on disk and
the code that interpreted them — so a validator derived from the file alone is
wrong, and wrong in a way that hides exactly the changes worth shipping.

That is not hypothetical. Small binaries used to be read as text with
``errors="replace"`` and moved to the Bytes view; browsers that had already
cached one kept rendering a field of U+FFFD afterwards. Responses carry
``cache-control: no-cache``, so those browsers did revalidate — and the server,
comparing an mtime-derived tag against an unchanged file, answered 304 and told
them their stale copy was current.

:func:`build_scoped_etag` fixes that by folding this build's identity into the
tag. An upgrade invalidates every cached rendering exactly once; within one
version the tag stays stable, so restarting a server does not force clients to
re-fetch what they already hold.

In development the version names the commit, so a commit moves the tag, and an
editable install folds the newest change under its package tree in as well, so an
uncommitted edit moves it too: the server that answers is the code on disk when
it started, and a page it serves names that tag. What that does not reach is a
server left running across an edit, which answers from the code it imported
under a tag that now names the edited tree; restart it. A body marked
``immutable`` is the case that matters: the browser keeps it for a year without
asking, and a hard reload refreshes the page's own resources and not the
``fetch()`` requests the page makes afterwards, so a stale one is cleared only by
site data or by DevTools with its cache disabled.

Every route that answers conditionally goes through this module. That is the
point of it: the rule about what belongs in a validator is only worth stating
if it cannot be restated differently three files away. It was, four times over
— the shell, two built-in plugins, and the plugin static-asset route each built
their own tag, one of them under a comment claiming it matched the others while
using a different prefix. Fixing the rule in one of them fixed one of them.

``tests/test_http_caching.py`` fails the build if a validator is constructed
anywhere else.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections import OrderedDict
from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path
from typing import TYPE_CHECKING

from metabrowser import __version__

if TYPE_CHECKING:
    from starlette.requests import Request

# How much of a store's `info/attributes` is read into its tag. A store never has one, and
# a hand-written one is a few lines. A file past this is named by its size and its
# modification time as well, so an edit past the first MiB moves the tag too.
_ATTRIBUTES_TAG_BYTES = 1024 * 1024

# The tag of each store asked for lately, with the stat of the attributes file it was made
# from. Every comparison request and every page serve asks for the tag (review of #284,
# D5), so the file is read when the stat says it changed and not otherwise. Measured
# 2026-11-03 on a laptop, 20,000 calls: 6.9 µs a call reading a 12-byte file, 1.7 µs with a
# stat; 1.1 µs a call with no file. Bounded because a test process makes stores by the
# hundred; a server has a few.
_STORE_TAGS: OrderedDict[Path, tuple[tuple[int, int, int, int] | None, str]] = OrderedDict()
_MAX_STORE_TAGS = 64


def _newest_source_change() -> str:
    """The newest change under this package's tree in an editable install, else nothing.

    Measured 2026-11-02: 317 files walked in 2.3 ms, once per process.
    """
    try:
        direct = distribution("metabrowser").read_text("direct_url.json")
    except PackageNotFoundError:
        return ""
    if not direct:
        return ""
    try:
        editable = json.loads(direct).get("dir_info", {}).get("editable") is True
    except (ValueError, AttributeError):
        return ""
    if not editable:
        return ""
    newest = 0
    for root, dirs, files in os.walk(Path(__file__).parent):
        dirs[:] = [name for name in dirs if name != "__pycache__"]
        for name in files:
            try:
                newest = max(newest, os.stat(os.path.join(root, name)).st_mtime_ns)
            except OSError:
                continue
    return str(newest)


# Short digest rather than the raw version: it keeps the header small, and it
# means a version string with quotes or spaces in it cannot break the tag's
# RFC 7232 syntax.
BUILD_TAG = hashlib.blake2b(
    f"{__version__}\0{_newest_source_change()}".encode(), digest_size=6
).hexdigest()


def _attributes_signature(path: Path) -> tuple[int, int, int, int] | None:
    """What a stat says of the attributes file, or None for a store without one."""
    try:
        found = path.stat()
    except OSError:
        return None
    return (found.st_mtime_ns, found.st_ctime_ns, found.st_size, found.st_ino)


def _attributes_bytes(path: Path) -> bytes:
    try:
        with path.open("rb") as handle:
            return handle.read(_ATTRIBUTES_TAG_BYTES)
    except OSError:
        return b""


def store_tag(git_dir: Path) -> str:
    """The token that names a store in an address and in a tag, with no path in it.

    A body kept by a store's address, or validated by its tag, must not be replayed for
    another store on the same origin, nor for a folder, which has no token; and a store's
    ``info/attributes``, which Git reads whatever else is isolated, is an input the token
    names too, so an edit to it moves every address, and the key the comparison route
    keeps an answer under in memory.
    """
    attributes = git_dir / "info" / "attributes"
    signature = _attributes_signature(attributes)
    kept = _STORE_TAGS.get(git_dir)
    if kept is not None and kept[0] == signature:
        _STORE_TAGS.move_to_end(git_dir)
        return kept[1]
    digest = hashlib.blake2b(digest_size=8)
    digest.update(os.fsencode(git_dir))
    digest.update(b"\0")
    digest.update(_attributes_bytes(attributes))
    if signature is not None and signature[2] > _ATTRIBUTES_TAG_BYTES:
        # Past what the digest read: the size and the time, which any edit moves.
        digest.update(b"\0")
        digest.update(f"{signature[2]}\0{signature[0]}".encode())
    tag = digest.hexdigest()
    _STORE_TAGS[git_dir] = (signature, tag)
    while len(_STORE_TAGS) > _MAX_STORE_TAGS:
        _STORE_TAGS.popitem(last=False)
    return tag


def build_scoped_etag(content_identity: str) -> str:
    """Return a strong ETag scoped to both ``content_identity`` and this build.

    ``content_identity`` names the source the body was derived from — a file's
    ``strif.file_mtime_hash``, or a state key such as an index revision. Strong
    ETags are quoted per RFC 7232, and this is the only place in the package
    that produces that quoting.
    """
    return f'"{BUILD_TAG}-{content_identity}"'


def etag_headers(etag: str) -> dict[str, str]:
    """Return the response headers that make ``etag`` usable.

    ``no-cache`` is not "do not cache" — it requires the client to revalidate,
    which is what makes the validator load-bearing rather than advisory.
    """
    return {"ETag": etag, "Cache-Control": "no-cache"}


def immutable_headers(etag: str) -> dict[str, str]:
    """Return the headers for a body that cannot change at this address, for this build.

    The address has to name the build. A body is a function of the code that made it, and
    this tells a browser not to ask again for a year, so an address with no build in it would
    replay what an older build made, past any upgrade: ``no-cache`` above exists because
    that happened. It has to name the subject as well, with :func:`store_tag`, or one
    store's body answers for another, or for a folder, on the same origin. ``private``
    because a body can hold a private repository's code.
    """
    return {"ETag": etag, "Cache-Control": "private, max-age=31536000, immutable"}


def matches_if_none_match(request: Request, etag: str) -> bool:
    """Whether the client already holds ``etag``.

    Header names are case-insensitive and Starlette normalizes them, but the
    call sites did not agree on the spelling; reading it here means they no
    longer have to.
    """
    return request.headers.get("if-none-match", "") == etag


__all__ = [
    "BUILD_TAG",
    "build_scoped_etag",
    "etag_headers",
    "immutable_headers",
    "matches_if_none_match",
    "store_tag",
]
