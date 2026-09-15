"""Tests for bounded local and remote TCP port selection."""

from __future__ import annotations

import socket

import pytest

from metabrowser import server_utils


def test_port_search_range_stops_at_maximum_tcp_port(monkeypatch) -> None:
    attempted: list[int] = []

    def _occupied(_host: str, port: int) -> bool:
        attempted.append(port)
        return False

    monkeypatch.setattr(server_utils, "local_port_is_free", _occupied)

    expected_range = rf"range {server_utils.MAX_TCP_PORT}\.\.{server_utils.MAX_TCP_PORT}"
    with pytest.raises(RuntimeError, match=expected_range):
        server_utils.find_available_local_port(
            "127.0.0.1",
            server_utils.port_search_range(server_utils.MAX_TCP_PORT),
        )

    assert attempted == [server_utils.MAX_TCP_PORT]


def test_remote_port_probe_script_stops_at_maximum_tcp_port() -> None:
    script = server_utils.remote_port_probe_script(server_utils.MAX_TCP_PORT)

    expected_loop = f"range({server_utils.MAX_TCP_PORT}, {server_utils.MAX_TCP_PORT + 1})"
    assert expected_loop in script
    assert str(server_utils.MAX_TCP_PORT + server_utils.DEFAULT_PORT_SEARCH_COUNT) not in script


def test_a_port_held_only_by_a_lingering_connection_is_free() -> None:
    """The probe answers the question uvicorn will ask, not a stricter one.

    A reader whose server stopped is told to start it again and that the page
    will reconnect. That page still holds a connection, so when the server goes
    the socket lingers in ``TIME_WAIT`` on its port. A probe that binds without
    ``SO_REUSEADDR`` calls the port busy, the search takes the next one, and the
    page polls a port nothing serves. Uvicorn, which sets the option, binds it.
    """

    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    listener.listen(1)
    client = socket.create_connection(("127.0.0.1", port))
    served, _address = listener.accept()
    try:
        # The server closes first, which is what leaves its side in TIME_WAIT.
        served.close()
        listener.close()
        assert server_utils.local_port_is_free("127.0.0.1", port), (
            "a port whose only occupant is a lingering connection is bindable by the "
            "server, so the probe must not send the search to the next port"
        )
    finally:
        client.close()
