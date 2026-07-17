"""Host-header allowlist regression tests.

The server binds to loopback, but DNS rebinding lets a malicious page on an
attacker-controlled domain issue browser-same-origin requests that arrive
here with the attacker's hostname in ``Host``. ``_HostValidationMiddleware``
must reject those while leaving loopback names, Starlette's ``testserver``,
and operator-configured extra hosts untouched.
"""

from __future__ import annotations

from starlette.testclient import TestClient

from metabrowser.server import _HostValidationMiddleware, app


def test_default_testserver_host_is_allowed() -> None:
    client = TestClient(app)
    resp = client.get("/api/capabilities")
    assert resp.status_code == 200


def test_loopback_hosts_are_allowed() -> None:
    client = TestClient(app)
    for host in ("localhost", "127.0.0.1", "localhost:8411", "127.0.0.1:9000", "[::1]:8411"):
        resp = client.get("/api/capabilities", headers={"host": host})
        assert resp.status_code == 200, host


def test_rebound_host_is_rejected() -> None:
    client = TestClient(app)
    for host in ("evil.example", "evil.example:8411", "metab.attacker.io"):
        resp = client.get("/api/capabilities", headers={"host": host})
        assert resp.status_code == 421, host
        assert "not a permitted name" in resp.text


def test_extra_hosts_from_environment(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    client = TestClient(app)
    rejected = client.get("/api/capabilities", headers={"host": "workstation.lan"})
    assert rejected.status_code == 421

    monkeypatch.setenv("METABROWSER_ALLOWED_HOSTS", "workstation.lan, 10.0.0.5")
    for host in ("workstation.lan", "workstation.lan:8411", "10.0.0.5:8411"):
        resp = client.get("/api/capabilities", headers={"host": host})
        assert resp.status_code == 200, host


def test_hostname_parsing_handles_ports_and_ipv6() -> None:
    parse = _HostValidationMiddleware._hostname
    assert parse("localhost:8411") == "localhost"
    assert parse("127.0.0.1") == "127.0.0.1"
    assert parse("[::1]:8411") == "[::1]"
    assert parse("[::1]") == "[::1]"
    assert parse("Evil.Example:80") == "evil.example"
    assert parse("") == ""
