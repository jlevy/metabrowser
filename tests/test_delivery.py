"""Who is sent gzip (H115): not a browser on this machine of a server started for one.

The start leads and the peer follows. Compression is the default; a server on a loopback
address that opened its own browser, or that the macOS app started with ``--exit-on-eof``,
leaves a loopback client's answers uncompressed and compresses for every other client.
The far server ``--remote`` starts, from a client of this version or an older one, keeps
compressing for the tunnel that reaches it from its own loopback; and a request a proxy
names is compressed.
"""

from __future__ import annotations

import shlex
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from starlette.testclient import TestClient
from typer.testing import CliRunner

from metabrowser import delivery, encoded_assets, server
from metabrowser.cli import main as cli_main
from metabrowser.cli import remote
from metabrowser.cli import serve as serve_module
from metabrowser.cli.main import _app  # pyright: ignore[reportPrivateUsage]
from metabrowser.encoded_assets import EncodedAssets

GZIP = {"accept-encoding": "gzip, deflate, br, zstd"}


def _scope(client: tuple[str, int] | None, **headers: str) -> dict[str, Any]:
    return {
        "type": "http",
        "client": client,
        "headers": [(name.encode(), value.encode()) for name, value in headers.items()],
    }


@pytest.mark.parametrize(
    ("host", "loopback"),
    [
        ("127.0.0.1", True),
        ("127.0.0.2", True),
        ("::1", True),
        ("[::1]", True),
        ("localhost", True),
        ("LocalHost", True),
        ("0.0.0.0", False),
        ("::", False),
        ("192.168.1.20", False),
        ("metabrowser.example", False),
    ],
)
def test_a_bind_is_local_only_on_a_loopback_address(host: str, loopback: bool) -> None:
    assert delivery.loopback_host(host) is loopback


def test_a_server_started_for_local_use_does_not_gzip_for_a_loopback_peer() -> None:
    delivery.serve_locally(True)
    assert not delivery.gzip_wanted(_scope(("127.0.0.1", 50000), **GZIP))
    assert not delivery.gzip_wanted(_scope(("::1", 50000), **GZIP))
    assert not delivery.gzip_wanted(_scope(("::ffff:127.0.0.1", 50000), **GZIP))


def test_it_still_gzips_for_any_other_peer_and_for_a_proxied_request() -> None:
    delivery.serve_locally(True)
    assert delivery.gzip_wanted(_scope(("192.168.1.20", 50000), **GZIP))
    assert delivery.gzip_wanted(_scope(("::ffff:10.0.0.4", 50000), **GZIP))
    assert delivery.gzip_wanted(_scope(None, **GZIP)), "no peer address is not a local one"
    assert delivery.gzip_wanted(_scope(("testclient", 50000), **GZIP))
    for header in delivery.PROXY_HEADERS:
        proxied = _scope(("127.0.0.1", 50000), **GZIP, **{header: "203.0.113.9"})
        assert delivery.gzip_wanted(proxied), header


def test_a_server_not_started_for_local_use_gzips_for_a_loopback_peer_too() -> None:
    # `metab --remote` starts the far server --no-open, and the SSH tunnel reaches it from
    # that host's loopback; `--api` and in-process clients never say local.
    delivery.serve_locally(False)
    assert delivery.gzip_wanted(_scope(("127.0.0.1", 50000), **GZIP))


def test_a_client_that_refuses_gzip_is_never_sent_it() -> None:
    for local in (True, False):
        delivery.serve_locally(local)
        assert not delivery.gzip_wanted(_scope(("192.168.1.20", 1), **{"accept-encoding": "br"}))
        assert not delivery.gzip_wanted(_scope(("192.168.1.20", 1)))


@pytest.fixture
def store(monkeypatch: pytest.MonkeyPatch) -> EncodedAssets:
    fresh = EncodedAssets()
    monkeypatch.setattr(encoded_assets, "ENCODED_ASSETS", fresh)
    return fresh


def _get(client: TestClient, address: str) -> Any:
    answer = client.get(address, headers=GZIP)
    assert answer.status_code == 200, address
    return answer


@pytest.mark.parametrize("local", [True, False])
def test_the_application_answers_as_the_mode_says(
    tmp_path: Path, store: EncodedAssets, local: bool
) -> None:
    (tmp_path / "a.md").write_text("# A\n\n" + "Some prose. " * 4000 + "\n")
    server._set_root_dir(tmp_path)  # pyright: ignore[reportPrivateUsage]
    server.prepare_asset_stamps()
    stamp = server._STATIC_TREE.stamp()  # pyright: ignore[reportPrivateUsage]
    assert stamp is not None
    delivery.serve_locally(local)
    browser = TestClient(server.app, client=("127.0.0.1", 50000))
    elsewhere = TestClient(server.app, client=("192.168.1.20", 50000))
    for address in (f"/static/app.js?v={stamp.digests['app.js']}", "/api/file?path=a.md"):
        here = _get(browser, address)
        there = _get(elsewhere, address)
        assert here.content == there.content, address
        assert there.headers["content-encoding"] == "gzip", address
        if local:
            assert "content-encoding" not in here.headers, address
            assert here.num_bytes_downloaded == len(here.content), address
        else:
            assert here.headers["content-encoding"] == "gzip", address


def _serves_locally(monkeypatch: pytest.MonkeyPatch, argv: list[str]) -> bool:
    """Run *argv* through the CLI with uvicorn stubbed, and say what the server was told."""
    seen: list[bool] = []

    def serve_in_place_of_uvicorn(_server: object) -> bool:
        seen.append(delivery.serving_locally())
        return False

    monkeypatch.setattr(serve_module, "find_available_local_port", lambda *_args: 8765)
    monkeypatch.setattr(serve_module, "_QuietForceExitServer", MagicMock())
    monkeypatch.setattr(serve_module, "_run_until_interrupted", serve_in_place_of_uvicorn)
    # Opening a browser, and the stdin watch --exit-on-eof starts, are not under test.
    monkeypatch.setattr(serve_module, "_wait_for_http_ok_then_open", lambda *_args: None)
    monkeypatch.setattr(cli_main, "stop_when_stdin_closes", lambda: None)
    result = CliRunner().invoke(_app, argv)
    assert result.exit_code == 0, f"{result.output}{result.exception!r}"
    assert len(seen) == 1
    return seen[0]


# The far server's command line from every `--remote` since the flat CLI (8433b9b7f,
# 2026-07-27) to this one, after `metab`: an older client starts a newer far server so.
# Before the flat CLI it began `metab serve` or `metabrowser serve`, which today's CLI
# already refused before H115.
OLD_REMOTE_SIDE = ["--port", "8412", "--host", "127.0.0.1", "--no-open"]
# The macOS app's start (CLIServeLaunch.arguments in apps/macos/Sources/ShellCore).
APP = ["--no-open", "--exit-on-eof", "--host", "127.0.0.1", "--port", "8411"]


@pytest.mark.parametrize(
    ("args", "local"),
    [
        ([], True),
        (["--host", "localhost"], True),
        (APP, True),
        (["--host", "0.0.0.0"], False),
        (["--host", "0.0.0.0", "--exit-on-eof"], False),
        (["--no-open"], False),
        (OLD_REMOTE_SIDE, False),
    ],
)
def test_only_a_start_for_this_machine_on_loopback_serves_locally(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, args: list[str], local: bool
) -> None:
    delivery.serve_locally(not local)
    assert _serves_locally(monkeypatch, [str(tmp_path), *args]) is local


def test_the_far_server_this_remote_starts_compresses(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The exact command line this version's `--remote` sends, run through this CLI."""
    sent: list[list[str]] = []

    class _Finished:
        returncode = 0

        def poll(self) -> int:
            return 0

        def wait(self) -> int:
            return 0

    def popen(cmd: list[str], *_args: object, **_kwargs: object) -> _Finished:
        sent.append(list(cmd))
        return _Finished()

    monkeypatch.setattr(remote.subprocess, "Popen", popen)
    monkeypatch.setattr(remote, "_probe_remote_free_port", lambda *_a, **_k: 8412)
    monkeypatch.setattr(remote, "find_available_local_port", lambda *_a, **_k: 8411)
    remote.run_remote("user@vm", path=str(tmp_path), no_open=True)
    # The watchdog wraps it: bash -c '( export PATH=... && metab ROOT ARGS ) </dev/null & ...'.
    script = shlex.split(sent[0][-1])[-1]
    inner = script[script.index("metab ") : script.index(" ) </dev/null")]
    argv = shlex.split(inner)[1:]
    assert argv == [str(tmp_path), *OLD_REMOTE_SIDE], "an older far server must parse it"
    delivery.serve_locally(True)
    assert _serves_locally(monkeypatch, argv) is False
