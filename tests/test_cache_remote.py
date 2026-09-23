"""Git's error text for an https origin becomes a typed state; nothing else leaks."""

from __future__ import annotations

import pytest

from metabrowser.cache.remote import (
    HTTP_LOW_SPEED_LIMIT_BYTES,
    HTTP_LOW_SPEED_TIME_S,
    PROTOCOL_ARGS,
    classify_remote_failure,
    describe_remote_failure,
    remote_git_args,
)

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
}


@pytest.mark.parametrize(("stderr", "state"), CAPTURED.items())
def test_captured_git_errors_classify(stderr: str, state: str) -> None:
    assert classify_remote_failure(stderr) == state


def test_a_url_inside_quotes_never_decides_the_state() -> None:
    text = "fatal: repository 'https://github.com/octo/tls-ssl-timeout-notes/' not found"
    assert classify_remote_failure(text) == "not_found_or_private"


def test_unrecognized_text_is_unclassified() -> None:
    assert classify_remote_failure("fatal: the remote end hung up unexpectedly") is None
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
