"""Run ``gh`` with fixed arguments, an isolated environment, and hard bounds.

``gh`` owns GitHub authentication; Metabrowser never reads, stores, or logs a token.
Every run gets no stdin, prompts and update checks off, no colour, and no inherited
``GH_DEBUG``, ``GH_HOST``, ``GH_REPO``, ``CLICOLOR_FORCE``, or ``GH_FORCE_TTY``; a
deadline and an output cap; and its own process group, so a timeout or cancellation
kills anything it started. Its stdout is never logged, because it can be private
repository data or, for ``auth status``, the account's scopes.

:func:`gh_api` issues one ``gh api --hostname github.com --include`` request and returns
the status, headers, and body; :func:`gh_active_account` reads the active github.com
account from ``gh auth status``, with its token's source and scopes where gh reports
them, and :func:`gh_account` its login alone, from a conditional ``gh api user`` that
GitHub does not count against the rate limit while the login is the same. Each raises
:class:`GhError` with a typed ``state`` a user can act on.
:func:`gh_version` reads the version; :mod:`.gh_status` combines them into the one
status check that ``metab --doctor``, a route, and the checks before GitHub work read. Nothing here
paginates, caches, or shares a read: callers name every page, as ``gh api --paginate``
and ``--cache`` would hide the page cap, the ETags, and the rate-limit headers. Each
read is owned by the one refresh job of what it reads, so identical reads do not overlap:
in the GitHub plugin's test flows, 3 of 1,523 launches did, all in one test that runs
same-second refreshes at once on purpose (measured 2026-11-11).
:func:`gh_graphql` runs only a read-only query document, checked by its structure. Both
hand every response's rate-limit headers, and every ``rate_limited`` refusal, to
:mod:`.gh_budget`, which decides whether background work may spend the account's budget.

Every run is a span in the event log (:func:`_run`), and a read of GitHub's answer
records its HTTP status and what it cost there, the same number :mod:`.gh_budget`
counts; :mod:`.gh_requests` reports them.
"""

from __future__ import annotations

import asyncio
import functools
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Final, Literal

from metabrowser import event_log, network_cause
from metabrowser.builtin_plugins.github import gh_budget
from metabrowser.git.process import (
    forget_process_group,
    kill_when_spawned,
    start_process_group,
    terminate_git_process,
)

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
# The one path outside a repository that :func:`gh_api` reads: the account of the token
# gh uses, for :func:`gh_account`.
ACCOUNT_PATH: Final = "user"
_API_PATH = re.compile(r"^(?:user|repos/[A-Za-z0-9._/-]+(?:\?[A-Za-z0-9_=&.-]*)?)$")
_ETAG = re.compile(r'^(?:W/)?"[\x21\x23-\x7e]{1,256}"$')
_LOGIN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$")
_STATUS_LINE = re.compile(rb"^HTTP/[0-9.]+ ([0-9]{3})(?: [^\r\n]*)?$")
# The page ``rel="last"`` names: ``<https://api.github.com/...&page=12>; rel="last"``.
_LAST_PAGE = re.compile(r'[?&]page=([1-9][0-9]{0,5})(?:&[^>]*)?>; rel="last"')

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
# "error connecting to api.github.com" (which gh prints only for a name that did not
# resolve), and a gh without ``auth status --json`` answers
# "unknown flag: --json". Only ever matched, never shown: the cause it names
# (metabrowser.network_cause.classify, shared with Git's errors) is what a message says.
# A gh that gives up, or cannot connect, is followed by a probe of the network
# (network_cause.probe), which names the address and the step that failed.
_AUTH_STATE_PROBLEM = re.compile(rb'"state"\s*:\s*"(?:timeout|error)"')
SIGN_IN_COMMAND: Final = f"gh auth login --hostname {GH_HOSTNAME}"
_SIGN_IN_MESSAGE: Final = (
    f"GitHub CLI is not signed in to {GH_HOSTNAME}. Run {SIGN_IN_COMMAND}, then retry."
)


class GhError(Exception):
    """``gh`` could not answer; ``state`` says why. The message never carries its output."""

    def __init__(
        self,
        message: str,
        *,
        state: GhFailureState = "gh_failed",
        reset_at: str | None = None,
        cause: network_cause.NetworkCause | None = None,
    ) -> None:
        super().__init__(message)
        self.state: GhFailureState = state
        self.reset_at: str | None = reset_at
        # What actually happened, in the vocabulary gh and Git share
        # (metabrowser.network_cause); ``state`` is what to do about it.
        self.cause: network_cause.NetworkCause | None = cause


class GhUnavailableError(GhError):
    """No ``gh`` executable on ``PATH``."""

    def __init__(
        self,
        message: str = (
            "Metabrowser could not find GitHub CLI (gh). Install it from https://cli.github.com/, "
            "then run gh auth login --hostname github.com."
        ),
    ) -> None:
        super().__init__(message, state="gh_missing")


# The environment variables gh reads a github.com token from, in its order. gh names
# the one it used as the account's ``tokenSource``.
ENVIRONMENT_TOKENS: Final[tuple[str, ...]] = ("GH_TOKEN", "GITHUB_TOKEN")


class GhTokenRefusedError(GhError):
    """GitHub refused a token gh read from *variable*, one of :data:`ENVIRONMENT_TOKENS`.

    gh names no account for such a token, and refuses ``gh auth login`` while the
    variable is set, so the step is to replace the token or unset the variable.
    """

    def __init__(self, variable: str) -> None:
        self.variable = variable
        self.fix = replace_token_step(variable)
        super().__init__(
            f"GitHub refused the token in {variable}. To sign in again: {self.fix}.",
            state="not_logged_in",
        )


def replace_token_step(variable: str) -> str:
    """The step for a refused token from *variable*: gh will not sign in while it is set."""

    return f"replace the token in {variable}, or unset it and run {SIGN_IN_COMMAND}"


class GhServerError(GhError):
    """GitHub responded with a server error, so the host connection worked.

    The message names the status and not GitHub's own text, which, like every upstream
    message, is never shown; the event log keeps it, redacted (``server_message`` on the
    span that asked).
    """

    def __init__(self, status: int) -> None:
        self.status = status
        super().__init__(
            network_cause.reason("server_error", status=status),
            state="network_error",
            cause="server_error",
        )


class GhCursorError(GhError):
    """A provider cursor expired or is invalid; its bounded scan can restart."""


class GhOutputTooLargeError(GhError):
    """``gh`` wrote more than the output cap; a caller may ask for less."""


@dataclass(frozen=True, slots=True)
class _Completed:
    returncode: int
    stdout: bytes
    stderr: bytes
    # GitHub's answer, read in the gh span when :func:`_run` is asked to read one, and
    # ``None`` when it was not or gh printed none.
    answer: _Answer | None = None


@dataclass(frozen=True, slots=True)
class _Answer:
    """GitHub's answer as ``gh api --include`` printed it, read inside the gh span.

    ``cost`` is what GitHub charged for it, which the span records and :mod:`.gh_budget`
    counts (:func:`_read_answer`). ``payload`` is a GraphQL answer's body, parsed, for an
    answer GitHub did not refuse, and ``json_error`` why that body could not be; both are
    ``None`` for a REST answer, whose callers parse the body they want.
    """

    response: GhResponse
    cost: int
    payload: object = None
    json_error: ValueError | None = None


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

    @property
    def last_page(self) -> int | None:
        """The page number ``rel="last"`` names in the ``Link`` header, or ``None``.

        GitHub sends it on every page but the last, so it counts pages and not items.
        """

        found = _LAST_PAGE.search(self.headers.get("link", ""))
        return int(found.group(1)) if found is not None else None

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
            "GH_STACK_NO_UPDATE_NOTIFIER": "1",
            "GH_SPINNER_DISABLED": "1",
            "NO_COLOR": "1",
            "CLICOLOR": "0",
        }
    )
    return env


async def _read_capped(
    stream: asyncio.StreamReader | None, limit: int, *, kept: list[bytes] | None = None
) -> tuple[bytes, bool]:
    """Drain *stream*, keeping at most *limit* bytes, into *kept* when given.

    A caller that passes *kept* still has what was read when the read is cancelled, as a
    deadline cancels it: the event log says how far gh got.
    """
    if stream is None:
        return b"", False
    chunks: list[bytes] = [] if kept is None else kept
    total = 0
    overflowed = False
    while chunk := await stream.read(_READ_CHUNK_BYTES):
        total += len(chunk)
        if total > limit:
            overflowed = True
            continue
        chunks.append(chunk)
    return b"".join(chunks), overflowed


async def _run(
    args: Sequence[str],
    *,
    timeout_s: float,
    max_bytes: int,
    cwd: Path | None = None,
    answer: Literal["rest", "graphql"] | None = None,
) -> _Completed:
    """Run ``gh`` once. Raises only for a missing gh, a deadline, or too much output.

    A cancellation while gh is still being spawned waits for the spawn and kills the
    child, so no gh process outlives the call untracked. With *answer*, the ``gh api
    --include`` output is read as a REST or a GraphQL answer inside the span, which then
    records its status and cost, and the result carries it.
    """

    exe = gh_executable()
    if exe is None:
        raise GhUnavailableError
    # Every gh process is a span in the event log (metabrowser.event_log): its command
    # without field values or headers, its deadline, the budget it is charged to
    # (gh_budget.current_budget), a fingerprint that is the same for two calls that ask
    # GitHub the same thing (fingerprint), how it ended, and the cause its error text
    # names; for a read of GitHub's answer, its HTTP status and what it cost. Its time is
    # gh's: the clock stops when gh exits, before its output is read. The request report
    # (gh_requests) reads these.
    unreachable = False
    try:
        with event_log.span(
            "subprocess",
            f"gh {next((arg for arg in args if not arg.startswith('-')), '')}".rstrip(),
            attrs={
                "args": loggable_args(args),
                "timeout_s": timeout_s,
                "host": network_cause.GITHUB_API_HOST,
                "budget": gh_budget.current_budget(),
                "fingerprint": fingerprint(args),
            },
        ) as span:
            completed = await _run_in(exe, args, timeout_s=timeout_s, max_bytes=max_bytes, cwd=cwd)
            span.stop()
            span.set(exit=completed.returncode, stdout_bytes=len(completed.stdout))
            if answer is not None:
                read = _read_answer(completed.stdout, graphql=answer == "graphql")
                if read is not None:
                    span.set(http_status=read.response.status, cost=read.cost)
                    completed = _Completed(
                        completed.returncode, completed.stdout, completed.stderr, read
                    )
            if completed.returncode != 0:
                diagnostic = completed.stderr.decode("utf-8", errors="replace")
                cause = network_cause.classify(diagnostic)
                if cause is not None:
                    span.set(cause=cause)
                    unreachable = cause in network_cause.TRANSPORT_CAUSES
                address = network_cause.failed_address(diagnostic)
                if address is not None:
                    span.set(address=address)
                span.note_failure("exit", event_log.stderr_tail(completed.stderr))
    except GhError as exc:
        if exc.cause not in {"no_answer", "stalled"}:
            raise
        raise await _explained_silence(exc, timeout_s=timeout_s) from None
    if unreachable:
        # gh could not connect: the probe names the address and the step that failed,
        # for the message the caller builds from this run (_unreachable).
        await network_cause.probe()
    return completed


async def _explained_silence(silence: GhError, *, timeout_s: float) -> GhError:
    """*silence*, a gh that gave up with no answer, with what a probe found.

    When the network could not reach GitHub either, that is the message: "GitHub could
    not be reached because the connection to api.github.com at 20.172.24.160 timed out
    after 2 s; gh gave up after 15 s". When it could, the message says only what this
    lookup found, since DNS answers vary and gh may have dialed another address: "gh did
    not answer within 15 s; a fresh lookup of api.github.com gave 140.82.112.6, which
    accepted a connection in 38 ms; DNS answers vary, so gh may have used another
    address", with the addresses that failed lately.
    """

    found = await network_cause.probe()
    if found is None:
        failure = silence
    elif found.reachable:
        lately = event_log.recent_failed_addresses(
            causes=network_cause.TRANSPORT_CAUSES, host=network_cause.is_github_host
        )
        failure = GhError(
            f"{silence}; {found.headline(failed_lately=lately)}",
            state="network_error",
            cause=silence.cause,
        )
    else:
        failure = GhError(
            f"{found.headline()}; gh gave up after {timeout_s:g} s",
            state="network_error",
            cause=found.cause,
        )
    return _noted(_counted(failure))


def _counted(failure: GhError) -> GhError:
    """*failure* with how many gh and git calls failed to reach GitHub in the last hour,
    when this is not the first: a pattern, not a blip. Only calls to GitHub's hosts
    count: a fetch from another origin that failed says nothing about GitHub."""

    count = event_log.recent_failures(
        causes=network_cause.TRANSPORT_CAUSES, host=network_cause.is_github_host
    )
    if count < 2:
        return failure
    renamed = GhError(
        f"{failure} ({count} calls could not reach GitHub in the last hour)",
        state=failure.state,
        reset_at=failure.reset_at,
        cause=failure.cause,
    )
    return renamed


def _noted(failure: GhError) -> GhError:
    """*failure*, with its cause on the span that asked for it: the job or request."""

    if failure.cause is not None:
        event_log.current().set(cause=failure.cause)
    return failure


# The causes whose gh text says little: the probe's finding, when it failed, says more.
_VAGUE_CAUSES: Final[frozenset[network_cause.NetworkCause]] = frozenset(
    {"connect_failed", "no_answer", "stalled"}
)


def _unreachable(cause: network_cause.NetworkCause, diagnostic: str = "") -> GhError:
    """A gh that could not reach GitHub, in the words of the latest probe if it failed
    and gh's own text says no more than it, or the same.

    Otherwise gh's own error names the cause and, for a connection, the address: gh
    2.98.0 prints ``dial tcp 172.182.252.137:443: i/o timeout``. A probe from up to
    :data:`~metabrowser.network_cause.PROBE_INTERVAL_S` ago does not override a cause gh
    reported now, such as a TLS failure.
    """

    found = network_cause.recent_probe()
    if (
        found is not None
        and not found.reachable
        and (cause in _VAGUE_CAUSES or found.cause == cause)
    ):
        return _noted(_counted(GhError(found.headline(), state="network_error", cause=found.cause)))
    address = network_cause.failed_address(diagnostic) if diagnostic else None
    message = network_cause.reason(cause, address=address)
    return _noted(_counted(GhError(message, state="network_error", cause=cause)))


# Options whose value is data rather than the command: a GraphQL query or field, a header,
# a jq program. The event log keeps the option and the field's name, never the value.
_FIELD_OPTIONS: Final = frozenset({"-f", "-F", "--field", "--raw-field"})
_HEADER_OPTIONS: Final = frozenset({"-H", "--header"})
_PROGRAM_OPTIONS: Final = frozenset({"-q", "--jq", "-t", "--template", "--input"})


def loggable_args(args: Sequence[str]) -> list[str]:
    """*args* as the event log records them: no field values, header values, or programs.

    ``-f query=…`` keeps the field's name; ``-H 'If-None-Match: …'`` the header's. What
    remains is passed through :func:`metabrowser.event_log.redact`.
    """

    out: list[str] = []
    rest = iter(args)
    for arg in rest:
        if arg in _FIELD_OPTIONS:
            out += [arg, f"{next(rest, '').partition('=')[0][:60]}=…"]
        elif arg in _HEADER_OPTIONS:
            out += [arg, f"{next(rest, '').partition(':')[0][:60]}: …"]
        elif arg in _PROGRAM_OPTIONS:
            next(rest, None)
            out += [arg, "…"]
        else:
            out.append(event_log.redact(arg, limit=200))
        if len(out) >= event_log.MAX_LOGGED_ARGS:
            out.append("…")
            break
    return out


# The hex digits of a request's fingerprint the event log keeps: 64 bits, so two different
# requests share one with a chance of about one in 10^19 a pair.
_FINGERPRINT_CHARS: Final = 16
# The header a conditional read sends its ETag in.
_CONDITIONAL_HEADER: Final = "if-none-match"


def fingerprint(args: Sequence[str]) -> str:
    """A digest of *args* that is the same for two gh calls that ask GitHub the same thing.

    The ETag header a conditional read sends is left out, since it says what the reader
    holds rather than what it asks: a probe asked again with the ETag its last answer gave,
    or read again without one, is the same request. Everything else counts, the values
    :func:`loggable_args` drops included, a GraphQL query's variables among them: those are
    what tell one pull request's read from another's. The log keeps the digest, never a
    value it was made from.
    """

    kept: list[str] = []
    rest = iter(args)
    for arg in rest:
        if arg in _HEADER_OPTIONS:
            header = next(rest, "")
            if header.partition(":")[0].strip().lower() != _CONDITIONAL_HEADER:
                kept += [arg, header]
        else:
            kept.append(arg)
    text = "\0".join(kept).encode("utf-8", errors="backslashreplace")
    return hashlib.sha256(text).hexdigest()[:_FINGERPRINT_CHARS]


async def _run_in(
    exe: str, args: Sequence[str], *, timeout_s: float, max_bytes: int, cwd: Path | None
) -> _Completed:
    env = gh_environment()

    own_group = os.name == "posix"

    async def spawn() -> asyncio.subprocess.Process:
        return await asyncio.create_subprocess_exec(
            exe,
            *args,
            stdin=subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            cwd=cwd,
            start_new_session=own_group,
        )

    # A Ctrl-C, hangup, or closed stdin that cannot unwind kills Git's groups; gh's too,
    # including one whose spawn is under way when the stop begins.
    spawning = asyncio.create_task(
        start_process_group(spawn, program=exe, cwd=cwd, env=env) if own_group else spawn()
    )
    try:
        proc = await asyncio.shield(spawning)
    except asyncio.CancelledError:
        await kill_when_spawned(spawning)
        raise
    except OSError as exc:
        # The system's reason goes to the gh span, and the error keeps it as its cause: the
        # message is what an answer's reader field may show.
        event_log.current().set(spawn_error=exc.strerror or type(exc).__name__)
        raise GhError("could not run gh") from exc
    try:
        return await _finish(proc, args, timeout_s=timeout_s, max_bytes=max_bytes)
    finally:
        forget_process_group(proc)


async def _finish(
    proc: asyncio.subprocess.Process, args: Sequence[str], *, timeout_s: float, max_bytes: int
) -> _Completed:
    printed: list[bytes] = []
    complained: list[bytes] = []
    stdout_task = asyncio.ensure_future(_read_capped(proc.stdout, max_bytes, kept=printed))
    stderr_task = asyncio.ensure_future(
        _read_capped(proc.stderr, _STDERR_MAX_BYTES, kept=complained)
    )
    try:
        (stdout, overflowed), (stderr, _), returncode = await asyncio.wait_for(
            asyncio.gather(stdout_task, stderr_task, proc.wait()), timeout=timeout_s
        )
    except TimeoutError:
        stdout_task.cancel()
        stderr_task.cancel()
        await terminate_git_process(proc)
        # Where it stalled, as far as its output says: before a byte of an answer, or
        # partway through one.
        received = sum(len(chunk) for chunk in printed)
        cause: network_cause.NetworkCause = "no_answer" if received == 0 else "stalled"
        event_log.current().end(
            "timeout",
            stdout_bytes=received,
            stderr_tail=event_log.stderr_tail(b"".join(complained)),
            stalled="before any answer" if received == 0 else "partway through its answer",
            cause=cause,
        )
        message = (
            f"gh did not answer within {timeout_s:g} s"
            if received == 0
            else f"gh stopped partway through GitHub's answer and gave up after {timeout_s:g} s"
        )
        raise GhError(message, state="network_error", cause=cause) from None
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


async def gh_stack_available() -> bool:
    """Probe the optional extension without resolving or writing local stack state.

    The official version command only prints its version. In contrast, even
    ``view --json`` saves local tracking state and must never run here.
    """
    result = await _run(["stack", "--version"], timeout_s=5.0, max_bytes=4096, cwd=Path("/"))
    return (
        result.returncode == 0
        and re.fullmatch(rb"gh stack version [^\r\n]{1,80}\r?\n?", result.stdout) is not None
    )


async def run_gh(
    args: Sequence[str], *, timeout_s: float = GH_TIMEOUT_S, max_bytes: int = GH_MAX_BYTES
) -> bytes:
    """Run ``gh`` with *args* and return its stdout, or raise :class:`GhError`."""

    completed = await _run(args, timeout_s=timeout_s, max_bytes=max_bytes)
    if completed.returncode != 0:
        raise GhError(f"gh exited {completed.returncode}")
    return completed.stdout


def _diagnosed_failure(diagnostic: str) -> GhError | None:
    """Classify recognizable diagnostics without returning gh's text.

    The cause comes from the classifier gh and Git share (:mod:`metabrowser.network_cause`).
    Only a server error, a failure to reach GitHub, and a refused sign-in are typed here;
    the others keep the generic failure their callers expect.
    """

    cause = network_cause.classify(diagnostic)
    if cause == "server_error":
        return _noted(GhServerError(network_cause.http_status(diagnostic) or 500))
    if cause in network_cause.TRANSPORT_CAUSES:
        return _unreachable(cause, diagnostic)
    if cause in {"auth_refused", "not_signed_in"}:
        return _noted(GhError(_SIGN_IN_MESSAGE, state="not_logged_in", cause=cause))
    return None


def _failure_without_response(completed: _Completed) -> GhError:
    """The typed state of a ``gh`` run that printed no HTTP response."""

    if completed.returncode == _GH_EXIT_AUTH:
        return _noted(GhError(_SIGN_IN_MESSAGE, state="not_logged_in", cause="not_signed_in"))
    diagnostic = completed.stderr.decode("utf-8", errors="replace")
    return _diagnosed_failure(diagnostic) or GhError(
        f"gh exited {completed.returncode} without an HTTP response"
    )


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
    resets at ``x-ratelimit-reset``, in epoch seconds. A time no clock can hold is header
    text saying there is a limit and not when, so it is ``"unknown"``.
    """

    if response.status not in {403, 429}:
        return None
    retry_after = response.headers.get("retry-after", "")
    try:
        if retry_after.isdigit():
            return (now + timedelta(seconds=int(retry_after))).strftime("%Y-%m-%dT%H:%M:%SZ")
        if response.headers.get("x-ratelimit-remaining") == "0":
            reset = response.headers.get("x-ratelimit-reset", "")
            return _epoch_text(int(reset)) if reset.isdigit() else "unknown"
    except (OverflowError, ValueError, OSError):
        return "unknown"
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
    return isinstance(message, str) and network_cause.mentions_rate_limit(message)


def _accepted(status: int) -> bool:
    """Whether GitHub answered *status* without refusing: 2xx, or ``304`` unchanged."""

    return 200 <= status < 300 or status == 304


def _read_answer(stdout: bytes, *, graphql: bool) -> _Answer | None:
    """GitHub's answer in *stdout* and what it cost, or ``None`` when gh printed none.

    GitHub counts every REST answer but a ``304`` against the rate limit, refusals
    included. A GraphQL query costs what its answer reports (:func:`_graphql_cost`), and
    one when GitHub refused it or its body cannot be read. Both are one rule here, which
    the span records and :mod:`.gh_budget` counts.
    """

    response = parse_included_response(stdout)
    if response is None:
        return None
    if not graphql:
        return _Answer(response, 0 if response.status == 304 else 1)
    payload: object = None
    json_error: ValueError | None = None
    if _accepted(response.status):
        try:
            payload = json.loads(response.body)
        except ValueError as exc:
            json_error = exc
    return _Answer(response, _graphql_cost(payload), payload, json_error)


def _refusal(response: GhResponse, *, now: datetime) -> GhError | None:
    """The typed failure an HTTP status means, or ``None`` for 2xx and 304."""

    if _accepted(response.status):
        return None
    # The cause goes on the span that asked (the job or request), so the event log says
    # which status GitHub answered with.
    event_log.current().set(http_status=response.status)
    reset = rate_limit_reset(response, now=now)
    if reset is not None:
        when = "; try again in a few minutes" if reset == "unknown" else f" until {reset}"
        return _noted(
            GhError(
                f"GitHub's API rate limit is exhausted{when}",
                state="rate_limited",
                reset_at=None if reset == "unknown" else reset,
                cause="rate_limited",
            )
        )
    if response.status == 401:
        return _noted(
            GhError(
                "gh's github.com credentials were refused; run gh auth login",
                state="not_logged_in",
                cause="auth_refused",
            )
        )
    if response.status in {403, 404, 410}:
        return _noted(
            GhError(
                "GitHub has no such pull request, or it is private and the gh account cannot "
                "read it",
                state="not_found_or_private",
                cause="forbidden" if response.status == 403 else "not_found",
            )
        )
    if response.status >= 500:
        detail = _server_message(response.body)
        if detail:
            event_log.current().set(server_message=event_log.redact(detail, limit=200))
        return _noted(GhServerError(response.status))
    return GhError(f"GitHub answered HTTP {response.status}")


def _server_message(body: bytes) -> str | None:
    """GitHub's own ``message`` in an error answer's JSON body, if it has one.

    GitHub's 5xx answers are often an HTML page rather than JSON; that has no message.
    It goes to the event log only, redacted: like every upstream message, it is not
    shown.
    """

    try:
        payload = json.loads(body[:_STDERR_MAX_BYTES])
    except ValueError:
        return None
    message = payload.get("message") if isinstance(payload, dict) else None
    return message.strip() or None if isinstance(message, str) else None


async def gh_api(path: str, *, etag: str | None = None, now: datetime | None = None) -> GhResponse:
    """``GET`` one github.com API *path*; a ``304`` is returned, other failures raise.

    *path* is a repository's, ``repos/…``, or :data:`ACCOUNT_PATH`, and nothing else. It
    is built by the caller from validated parts and is checked again here, so no user text
    reaches gh as an option. *etag*, when given, is sent as ``If-None-Match``.
    """

    if not _API_PATH.match(path) or any(
        part in {"", ".", ".."} for part in path.split("?", 1)[0].split("/")
    ):
        raise ValueError("not an API path Metabrowser reads")
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
    completed = await _run(
        args, timeout_s=GH_API_TIMEOUT_S, max_bytes=GH_API_MAX_BYTES, answer="rest"
    )
    read = completed.answer
    if read is None:
        raise _failure_without_response(completed)
    response = read.response
    moment = now or datetime.now(UTC)
    gh_budget.observe(response.headers, resource="core")
    gh_budget.spent(read.cost, now=moment)
    refused = _refusal(response, now=moment)
    if refused is not None:
        if refused.state == "rate_limited":
            gh_budget.hold(refused.reset_at, now=moment)
        raise refused
    return response


_GH_GRAPHQL_FIELDS: Final = frozenset({"query", "operationName"})
# GraphQL's ignored tokens (whitespace, commas, a byte-order mark, and comments), then
# the tokens a document is made of: block strings, strings, names, punctuators, and
# numbers. Anything else does not lex, and the document is refused.
_GRAPHQL_IGNORED: Final = re.compile(r"(?:[\s,﻿]|#[^\n\r]*)+")
_GRAPHQL_TOKEN: Final = re.compile(
    r'"""(?:\\"""|[^"]|"(?!""))*"""'
    r'|"(?:\\.|[^"\\\n\r])*"'
    r"|[A-Za-z_][A-Za-z0-9_]*"
    r"|\.\.\.|[!$&():=@\[\]{}|]"
    r"|-?[0-9][0-9A-Za-z.+-]*"
)


# Every document the plugin sends is a module constant or one of the core batch sizes, about
# 40 in all, and lexing one on the event loop took 67 to 131 µs, and 1.4 ms for the
# 25-core batch (measured 2026-11-11), so each answer is kept.
@functools.lru_cache(maxsize=64)
def _is_one_read_only_query(document: str) -> bool:
    """Whether *document* defines exactly one operation, a query, besides fragments.

    It reads the document's top-level definitions, not its first word, so a second
    ``mutation`` or ``subscription`` after a query is refused, as is anything that is not
    an executable definition or does not lex. A refused document is never sent.
    """

    operations: list[str] = []
    depth = 0
    starting = True
    position = 0
    while position < len(document):
        ignored = _GRAPHQL_IGNORED.match(document, position)
        if ignored is not None:
            position = ignored.end()
            continue
        match = _GRAPHQL_TOKEN.match(document, position)
        if match is None:
            return False
        position = match.end()
        token = match.group()
        if depth == 0 and starting:
            if token == "{":
                operations.append("query")
            elif token in {"query", "mutation", "subscription"}:
                operations.append(token)
            elif token != "fragment":
                return False
            starting = False
        if token in {"{", "("}:
            depth += 1
        elif token in {"}", ")"}:
            depth -= 1
            if depth < 0:
                return False
            if depth == 0 and token == "}":
                starting = True
    return depth == 0 and starting and operations == ["query"]


# The most one query is taken to have cost, whatever its answer says: GitHub's own limit
# on a query is 500,000 nodes, 5,000 points at a hundred nodes a point.
_MAX_GRAPHQL_COST: Final = 5000


def _graphql_cost(payload: object) -> int:
    """What GitHub says the query cost, ``rateLimit { cost }``, or one when it does not say.

    *payload* is the answer already parsed, ``None`` for one that could not be: a catalog
    page is the largest body the plugin reads, so it is parsed once (review A10 of #737).
    Each of the plugin's queries asks for it, and each reported 1 on 2026-11-22: a catalog
    page by either order, core batches of 8 and of 25, a timeline page, and one core
    (cli/cli and jlevy/metabrowser, gh 2.98.0).
    """

    data = payload.get("data") if isinstance(payload, dict) else None
    limit = data.get("rateLimit") if isinstance(data, dict) else None
    cost = limit.get("cost") if isinstance(limit, dict) else None
    return cost if type(cost) is int and 0 <= cost <= _MAX_GRAPHQL_COST else 1


async def gh_graphql(
    query: str,
    variables: Mapping[str, str | int | bool | None],
    *,
    now: datetime | None = None,
    max_bytes: int = GH_API_MAX_BYTES,
) -> dict[str, Any]:
    """Execute an internal fixed read-only query with separately encoded variables.

    GraphQL can return HTTP 200 with errors and partial data. No caller receives that
    partial data, especially a cursor it could mistakenly persist as completed work.
    """
    if not _is_one_read_only_query(query):
        raise ValueError("only a fixed GraphQL query is supported")
    args = ["api", "graphql", "--hostname", GH_HOSTNAME, "--method", "POST", "--include"]
    args.extend(("-f", f"query={query}"))
    for name, value in variables.items():
        # gh reads ``query`` and ``operationName`` as the request itself, not as variables.
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) or name in _GH_GRAPHQL_FIELDS:
            raise ValueError("invalid GraphQL variable name")
        if value is None:
            continue
        if isinstance(value, str):
            args.extend(("-f", f"{name}={value}"))
        else:
            args.extend(("-F", f"{name}={json.dumps(value)}"))
    completed = await _run(args, timeout_s=GH_API_TIMEOUT_S, max_bytes=max_bytes, answer="graphql")
    read = completed.answer
    if read is None:
        raise _failure_without_response(completed)
    response = read.response
    moment = now or datetime.now(UTC)
    gh_budget.observe(response.headers, resource="graphql")
    # Counted before anything below can refuse the answer: GitHub charged for it.
    gh_budget.spent(read.cost, now=moment)
    refused = _refusal(response, now=moment)
    if refused is not None:
        if refused.state == "rate_limited":
            gh_budget.hold(refused.reset_at, now=moment)
        raise refused
    if read.json_error is not None:
        raise GhError("GitHub answered with something other than JSON") from read.json_error
    payload = read.payload
    if not isinstance(payload, dict):
        raise GhError("GitHub answered with an unreadable GraphQL response")
    errors = payload.get("errors")
    if errors:
        failures = errors if isinstance(errors, list) else []
        limited = any(
            isinstance(error, dict)
            and (
                error.get("type") == "RATE_LIMITED"
                or "rate limit" in str(error.get("message", "")).lower()
            )
            for error in failures
        )
        if limited:
            reset = rate_limit_reset(GhResponse(429, response.headers, response.body), now=moment)
            reset_at = None if reset == "unknown" else reset
            gh_budget.hold(reset_at, now=moment)
            raise GhError(
                "GitHub's API rate limit is exhausted", state="rate_limited", reset_at=reset_at
            )
        if any(
            isinstance(error, dict)
            and (
                error.get("type") == "INVALID_CURSOR_ARGUMENTS"
                or (
                    "cursor" in str(error.get("message", "")).lower()
                    and any(
                        word in str(error.get("message", "")).lower()
                        for word in ("invalid", "exist", "expired")
                    )
                )
            )
            for error in failures
        ):
            raise GhCursorError("GitHub could not resume the metadata cursor")
        if any(
            isinstance(error, dict) and error.get("type") in ("NOT_FOUND", "FORBIDDEN")
            for error in failures
        ):
            raise GhError("GitHub has no readable repository here", state="not_found_or_private")
        raise GhError("GitHub could not complete the metadata query")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise GhError("GitHub answered without query data")
    return data


@dataclass(frozen=True, slots=True)
class GhAccount:
    """The active github.com account ``gh auth status --json hosts`` names.

    ``token_source`` is where gh found the token: ``keyring``, ``oauth_token`` for its
    own configuration file, or an environment variable's name such as ``GH_TOKEN``.
    ``scopes`` are the token's OAuth scopes as gh reports them, sorted, or ``None`` where
    gh reports none, as for a fine-grained or GitHub App token. ``problem`` is gh's own
    verdict when it could not confirm the token, typed: offline is ``network_error``,
    which is not being signed out, and a refused token is ``not_logged_in``. The token
    and gh's own text are never read into it.
    """

    login: str
    token_source: str | None = None
    scopes: tuple[str, ...] | None = None
    problem: GhError | None = None


# One OAuth scope as GitHub names them, such as ``repo``, ``read:org``, or
# ``admin:repo_hook``; anything else in the list is left out. A classic token holds at
# most the two dozen scopes GitHub defines, so the cap only bounds a malformed answer.
_SCOPE = re.compile(r"^[a-z][a-z0-9_]{0,39}(?::[a-z][a-z0-9_]{0,39})?$")
_MAX_SCOPES: Final = 64
_TOKEN_SOURCE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
_TOO_OLD_MESSAGE: Final = (
    "This GitHub CLI cannot report the active account. Update gh from "
    "https://cli.github.com/, then run gh auth status --hostname github.com."
)


def _scopes(value: object) -> tuple[str, ...] | None:
    """The scopes gh names, as one comma-separated string or a list, or ``None``."""

    if isinstance(value, str):
        items: list[object] = list(value.split(","))
    elif isinstance(value, list):
        items = list(value)  # pyright: ignore[reportUnknownArgumentType]
    else:
        return None
    named = {item.strip() for item in items if isinstance(item, str)}
    scopes = sorted(scope for scope in named if _SCOPE.match(scope))[:_MAX_SCOPES]
    return tuple(scopes) or None


def _token_problem(entry: Mapping[str, object]) -> GhError | None:
    """gh's verdict on the active token, typed, or ``None`` when it confirmed it."""

    state = entry.get("state")
    if state in {None, "success"}:
        return None
    if state == "timeout":
        return _unreachable("no_answer")
    diagnostic = entry.get("error")
    if isinstance(diagnostic, str) and (failure := _diagnosed_failure(diagnostic)):
        return failure
    return GhError("gh could not confirm the account's token")


def parse_active_account(stdout: bytes) -> GhAccount | None:
    """The active github.com account from ``gh auth status --json hosts``, or ``None``.

    A non-success ``state`` still names the login: gh reports an error state when it is
    offline, which is not being signed out, so the login is kept and the state is the
    account's ``problem``.
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
            source = entry.get("tokenSource")
            return GhAccount(
                login=login,
                token_source=(
                    source if isinstance(source, str) and _TOKEN_SOURCE.match(source) else None
                ),
                scopes=_scopes(entry.get("scopes")),
                problem=_token_problem(entry),
            )
        # An environment token needs GitHub to resolve its login. A saved
        # account with a valid login remains available through a network failure.
        if login == "":
            state = entry.get("state")
            if state == "timeout":
                raise _unreachable("no_answer")
            diagnostic = entry.get("error")
            if (
                state == "error"
                and isinstance(diagnostic, str)
                and (failure := _diagnosed_failure(diagnostic))
            ):
                # gh 2.98.0 answers a refused GH_TOKEN with an empty login, its
                # tokenSource, and the 401 (checked 2026-11-18).
                source = entry.get("tokenSource")
                if failure.state == "not_logged_in" and source in ENVIRONMENT_TOKENS:
                    raise GhTokenRefusedError(str(source)) from failure
                raise failure
        raise GhError("gh auth status named an account that is not a GitHub login")
    return None


async def gh_active_account(*, timeout_s: float = GH_TIMEOUT_S) -> GhAccount:
    """The active github.com account, from ``gh auth status --active --json hosts``.

    Raises :class:`GhError` when there is none or gh cannot say; an account gh could not
    confirm is returned with its ``problem``.
    """

    completed = await _run(
        ["auth", "status", "--active", "--hostname", GH_HOSTNAME, "--json", "hosts"],
        timeout_s=timeout_s,
        max_bytes=_ACCOUNT_MAX_BYTES,
    )
    if completed.stdout.strip().startswith(b"{"):
        # gh checks the token with GitHub, and reports a check that timed out, or could
        # not connect, in its JSON rather than its exit: probe first, so the account's
        # problem names the step that failed (_unreachable).
        if _AUTH_STATE_PROBLEM.search(completed.stdout) and (
            b'"timeout"' in completed.stdout
            or network_cause.classify(completed.stdout.decode("utf-8", errors="replace"))
            in network_cause.TRANSPORT_CAUSES
        ):
            await network_cause.probe()
        account = parse_active_account(completed.stdout)
        if account is None:
            raise GhError(_SIGN_IN_MESSAGE, state="not_logged_in")
        gh_budget.note_account(account.login)
        return account
    if b"unknown flag" in completed.stderr:
        raise GhError(_TOO_OLD_MESSAGE, state="gh_too_old")
    raise _failure_without_response(completed)


@dataclass(frozen=True, slots=True)
class _KnownLogin:
    """The login GitHub last named for a host's token, and that answer's ETag."""

    etag: str
    login: str


# By host, though github.com is the only one read: this process's last ``200`` from
# ``gh api user``. A switch to another account sends its token with the old ETag. That
# ETag names another account's body, so GitHub should answer ``200`` with the new login;
# this follows from what an ETag is and was not measured, the machine that measured the
# ``304`` having one account.
_KNOWN_LOGINS: dict[str, _KnownLogin] = {}


def forget_account() -> None:
    """Forget the login GitHub last named, as a new process knows none; for tests."""

    _KNOWN_LOGINS.clear()


async def gh_account() -> str:
    """The login of the github.com account gh is signed in to, from ``gh api user``.

    The request carries the ETag of this process's last answer, and a ``304`` means the
    same login. GitHub does not count a ``304`` against the rate limit, where
    ``gh auth status`` spent one ``core`` call each time: on 2026-11-22 with gh 2.98.0 a
    conditional ``gh api user`` answered ``304`` in 4 of 4 trials and moved the account's
    ``used`` by 0 in 3 of them, the fourth by 1 with another client spending beside it,
    and ``gh auth status`` moved it by 1 in 3 of 3
    (docs/project/specs/active/plan-2026-11-22-pull-request-update-cadence.md). Every
    job's account check is this one; :func:`gh_active_account` is the status check's,
    since only ``gh auth status`` reports the token's source and scopes.

    Either answer names the account to :mod:`.gh_budget`. Two failures ask
    ``gh auth status`` instead, so each ends as it did before this check was conditional.
    When gh or GitHub says no account is signed in, it says why: a refused token in an
    environment variable, or the sign-in command. When GitHub cannot be reached, it
    names the account gh has saved, which needs no network, so a switch of account is
    still seen offline; the read that follows then fails for the network itself.
    """

    known = _KNOWN_LOGINS.get(GH_HOSTNAME)
    try:
        response = await gh_api(ACCOUNT_PATH, etag=known.etag if known else None)
    except GhError as exc:
        if exc.state == "not_found_or_private":
            raise GhError("GitHub would not name the account gh is signed in to") from exc
        if exc.state not in {"not_logged_in", "network_error"}:
            raise
        account = await gh_active_account()
        if exc.state == "network_error":
            return account.login
        if account.problem is not None:
            raise account.problem from exc
        raise
    if response.status == 304:
        if known is None:
            raise GhError("GitHub answered 304 to a request that was not conditional")
        login = known.login
    else:
        payload = response.json()
        named: object = payload.get("login") if isinstance(payload, dict) else None  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        if not isinstance(named, str) or not _LOGIN.match(named):
            raise GhError("GitHub named an account that is not a GitHub login")
        login = named
        if response.etag is not None:
            _KNOWN_LOGINS[GH_HOSTNAME] = _KnownLogin(response.etag, login)
        else:
            _KNOWN_LOGINS.pop(GH_HOSTNAME, None)
    gh_budget.note_account(login)
    return login


# ``gh --version`` prints ``gh version 2.98.0 (2026-08-20)`` and then a release link.
_VERSION_LINE = re.compile(rb"^gh version ([0-9][0-9A-Za-z.+-]{0,31})(?: |\r?$)")
_VERSION_MAX_BYTES: Final = 4096


async def gh_version(*, timeout_s: float) -> str | None:
    """The version ``gh --version`` names, or ``None`` when it names none.

    Raises :class:`GhError` only for a missing gh, a deadline, or too much output.
    """

    completed = await _run(
        ["--version"], timeout_s=timeout_s, max_bytes=_VERSION_MAX_BYTES, cwd=Path("/")
    )
    if completed.returncode != 0:
        return None
    match = _VERSION_LINE.match(completed.stdout.split(b"\n", 1)[0])
    return match.group(1).decode("ascii") if match is not None else None


__all__ = [
    "ACCOUNT_PATH",
    "ENVIRONMENT_TOKENS",
    "GH_API_MAX_BYTES",
    "GH_API_TIMEOUT_S",
    "GH_MAX_BYTES",
    "GH_TIMEOUT_S",
    "SIGN_IN_COMMAND",
    "GhAccount",
    "GhCursorError",
    "GhError",
    "GhFailureState",
    "GhResponse",
    "GhServerError",
    "GhTokenRefusedError",
    "GhUnavailableError",
    "fingerprint",
    "forget_account",
    "gh_account",
    "gh_active_account",
    "gh_api",
    "gh_graphql",
    "gh_environment",
    "gh_executable",
    "gh_version",
    "loggable_args",
    "parse_active_account",
    "parse_included_response",
    "rate_limit_reset",
    "replace_token_step",
    "run_gh",
]
