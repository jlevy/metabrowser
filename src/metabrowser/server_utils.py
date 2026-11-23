"""Port utilities for the metabrowser.

All components that need a port walk a small range from the requested default rather
than hardcoding one. A server that will bind the port itself takes it with
``listen_on_available_local_port``, which keeps it. ``find_available_local_port`` only
probes, for a port another process binds, as ``ssh`` binds a tunnel's.

Pattern mirrors ``kash.local_server.port_tools`` for consistency.
"""

from __future__ import annotations

import errno
import ipaddress
import shlex
import socket
from collections.abc import Iterable
from typing import Any

DEFAULT_PORT_SEARCH_COUNT = 32
"""How many consecutive ports to try when walking from a start port."""

MIN_TCP_PORT = 1
"""Lowest assignable TCP port accepted by CLI port selection."""

MAX_TCP_PORT = 65_535
"""Highest TCP port allowed by the socket APIs."""


def port_search_range(
    base_port: int,
    count: int = DEFAULT_PORT_SEARCH_COUNT,
) -> range:
    """Return a nonempty candidate range bounded to valid TCP ports."""
    if not MIN_TCP_PORT <= base_port <= MAX_TCP_PORT:
        raise ValueError(f"base port must be between {MIN_TCP_PORT} and {MAX_TCP_PORT}")
    if count < 1:
        raise ValueError("port search count must be positive")
    return range(base_port, min(base_port + count, MAX_TCP_PORT + 1))


class UnusableHostError(RuntimeError):
    """The host names no address this machine can listen on, whatever the port."""


def _bare_host(host: str) -> str:
    """*host* without the brackets a URL puts around an IPv6 literal."""
    name = host.strip()
    return name[1:-1] if name.startswith("[") and name.endswith("]") else name


def _ip_literal(host: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    try:
        return ipaddress.ip_address(_bare_host(host))
    except ValueError:
        return None


def ipv6_literal(host: str) -> ipaddress.IPv6Address | None:
    """The address *host* spells when it is an IPv6 literal, bracketed or bare."""
    address = _ip_literal(host)
    return address if isinstance(address, ipaddress.IPv6Address) else None


def wildcard_host(host: str) -> bool:
    """Whether binding *host* accepts on every interface: empty, ``0.0.0.0``, or ``::``.

    Such a value names interfaces, not a host a browser can be sent to, so it is never
    a URL's host or a ``Host`` header the server admits.
    """
    address = _ip_literal(host)
    return not _bare_host(host) or (address is not None and address.is_unspecified)


def url_host(host: str, listener: socket.socket) -> str:
    """The host to write in the URL of a server that bound *host* as *listener*.

    A wildcard bind is reached through loopback: ``127.0.0.1``, which an IPv4 wildcard
    and a dual-stack ``::`` both accept, or ``[::1]`` where the platform kept the
    listener to IPv6. An IPv6 literal takes the brackets a URL needs around it, and any
    other host stands as given.
    """
    if wildcard_host(host):
        if listener.family == socket.AF_INET6 and listener.getsockopt(
            socket.IPPROTO_IPV6, socket.IPV6_V6ONLY
        ):
            return "[::1]"
        return "127.0.0.1"
    if ipv6_literal(host) is not None:
        return f"[{_bare_host(host)}]"
    return host


def _listen_addresses(host: str) -> list[tuple[socket.AddressFamily, tuple[Any, ...]]]:
    """The addresses *host* names, as ``(family, sockaddr)`` with port 0, IPv4 first.

    The family comes from the host, so ``::1`` and ``::`` get an IPv6 socket. A name
    that resolves to both families (``localhost``) listens on its IPv4 address, as it
    did when every listener was IPv4: one server holds one address, and the search
    below must not take a port on ``::1`` that another server holds on ``127.0.0.1``.
    """
    try:
        found = socket.getaddrinfo(
            _bare_host(host) or None,
            0,
            type=socket.SOCK_STREAM,
            flags=socket.AI_PASSIVE,
        )
    except (socket.gaierror, UnicodeError) as exc:
        reason = exc.strerror if isinstance(exc, socket.gaierror) else str(exc)
        raise UnusableHostError(
            f"Cannot listen on host {host!r}: it names no address ({reason})"
        ) from exc
    addresses = [
        (family, sockaddr)
        for family, _type, _proto, _name, sockaddr in found
        if family in (socket.AF_INET, socket.AF_INET6)
    ]
    if not addresses:
        raise UnusableHostError(f"Cannot listen on host {host!r}: it names no IP address")
    return sorted(addresses, key=lambda address: address[0] != socket.AF_INET)


# A bind that fails this way fails on every port: the address is not one of this
# machine's (``EADDRNOTAVAIL``), or the machine has no such family (``EAFNOSUPPORT``).
_NO_SUCH_ADDRESS = frozenset({errno.EADDRNOTAVAIL, errno.EAFNOSUPPORT})


def local_port_is_free(host: str, port: int) -> bool:
    """Return True if *port* on the IPv4 address *host* can be bound right now.

    IPv4 only: its one caller is ``metab --remote``, which probes ``127.0.0.1`` for the
    port ``ssh`` binds a tunnel on. A server takes its own port, of either family, with
    :func:`listen_on_available_local_port`.

    The probe binds the way the server will. Uvicorn sets ``SO_REUSEADDR`` on
    its listener, so without it here the probe answers a different question and
    answers it wrongly in the one case that matters: a reader whose server
    stopped is told to start it again, and the browser tab reading that message
    still holds a connection whose socket is in ``TIME_WAIT``. A plain bind
    fails on that port, the search moves to the next one, and the page polls a
    port nothing will ever serve. Uvicorn would have bound it.
    """

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
            return True
        except OSError:
            return False


def find_available_local_port(host: str, ports: Iterable[int]) -> int:
    """Return the first port in *ports* that is free on *host*.

    Raises RuntimeError if none are available — callers should pass a range
    wide enough that exhaustion indicates a real problem (e.g. an orphaned
    server holding multiple ports), not just casual contention.
    """
    tried: list[int] = []
    for port in ports:
        tried.append(port)
        if local_port_is_free(host, port):
            return port
    msg = f"No available port on {host} in range {tried[0]}..{tried[-1]}"
    raise RuntimeError(msg)


def listen_on_available_local_port(host: str, ports: Iterable[int]) -> socket.socket:
    """Return a socket listening on the first port in *ports* that is free on *host*.

    The server takes its port here and keeps it: the socket goes to Uvicorn, which
    accepts on it once the application has started. A probe that closed its socket
    left the port open to whoever asked next, for as long as startup took, so two
    servers started together on one ``--port`` both found it free and both named it
    in their ``Serving`` line. One then failed to bind and exited, and the other
    answered at the address the first had printed, with its own folder. A fixture
    that started two servers lost a run that way (mb-oru2, mb-a124).

    It listens at once because a bound socket alone holds nothing on Linux, where a
    second ``SO_REUSEADDR`` bind succeeds beside one that is not yet listening. So
    a connection made during startup waits for its answer in the accept queue, where
    it used to be refused. ``SO_REUSEADDR`` is set for the reason
    :func:`local_port_is_free` records.

    The socket's family is the host's (:func:`_listen_addresses`), so an IPv6 host is
    served. ``::`` listens dual-stack, with ``IPV6_V6ONLY`` cleared: it is the wildcard
    spelling, said to accept on every interface, and its banner names ``127.0.0.1``
    (:func:`url_host`), so an IPv4 client must reach it. The platform default cannot be
    left to decide that: Linux follows ``net.ipv6.bindv6only`` and Windows keeps such a
    socket to IPv6. Where the option cannot be cleared the listener stays IPv6-only and
    ``url_host`` names ``[::1]``.

    Raises RuntimeError if no port is available, as :func:`find_available_local_port`
    does, and :class:`UnusableHostError` if the host has no address to listen on.
    """
    ports = list(ports)
    refusal: OSError | None = None
    for family, address in _listen_addresses(host):
        for port in ports:
            try:
                sock = socket.socket(family, socket.SOCK_STREAM)
            except OSError as exc:
                refusal = exc
                break
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                if family == socket.AF_INET6 and wildcard_host(host):
                    _accept_ipv4_too(sock)
                sock.bind((address[0], port, *address[2:]))
                sock.listen()
            except OSError as exc:
                sock.close()
                if exc.errno in _NO_SUCH_ADDRESS:
                    refusal = exc
                    break
                continue
            return sock
        else:
            msg = f"No available port on {host} in range {ports[0]}..{ports[-1]}"
            raise RuntimeError(msg)
    reason = refusal.strerror if refusal is not None else "no address"
    raise UnusableHostError(
        f"Cannot listen on host {host!r}: this machine has no such address ({reason})"
    ) from refusal


def _accept_ipv4_too(sock: socket.socket) -> None:
    """Clear ``IPV6_V6ONLY`` where the platform allows it; ``url_host`` reads the result."""
    try:
        sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
    except OSError:
        return


def remote_port_probe_script(base_port: int, count: int = DEFAULT_PORT_SEARCH_COUNT) -> str:
    """Return a shell command that prints the first free port on 127.0.0.1.

    Used by ``metab --remote`` to discover a free port on the remote host
    before opening the SSH tunnel, so local and remote always agree on which
    port the remote ``metab`` server will bind to. This lets multiple
    browser sessions coexist on the same remote host.

    Exits non-zero and prints nothing if no port in the range is free.
    """
    ports = port_search_range(base_port, count)
    # The remote probe binds the way the remote server will, for the reason
    # `local_port_is_free` records: without SO_REUSEADDR a port whose only
    # occupant is a lingering connection reads as busy, and the tunnel is then
    # built to a port the remote `metab` did not take.
    script = (
        "import socket, sys\n"
        f"for p in range({ports.start}, {ports.stop}):\n"
        "    s = socket.socket()\n"
        "    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)\n"
        "    try:\n"
        "        s.bind(('127.0.0.1', p))\n"
        "        s.close()\n"
        "        print(p)\n"
        "        sys.exit(0)\n"
        "    except OSError:\n"
        "        s.close()\n"
        "sys.exit(1)\n"
    )
    return "python3 -c " + shlex.quote(script)
