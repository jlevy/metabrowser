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

A caveat worth knowing in development: the salt comes from the installed
version, which an editable install does not change when you edit source. Give
the browser a hard reload after changing how a file renders locally, or the
same 304 will hand it the previous rendering.

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
from typing import TYPE_CHECKING

from metabrowser import __version__

if TYPE_CHECKING:
    from starlette.requests import Request

# Short digest rather than the raw version: it keeps the header small, and it
# means a version string with quotes or spaces in it cannot break the tag's
# RFC 7232 syntax.
BUILD_TAG = hashlib.blake2b(__version__.encode("utf-8"), digest_size=6).hexdigest()


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


def matches_if_none_match(request: Request, etag: str) -> bool:
    """Whether the client already holds ``etag``.

    Header names are case-insensitive and Starlette normalizes them, but the
    call sites did not agree on the spelling; reading it here means they no
    longer have to.
    """
    return request.headers.get("if-none-match", "") == etag


__all__ = ["BUILD_TAG", "build_scoped_etag", "etag_headers", "matches_if_none_match"]
