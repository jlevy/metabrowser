"""Why a call to GitHub failed, in one vocabulary that ``gh``, ``git``, and the log share.

A failed network call has two names. Its *state* says what to do about it, and each
caller keeps its own: :data:`metabrowser.builtin_plugins.github.gh.GhFailureState` for
``gh``, and :data:`metabrowser.cache.origin.RemoteFailureState` for a clone or fetch, whose
values the macOS app reads (``GitHubFailure.swift``). Its *cause* says what actually
happened: the name did not resolve, the connection was refused or timed out, the TLS
check failed, a proxy refused, or GitHub answered with an HTTP error. :func:`classify`
reads it from a tool's error text, both ``gh``'s (Go's ``net`` errors) and ``git``'s
(curl's), so a cause has one name whichever tool reported it. The states are derived from
causes, and messages (:func:`reason`) lead with them.

A ``gh`` that gives up with no answer says nothing about why. :func:`probe` asks the
network directly: it resolves ``api.github.com`` and opens a TCP connection to each
address the name resolved to (DNS can answer with addresses some networks cannot reach),
through the proxy ``gh`` would use when one is set, and reports which step failed and at
which address; when none connects, it tries one host outside GitHub. That
tells "GitHub is unreachable from here" from "GitHub, or ``gh``, is slow". A probe sends
no request and no credential, runs at most once per :data:`PROBE_INTERVAL_S` per target,
and is a ``probe`` span in the event log (:mod:`metabrowser.event_log`).
"""

from __future__ import annotations

import asyncio
import contextlib
import errno
import os
import re
import socket
import time
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Final, Literal
from urllib.parse import urlsplit

from metabrowser import event_log

# The host gh's API calls go to, and the probe's default target.
GITHUB_API_HOST: Final = "api.github.com"


type NetworkCause = Literal[
    "dns_failed",
    "connect_refused",
    "connect_timeout",
    "network_unreachable",
    "connect_failed",
    "connection_reset",
    "tls_failed",
    "proxy_auth_required",
    "proxy_failed",
    "stalled",
    "no_answer",
    "auth_refused",
    "forbidden",
    "not_found",
    "rate_limited",
    "server_error",
    "not_signed_in",
]
CAUSES: Final[tuple[NetworkCause, ...]] = (
    "dns_failed",
    "connect_refused",
    "connect_timeout",
    "network_unreachable",
    "connect_failed",
    "connection_reset",
    "tls_failed",
    "proxy_auth_required",
    "proxy_failed",
    "stalled",
    "no_answer",
    "auth_refused",
    "forbidden",
    "not_found",
    "rate_limited",
    "server_error",
    "not_signed_in",
)
# The causes in which nothing from GitHub arrived: the way to it failed, or it never
# answered. The rest are GitHub's own answers.
TRANSPORT_CAUSES: Final[frozenset[NetworkCause]] = frozenset(
    {
        "dns_failed",
        "connect_refused",
        "connect_timeout",
        "network_unreachable",
        "connect_failed",
        "connection_reset",
        "tls_failed",
        "proxy_auth_required",
        "proxy_failed",
        "stalled",
        "no_answer",
    }
)

# Matched in lower case, with single-quoted text removed first: Git quotes the URL, so a
# repository named ``tls-timeout-notes`` decides nothing. Order matters, because one
# failure prints several lines:
# - a timeout comes first, since a low-speed abort also prints ``early EOF``;
# - a proxy's 407 comes before the tunnel failure it is reported in;
# - an HTTP status outranks the connection it arrived on;
# - an interrupted connection outranks the TLS layer it was reported through;
# - a name that did not resolve, and a refused connection, outrank the generic failure to
#   connect that carries them.
# curl's texts are Git's under LC_ALL=C, captured 2026-09-23 from Git 2.50.1 (samples in
# tests/test_cache_origin.py); Go's are gh 2.98.0's, whose ``error connecting to`` hides
# the underlying error, which is what :func:`probe` is for (samples in
# tests/test_network_cause.py).
_QUOTED = re.compile(r"'[^'\n]*'")
_PATTERN_TEXT: Final[tuple[tuple[NetworkCause, str], ...]] = (
    (
        "connect_timeout",
        r"connection timed out|connection timeout|tls handshake timeout"
        r"|dial tcp[^\n]*i/o timeout",
    ),
    (
        "stalled",
        r"operation too slow|operation timed out|timeout was reached|curl 28 |timed out"
        r"|timeout awaiting response headers|context deadline exceeded|i/o timeout",
    ),
    ("proxy_auth_required", r"response 407|received http code 407|error: 407|\bhttp 407\b"),
    ("rate_limited", r"returned error: 429|\bhttp 429\b|rate limit exceeded"),
    ("server_error", r"returned error: 5\d\d\b|\bhttp 5\d\d\b"),
    (
        "connection_reset",
        r"connection reset|ssl_error_syscall|unexpected eof|transferred a partial file"
        r"|transfer closed with outstanding read data|curl (?:18|56|92) "
        r"|was not closed cleanly|unexpected disconnect|early eof"
        r"|the remote end hung up unexpectedly|broken pipe",
    ),
    (
        "tls_failed",
        r"ssl certificate problem|ssl: no alternative certificate|ssl: certificate subject name"
        r"|ssl connect error|tls connect error|gnutls_handshake"
        r"|server certificate verification failed|certificate verify failed|schannel"
        r"|x509: |remote error: tls|tls: failed to verify",
    ),
    ("proxy_failed", r"could not resolve proxy|proxyconnect|connect tunnel failed"),
    (
        "dns_failed",
        r"could not resolve host|no such host|name or service not known"
        r"|nodename nor servname|temporary failure in name resolution",
    ),
    ("connect_refused", r"connection refused"),
    ("network_unreachable", r"network is unreachable|no route to host|host is unreachable"),
    (
        "connect_failed",
        r"couldn't connect to server|failed to connect|error connecting to|dial tcp",
    ),
    (
        "auth_refused",
        r"returned error: 401|\bhttp 401\b|bad credentials|authentication failed"
        r"|could not read username|could not read password",
    ),
    ("forbidden", r"returned error: 403|\bhttp 403\b"),
    ("not_found", r"repository not found|returned error: 40[4]|\bhttp 404\b|not found"),
    ("not_signed_in", r"gh auth login|not logged in"),
)
_PATTERNS: Final[tuple[tuple[NetworkCause, re.Pattern[str]], ...]] = tuple(
    (cause, re.compile(pattern)) for cause, pattern in _PATTERN_TEXT
)
_STATUS = re.compile(r"returned error: ([1-5]\d\d)\b|\bhttp ([1-5]\d\d)\b")


def classify(text: str) -> NetworkCause | None:
    """The cause a tool's error *text* reports, or ``None`` when it names none.

    The text is only matched, never kept; a caller that shows it passes it through
    :func:`metabrowser.event_log.redact` first.
    """

    lowered = _QUOTED.sub("''", text).lower()
    for cause, pattern in _PATTERNS:
        if pattern.search(lowered):
            return cause
    return None


def http_status(text: str) -> int | None:
    """The HTTP status a tool's error *text* names, such as curl's ``returned error: 503``."""

    match = _STATUS.search(_QUOTED.sub("''", text).lower())
    return int(match[1] or match[2]) if match else None


# The address a connection failed to, in Go's error (gh: ``dial tcp 172.182.252.137:443:
# i/o timeout``) or curl's (Git: ``Failed to connect to github.com port 443 after 75003
# ms``, which names the host, not the address, so only Go's form is read).
_DIALED = re.compile(r"dial tcp (?:\[([0-9A-Fa-f:.]{2,45})\]|([0-9.]{7,15})):\d{1,5}:")


def failed_address(text: str) -> str | None:
    """The IP address a connection named in *text* was to, if the text names one."""

    match = _DIALED.search(text)
    return (match[1] or match[2]) if match else None


# How a cause reads at the head of a message: "Couldn't reach GitHub: ..." for the way to
# GitHub, "GitHub answered ..." for its own refusals. ``{host}`` is the host the call was
# for, and ``{where}`` the host with the address that failed, when one is known.
_REASONS: Final[Mapping[NetworkCause, str]] = {
    "dns_failed": "Couldn't reach GitHub: {host} did not resolve (DNS)",
    "connect_refused": "Couldn't connect to GitHub ({where}): the connection was refused",
    "connect_timeout": "Couldn't connect to GitHub ({where}): the connection timed out",
    "network_unreachable": "Couldn't reach GitHub: the network is unreachable",
    "connect_failed": "Couldn't reach GitHub: the connection to {where} failed",
    "connection_reset": "The connection to GitHub dropped before GitHub finished answering",
    "tls_failed": "Couldn't reach GitHub: the secure connection (TLS) to {host} failed",
    "proxy_auth_required": "Couldn't reach GitHub: the proxy requires authentication",
    "proxy_failed": "Couldn't reach GitHub through the proxy",
    "stalled": "GitHub stopped answering before it finished",
    "no_answer": "GitHub did not answer in time",
    "auth_refused": "GitHub refused the credentials (HTTP 401)",
    "forbidden": "GitHub answered HTTP 403: access refused",
    "not_found": "GitHub answered HTTP 404: not found",
    "rate_limited": "GitHub rate limit reached",
    "server_error": "GitHub answered with a server error",
    "not_signed_in": "GitHub CLI is not signed in",
}


def reason(
    cause: NetworkCause,
    *,
    host: str = GITHUB_API_HOST,
    address: str | None = None,
    status: int | None = None,
) -> str:
    """The plain words for *cause*, led by it: what a failure message starts with.

    *address* is the IP address a connection failed to, when the error named one.
    *status* is the HTTP status GitHub answered with, when it answered: "GitHub answered
    HTTP 503". GitHub's own message is never part of it; the event log keeps that.
    """

    if status is not None and cause in {"server_error", "forbidden", "not_found"}:
        return f"GitHub answered HTTP {status}"
    where = f"{host} at {address}" if address else host
    return _REASONS[cause].format(host=host, where=where)


# ── The probe ──────────────────────────────────────────────────────────────

# The host and port gh's API calls go to.
PROBE_HOST: Final = GITHUB_API_HOST
PROBE_PORT: Final = 443
# How long a probe waits for the name to resolve and a connection to open, together.
# Measured 2026-11-19 from one macOS machine on a home network: resolving api.github.com
# took 5-10 ms, and TCP connections to reachable hosts (pypi.org, registry.npmjs.org,
# one.one.one.one) 5-26 ms, so 3 s is over 100 times the slowest. At that moment DNS
# answered api.github.com with an address this network could not reach, and the
# connection to it timed out at whatever bound was set.
PROBE_TIMEOUT_S: Final = 3.0
# At most one probe per target in this long: later failures reuse its result, so a burst
# of failing calls costs one probe, never one each.
PROBE_INTERVAL_S: Final = 30.0
# The most resolved addresses a probe tries, all at once. DNS can answer a GitHub name
# with addresses some networks cannot reach, and which it returns varies between lookups,
# so a probe tries each and records each.
PROBE_ADDRESSES: Final = 4
# ``0`` (or ``off``) turns the probe off, as the test suite does so that no test reaches
# the network; ``HOST:PORT`` probes that target instead, as tests do with a local port.
PROBE_ENV: Final = "METABROWSER_NETWORK_PROBE"
# When GitHub cannot be reached, one connection to a host outside GitHub says whether
# the rest of the network can be: "other sites are reachable" makes the failure
# GitHub's or the route to it, not the machine's connection. The default is the host
# macOS itself connects to to check for a network (its captive-portal check), so the
# probe tells no new party anything; ``0`` turns it off, and ``HOST:PORT`` replaces it.
CONTROL_ENV: Final = "METABROWSER_NETWORK_PROBE_CONTROL"
CONTROL_TARGET: Final = ("captive.apple.com", 80)
_OFF: Final = frozenset({"0", "false", "no", "off"})
_PROXY_VARIABLES: Final = ("HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy")
_UNREACHABLE_ERRNOS: Final = frozenset({errno.ENETUNREACH, errno.EHOSTUNREACH})

type ProbeVerdict = Literal[
    "reachable",
    "dns_failed",
    "connect_timeout",
    "connect_refused",
    "network_unreachable",
    "connect_failed",
]
type AttemptResult = Literal["connected", "timeout", "refused", "unreachable", "failed"]
_VERDICT_OF: Final[Mapping[AttemptResult, ProbeVerdict]] = {
    "connected": "reachable",
    "timeout": "connect_timeout",
    "refused": "connect_refused",
    "unreachable": "network_unreachable",
    "failed": "connect_failed",
}
_HOW: Final[Mapping[ProbeVerdict, str]] = {
    "reachable": "it accepted a connection",
    "dns_failed": "the name did not resolve (DNS)",
    "connect_timeout": "the connection timed out",
    "connect_refused": "the connection was refused",
    "network_unreachable": "the network is unreachable",
    "connect_failed": "the connection failed",
}


@dataclass(frozen=True, slots=True)
class Attempt:
    """One connection a probe tried: the address, how it ended, and how long it took."""

    address: str
    result: AttemptResult
    ms: float


@dataclass(frozen=True, slots=True)
class ProbeResult:
    """What one probe found: the addresses DNS gave, which step failed, and how long each
    took; and, when GitHub could not be reached, whether another host could."""

    host: str
    port: int
    via_proxy: bool
    verdict: ProbeVerdict
    dns_ms: float | None
    attempts: tuple[Attempt, ...]
    timeout_s: float
    control: ProbeResult | None
    at: float
    at_wall: str

    @property
    def target(self) -> str:
        return f"{self.host}:{self.port}"

    @property
    def reachable(self) -> bool:
        return self.verdict == "reachable"

    @property
    def cause(self) -> NetworkCause | None:
        verdict = self.verdict
        return None if verdict == "reachable" else verdict

    @property
    def connect_ms(self) -> float | None:
        times = [a.ms for a in self.attempts if a.result == "connected"]
        return min(times) if times else None

    def _where(self) -> str:
        """``api.github.com at 20.172.24.160``: the name and the addresses that failed."""

        failed = [a.address for a in self.attempts if a.result != "connected"]
        name = f"the proxy {self.host}" if self.via_proxy else self.host
        return f"{name} at {', '.join(failed)}" if failed else name

    def _elsewhere(self) -> str:
        if self.control is None:
            return ""
        if self.control.reachable:
            return "; other sites are reachable"
        return "; other sites are not reachable either"

    def headline(self) -> str:
        """The failure the probe found, as a message's head, or what it found reachable.

        "Couldn't connect to GitHub (api.github.com at 20.172.24.160): the connection timed
        out; other sites are reachable".
        """

        if self.reachable:
            connected = next(a for a in self.attempts if a.result == "connected")
            name = f"the proxy {self.host}" if self.via_proxy else self.host
            return f"{name} ({connected.address}) accepted a connection in {connected.ms:.0f} ms"
        if self.verdict == "dns_failed":
            return f"Couldn't reach GitHub: {self.host} did not resolve (DNS){self._elsewhere()}"
        what = "the proxy" if self.via_proxy else "GitHub"
        how = _HOW[self.verdict]
        if self.verdict == "connect_timeout":
            how += f" after {self.timeout_s:g} s"
        return f"Couldn't connect to {what} ({self._where()}): {how}{self._elsewhere()}"

    def as_attrs(self) -> dict[str, object]:
        attrs: dict[str, object] = {
            "target": self.target,
            "via_proxy": self.via_proxy,
            "verdict": self.verdict,
            "dns_ms": self.dns_ms,
            "addresses": [
                {"address": a.address, "result": a.result, "ms": a.ms} for a in self.attempts
            ],
            "probed_at": self.at_wall,
        }
        if self.control is not None:
            attrs["control"] = {
                "target": self.control.target,
                "verdict": self.control.verdict,
            }
        return attrs


def _setting(env: Mapping[str, str], name: str) -> tuple[str, int] | None | Literal["off"]:
    """An ``HOST:PORT`` override in *name*, ``"off"``, or ``None`` when it is unset."""

    setting = env.get(name, "").strip()
    if not setting:
        return None
    if setting.lower() in _OFF:
        return "off"
    host, _, port = setting.rpartition(":")
    if host and port.isdigit():
        return host.strip("[]"), int(port)
    return None


def probe_target(environ: Mapping[str, str] | None = None) -> tuple[str, int, bool] | None:
    """``(host, port, via_proxy)`` to probe, or ``None`` when probing is off.

    gh connects through ``HTTPS_PROXY`` (or ``ALL_PROXY``) when one is set, so the probe
    connects to that proxy: a direct connection would test a path gh does not take. The
    proxy URL's credentials are never read.
    """

    env = os.environ if environ is None else environ
    setting = _setting(env, PROBE_ENV)
    if setting == "off":
        return None
    if setting is not None:
        return *setting, False
    for name in _PROXY_VARIABLES:
        proxy = env.get(name, "").strip()
        if not proxy:
            continue
        try:
            parts = urlsplit(proxy if "://" in proxy else f"http://{proxy}")
            default_port = 443 if parts.scheme == "https" else 80
            port = parts.port or (1080 if parts.scheme.startswith("socks") else default_port)
        except ValueError:
            continue
        if parts.hostname:
            return parts.hostname, port, True
    return PROBE_HOST, PROBE_PORT, False


def control_target(environ: Mapping[str, str] | None = None) -> tuple[str, int] | None:
    """The host outside GitHub a failed probe tries, or ``None`` when that is off."""

    env = os.environ if environ is None else environ
    setting = _setting(env, CONTROL_ENV)
    if setting == "off":
        return None
    return setting if setting is not None else CONTROL_TARGET


_recent: dict[tuple[str, int], ProbeResult] = {}
_running: dict[tuple[int, str, int], asyncio.Future[ProbeResult]] = {}


def recent_probe(environ: Mapping[str, str] | None = None) -> ProbeResult | None:
    """The last probe of the current target, if it ran within :data:`PROBE_INTERVAL_S`."""

    target = probe_target(environ)
    if target is None:
        return None
    found = _recent.get(target[:2])
    if found is None or time.monotonic() - found.at > PROBE_INTERVAL_S:
        return None
    return found


async def probe(
    environ: Mapping[str, str] | None = None, *, timeout_s: float = PROBE_TIMEOUT_S
) -> ProbeResult | None:
    """Resolve and connect to the API host (or proxy); ``None`` when probing is off.

    A probe from the last :data:`PROBE_INTERVAL_S` is reused, and one under way on this
    event loop is awaited rather than repeated. When the target cannot be reached, the
    control host (:func:`control_target`) is tried too.
    """

    target = probe_target(environ)
    if target is None:
        return None
    host, port, via_proxy = target
    found = recent_probe(environ)
    if found is not None:
        return found
    key = (id(asyncio.get_running_loop()), host, port)
    running = _running.get(key)
    if running is None:
        control = control_target(environ)
        running = asyncio.ensure_future(_probe(host, port, via_proxy, timeout_s, control))
        _running[key] = running
        running.add_done_callback(lambda _: _running.pop(key, None))
    return await asyncio.shield(running)


async def _connect(address: tuple[str, int], family: int, timeout_s: float) -> Attempt:
    started = time.perf_counter()
    result: AttemptResult = "connected"
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(address[0], address[1], family=family), timeout=timeout_s
        )
        writer.close()
        with contextlib.suppress(TimeoutError, OSError):
            await asyncio.wait_for(writer.wait_closed(), timeout=1.0)
    except TimeoutError:
        result = "timeout"
    except ConnectionRefusedError:
        result = "refused"
    except OSError as exc:
        result = "unreachable" if exc.errno in _UNREACHABLE_ERRNOS else "failed"
    return Attempt(address[0], result, round((time.perf_counter() - started) * 1000, 1))


async def _resolve_and_connect(
    host: str, port: int, via_proxy: bool, timeout_s: float, control: ProbeResult | None = None
) -> ProbeResult:
    loop = asyncio.get_running_loop()
    deadline = time.monotonic() + timeout_s
    dns_ms: float | None = None
    attempts: tuple[Attempt, ...] = ()
    verdict: ProbeVerdict = "dns_failed"
    started = time.perf_counter()
    try:
        infos = await asyncio.wait_for(
            loop.getaddrinfo(host, port, type=socket.SOCK_STREAM), timeout=timeout_s
        )
        dns_ms = round((time.perf_counter() - started) * 1000, 1)
    except (TimeoutError, OSError):
        infos = []
    seen: dict[str, tuple[int, tuple[str, int]]] = {}
    for family, _, _, _, address in infos:
        seen.setdefault(str(address[0]), (family, (str(address[0]), int(address[1]))))
    targets = list(seen.values())[:PROBE_ADDRESSES]
    if targets:
        remaining = max(0.001, deadline - time.monotonic())
        attempts = tuple(
            await asyncio.gather(*(_connect(addr, fam, remaining) for fam, addr in targets))
        )
        if any(a.result == "connected" for a in attempts):
            verdict = "reachable"
        else:
            # Every address failed; the first one's way of failing names the verdict.
            verdict = _VERDICT_OF[attempts[0].result]
    return ProbeResult(
        host=host,
        port=port,
        via_proxy=via_proxy,
        verdict=verdict,
        dns_ms=dns_ms,
        attempts=attempts,
        timeout_s=timeout_s,
        control=control,
        at=time.monotonic(),
        at_wall=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )


async def _probe(
    host: str, port: int, via_proxy: bool, timeout_s: float, control: tuple[str, int] | None
) -> ProbeResult:
    with event_log.span(
        "probe", f"probe {host}:{port}", attrs={"timeout_s": timeout_s, "via_proxy": via_proxy}
    ) as span:
        result = await _resolve_and_connect(host, port, via_proxy, timeout_s)
        if not result.reachable and control is not None:
            checked = await _resolve_and_connect(*control, False, timeout_s)
            result = replace(result, control=checked)
        _recent[(host, port)] = result
        span.set(**result.as_attrs())
        if not result.reachable:
            span.end("failed", cause=result.verdict, message=result.headline())
    return result


def remember_probe(result: ProbeResult) -> None:
    """Keep *result* as the target's latest probe; for tests that stand in for one."""

    _recent[(result.host, result.port)] = result


def forget_probes() -> None:
    """Drop remembered probe results; for tests."""

    _recent.clear()


__all__ = [
    "CAUSES",
    "GITHUB_API_HOST",
    "CONTROL_ENV",
    "CONTROL_TARGET",
    "PROBE_ADDRESSES",
    "PROBE_ENV",
    "PROBE_HOST",
    "PROBE_INTERVAL_S",
    "PROBE_PORT",
    "PROBE_TIMEOUT_S",
    "TRANSPORT_CAUSES",
    "Attempt",
    "NetworkCause",
    "ProbeResult",
    "ProbeVerdict",
    "classify",
    "failed_address",
    "control_target",
    "forget_probes",
    "http_status",
    "probe",
    "probe_target",
    "reason",
    "recent_probe",
    "remember_probe",
]
