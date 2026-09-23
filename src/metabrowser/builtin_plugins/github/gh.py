"""Run ``gh`` with fixed arguments, an isolated environment, and hard bounds.

``gh`` owns GitHub authentication; Metabrowser never reads, stores, or logs a token.
Every run gets no stdin, prompts and update checks off, no colour, and no inherited
``GH_DEBUG``, ``GH_HOST``, or ``GH_REPO``; a deadline and an output cap; and its own
process group, so a timeout or cancellation kills anything it started. Its stdout is
never logged, because it can be private repository data or, for ``auth status``, the
account's scopes.

:func:`gh_api` issues one ``gh api --hostname github.com --include`` request and returns
the status, headers, and body; :func:`gh_account` reads the active github.com login.
Both raise :class:`GhError` with a typed ``state`` a user can act on. Nothing here
paginates or caches: callers name every page, as ``gh api --paginate`` and ``--cache``
would hide the page cap, the ETags, and the rate-limit headers.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final, Literal

from metabrowser.git.process import terminate_git_process

log = logging.getLogger(__name__)

# One repository-size read is a few kilobytes and answers in well under a second; these
# bound a hung or runaway gh, not a slow one.
GH_TIMEOUT_S: Final[float] = 15.0
GH_MAX_BYTES: Final[int] = 256 * 1024
# One API page. Measured 2026-09-23 with gh 2.98.0 on one macOS machine under load
# average 23: the largest of 100-item pages across ten public pull requests was 773,572
# bytes with headers (kubernetes/kubernetes#102884 review comments, whose diff hunks
# reach 61 KB each) and took 1.6 to 2.0 s. The cap is about ten times that page, and
# the deadline about fifteen times its slowest read.
GH_API_TIMEOUT_S: Final[float] = 30.0
GH_API_MAX_BYTES: Final[int] = 8 * 1024 * 1024
# The first gh release with ``gh auth status --json`` (release notes, 2025-10-01).
GH_MIN_VERSION: Final = "2.81.0"
GH_HOSTNAME: Final = "github.com"
GITHUB_API_VERSION: Final = "2022-11-28"
_READ_CHUNK_BYTES: Final[int] = 64 * 1024
_STDERR_MAX_BYTES: Final[int] = 16 * 1024
_ACCOUNT_MAX_BYTES: Final[int] = 64 * 1024
# Dropped from the inherited environment. CLICOLOR_FORCE and GH_FORCE_TTY, both common in
# dotfiles, make gh colorize --include headers and JSON even with NO_COLOR set, and
# escape codes in a status line or a body make every read unparseable.
_DROPPED_ENV: Final[tuple[str, ...]] = (
    "GH_DEBUG",
    "GH_HOST",
    "GH_REPO",
    "GH_PAGER",
    "GH_FORCE_TTY",
    "CLICOLOR_FORCE",
    "DEBUG",
)
# gh's documented exit status when a command needs authentication.
_GH_EXIT_AUTH: Final = 4
_API_PATH = re.compile(r"^repos/[A-Za-z0-9._/-]+(?:\?[A-Za-z0-9_=&.-]*)?$")
_ETAG = re.compile(r'^(?:W/)?"[\x21\x23-\x7e]{1,256}"$')
_LOGIN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$")
_STATUS_LINE = re.compile(rb"^HTTP/[0-9.]+ ([0-9]{3})(?: [^\r\n]*)?$")

type GhFailureState = Literal[
    "gh_missing",
    "gh_too_old",
    "not_logged_in",
    "rate_limited",
    "not_found_or_private",
    "network_error",
    "gh_failed",
]

# gh's own text, captured 2026-09-23 from gh 2.98.0: a logged-out ``gh api`` exits 4
# with "To get started with GitHub CLI, please run:  gh auth login", an offline one with
# "error connecting to api.github.com", and a gh without ``auth status --json`` answers
# "unknown flag: --json". Only ever matched, never shown.
_NETWORK_TEXT: Final[tuple[str, ...]] = (
    "error connecting to",
    "dial tcp",
    "no such host",
    "connection refused",
    "connection reset",
    "i/o timeout",
    "tls handshake timeout",
    "network is unreachable",
    "timeout awaiting response headers",
)
_LOGIN_TEXT: Final[tuple[str, ...]] = ("gh auth login", "not logged in", "bad credentials")


class GhError(Exception):
    """``gh`` could not answer; ``state`` says why. The message never carries its output."""

    def __init__(
        self, message: str, *, state: GhFailureState = "gh_failed", reset_at: str | None = None
    ) -> None:
        super().__init__(message)
        self.state: GhFailureState = state
        self.reset_at: str | None = reset_at


class GhUnavailableError(GhError):
    """No ``gh`` executable on ``PATH``."""

    def __init__(self, message: str = "GitHub CLI (gh) is not on PATH") -> None:
        super().__init__(message, state="gh_missing")


class GhOutputTooLargeError(GhError):
    """``gh`` wrote more than the output cap; a caller may ask for less."""


@dataclass(frozen=True, slots=True)
class _Completed:
    returncode: int
    stdout: bytes
    stderr: bytes


@dataclass(frozen=True, slots=True)
class GhResponse:
    """One HTTP response ``gh api --include`` printed: status, lowercased headers, body."""

    status: int
    headers: Mapping[str, str]
    body: bytes

    @property
    def etag(self) -> str | None:
        value = self.headers.get("etag")
        return value if value is not None and _ETAG.match(value) else None

    @property
    def has_next_page(self) -> bool:
        return 'rel="next"' in self.headers.get("link", "")

    def json(self) -> object:
        try:
            return json.loads(self.body)
        except ValueError as exc:
            raise GhError("GitHub answered with something other than JSON") from exc


def gh_executable() -> str | None:
    """Absolute path of ``gh`` on ``PATH``, or ``None``. Looked up on every call."""

    found = shutil.which("gh")
    return os.path.abspath(found) if found else None


def gh_environment() -> dict[str, str]:
    """The environment every ``gh`` run gets."""

    env = {name: value for name, value in os.environ.items() if name not in _DROPPED_ENV}
    env.update(
        {
            "GH_PROMPT_DISABLED": "1",
            "GH_NO_UPDATE_NOTIFIER": "1",
            "GH_SPINNER_DISABLED": "1",
            "NO_COLOR": "1",
            "CLICOLOR": "0",
        }
    )
    return env


async def _read_capped(stream: asyncio.StreamReader | None, limit: int) -> tuple[bytes, bool]:
    if stream is None:
        return b"", False
    chunks: list[bytes] = []
    total = 0
    overflowed = False
    while chunk := await stream.read(_READ_CHUNK_BYTES):
        total += len(chunk)
        if total > limit:
            overflowed = True
            continue
        chunks.append(chunk)
    return b"".join(chunks), overflowed


async def _run(args: Sequence[str], *, timeout_s: float, max_bytes: int) -> _Completed:
    """Run ``gh`` once. Raises only for a missing gh, a deadline, or too much output."""

    exe = gh_executable()
    if exe is None:
        raise GhUnavailableError
    try:
        proc = await asyncio.create_subprocess_exec(
            exe,
            *args,
            stdin=subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=gh_environment(),
            start_new_session=os.name == "posix",
        )
    except OSError as exc:
        raise GhError(f"could not run gh: {exc.strerror}") from exc
    stdout_task = asyncio.ensure_future(_read_capped(proc.stdout, max_bytes))
    stderr_task = asyncio.ensure_future(_read_capped(proc.stderr, _STDERR_MAX_BYTES))
    try:
        (stdout, overflowed), (stderr, _), returncode = await asyncio.wait_for(
            asyncio.gather(stdout_task, stderr_task, proc.wait()), timeout=timeout_s
        )
    except TimeoutError:
        stdout_task.cancel()
        stderr_task.cancel()
        await terminate_git_process(proc)
        raise GhError(f"gh did not answer within {timeout_s:g} s", state="network_error") from None
    except asyncio.CancelledError:
        stdout_task.cancel()
        stderr_task.cancel()
        await terminate_git_process(proc)
        raise
    if overflowed:
        raise GhOutputTooLargeError(f"gh wrote more than {max_bytes} bytes")
    if returncode != 0:
        log.debug("gh %s exited %s: %s", args[0] if args else "", returncode, stderr[:512])
    return _Completed(returncode, stdout, stderr)


async def run_gh(
    args: Sequence[str], *, timeout_s: float = GH_TIMEOUT_S, max_bytes: int = GH_MAX_BYTES
) -> bytes:
    """Run ``gh`` with *args* and return its stdout, or raise :class:`GhError`."""

    completed = await _run(args, timeout_s=timeout_s, max_bytes=max_bytes)
    if completed.returncode != 0:
        raise GhError(f"gh exited {completed.returncode}")
    return completed.stdout


def _failure_without_response(completed: _Completed) -> GhError:
    """The typed state of a ``gh`` run that printed no HTTP response."""

    text = completed.stderr.decode("utf-8", errors="replace").lower()
    if completed.returncode == _GH_EXIT_AUTH or any(needle in text for needle in _LOGIN_TEXT):
        return GhError(
            "gh is not signed in to github.com; run gh auth login", state="not_logged_in"
        )
    if any(needle in text for needle in _NETWORK_TEXT):
        return GhError("gh could not reach api.github.com", state="network_error")
    return GhError(f"gh exited {completed.returncode} without an HTTP response")


def parse_included_response(stdout: bytes) -> GhResponse | None:
    """Split ``gh api --include`` output into status, headers, and body, or ``None``.

    gh ends the status line with LF and each header with CRLF, then a blank line.
    """

    head, separator, body = stdout.partition(b"\r\n\r\n")
    if not separator:
        head, separator, body = stdout.partition(b"\n\n")
        if not separator:
            head, body = stdout, b""
    lines = head.replace(b"\r\n", b"\n").split(b"\n")
    match = _STATUS_LINE.match(lines[0]) if lines else None
    if match is None:
        return None
    headers: dict[str, str] = {}
    for line in lines[1:]:
        name, colon, value = line.partition(b":")
        if colon:
            headers[name.decode("latin-1").strip().lower()] = value.decode("latin-1").strip()
    return GhResponse(status=int(match.group(1)), headers=headers, body=body)


def _epoch_text(seconds: float) -> str:
    return datetime.fromtimestamp(seconds, tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def rate_limit_reset(response: GhResponse, *, now: datetime) -> str | None:
    """When GitHub will answer again, if *response* is a rate-limit refusal, else ``None``.

    ``Retry-After`` (a secondary limit) wins; otherwise an exhausted primary limit
    resets at ``x-ratelimit-reset``, in epoch seconds.
    """

    if response.status not in {403, 429}:
        return None
    retry_after = response.headers.get("retry-after", "")
    if retry_after.isdigit():
        return (now + timedelta(seconds=int(retry_after))).strftime("%Y-%m-%dT%H:%M:%SZ")
    if response.headers.get("x-ratelimit-remaining") == "0":
        reset = response.headers.get("x-ratelimit-reset", "")
        return _epoch_text(int(reset)) if reset.isdigit() else "unknown"
    if response.status == 429 or _mentions_rate_limit(response.body):
        return "unknown"
    return None


def _mentions_rate_limit(body: bytes) -> bool:
    """Whether a refusal's message names a rate limit, as a secondary limit's does.

    A secondary limit can answer 403 with requests still remaining and no
    ``Retry-After``; its message ("You have exceeded a secondary rate limit") is then
    the only sign. The message is matched, never shown.
    """

    try:
        payload = json.loads(body[:_STDERR_MAX_BYTES])
    except ValueError:
        return False
    message = payload.get("message") if isinstance(payload, dict) else None
    return isinstance(message, str) and "rate limit" in message.lower()


def _refusal(response: GhResponse, *, now: datetime) -> GhError | None:
    """The typed failure an HTTP status means, or ``None`` for 2xx and 304."""

    if 200 <= response.status < 300 or response.status == 304:
        return None
    reset = rate_limit_reset(response, now=now)
    if reset is not None:
        when = "; try again in a few minutes" if reset == "unknown" else f" until {reset}"
        return GhError(
            f"GitHub's API rate limit is exhausted{when}",
            state="rate_limited",
            reset_at=None if reset == "unknown" else reset,
        )
    if response.status == 401:
        return GhError(
            "gh's github.com credentials were refused; run gh auth login", state="not_logged_in"
        )
    if response.status in {403, 404, 410}:
        return GhError(
            "GitHub has no such pull request, or it is private and the gh account cannot read it",
            state="not_found_or_private",
        )
    if response.status >= 500:
        return GhError(f"GitHub answered HTTP {response.status}", state="network_error")
    return GhError(f"GitHub answered HTTP {response.status}")


async def gh_api(path: str, *, etag: str | None = None, now: datetime | None = None) -> GhResponse:
    """``GET`` one github.com API *path*; a ``304`` is returned, other failures raise.

    *path* is built by the caller from validated parts and is checked again here, so no
    user text reaches gh as an option. *etag*, when given, is sent as ``If-None-Match``.
    """

    if not _API_PATH.match(path) or any(
        part in {"", ".", ".."} for part in path.split("?", 1)[0].split("/")
    ):
        raise ValueError("not a repository API path")
    args = [
        "api",
        "--hostname",
        GH_HOSTNAME,
        "--method",
        "GET",
        "--include",
        "-H",
        f"X-GitHub-Api-Version: {GITHUB_API_VERSION}",
    ]
    if etag is not None:
        if not _ETAG.match(etag):
            raise ValueError("not an ETag")
        args += ["-H", f"If-None-Match: {etag}"]
    args.append(path)
    completed = await _run(args, timeout_s=GH_API_TIMEOUT_S, max_bytes=GH_API_MAX_BYTES)
    response = parse_included_response(completed.stdout)
    if response is None:
        raise _failure_without_response(completed)
    refused = _refusal(response, now=now or datetime.now(UTC))
    if refused is not None:
        raise refused
    return response


def parse_account(stdout: bytes) -> str | None:
    """The active github.com login from ``gh auth status --json hosts``, or ``None``.

    A non-success ``state`` still names the login: gh reports an error state when it is
    offline, which is not being signed out. Scopes and token source are never read.
    """

    try:
        payload = json.loads(stdout)
    except ValueError as exc:
        raise GhError("gh auth status answered with something other than JSON") from exc
    hosts = payload.get("hosts") if isinstance(payload, dict) else None
    entries = hosts.get(GH_HOSTNAME) if isinstance(hosts, dict) else None
    if not isinstance(entries, list):
        return None
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("active") is not True:
            continue
        login = entry.get("login")
        if isinstance(login, str) and _LOGIN.match(login):
            return login
        raise GhError("gh auth status named an account that is not a GitHub login")
    return None


async def gh_account() -> str:
    """The active github.com login, from ``gh auth status --active --json hosts``."""

    completed = await _run(
        ["auth", "status", "--active", "--hostname", GH_HOSTNAME, "--json", "hosts"],
        timeout_s=GH_TIMEOUT_S,
        max_bytes=_ACCOUNT_MAX_BYTES,
    )
    if completed.stdout.strip().startswith(b"{"):
        login = parse_account(completed.stdout)
        if login is None:
            raise GhError(
                "gh is not signed in to github.com; run gh auth login", state="not_logged_in"
            )
        return login
    if b"unknown flag" in completed.stderr:
        raise GhError(
            f"this gh is too old to report its account; install gh {GH_MIN_VERSION} or newer",
            state="gh_too_old",
        )
    raise _failure_without_response(completed)


__all__ = [
    "GH_API_MAX_BYTES",
    "GH_API_TIMEOUT_S",
    "GH_MAX_BYTES",
    "GH_MIN_VERSION",
    "GH_TIMEOUT_S",
    "GhError",
    "GhFailureState",
    "GhResponse",
    "GhUnavailableError",
    "gh_account",
    "gh_api",
    "gh_environment",
    "gh_executable",
    "parse_account",
    "parse_included_response",
    "rate_limit_reset",
    "run_gh",
]
