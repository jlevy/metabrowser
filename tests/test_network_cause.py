"""Why a call to GitHub failed: one cause vocabulary for gh and Git, and the probe.

The owner reported, 2026-11-19, "The last refresh failed: gh did not answer within 15 s"
often, and asked that the underlying error, network or GitHub, be captured, logged, and
surfaced. That day's cause, found by hand: DNS answered api.github.com with an address
the network could not connect to, and with a reachable one at other times. These tests
hold each class of failure to its cause, its message, and its record.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import socket
import stat
from collections.abc import Generator, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from metabrowser import event_log, home, network_cause
from metabrowser.builtin_plugins.github import gh as gh_module
from metabrowser.cache.origin import classify_remote_failure
from metabrowser.event_log_route import summarize_failures
from metabrowser.git.process import GitCommandError, run_git
from tests.required_tools import require_git

# gh 2.98.0's error text (Go's net and net/http errors, wrapped by gh). The first was
# captured 2026-11-19 from a `gh pr create` on this repository while api.github.com
# resolved to an address the network could not reach; the rest are the forms Go prints
# for each failure (net.OpError, net.DNSError, tls, and net/http).
GH_SAMPLES: dict[str, network_cause.NetworkCause] = {
    'Post "https://api.github.com/graphql": dial tcp 172.182.252.137:443: i/o timeout': (
        "connect_timeout"
    ),
    "dial tcp: lookup api.github.com: no such host": "dns_failed",
    "dial tcp: lookup api.github.com on 192.168.1.1:53: no such host": "dns_failed",
    "dial tcp 140.82.112.6:443: connect: connection refused": "connect_refused",
    "dial tcp 140.82.112.6:443: connect: network is unreachable": "network_unreachable",
    "dial tcp [2606:50c0:8000::154]:443: connect: no route to host": "network_unreachable",
    "error connecting to api.github.com\ncheck your internet connection or "
    "https://githubstatus.com": "connect_failed",
    'Get "https://api.github.com/user": net/http: TLS handshake timeout': "connect_timeout",
    "tls: failed to verify certificate: x509: certificate signed by unknown authority": (
        "tls_failed"
    ),
    "proxyconnect tcp: dial tcp 10.0.0.1:3128: connect: connection refused": "proxy_failed",
    'Get "https://api.github.com/user": net/http: timeout awaiting response headers': "stalled",
    "read tcp 10.0.0.2:52000->140.82.112.6:443: read: connection reset by peer": (
        "connection_reset"
    ),
    "HTTP 503: Service Unavailable (https://api.github.com/graphql)": "server_error",
    "HTTP 401: Bad credentials (https://api.github.com/graphql)": "auth_refused",
    "HTTP 403: API rate limit exceeded for user ID 1.": "rate_limited",
    "HTTP 403: Resource not accessible by integration": "forbidden",
    "HTTP 404: Not Found (https://api.github.com/repos/o/r)": "not_found",
    "To get started with GitHub CLI, please run:  gh auth login": "not_signed_in",
}


@pytest.mark.parametrize(("text", "cause"), list(GH_SAMPLES.items()))
def test_gh_errors_classify_to_their_cause(text: str, cause: str) -> None:
    assert network_cause.classify(text) == cause


def test_an_address_gh_failed_to_connect_to_is_read_from_its_error() -> None:
    timeout = 'Post "https://api.github.com/graphql": dial tcp 172.182.252.137:443: i/o timeout'
    assert network_cause.failed_address(timeout) == "172.182.252.137"
    assert network_cause.failed_address("dial tcp [2606:50c0:8000::154]:443: x") == (
        "2606:50c0:8000::154"
    )
    assert network_cause.failed_address("dial tcp: lookup api.github.com: no such host") is None
    assert network_cause.http_status("HTTP 503: Service Unavailable") == 503
    assert network_cause.http_status("The requested URL returned error: 429") == 429


def test_every_cause_has_words_and_git_causes_have_a_state() -> None:
    for cause in network_cause.CAUSES:
        assert network_cause.reason(cause)
    # A cause Git reports maps to a state the app reads; gh's two own causes do not.
    for text, cause in GH_SAMPLES.items():
        if cause in {"not_signed_in"}:
            continue
        assert classify_remote_failure(text) is not None, text
    assert network_cause.reason("server_error", status=503) == "GitHub answered HTTP 503"
    assert network_cause.reason("connect_timeout", address="20.172.24.160") == (
        "Couldn't connect to GitHub (api.github.com at 20.172.24.160): the connection timed out"
    )


# ── the probe ──────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def fresh_probes() -> Iterator[None]:
    network_cause.forget_probes()
    yield
    network_cause.forget_probes()


@pytest.fixture
def sink(tmp_path: Path) -> Generator[event_log.EventLog]:
    state = tmp_path / "state"
    home.ensure_storage_root(state)
    home.ensure_private_directory(state, event_log.EVENTS_DIRECTORY)
    log = event_log.EventLog(state / event_log.EVENTS_DIRECTORY, state)
    with event_log.installed(log):
        yield log
    log.close()


def _records(log: event_log.EventLog) -> list[dict[str, Any]]:
    assert log.path is not None
    return [json.loads(line) for line in log.path.read_text(encoding="utf-8").splitlines()]


@contextlib.contextmanager
def _listening() -> Generator[int]:
    """A local port that accepts connections."""

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(8)
    try:
        yield server.getsockname()[1]
    finally:
        server.close()


def _closed_port() -> int:
    """A local port nothing listens on, so a connection to it is refused."""

    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    return port


def test_a_probe_is_off_in_the_suite_and_follows_a_proxy_without_its_credentials() -> None:
    assert network_cause.probe_target() is None  # tests/conftest.py turns it off
    assert network_cause.probe_target({}) == ("api.github.com", 443, False)
    assert network_cause.probe_target({"HTTPS_PROXY": "http://user:secret@proxy.example:3128"}) == (
        "proxy.example",
        3128,
        True,
    )
    assert network_cause.probe_target({"METABROWSER_NETWORK_PROBE": "127.0.0.1:9"}) == (
        "127.0.0.1",
        9,
        False,
    )
    assert network_cause.control_target({}) == network_cause.CONTROL_TARGET
    assert network_cause.control_target({"METABROWSER_NETWORK_PROBE_CONTROL": "off"}) is None


def test_a_reachable_target_names_its_address_and_time(sink: event_log.EventLog) -> None:
    with _listening() as port:
        env = {"METABROWSER_NETWORK_PROBE": f"127.0.0.1:{port}"}
        found = asyncio.run(network_cause.probe(env))
    assert found is not None and found.reachable
    assert [a.address for a in found.attempts] == ["127.0.0.1"]
    assert found.headline().startswith("127.0.0.1 (127.0.0.1) accepted a connection in ")
    (record,) = [r for r in _records(sink) if r["kind"] == "probe"]
    assert record["outcome"] == "ok" and record["attrs"]["verdict"] == "reachable"


def test_a_refused_target_with_a_reachable_control_blames_the_route_to_github(
    sink: event_log.EventLog,
) -> None:
    refused = _closed_port()
    with _listening() as control:
        env = {
            "METABROWSER_NETWORK_PROBE": f"127.0.0.1:{refused}",
            "METABROWSER_NETWORK_PROBE_CONTROL": f"127.0.0.1:{control}",
        }
        found = asyncio.run(network_cause.probe(env))
        assert found is not None and found.cause == "connect_refused"
        assert found.headline() == (
            "Couldn't connect to GitHub (127.0.0.1 at 127.0.0.1): the connection was refused; "
            "other sites are reachable"
        )
        # Within the interval a later failure reuses the result: one probe, one record.
        again = asyncio.run(network_cause.probe(env))
    assert again is found
    (record,) = [r for r in _records(sink) if r["kind"] == "probe"]
    assert record["outcome"] == "failed"
    assert record["attrs"]["cause"] == "connect_refused"
    assert record["attrs"]["addresses"][0]["result"] == "refused"
    assert record["attrs"]["control"]["verdict"] == "reachable"


def test_a_connection_that_never_opens_is_a_timeout_naming_the_address(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def never(*_: Any, **__: Any) -> Any:
        await asyncio.sleep(30)

    monkeypatch.setattr(asyncio, "open_connection", never)
    env = {
        "METABROWSER_NETWORK_PROBE": "127.0.0.1:443",
        "METABROWSER_NETWORK_PROBE_CONTROL": "0",
    }
    found = asyncio.run(network_cause.probe(env, timeout_s=0.2))
    assert found is not None and found.cause == "connect_timeout"
    assert found.attempts[0].result == "timeout"
    assert found.headline() == (
        "Couldn't connect to GitHub (127.0.0.1 at 127.0.0.1): the connection timed out after 0.2 s"
    )


def test_a_name_that_does_not_resolve_is_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    async def unresolvable(self: Any, *_: Any, **__: Any) -> Any:
        raise socket.gaierror(socket.EAI_NONAME, "nodename nor servname provided")

    monkeypatch.setattr(asyncio.BaseEventLoop, "getaddrinfo", unresolvable)
    env = {
        "METABROWSER_NETWORK_PROBE": "api.github.example:443",
        "METABROWSER_NETWORK_PROBE_CONTROL": "0",
    }
    found = asyncio.run(network_cause.probe(env))
    assert found is not None and found.cause == "dns_failed"
    assert found.headline() == "Couldn't reach GitHub: api.github.example did not resolve (DNS)"


# ── gh, with a stand-in ────────────────────────────────────────────────────


def _stand_in(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, script: str) -> None:
    directory = tmp_path / "bin"
    directory.mkdir(exist_ok=True)
    gh = directory / "gh"
    gh.write_text(f"#!/bin/sh\n{script}\n")
    gh.chmod(gh.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("PATH", f"{directory}{os.pathsep}{os.environ.get('PATH', '')}")


pytestmark_posix = pytest.mark.skipif(
    os.name != "posix", reason="the stand-in gh is a shell script"
)


@pytestmark_posix
def test_a_gh_that_never_answers_says_what_the_probe_found(
    sink: event_log.EventLog, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The owner's "gh did not answer within 15 s", with the probe's finding at its head."""

    _stand_in(tmp_path, monkeypatch, "exec sleep 30")
    monkeypatch.setenv("METABROWSER_NETWORK_PROBE", f"127.0.0.1:{_closed_port()}")
    monkeypatch.setenv("METABROWSER_NETWORK_PROBE_CONTROL", "0")

    async def scenario() -> gh_module.GhError:
        with pytest.raises(gh_module.GhError) as failed:
            await event_log.job(gh_module.gh_active_account(timeout_s=0.5), "pulls.refresh")
        return failed.value

    failure = asyncio.run(scenario())
    assert failure.state == "network_error" and failure.cause == "connect_refused"
    assert str(failure) == (
        "Couldn't connect to GitHub (127.0.0.1 at 127.0.0.1): the connection was refused; "
        "gh gave up after 0.5 s"
    )
    records = _records(sink)
    (gh_end,) = [r for r in records if r["name"] == "gh auth"]
    assert gh_end["outcome"] == "timeout" and gh_end["attrs"]["cause"] == "no_answer"
    (probe_end,) = [r for r in records if r["kind"] == "probe"]
    job_end = next(r for r in records if r["name"] == "pulls.refresh" and r["event"] == "end")
    assert probe_end["parent"] == job_end["span"]
    assert job_end["attrs"]["cause"] == "connect_refused"


@pytestmark_posix
def test_a_slow_gh_on_a_working_network_says_so(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stand_in(tmp_path, monkeypatch, "exec sleep 30")
    with _listening() as port:
        monkeypatch.setenv("METABROWSER_NETWORK_PROBE", f"127.0.0.1:{port}")
        with pytest.raises(gh_module.GhError) as failed:
            asyncio.run(gh_module.gh_active_account(timeout_s=0.5))
    message = str(failed.value)
    assert message.startswith("gh did not answer within 0.5 s, although 127.0.0.1 (127.0.0.1)")
    assert failed.value.cause == "no_answer"


@pytestmark_posix
@pytest.mark.parametrize(
    ("stderr", "state", "cause", "message"),
    [
        (
            'Post "https://api.github.com/graphql": dial tcp 172.182.252.137:443: i/o timeout',
            "network_error",
            "connect_timeout",
            "Couldn't connect to GitHub (api.github.com at 172.182.252.137): "
            "the connection timed out",
        ),
        (
            "dial tcp: lookup api.github.com: no such host",
            "network_error",
            "dns_failed",
            "Couldn't reach GitHub: api.github.com did not resolve (DNS)",
        ),
        (
            "dial tcp 140.82.112.6:443: connect: connection refused",
            "network_error",
            "connect_refused",
            "Couldn't connect to GitHub (api.github.com at 140.82.112.6): "
            "the connection was refused",
        ),
        (
            "tls: failed to verify certificate: x509: certificate signed by unknown authority",
            "network_error",
            "tls_failed",
            "Couldn't reach GitHub: the secure connection (TLS) to api.github.com failed",
        ),
        (
            "proxyconnect tcp: dial tcp 10.0.0.1:3128: connect: connection refused",
            "network_error",
            "proxy_failed",
            "Couldn't reach GitHub through the proxy",
        ),
        ("HTTP 502: Bad Gateway", "network_error", "server_error", "GitHub answered HTTP 502"),
        ("HTTP 401: Bad credentials", "not_logged_in", "auth_refused", "gh auth login"),
        ("something private went wrong", "gh_failed", None, "gh exited 1 without"),
    ],
)
def test_each_class_of_gh_failure_has_its_state_cause_and_words(
    sink: event_log.EventLog,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stderr: str,
    state: str,
    cause: str | None,
    message: str,
) -> None:
    _stand_in(tmp_path, monkeypatch, f"echo '{stderr}' >&2\nexit 1")
    with pytest.raises(gh_module.GhError) as failed:
        asyncio.run(gh_module.gh_api("repos/o/r/pulls/1"))
    assert failed.value.state == state and failed.value.cause == cause
    assert message in str(failed.value)
    # gh's own text is never in the message; the log keeps it, redacted.
    assert "private" not in str(failed.value)
    (gh_end,) = [r for r in _records(sink) if r["name"] == "gh api"]
    assert gh_end["attrs"]["failure_message"] == stderr
    if cause is not None:
        assert gh_end["attrs"]["cause"] == cause


def test_an_http_refusal_names_its_cause_and_the_log_keeps_githubs_words(
    sink: event_log.EventLog,
) -> None:
    now = datetime(2026, 11, 19, 21, 0, tzinfo=UTC)

    def refusal(
        status: int, body: bytes = b"", headers: dict[str, str] | None = None
    ) -> gh_module.GhError | None:
        response = gh_module.GhResponse(status=status, headers=headers or {}, body=body)
        with event_log.span("job", f"answer {status}"):
            return gh_module._refusal(response, now=now)  # pyright: ignore[reportPrivateUsage]

    server = refusal(503, b'{"message":"Service Unavailable"}')
    assert server is not None and str(server) == "GitHub answered HTTP 503"
    assert server.cause == "server_error"
    unauthorized = refusal(401)
    assert unauthorized is not None and unauthorized.cause == "auth_refused"
    forbidden = refusal(403)
    assert forbidden is not None and forbidden.cause == "forbidden"
    missing = refusal(404)
    assert missing is not None and missing.cause == "not_found"
    limited = refusal(429, headers={"retry-after": "60"})
    assert limited is not None and limited.cause == "rate_limited"
    ends = {r["name"]: r for r in _records(sink) if r["event"] == "end"}
    assert ends["answer 503"]["attrs"]["server_message"] == "Service Unavailable"
    assert ends["answer 503"]["attrs"]["http_status"] == 503
    assert ends["answer 404"]["attrs"]["cause"] == "not_found"


@pytestmark_posix
def test_repeated_failures_say_how_many_in_the_last_hour(
    sink: event_log.EventLog, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stand_in(tmp_path, monkeypatch, "echo 'dial tcp 20.172.24.160:443: i/o timeout' >&2\nexit 1")

    async def twice() -> list[str]:
        messages = []
        for _ in range(2):
            with pytest.raises(gh_module.GhError) as failed:
                await gh_module.gh_api("repos/o/r/pulls/1")
            messages.append(str(failed.value))
        return messages

    first, second = asyncio.run(twice())
    assert "in the last hour" not in first
    assert second.endswith("(2 calls could not reach GitHub in the last hour)")
    assert event_log.recent_failures(causes=network_cause.TRANSPORT_CAUSES) == 2


def test_a_git_fetch_that_cannot_connect_records_its_cause(
    sink: event_log.EventLog, tmp_path: Path
) -> None:
    require_git()
    port = _closed_port()

    async def scenario() -> None:
        with pytest.raises(GitCommandError):
            await run_git(["ls-remote", f"http://127.0.0.1:{port}/x.git"], cwd=tmp_path)

    asyncio.run(scenario())
    (record,) = [r for r in _records(sink) if r["name"] == "git ls-remote"]
    assert record["outcome"] == "failed"
    assert record["attrs"]["cause"] in {"connect_refused", "connect_failed"}


def test_failures_are_summarized_by_cause_with_links_to_their_records(
    sink: event_log.EventLog,
) -> None:
    with event_log.span("subprocess", "gh api") as span:
        span.end("failed", cause="connect_timeout", address="20.172.24.160")
    with event_log.span("subprocess", "gh api") as span:
        span.end("timeout", cause="no_answer")
    with event_log.span("job", "pull_files_refresh.refresh") as span:
        span.note_failure("network_error", "Couldn't connect to GitHub")
        span.set(cause="connect_timeout")
    with event_log.span("request", "GET /api/plugin/github/pull"):
        pass
    assert sink.path is not None
    answer = summarize_failures(
        state=sink.path.parent.parent,
        directory=sink.path.parent,
        since=datetime(2000, 1, 1, tzinfo=UTC),
        until=None,
        kinds=(),
    )
    assert answer["failures"] == 3
    first, second = answer["causes"]
    assert (first["cause"], first["count"], first["kinds"]) == (
        "connect_timeout",
        2,
        {"subprocess": 1, "job": 1},
    )
    assert first["message"] == "Couldn't connect to GitHub"
    assert first["examples"][0]["details"].startswith(f"/api/event-log?file={sink.path.name}&span=")
    assert (second["cause"], second["count"]) == ("no_answer", 1)
    only_processes = summarize_failures(
        state=sink.path.parent.parent,
        directory=sink.path.parent,
        since=datetime(2000, 1, 1, tzinfo=UTC),
        until=None,
        kinds=("subprocess",),
    )
    assert only_processes["failures"] == 2
