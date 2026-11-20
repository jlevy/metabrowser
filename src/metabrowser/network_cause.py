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
which address. On macOS, when none connects and no proxy is in the way, it tries one
host outside GitHub (:data:`CONTROL_TARGET`). That tells "GitHub is unreachable from
here" from "GitHub, or ``gh``, is slow". A probe sends no request and no credential,
runs at most once per :data:`PROBE_INTERVAL_S` per target, finishes within
:data:`PROBE_TIMEOUT_S`, never raises, and is a ``probe`` span in the event log
(:mod:`metabrowser.event_log`).
"""

from __future__ import annotations

import asyncio
import contextlib
import errno
import ipaddress
import logging
import os
import re
import socket
import sys
import time
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Final, Literal
from urllib.parse import urlsplit

from metabrowser import event_log

log = logging.getLogger(__name__)
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

# The words that name a rate limit in GitHub's refusals, its primary ("API rate limit
# exceeded") and secondary ("You have exceeded a secondary rate limit") alike. One
# vocabulary: the classifier reads it in a tool's error, and gh's refusal reader in the
# message of an answer (:func:`mentions_rate_limit`).
_RATE_LIMIT_WORDS: Final = r"\brate limit"
_RATE_LIMIT = re.compile(_RATE_LIMIT_WORDS, re.IGNORECASE)


def mentions_rate_limit(text: str) -> bool:
    """Whether *text*, a tool's error or GitHub's message, names a rate limit."""

    return _RATE_LIMIT.search(text) is not None


# Matched in lower case, with quoted text removed first: Git quotes the URL in single
# quotes and Go in double quotes, so a repository named ``tls-timeout-notes`` or
# ``schannel-notes`` decides nothing. Order matters, because one failure prints several
# lines:
# - a proxy's failure comes first, since Go reports the proxy's own connection
#   (``proxyconnect tcp: dial tcp 10.0.0.1:3128: i/o timeout``) in the words a direct
#   connection to GitHub would use; its 407 comes before the tunnel failure it is
#   reported in;
# - a timeout comes next, since a low-speed abort also prints ``early EOF``, and a
#   timed-out lookup or a header wait before the generic ``timed out``;
# - an HTTP status outranks the connection it arrived on;
# - an interrupted connection outranks the TLS layer it was reported through;
# - a name that did not resolve, and a refused connection, outrank the generic failure to
#   connect that carries them.
# curl's texts are Git's under LC_ALL=C, captured 2026-09-23 from Git 2.50.1 (samples in
# tests/test_cache_origin.py); Go's are gh 2.98.0's (samples in
# tests/test_network_cause.py). gh prints ``error connecting to <host>`` only for a name
# that did not resolve (Go's ``*net.DNSError``), checked live against gh 2.98.0, so it is
# ``dns_failed``.
_QUOTED = re.compile(r"'[^'\n]*'|\"https?://[^\"\n]*\"")
_PATTERN_TEXT: Final[tuple[tuple[NetworkCause, str], ...]] = (
    ("proxy_auth_required", r"response 407|received http code 407|error: 407|\bhttp 407\b"),
    ("proxy_failed", r"could not resolve proxy|proxyconnect|connect tunnel failed"),
    (
        "connect_timeout",
        r"connection timed out|connection timeout|tls handshake timeout"
        r"|dial tcp[^\n]*(?:i/o timeout|operation timed out)"
        r"|failed to connect[^\n]*timed out",
    ),
    ("dns_failed", r"resolving timed out"),
    ("no_answer", r"timeout awaiting response headers|while awaiting headers"),
    (
        "stalled",
        r"operation too slow|operation timed out|timeout was reached|curl 28 |timed out"
        r"|context deadline exceeded|i/o timeout",
    ),
    ("rate_limited", r"returned error: 429|\bhttp 429\b|" + _RATE_LIMIT_WORDS),
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
    (
        "dns_failed",
        r"could not resolve host|no such host|name or service not known"
        r"|nodename nor servname|temporary failure in name resolution|error connecting to",
    ),
    ("connect_refused", r"connection refused"),
    ("network_unreachable", r"network is unreachable|no route to host|host is unreachable"),
    (
        "connect_failed",
        r"couldn't connect to server|failed to connect|dial tcp",
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
# ms``, which names the host, not the address, so only Go's form is read). A line about a
# proxy's connection (``proxyconnect tcp: dial tcp …``) names the proxy's address, never
# GitHub's, so it is skipped.
_DIALED = re.compile(r"dial tcp (?:\[([0-9A-Fa-f:.]{2,45})\]|([0-9.]{7,15})):\d{1,5}:")


def failed_address(text: str) -> str | None:
    """The IP address a connection to GitHub named in *text* was to, if it names one."""

    for line in text.splitlines():
        if "proxyconnect" in line.lower():
            continue
        match = _DIALED.search(line)
        if match:
            return match[1] or match[2]
    return None


# The host a tool's error names: the URL Git could not access, the name curl or ssh could
# not resolve or connect to. Only the host is kept, never the URL or its credentials.
_NAMED_HOST = re.compile(
    r"(?:https?|ssh|git)://(?:[^@/\s'\"]*@)?([a-z0-9][a-z0-9.-]*)"
    r"|resolve host(?:name)?:? ([a-z0-9][a-z0-9.-]*)"
    r"|connect to ([a-z0-9][a-z0-9.-]*) port"
    r"|\bgit@([a-z0-9][a-z0-9.-]*):",
    re.IGNORECASE,
)


def named_host(text: str) -> str | None:
    """The host *text*, a tool's error, says it failed to reach, in lower case."""

    match = _NAMED_HOST.search(text)
    if match is None:
        return None
    return next(group for group in match.groups() if group).rstrip(".").lower()


def is_github_host(host: str | None) -> bool:
    """Whether *host* is GitHub's: ``github.com`` or a name under it, such as the API's."""

    if not host:
        return False
    host = host.lower().rstrip(".")
    return host == "github.com" or host.endswith(".github.com")


# How a cause reads at the head of a message. Each starts with "GitHub" and has no colon,
# so a caller's prefix ("The last refresh failed: ...") reads as one sentence: "GitHub
# could not be reached because ..." for the way to GitHub, "GitHub answered ..." for its
# own refusals. ``{host}`` is the host the call was for, and ``{where}`` the host with the
# address that failed, when one is known.
_REACH: Final = "GitHub could not be reached because"
_REASONS: Final[Mapping[NetworkCause, str]] = {
    "dns_failed": f"{_REACH} {{host}} did not resolve (DNS)",
    "connect_refused": f"{_REACH} {{where}} refused the connection",
    "connect_timeout": f"{_REACH} the connection to {{where}} timed out",
    "network_unreachable": f"{_REACH} the network has no route to {{where}}",
    "connect_failed": f"{_REACH} the connection to {{where}} failed",
    "connection_reset": "GitHub's answer was cut off because the connection dropped",
    "tls_failed": f"{_REACH} the secure connection (TLS) to {{host}} failed",
    "proxy_auth_required": f"{_REACH} the proxy requires authentication",
    "proxy_failed": f"{_REACH} the connection through the proxy failed",
    "stalled": "GitHub stopped answering before it finished",
    "no_answer": "GitHub did not answer in time",
    "auth_refused": "GitHub refused the credentials (HTTP 401)",
    "forbidden": "GitHub answered HTTP 403 (access refused)",
    "not_found": "GitHub answered HTTP 404 (not found)",
    "rate_limited": "GitHub's rate limit was reached",
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
# How long a whole probe takes at most: the name's lookup, the connections, closing them,
# and the control's, under one deadline. Measured 2026-11-19 from one macOS machine on a
# home network: resolving api.github.com took 5-10 ms, and TCP connections to reachable
# hosts (pypi.org, registry.npmjs.org, one.one.one.one) 5-26 ms, so even the 2 s left to
# the target when a control runs is over 75 times the slowest. At that moment DNS
# answered api.github.com with an address this network could not reach, and the
# connection to it timed out at whatever bound was set.
PROBE_TIMEOUT_S: Final = 3.0
# The part of :data:`PROBE_TIMEOUT_S` kept for the control host when one will run, at
# most a third of the probe's time: about 40 times the slowest connection measured.
CONTROL_TIMEOUT_S: Final = 1.0
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
# When GitHub cannot be reached, one TCP connection to a host outside GitHub says whether
# the rest of the network can be: "other sites are reachable" makes the failure
# GitHub's or the route to it, not the machine's connection. The default is the host
# macOS itself connects to to check for a network (its captive-portal check), so on
# macOS the probe tells no new party anything; it opens the connection and sends
# nothing. It runs only on macOS, and never when gh goes through a proxy, since a
# direct connection would bypass the proxy the user configured (the owner's decision is
# recorded in the event log's plan, under Open Questions). ``0`` turns it off, and
# ``HOST:PORT`` names another host, which then runs on any platform.
CONTROL_ENV: Final = "METABROWSER_NETWORK_PROBE_CONTROL"
CONTROL_TARGET: Final = ("captive.apple.com", 80)
_OFF: Final = frozenset({"0", "false", "no", "off"})
# The variables gh's Go HTTP client reads for an https request, upper case first
# (``golang.org/x/net/http/httpproxy``): it ignores ``ALL_PROXY`` and honors ``NO_PROXY``.
_PROXY_VARIABLES: Final = ("HTTPS_PROXY", "https_proxy")
_NO_PROXY_VARIABLES: Final = ("NO_PROXY", "no_proxy")
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
_ATTEMPT_HOW: Final[Mapping[AttemptResult, str]] = {
    "connected": "connected",
    "timeout": "timed out",
    "refused": "refused the connection",
    "unreachable": "had no route",
    "failed": "failed to connect",
}
_VERDICT_OF: Final[Mapping[AttemptResult, ProbeVerdict]] = {
    "connected": "reachable",
    "timeout": "connect_timeout",
    "refused": "connect_refused",
    "unreachable": "network_unreachable",
    "failed": "connect_failed",
}
# What failed, after "GitHub could not be reached because"; ``{where}`` is the name and
# the addresses that failed.
_HOW: Final[Mapping[ProbeVerdict, str]] = {
    "reachable": "{where} accepted a connection",
    "dns_failed": "{where} did not resolve (DNS)",
    "connect_timeout": "the connection to {where} timed out",
    "connect_refused": "{where} refused the connection",
    "network_unreachable": "the network has no route to {where}",
    "connect_failed": "the connection to {where} failed",
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

    def _name(self) -> str:
        return f"the proxy at {self.host}" if self.via_proxy else self.host

    def _where(self) -> str:
        """``api.github.com at 20.172.24.160``, or ``the proxy at proxy.corp
        (10.0.0.1)``: the name and the addresses that failed."""

        failed = ", ".join(a.address for a in self.attempts if a.result != "connected")
        if not failed:
            return self._name()
        return f"{self._name()} ({failed})" if self.via_proxy else f"{self.host} at {failed}"

    def _elsewhere(self) -> str:
        if self.control is None:
            return ""
        if self.control.reachable:
            return "; other sites are reachable"
        return "; other sites are not reachable either"

    def headline(self, *, failed_lately: tuple[str, ...] = ()) -> str:
        """The failure the probe found, as a message's head, or what it found reachable.

        "GitHub could not be reached because the connection to api.github.com at
        20.172.24.160 timed out after 2 s; other sites are reachable".

        A reachable probe says only what this lookup found, since the address gh dialed
        may not be one of them: DNS answers vary between lookups. It names the addresses
        that failed in this probe and, in *failed_lately*, others that failed recently:
        "a fresh lookup of api.github.com gave 140.82.114.5, which accepted a connection
        in 38 ms (20.172.24.160 timed out); DNS answers vary, so gh may have used another
        address".
        """

        if self.reachable:
            connected = next(a for a in self.attempts if a.result == "connected")
            text = (
                f"a fresh lookup of {self._name()} gave {connected.address}, which accepted "
                f"a connection in {connected.ms:.0f} ms"
            )
            failed = [a for a in self.attempts if a.result != "connected"]
            if failed:
                text += f" ({', '.join(f'{a.address} {_ATTEMPT_HOW[a.result]}' for a in failed)})"
            text += "; DNS answers vary, so gh may have used another address"
            seen = {a.address for a in self.attempts}
            lately = [address for address in failed_lately if address not in seen]
            if lately:
                text += f", and {', '.join(lately)} could not be reached in the last hour"
            return text
        how = _HOW[self.verdict].format(where=self._where())
        if self.verdict == "dns_failed":
            how = _HOW["dns_failed"].format(where=self._name())
        if self.verdict == "connect_timeout":
            how += f" after {self.timeout_s:g} s"
        return f"{_REACH} {how}{self._elsewhere()}"

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


def _bypasses_proxy(host: str, port: int, no_proxy: str) -> bool:
    """Whether *no_proxy*, as Go reads ``NO_PROXY``, sends *host* past the proxy: ``*``,
    the host or a domain above it (``github.com``, ``.github.com``), with an optional
    port, or an address or CIDR block that holds it."""

    host = host.lower()
    for entry in (part.strip().lower() for part in no_proxy.split(",")):
        if not entry:
            continue
        if entry == "*":
            return True
        try:
            if ipaddress.ip_address(host) in ipaddress.ip_network(entry, strict=False):
                return True
            continue
        except ValueError:
            pass
        name, _, entry_port = entry.rpartition(":") if ":" in entry else (entry, "", "")
        if entry_port and entry_port != str(port):
            continue
        name = name.lstrip("*")
        if host == name.lstrip(".") or host.endswith(name if name.startswith(".") else f".{name}"):
            return True
    return False


def probe_target(environ: Mapping[str, str] | None = None) -> tuple[str, int, bool] | None:
    """``(host, port, via_proxy)`` to probe, or ``None`` when probing is off.

    gh connects through ``HTTPS_PROXY`` when one is set and ``NO_PROXY`` does not exempt
    GitHub, so the probe connects to that proxy: a direct connection would test a path gh
    does not take. The proxy URL's credentials are never read.
    """

    env = os.environ if environ is None else environ
    setting = _setting(env, PROBE_ENV)
    if setting == "off":
        return None
    if setting is not None:
        return *setting, False
    no_proxy = next((env[n] for n in _NO_PROXY_VARIABLES if env.get(n, "").strip()), "")
    if no_proxy and _bypasses_proxy(PROBE_HOST, PROBE_PORT, no_proxy):
        return PROBE_HOST, PROBE_PORT, False
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
        # gh takes the first set variable whole, so an unusable one is no proxy at all.
        break
    return PROBE_HOST, PROBE_PORT, False


def control_target(
    environ: Mapping[str, str] | None = None,
    *,
    via_proxy: bool = False,
    platform: str = sys.platform,
) -> tuple[str, int] | None:
    """The host outside GitHub a failed probe tries, or ``None`` when none is tried.

    None through a proxy, which a direct connection would bypass. :data:`CONTROL_TARGET`
    only on macOS, which connects to it itself; a ``HOST:PORT`` in :data:`CONTROL_ENV`
    on any platform.
    """

    if via_proxy:
        return None
    env = os.environ if environ is None else environ
    setting = _setting(env, CONTROL_ENV)
    if setting == "off":
        return None
    if setting is not None:
        return setting
    return CONTROL_TARGET if platform == "darwin" else None


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
    control host (:func:`control_target`) is tried too, all within *timeout_s*.

    Best effort: it explains a failure and must never replace it, so anything it cannot
    do, such as a proxy whose name is not a valid host, is logged and the answer is
    ``None``. Only a cancellation passes through.
    """

    try:
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
            control = control_target(environ, via_proxy=via_proxy)
            running = asyncio.ensure_future(_probe(host, port, via_proxy, timeout_s, control))
            _running[key] = running
            running.add_done_callback(lambda _: _running.pop(key, None))
        return await asyncio.shield(running)
    except Exception as exc:
        log.debug("the network probe failed: %s", exc, exc_info=True)
        return None


async def _connect(address: tuple[str, int], family: int, deadline: float) -> Attempt:
    """One connection, opened and closed by *deadline* (monotonic)."""

    started = time.perf_counter()
    result: AttemptResult = "connected"
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(address[0], address[1], family=family),
            timeout=max(0.001, deadline - time.monotonic()),
        )
        writer.close()
        with contextlib.suppress(TimeoutError, OSError):
            await asyncio.wait_for(
                writer.wait_closed(), timeout=max(0.001, deadline - time.monotonic())
            )
    except TimeoutError:
        result = "timeout"
    except ConnectionRefusedError:
        result = "refused"
    except OSError as exc:
        result = "unreachable" if exc.errno in _UNREACHABLE_ERRNOS else "failed"
    return Attempt(address[0], result, round((time.perf_counter() - started) * 1000, 1))


async def _resolve_and_connect(
    host: str, port: int, via_proxy: bool, deadline: float, control: ProbeResult | None = None
) -> ProbeResult:
    """Resolve *host* and connect to its addresses, all by *deadline* (monotonic)."""

    loop = asyncio.get_running_loop()
    timeout_s = round(max(0.0, deadline - time.monotonic()), 1)
    dns_ms: float | None = None
    attempts: tuple[Attempt, ...] = ()
    verdict: ProbeVerdict = "dns_failed"
    started = time.perf_counter()
    try:
        infos = await asyncio.wait_for(
            loop.getaddrinfo(host, port, type=socket.SOCK_STREAM),
            timeout=max(0.001, deadline - time.monotonic()),
        )
        dns_ms = round((time.perf_counter() - started) * 1000, 1)
    except (TimeoutError, OSError, UnicodeError):
        # UnicodeError: a name IDNA cannot encode, such as one with an empty label.
        infos = []
    seen: dict[str, tuple[int, tuple[str, int]]] = {}
    for family, _, _, _, address in infos:
        seen.setdefault(str(address[0]), (family, (str(address[0]), int(address[1]))))
    targets = list(seen.values())[:PROBE_ADDRESSES]
    if targets:
        attempts = tuple(
            await asyncio.gather(*(_connect(addr, fam, deadline) for fam, addr in targets))
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
    # One deadline for the whole probe; a control that will run keeps its share of it.
    end = time.monotonic() + timeout_s
    reserve = min(CONTROL_TIMEOUT_S, timeout_s / 3) if control is not None else 0.0
    with event_log.span(
        "probe", f"probe {host}:{port}", attrs={"timeout_s": timeout_s, "via_proxy": via_proxy}
    ) as span:
        result = await _resolve_and_connect(host, port, via_proxy, end - reserve)
        if not result.reachable and control is not None:
            checked = await _resolve_and_connect(*control, False, end)
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
    "CONTROL_TIMEOUT_S",
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
    "is_github_host",
    "mentions_rate_limit",
    "named_host",
    "control_target",
    "forget_probes",
    "http_status",
    "probe",
    "probe_target",
    "reason",
    "recent_probe",
    "remember_probe",
]
