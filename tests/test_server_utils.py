"""Tests for bounded local and remote TCP port selection."""

from __future__ import annotations

import shlex
import socket
import subprocess
import sys

import pytest

from metabrowser import server_utils


class _lingering_connection_on_a_port:
    """A port whose only occupant is a connection in ``TIME_WAIT``.

    The server side closes first, which is what leaves its socket lingering,
    and is what happens when ``metab`` stops while a browser tab is open. The
    client stays open for the body, so the state under test cannot lapse.
    """

    def __enter__(self) -> int:
        self._listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self._listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._listener.bind(("127.0.0.1", 0))
            port = int(self._listener.getsockname()[1])
            self._listener.listen(1)
            self._client = socket.create_connection(("127.0.0.1", port))
            served, _address = self._listener.accept()
        except BaseException:
            self._listener.close()
            raise
        served.close()
        self._listener.close()
        return port

    def __exit__(self, *_exception: object) -> None:
        self._client.close()
        self._listener.close()


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

    with _lingering_connection_on_a_port() as port:
        assert server_utils.local_port_is_free("127.0.0.1", port), (
            "a port whose only occupant is a lingering connection is bindable by the "
            "server, so the probe must not send the search to the next port"
        )


def test_the_remote_port_probe_also_rebinds_a_port_a_connection_still_holds() -> None:
    """``metab --remote`` runs the same probe on the other host, so it needs the same answer.

    The generated script decides which port the remote ``metab`` will take and
    which port the tunnel is built to. Run its body here against a port whose
    only occupant is a lingering connection: it must choose that port.
    """

    with _lingering_connection_on_a_port() as port:
        command = server_utils.remote_port_probe_script(port, count=4)
        script = shlex.split(command)[-1]
        completed = subprocess.run(
            [sys.executable, "-c", script], capture_output=True, text=True, check=False
        )
        assert completed.returncode == 0, completed.stderr
        assert completed.stdout.strip() == str(port), (
            f"the remote probe chose {completed.stdout.strip()!r} rather than the port a "
            "lingering connection holds, so the tunnel would reach a port the remote "
            "server did not take"
        )
