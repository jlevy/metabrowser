"""What every Git command that talks to an origin is given, and how its failures read.

Acquisition today, and the refresh path later, pass :func:`remote_git_args` to each
``ls-remote`` and ``fetch``: the protocol allowlist, the measured low-speed stall bound,
and whatever an installed provider adds for that URL (the GitHub provider's ``gh``
credential helper). :func:`classify_remote_failure` turns Git's own error text, which is
only ever logged, into a typed state a user can act on.
"""

from __future__ import annotations

import re
from typing import Final, Literal

from metabrowser.cache.providers import provider_credential_hint, provider_git_config

# Git refuses every transport but these two. ``protocol.allow=never`` also covers the
# redirect protocols curl may follow, so an https origin cannot redirect to http.
PROTOCOL_ARGS: Final[tuple[str, ...]] = (
    "-c",
    "protocol.allow=never",
    "-c",
    "protocol.file.allow=always",
    "-c",
    "protocol.https.allow=always",
)

# An https transfer that moves fewer than HTTP_LOW_SPEED_LIMIT_BYTES per second for
# HTTP_LOW_SPEED_TIME_S seconds is stalled, and curl aborts it. Measured 2026-09-23 on
# one macOS machine (Git 2.50.1, load average 36 to 103), through a local CONNECT proxy
# in front of github.com:
# - healthy full fetches ran at 3.5 to 14.6 MB/s (flask, requests, mypy, django), and
#   the longest quiet gap in django's 291 MB pack stream was 0.38 s, so a limit of
#   1000 B/s sits more than three orders of magnitude below a healthy transfer;
# - with lowSpeedLimit=1000 and lowSpeedTime=10, a proxy that stopped forwarding 1.1 s
#   into a flask fetch failed it at 17.4 s (Git reported an early EOF), one throttled
#   to 500 B/s failed at 17.3 s ("curl 28 Operation too slow"), and one throttled to
#   4000 B/s kept going for the full 45 s the run allowed;
# - the bound does not apply before TLS completes: with lowSpeedTime=5, a server that
#   accepts and never answers failed only at 300.2 s, curl's connect timeout ("SSL
#   connection timeout"), which is why the first command against an origin also has
#   REMOTE_PROBE_TIMEOUT_S.
# - the bound covers a server preparing its pack, which a fetch with progress off sees
#   as silence broken only by keepalives: torvalds/linux, among the largest public
#   repositories, began its pack 1.7 s after the request, and its longest silence in
#   the first 290 MB was 0.49 s.
# 30 s tolerates a server much slower to start its pack than that, while bounding a
# stall at half a minute rather than the whole acquisition deadline.
HTTP_LOW_SPEED_LIMIT_BYTES: Final[int] = 1000
HTTP_LOW_SPEED_TIME_S: Final[int] = 30
_STALL_ARGS: Final[tuple[str, ...]] = (
    "-c",
    f"http.lowSpeedLimit={HTTP_LOW_SPEED_LIMIT_BYTES}",
    "-c",
    f"http.lowSpeedTime={HTTP_LOW_SPEED_TIME_S}",
)

# Deadline for ``ls-remote --symref -- <url> HEAD``, the first command against an
# origin. Measured 2026-09-23 against github.com from the same machine, three runs
# each: 0.76 to 2.36 s for octocat/Hello-World, django, kubernetes, torvalds/linux, and
# cpython. Thirteen times the slowest keeps a slow network from failing, and it bounds
# the stalled-TLS case above at 30 s instead of 300.
#
# The fetch that follows has no such deadline, because a whole clone must not be
# killed while it is making progress. Once its connection is up, the low-speed bound
# covers it to the end, pack preparation included. Before TLS completes it is bounded
# only by curl's 300 s connect timeout and GIT_ACQUISITION_TIMEOUT_S: Git has no
# configuration for a connect timeout alone. The ls-remote seconds earlier has just
# completed a TLS handshake with the same origin, so that window is narrow.
REMOTE_PROBE_TIMEOUT_S: Final[float] = 30.0

type RemoteFailureState = Literal[
    "not_found_or_private",
    "network_unreachable",
    "connection_interrupted",
    "tls_failed",
    "timed_out",
    "server_error",
    "rate_limited",
    "proxy_auth_required",
    "too_large",
]

# Git runs with LC_ALL=C, so these are its and curl's untranslated messages. The samples
# in tests/test_cache_remote.py were captured 2026-09-23 from Git 2.50.1 (Homebrew, curl
# with OpenSSL) against github.com, an unresolvable host, a closed port, badssl.com's
# certificate failures, a stalled server, CONNECT proxies that reset, truncate, or
# demand authentication, and HTTP servers answering 429, 500, and 503. Two reported
# forms the machine could not produce are included and marked there: OpenSSL on Linux
# reports a reset as ``SSL_ERROR_SYSCALL, errno 104``, and HTTP/2 as curl 92.
# Order matters, because one failure prints several lines: a low-speed abort also
# prints ``early EOF``, so a timeout is decided first; an HTTP status outranks the
# connection it arrived on; and an interrupted connection outranks the TLS layer it was
# reported through. Quoted text, which is where Git puts the URL, is removed before
# matching, so a repository named ``tls-notes`` stays not found.
_QUOTED = re.compile(r"'[^'\n]*'")
_SERVER_ERROR = re.compile(r"returned error: 5\d\d\b")
_PATTERNS: Final[tuple[tuple[RemoteFailureState, tuple[str, ...]], ...]] = (
    (
        "timed_out",
        (
            "operation too slow",
            "timed out",
            "connection timeout",
            "timeout was reached",
            "curl 28 ",
        ),
    ),
    (
        "proxy_auth_required",
        ("response 407", "received http code 407", "returned error: 407"),
    ),
    ("rate_limited", ("returned error: 429",)),
    (
        "connection_interrupted",
        (
            "connection reset",
            "ssl_error_syscall",
            "unexpected eof while reading",
            "transferred a partial file",
            "transfer closed with outstanding read data",
            "curl 18 ",
            "curl 56 ",
            "curl 92 ",
            "was not closed cleanly",
            "unexpected disconnect",
            "early eof",
            "the remote end hung up unexpectedly",
        ),
    ),
    (
        "tls_failed",
        (
            "ssl certificate problem",
            "ssl: no alternative certificate",
            "ssl: certificate subject name",
            "ssl connect error",
            "tls connect error",
            "gnutls_handshake",
            "server certificate verification failed",
            "certificate verify failed",
            "schannel",
        ),
    ),
    (
        "network_unreachable",
        (
            "could not resolve host",
            "could not resolve proxy",
            "couldn't connect to server",
            "failed to connect",
            "network is unreachable",
            "connection refused",
            "no route to host",
        ),
    ),
    (
        "not_found_or_private",
        (
            "repository not found",
            "not found",
            "could not read username",
            "could not read password",
            "authentication failed",
            "returned error: 401",
            "returned error: 403",
            "returned error: 404",
        ),
    ),
)

_STATE_TEXT: Final[dict[RemoteFailureState, str]] = {
    "not_found_or_private": "was not found, or it is private and Git has no credentials for it",
    "network_unreachable": "could not be reached; check the network connection",
    "connection_interrupted": "dropped the connection before the transfer finished; try again",
    "tls_failed": "failed the TLS security check",
    "timed_out": "stopped answering in time",
    "server_error": "answered with a server error; try again later",
    "rate_limited": "is limiting the rate of requests; try again later",
    "proxy_auth_required": "is behind a proxy that requires authentication",
    "too_large": "is too large to clone within the acquisition deadline",
}


def remote_git_args(remote_url: str) -> tuple[str, ...]:
    """``-c`` options for a Git command that talks to *remote_url*.

    The integration point for every network Git command: acquisition's ``ls-remote``
    and ``fetch`` now, and the refresh path's ``ls-remote --symref`` and
    ``fetch --prune --atomic`` when it lands.
    """

    return (*PROTOCOL_ARGS, *_STALL_ARGS, *provider_git_config(remote_url))


def classify_remote_failure(stderr_summary: str) -> RemoteFailureState | None:
    """The typed state Git's error text describes, or ``None`` when none matches."""

    text = _QUOTED.sub("''", stderr_summary).lower()
    for state, needles in _PATTERNS:
        if any(needle in text for needle in needles):
            return state
        if state == "rate_limited" and _SERVER_ERROR.search(text):
            return "server_error"
    return None


def describe_remote_failure(state: RemoteFailureState, source_url: str, *, detail: str = "") -> str:
    """A user-facing message: the source URL, what went wrong, and what to do.

    The source URL is credential-free by construction. Git's own text is never
    included, because it can carry local paths.
    """

    hint = provider_credential_hint(source_url) if state == "not_found_or_private" else None
    message = f"{source_url} {_STATE_TEXT[state]} ({state})"
    if detail:
        message += f"; {detail}"
    if hint:
        message += f"; {hint}"
    return message + "; nothing was published"


__all__ = [
    "HTTP_LOW_SPEED_LIMIT_BYTES",
    "HTTP_LOW_SPEED_TIME_S",
    "PROTOCOL_ARGS",
    "REMOTE_PROBE_TIMEOUT_S",
    "RemoteFailureState",
    "classify_remote_failure",
    "describe_remote_failure",
    "remote_git_args",
]
