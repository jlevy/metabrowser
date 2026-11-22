"""A stand-in for the socket a server holds its port with.

Serve mode takes its port as a listening socket (``listen_on_available_local_port`` in
``metabrowser.server_utils``) and hands the socket to Uvicorn. A test that runs serve mode
in process with Uvicorn replaced patches that function with this, which names a port and
binds nothing.
"""

from __future__ import annotations

import socket
from unittest.mock import MagicMock


def listener_on(port: int, host: str = "127.0.0.1") -> MagicMock:
    """A listener that says it holds *port* on *host*."""

    listener = MagicMock(spec=socket.socket)
    listener.getsockname.return_value = (host, port)
    return listener
