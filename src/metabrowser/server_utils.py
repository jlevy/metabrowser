"""Port utilities for the metabrowser.

All components that need a port should go through ``find_available_local_port``
(walking a small range from the requested default) rather than hardcoding one.

Pattern mirrors ``kash.local_server.port_tools`` for consistency.
"""

from __future__ import annotations

import shlex
import socket
from collections.abc import Iterable

DEFAULT_PORT_SEARCH_COUNT = 32
"""How many consecutive ports to try when walking from a start port."""


def local_port_is_free(host: str, port: int) -> bool:
    """Return True if *port* on *host* can be bound right now."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
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


def remote_port_probe_script(base_port: int, count: int = DEFAULT_PORT_SEARCH_COUNT) -> str:
    """Return a shell command that prints the first free port on 127.0.0.1.

    Used by ``metab remote`` to discover a free port on the remote host
    before opening the SSH tunnel, so local and remote always agree on which
    port the remote ``metab serve`` will bind to. This lets multiple
    browser sessions coexist on the same remote host.

    Exits non-zero and prints nothing if no port in the range is free.
    """
    script = (
        "import socket, sys\n"
        f"for p in range({base_port}, {base_port + count}):\n"
        "    s = socket.socket()\n"
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
