"""How the server encodes the bytes it sends: whether an answer is gzipped, and how.

One decision, made in one place, because two layers make it: the gzip middleware for an
ordinary answer, and :mod:`metabrowser.encoded_assets` for an asset it holds already
compressed. Were they to decide differently, one client would be sent some answers
compressed and others not for no reason it could see.

The level and the floor are Starlette's middleware settings, kept here so the startup
budget's check (``devtools/check_startup_scripts.py``) and the performance loop's
``run.py`` compress as the server does.
"""

from __future__ import annotations

import gzip
from typing import TYPE_CHECKING

from starlette.datastructures import Headers

if TYPE_CHECKING:
    from starlette.types import Scope

# Starlette's default, which trades CPU against size at the right point for the small
# JSON answers this application sends; the level the startup budget was measured at.
GZIP_LEVEL = 6
# An answer smaller than this is sent as it is: the gzip framing would cost more than
# it saves.
GZIP_MINIMUM_SIZE = 1024


def accepts_gzip(scope: Scope) -> bool:
    """Whether the request's ``Accept-Encoding`` names gzip, tested as Starlette tests it."""
    return "gzip" in Headers(scope=scope).get("accept-encoding", "")


def gzip_wanted(scope: Scope) -> bool:
    """Whether an answer of at least :data:`GZIP_MINIMUM_SIZE` bytes to *scope* is gzipped."""
    return accepts_gzip(scope)


def gzip_bytes(content: bytes) -> bytes:
    """*content* gzipped at :data:`GZIP_LEVEL`, with no time in the header.

    The middleware's stream writes the time it compressed; a body compressed once and
    kept carries none, so the same bytes give the same encoding. The size is the same.
    """
    return gzip.compress(content, compresslevel=GZIP_LEVEL, mtime=0)


def sent_size(content: bytes) -> int:
    """How many bytes the server sends for *content* to a client it gzips for."""
    if len(content) < GZIP_MINIMUM_SIZE:
        return len(content)
    return len(gzip_bytes(content))


__all__ = [
    "GZIP_LEVEL",
    "GZIP_MINIMUM_SIZE",
    "accepts_gzip",
    "gzip_bytes",
    "gzip_wanted",
    "sent_size",
]
