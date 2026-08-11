"""Tests for bounded local and remote TCP port selection."""

from __future__ import annotations

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
