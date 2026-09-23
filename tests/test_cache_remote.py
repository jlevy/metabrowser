"""Git's error text for an https origin becomes a typed state; nothing else leaks."""

from __future__ import annotations

import base64
import http.server
import os
import shutil
import subprocess
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import ClassVar

import pytest

from metabrowser.cache.remote import (
    HTTP_LOW_SPEED_LIMIT_BYTES,
    HTTP_LOW_SPEED_TIME_S,
    PROTOCOL_ARGS,
    classify_remote_failure,
    describe_remote_failure,
    remote_git_args,
)
from metabrowser.git.process import ACQUISITION_POLICY, git_environment

# Captured 2026-09-23 from Git 2.50.1 with LC_ALL=C; see cache/remote.py.
CAPTURED = {
    "fatal: could not read Username for 'https://github.com': terminal prompts disabled": (
        "not_found_or_private"
    ),
    "remote: Repository not found.\n"
    "fatal: repository 'https://github.com/octocat/definitely-not-a-repo-9431/' not found": (
        "not_found_or_private"
    ),
    "fatal: unable to access 'https://nonexistent-host-9431.invalid/x.git/': "
    "Could not resolve host: nonexistent-host-9431.invalid": "network_unreachable",
    "fatal: unable to access 'https://127.0.0.1:1/x.git/': Failed to connect to 127.0.0.1 "
    "port 1 after 0 ms: Couldn't connect to server": "network_unreachable",
    "fatal: unable to access 'https://self-signed.badssl.com/x.git/': "
    "SSL certificate problem: self signed certificate": "tls_failed",
    "fatal: unable to access 'https://expired.badssl.com/x.git/': "
    "SSL certificate problem: certificate has expired": "tls_failed",
    "fatal: unable to access 'https://wrong.host.badssl.com/x.git/': SSL: no alternative "
    "certificate subject name matches target host name 'wrong.host.badssl.com'": "tls_failed",
    "fatal: unable to access 'https://127.0.0.1:47001/x.git/': SSL connection timeout": (
        "timed_out"
    ),
    "error: RPC failed; curl 28 Operation too slow. Less than 1000 bytes/sec transferred "
    "the last 10 seconds\nfatal: expected flush after ref listing": "timed_out",
    # A low-speed abort mid-pack also reports the disconnect; the timeout decides.
    "error: RPC failed; curl 28 Operation too slow. Less than 1000 bytes/sec transferred "
    "the last 10 seconds\nfetch-pack: unexpected disconnect while reading sideband packet\n"
    "fatal: early EOF\nfatal: fetch-pack: invalid index-pack output": "timed_out",
    "error: RPC failed; curl 56 Recv failure: Connection reset by peer\n"
    "error: 9429 bytes of body are still expected\n"
    "fetch-pack: unexpected disconnect while reading sideband packet\n"
    "fatal: early EOF\nfatal: fetch-pack: invalid index-pack output": "connection_interrupted",
    "error: RPC failed; curl 18 Transferred a partial file\n"
    "error: 13410 bytes of body are still expected\n"
    "fetch-pack: unexpected disconnect while reading sideband packet\n"
    "fatal: early EOF\nfatal: fetch-pack: invalid index-pack output": "connection_interrupted",
    "fatal: unable to access 'https://github.com/pallets/flask/': Recv failure: "
    "Connection reset by peer": "connection_interrupted",
    "fatal: unable to access 'https://github.com/pallets/flask/': CONNECT tunnel failed, "
    "response 407": "proxy_auth_required",
    "fatal: unable to access 'http://127.0.0.1:47026/x.git/': The requested URL returned "
    "error: 429": "rate_limited",
    "fatal: unable to access 'http://127.0.0.1:47025/x.git/': The requested URL returned "
    "error: 503": "server_error",
    "fatal: unable to access 'http://127.0.0.1:47027/x.git/': The requested URL returned "
    "error: 500": "server_error",
}

# Reported forms this machine's Git and curl could not produce: OpenSSL on Linux reports
# a reset through the TLS layer, and curl over HTTP/2 reports a cancelled stream.
REPORTED = {
    "fatal: unable to access 'https://github.com/o/r/': OpenSSL SSL_read: "
    "SSL_ERROR_SYSCALL, errno 104": "connection_interrupted",
    "error: RPC failed; curl 92 HTTP/2 stream 5 was not closed cleanly: CANCEL (err 8)\n"
    "fatal: the remote end hung up unexpectedly": "connection_interrupted",
    "fatal: unable to access 'https://github.com/o/r/': gnutls_handshake() failed: "
    "The TLS connection was non-properly terminated.": "tls_failed",
}


@pytest.mark.parametrize(("stderr", "state"), [*CAPTURED.items(), *REPORTED.items()])
def test_captured_git_errors_classify(stderr: str, state: str) -> None:
    assert classify_remote_failure(stderr) == state


def test_a_url_inside_quotes_never_decides_the_state() -> None:
    text = "fatal: repository 'https://github.com/octo/tls-ssl-timeout-notes/' not found"
    assert classify_remote_failure(text) == "not_found_or_private"


def test_unrecognized_text_is_unclassified() -> None:
    assert classify_remote_failure("fatal: protocol error: bad pack header") is None
    assert classify_remote_failure("") is None


def test_messages_name_the_source_and_state_and_nothing_else() -> None:
    message = describe_remote_failure("tls_failed", "https://example.com/o/r.git")
    assert message == (
        "https://example.com/o/r.git failed the TLS security check (tls_failed); "
        "nothing was published"
    )
    detail = describe_remote_failure("timed_out", "https://example.com/o/r.git", detail="x")
    assert "(timed_out); x; nothing was published" in detail


def test_every_network_command_gets_the_allowlist_and_the_stall_bound() -> None:
    args = remote_git_args("https://example.com/o/r.git")
    assert args[: len(PROTOCOL_ARGS)] == PROTOCOL_ARGS
    assert "protocol.allow=never" in args
    assert "protocol.https.allow=always" in args and "protocol.file.allow=always" in args
    assert not any(
        arg.startswith(("protocol.http.", "protocol.ssh.", "protocol.git.")) for arg in args
    )
    assert f"http.lowSpeedLimit={HTTP_LOW_SPEED_LIMIT_BYTES}" in args
    assert f"http.lowSpeedTime={HTTP_LOW_SPEED_TIME_S}" in args


class _Challenge(http.server.BaseHTTPRequestHandler):
    """Answers every request 401 and records any credentials it was sent."""

    seen: ClassVar[list[str | None]] = []

    def do_GET(self) -> None:
        type(self).seen.append(self.headers.get("Authorization"))
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="origin"')
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        return


@pytest.fixture
def challenge_port() -> Iterator[int]:
    _Challenge.seen = []
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Challenge)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_address[1]
    finally:
        server.shutdown()
        server.server_close()


@pytest.mark.skipif(shutil.which("git") is None, reason="git executable is required")
@pytest.mark.skipif(os.name != "posix", reason="HOME=/dev/null is the POSIX spelling")
def test_acquisition_git_reads_no_netrc(tmp_path: Path, challenge_port: int) -> None:
    """curl answers a challenge from $HOME/.netrc; acquisition Git's HOME has none.

    Plain http is allowed here only so a local server can issue the challenge; curl
    reads .netrc the same way for https.
    """

    home = tmp_path / "home"
    home.mkdir()
    netrc = home / ".netrc"
    netrc.write_text("machine 127.0.0.1\nlogin u\npassword netrc-sentinel\n", encoding="utf-8")
    netrc.chmod(0o600)
    url = f"http://127.0.0.1:{challenge_port}/r.git"
    args = ["git", "-c", "protocol.allow=never", "-c", "protocol.http.allow=always"]

    def ls_remote(env: dict[str, str]) -> None:
        subprocess.run(
            [*args, "ls-remote", "--", url, "HEAD"],
            env=env,
            cwd=tmp_path,
            capture_output=True,
            timeout=30,
            check=False,
        )

    control = {**git_environment(ACQUISITION_POLICY), "HOME": str(home)}
    ls_remote(control)
    sentinel = "Basic " + base64.b64encode(b"u:netrc-sentinel").decode()
    assert sentinel in _Challenge.seen, "the control should show curl reading .netrc"

    production = git_environment(ACQUISITION_POLICY)
    assert production["HOME"] == os.devnull
    _Challenge.seen = []
    ls_remote(production)
    assert _Challenge.seen and all(auth is None for auth in _Challenge.seen)
