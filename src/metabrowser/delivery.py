"""How the server encodes the bytes it sends: whether an answer is gzipped, and how.

One decision, made in one place, because two layers make it: the gzip middleware for an
ordinary answer, and :mod:`metabrowser.encoded_assets` for an asset it holds already
compressed. Were they to decide differently, one client would be sent some answers
compressed and others not for no reason it could see.

**Who is not sent gzip (H115).** Compression buys a client fewer bytes on the wire and
costs the server CPU on the event loop, and a browser on the same machine has no wire to
save: a level-6 gzip of a 311 KB render took 12.3 ms of a 14.8 ms answer. Compression is
still the default, and an answer is sent uncompressed only when both of these hold:

- **the command line started the server for a client on this machine**, for local use
  (:func:`serve_locally`): ``metab`` serving on a loopback address and either opening
  the browser itself, or started with ``--exit-on-eof``, as the macOS app starts it,
  holding its stdin;
- **the request comes from this machine and names no proxy**: the peer is a loopback
  address, and the request carries none of the headers a reverse proxy adds
  (:data:`PROXY_HEADERS`).

The start is the first test because the server's own command line decides it, from
flags every release already has, and the peer address cannot tell a tunnel from a
browser: ``metab --remote`` reaches the far server through SSH, from that host's own
loopback. Every release's ``--remote`` starts the far server with ``--port N --host
127.0.0.1 --no-open`` after its root (and ``serve`` before the flat CLI of 2026-07-27),
with neither of the local starts' marks. So a far server of this version compresses for
a client of any version, and nothing new is passed to a far server of an older one. A hand-made tunnel
or a proxy in front of a ``--no-open`` server is compressed for the same reason.
Everything else is compressed as before: a wildcard or LAN bind, any peer elsewhere, and
any process that never calls :func:`serve_locally`, such as ``--api``, ``--check-api``,
and the tests' in-process clients.

The level and the floor are Starlette's middleware settings, kept here so the startup
budget's check (``devtools/check_startup_scripts.py``) and the performance loop's
``run.py`` compress as the server does for a client it gzips for.
"""

from __future__ import annotations

import gzip
import ipaddress
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

# Headers a reverse proxy adds to say who the client really is. A request carrying any of
# them did not come from a browser on this machine, whatever its peer address.
PROXY_HEADERS = ("forwarded", "x-forwarded-for", "x-forwarded-host", "x-real-ip", "via")

_serving_locally = False


def serve_locally(enabled: bool) -> None:
    """Say whether this process serves a client on this machine, which leaves a loopback
    client's answers uncompressed. ``metab``'s serve modes call it once, before serving."""
    global _serving_locally
    _serving_locally = enabled


def serving_locally() -> bool:
    """Whether :func:`serve_locally` said this process serves a client on this machine."""
    return _serving_locally


def loopback_host(host: str) -> bool:
    """Whether binding *host* listens on this machine's loopback interface alone."""
    if host.strip().lower() == "localhost":
        return True
    return _loopback_address(host)


def _loopback_address(text: str) -> bool:
    try:
        address = ipaddress.ip_address(text.strip().strip("[]"))
    except ValueError:
        return False
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        return address.ipv4_mapped.is_loopback
    return address.is_loopback


def loopback_peer(scope: Scope) -> bool:
    """Whether the request arrived from a loopback address and names no proxy."""
    client = scope.get("client")
    if not client or not _loopback_address(str(client[0])):
        return False
    headers = Headers(scope=scope)
    return not any(name in headers for name in PROXY_HEADERS)


def accepts_gzip(scope: Scope) -> bool:
    """Whether the request's ``Accept-Encoding`` names gzip, tested as Starlette tests it."""
    return "gzip" in Headers(scope=scope).get("accept-encoding", "")


def gzip_wanted(scope: Scope) -> bool:
    """Whether an answer of at least :data:`GZIP_MINIMUM_SIZE` bytes to *scope* is gzipped."""
    if not accepts_gzip(scope):
        return False
    return not (_serving_locally and loopback_peer(scope))


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
    "PROXY_HEADERS",
    "accepts_gzip",
    "gzip_bytes",
    "gzip_wanted",
    "loopback_host",
    "loopback_peer",
    "sent_size",
    "serve_locally",
    "serving_locally",
]
