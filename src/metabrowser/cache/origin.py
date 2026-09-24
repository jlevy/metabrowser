"""How a store talks to its origin: the ``ls-remote`` and ``fetch`` commands, and their failures.

Acquisition and refresh run the same two network commands, so their arguments are
built here and nowhere else: first ``ls-remote --symref`` to observe which branch the
origin's HEAD names, then one fetch of every branch and tag with explicit refspecs.
Branches land under ``refs/remotes/origin/`` and tags under ``refs/tags/``; Metabrowser
writes no ref of its own, and pruning those refspecs never touches any other namespace.

Both commands name the origin by URL and get :func:`origin_git_args` for it: the
protocol allowlist (``file`` and ``https``), the measured low-speed stall bound, and
whatever an installed provider adds for that URL, which is the ``gh`` credential helper
for github.com. They run under the acquisition policy, whose ``HOME=/dev/null`` keeps
curl from reading ``.netrc``. :func:`classify_remote_failure` turns Git's own error
text, which is only ever logged, into a typed state a user can act on.
"""

from __future__ import annotations

import re
from typing import Final, Literal

from metabrowser.cache.providers import provider_credential_hint, provider_git_config
from metabrowser.git.wire import is_full_revision

# Every refspec a store fetches. A branch is mirrored under the remote-tracking
# namespace so no local branch is invented; a tag keeps its own name.
MIRROR_REFSPECS: Final[tuple[str, ...]] = (
    "+refs/heads/*:refs/remotes/origin/*",
    "+refs/tags/*:refs/tags/*",
)
BRANCH_MIRROR_PREFIX: Final = "refs/remotes/origin/"
TAG_PREFIX: Final = "refs/tags/"


class OriginHeadError(Exception):
    """The origin did not advertise a usable HEAD."""


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


def origin_git_args(remote_url: str) -> tuple[str, ...]:
    """``-c`` options for a Git command that talks to the origin at *remote_url*."""

    return (*PROTOCOL_ARGS, *_STALL_ARGS, *provider_git_config(remote_url))


def ls_remote_head_args(remote_url: str) -> list[str]:
    """``ls-remote --symref`` for the origin's HEAD, naming *remote_url* after ``--``."""

    return [*origin_git_args(remote_url), "ls-remote", "--symref", "--", remote_url, "HEAD"]


def mirror_fetch_args(remote_url: str, *, prune: bool) -> list[str]:
    """One fetch of every branch and tag from *remote_url* into the mirror namespaces.

    The origin is named by URL, the same URL that chose the credential helper, rather
    than by the store's configured remote. ``--porcelain`` (Git 2.41) lists every ref
    the fetch wrote, which :func:`fetched_ref_names` reads. Acquisition fetches into an
    empty staging store and needs neither flag below. A refresh passes ``prune`` for
    ``--prune --atomic``: a branch or tag deleted upstream leaves the mirror, and every
    ref updates together or none does, so a killed or failed fetch never leaves some
    refs moved and others not. Objects written before a failure stay, which is
    harmless because nothing references them yet. With ``--porcelain`` a ref update
    goes to stdout rather than stderr, so a refresh with thousands of new refs keeps
    stderr to Git's errors; ``--quiet`` would do that too, but it also silences the
    porcelain listing a refresh checks its refs against.
    """

    flags = ["--prune", "--atomic"] if prune else []
    return [
        *origin_git_args(remote_url),
        "fetch",
        "--porcelain",
        *flags,
        "--no-write-fetch-head",
        remote_url,
        *MIRROR_REFSPECS,
    ]


def fetched_refs(porcelain: bytes) -> dict[str, str]:
    """The refs a ``fetch --porcelain`` wrote, each with the object it wrote, in order.

    Each line is ``<flag> <old-oid> <new-oid> <local-ref>``, and the flag may itself be
    a space. A pruned ref, whose new object ID is all zeros, is gone and not listed.
    """

    written: dict[str, str] = {}
    for line in porcelain.split(b"\n"):
        fields = line[2:].split(b" ")
        if len(line) > 2 and len(fields) == 3 and fields[1].strip(b"0"):
            written[fields[2].decode("utf-8", "surrogateescape")] = fields[1].decode(
                "ascii", "replace"
            )
    return written


def pruned_ref_names(porcelain: bytes) -> tuple[str, ...]:
    """The refs a ``fetch --porcelain --prune`` deleted: those whose new object ID is zeros."""

    names: list[str] = []
    for line in porcelain.split(b"\n"):
        fields = line[2:].split(b" ")
        if len(line) > 2 and len(fields) == 3 and fields[1] and not fields[1].strip(b"0"):
            names.append(fields[2].decode("utf-8", "surrogateescape"))
    return tuple(names)


def fetched_ref_names(porcelain: bytes) -> tuple[str, ...]:
    """The names of the refs a ``fetch --porcelain`` wrote; see :func:`fetched_refs`."""

    return tuple(fetched_refs(porcelain))


# ``remote prune`` takes a remote's name, not a URL. This one is defined only on the
# command line, so *remote_url* is its one URL whatever the store configures.
_PRUNE_REMOTE: Final = "metabrowser-origin"


def mirror_prune_args(remote_url: str) -> list[str]:
    """Delete the mirror refs whose branch or tag the origin no longer has, and nothing else.

    ``remote prune`` maps the origin's refs through the same refspecs a fetch uses. The
    remote it names is defined here, from *remote_url* and those refspecs, so it reads
    the origin the fetch reads, never the store's configured ``origin``, and it gets
    *remote_url*'s arguments, so the credential helper is the fetch's. It only
    deletes, so a refresh runs it before the atomic fetch when one transaction cannot
    both delete ``side`` and create ``side/x``.
    """

    remote = [
        "-c",
        f"remote.{_PRUNE_REMOTE}.url={remote_url}",
        *(
            arg
            for spec in MIRROR_REFSPECS
            for arg in ("-c", f"remote.{_PRUNE_REMOTE}.fetch={spec}")
        ),
    ]
    return [*origin_git_args(remote_url), *remote, "remote", "prune", _PRUNE_REMOTE]


def parse_symref_head(stdout: bytes) -> tuple[str | None, str]:
    """The ref the origin's HEAD names, if any, and the object ID it resolves to.

    The ``HEAD`` pattern also matches any ref whose last component is HEAD, such as a
    clone's ``refs/remotes/origin/HEAD``. Only the ref named exactly HEAD counts.
    """

    ref: str | None = None
    oid: str | None = None
    for line in stdout.decode("ascii", errors="replace").splitlines():
        payload, _, name = line.partition("\t")
        if name != "HEAD":
            continue
        if payload.startswith("ref:"):
            ref = payload.removeprefix("ref:").strip()
        else:
            oid = payload.strip()
    if oid is None or not is_full_revision(oid):
        raise OriginHeadError("the source did not advertise HEAD")
    return ref, oid


def remote_tracking_ref(head_ref: str | None) -> str | None:
    """The mirror ref for the origin branch *head_ref*, or ``None`` when HEAD is no branch."""

    if head_ref is None or not head_ref.startswith("refs/heads/"):
        return None
    return BRANCH_MIRROR_PREFIX + head_ref.removeprefix("refs/heads/")


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
    "BRANCH_MIRROR_PREFIX",
    "HTTP_LOW_SPEED_LIMIT_BYTES",
    "HTTP_LOW_SPEED_TIME_S",
    "MIRROR_REFSPECS",
    "PROTOCOL_ARGS",
    "REMOTE_PROBE_TIMEOUT_S",
    "TAG_PREFIX",
    "OriginHeadError",
    "RemoteFailureState",
    "classify_remote_failure",
    "describe_remote_failure",
    "fetched_ref_names",
    "fetched_refs",
    "pruned_ref_names",
    "ls_remote_head_args",
    "mirror_fetch_args",
    "mirror_prune_args",
    "origin_git_args",
    "parse_symref_head",
    "remote_tracking_ref",
]
