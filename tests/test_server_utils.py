"""Tests for bounded local and remote TCP port selection."""

from __future__ import annotations

import shlex
import socket
import subprocess
import sys

import pytest

from metabrowser import server_utils
from tests.ipv6_loopback import require_ipv6_loopback


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


def test_a_port_a_server_listens_on_is_held_against_the_next_search() -> None:
    """Two servers that search from one port take two ports, in either order of startup.

    The first socket is held and never accepted on, as a server's is while its
    application starts. The second search, and a probe, must both see the port taken.
    """

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        start = int(probe.getsockname()[1])
    ports = server_utils.port_search_range(start)
    with server_utils.listen_on_available_local_port("127.0.0.1", ports) as first:
        held = int(first.getsockname()[1])
        assert not server_utils.local_port_is_free("127.0.0.1", held)
        with server_utils.listen_on_available_local_port("127.0.0.1", ports) as second:
            assert int(second.getsockname()[1]) > held
        # A connection made before the server accepts waits for it, and is not refused.
        with socket.create_connection(("127.0.0.1", held), timeout=5):
            pass


def test_a_listener_takes_a_port_held_only_by_a_lingering_connection() -> None:
    """As ``local_port_is_free`` answers, for the reason its test below gives."""

    with _lingering_connection_on_a_port() as port:
        ports = server_utils.port_search_range(port)
        with server_utils.listen_on_available_local_port("127.0.0.1", ports) as listener:
            assert int(listener.getsockname()[1]) == port


def test_a_listener_search_names_the_range_it_exhausted() -> None:
    with server_utils.listen_on_available_local_port(
        "127.0.0.1", server_utils.port_search_range(server_utils.MAX_TCP_PORT - 40)
    ) as held:
        port = int(held.getsockname()[1])
        with pytest.raises(RuntimeError, match=rf"range {port}\.\.{port}"):
            server_utils.listen_on_available_local_port("127.0.0.1", range(port, port + 1))


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


def _free_port_on(family: socket.AddressFamily, address: str) -> int:
    with socket.socket(family, socket.SOCK_STREAM) as probe:
        probe.bind((address, 0))
        return int(probe.getsockname()[1])


def test_an_ipv4_host_gets_an_ipv4_listener_as_before() -> None:
    start = _free_port_on(socket.AF_INET, "127.0.0.1")
    for host in ("127.0.0.1", "0.0.0.0", ""):
        ports = server_utils.port_search_range(start)
        with server_utils.listen_on_available_local_port(host, ports) as listener:
            assert listener.family == socket.AF_INET, host
            assert listener.getsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR), host
            assert server_utils.url_host(host, listener) == "127.0.0.1", host


def test_localhost_keeps_its_ipv4_address_where_it_also_names_ipv6(monkeypatch) -> None:
    """One server holds one address, so a name of both families must not straddle them."""

    def _both(*_arguments: object, **_options: object) -> list[tuple[object, ...]]:
        return [
            (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("::1", 0, 0, 0)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 0)),
        ]

    monkeypatch.setattr(socket, "getaddrinfo", _both)
    ports = server_utils.port_search_range(_free_port_on(socket.AF_INET, "127.0.0.1"))
    with server_utils.listen_on_available_local_port("localhost", ports) as listener:
        assert listener.family == socket.AF_INET
        assert server_utils.url_host("localhost", listener) == "localhost"


@pytest.mark.parametrize("host", ["::1", "[::1]"])
def test_an_ipv6_loopback_host_gets_an_ipv6_listener_that_holds_its_port(host: str) -> None:
    require_ipv6_loopback()
    start = _free_port_on(socket.AF_INET6, "::1")
    ports = server_utils.port_search_range(start)
    with server_utils.listen_on_available_local_port(host, ports) as first:
        assert first.family == socket.AF_INET6
        assert first.getsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR)
        held = int(first.getsockname()[1])
        assert server_utils.url_host(host, first) == "[::1]"
        with server_utils.listen_on_available_local_port(host, ports) as second:
            assert int(second.getsockname()[1]) > held
        # Listening at once, as an IPv4 listener is: a connection waits for the server.
        with socket.create_connection(("::1", held), timeout=5):
            pass


def test_the_ipv6_wildcard_listens_for_both_families() -> None:
    """``::`` prints ``127.0.0.1``, so an IPv4 client has to reach it."""

    require_ipv6_loopback()
    ports = server_utils.port_search_range(_free_port_on(socket.AF_INET6, "::"))
    with server_utils.listen_on_available_local_port("::", ports) as listener:
        assert listener.family == socket.AF_INET6
        assert not listener.getsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY)
        assert server_utils.url_host("::", listener) == "127.0.0.1"
        port = int(listener.getsockname()[1])
        for address in ("127.0.0.1", "::1"):
            with socket.create_connection((address, port), timeout=5):
                pass


def test_an_ipv6_only_wildcard_listener_is_named_by_the_ipv6_loopback() -> None:
    """Where a platform keeps ``::`` to IPv6, ``127.0.0.1`` would name nothing."""

    require_ipv6_loopback()
    with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as listener:
        listener.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
        assert server_utils.url_host("::", listener) == "[::1]"


@pytest.mark.parametrize(
    ("host", "wildcard"),
    [
        ("", True),
        ("0.0.0.0", True),
        ("::", True),
        ("[::]", True),
        ("0:0:0:0:0:0:0:0", True),
        ("::1", False),
        ("127.0.0.1", False),
        ("localhost", False),
        ("0.0.0.0:8411", False),
    ],
)
def test_wildcard_hosts_are_the_unspecified_addresses(host: str, wildcard: bool) -> None:
    assert server_utils.wildcard_host(host) is wildcard


def test_a_host_that_names_no_address_is_refused_by_name(monkeypatch) -> None:
    def _unknown(*_arguments: object, **_options: object) -> list[tuple[object, ...]]:
        raise socket.gaierror(socket.EAI_NONAME, "Name or service not known")

    monkeypatch.setattr(socket, "getaddrinfo", _unknown)
    with pytest.raises(
        server_utils.UnusableHostError,
        match=r"Cannot listen on host 'nowhere\.example': it names no address \(Name or",
    ):
        server_utils.listen_on_available_local_port(
            "nowhere.example", server_utils.port_search_range(8411)
        )


def test_an_address_this_machine_lacks_is_refused_by_name_not_as_a_full_range() -> None:
    """``192.0.2.1`` is in TEST-NET-1 (RFC 5737), which no interface is given."""

    with pytest.raises(server_utils.UnusableHostError, match="has no such address"):
        server_utils.listen_on_available_local_port(
            "192.0.2.1", server_utils.port_search_range(8411)
        )
