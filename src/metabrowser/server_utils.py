"""Port utilities for the metabrowser.

All components that need a port walk a small range from the requested default rather
than hardcoding one. A server that will bind the port itself takes it with
``listen_on_available_local_port``, which keeps it. ``find_available_local_port`` only
probes, for a port another process binds, as ``ssh`` binds a tunnel's.

Pattern mirrors ``kash.local_server.port_tools`` for consistency.
"""

from __future__ import annotations

import shlex
import socket
from collections.abc import Iterable

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


def local_port_is_free(host: str, port: int) -> bool:
    """Return True if *port* on *host* can be bound right now.

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

    Raises RuntimeError if none are available, as :func:`find_available_local_port`
    does.
    """
    tried: list[int] = []
    for port in ports:
        tried.append(port)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((host, port))
            sock.listen()
        except OSError:
            sock.close()
            continue
        return sock
    msg = f"No available port on {host} in range {tried[0]}..{tried[-1]}"
    raise RuntimeError(msg)


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
