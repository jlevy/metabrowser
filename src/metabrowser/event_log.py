"""The structured event log: what the server did and how long it took, one JSON line each.

A served process writes every HTTP request, each background job wrapped in :func:`job`,
and every ``git`` and ``gh`` process it runs to completion to a JSON Lines file in the
user's state directory (:func:`log_directory`), with the time each took and how it
ended. A streaming ``git`` session (``spawn_git_process``), whose streams its caller
reads, is not a span of its own; the request that reads it is. The stderr log's
slow-request warning covers only requests; the work a page waits on after its request
has returned, such as a pull request's refresh or a comparison's listing, is recorded
only here. The specification is
``docs/project/specs/active/plan-2026-11-19-structured-event-log.md``, and
``docs/realtime-debugging.md`` says how to read it.

**Spans.** Each unit of work is a span with an integer ``span`` ID, unique within its
process, and the ``parent`` span that was current where it started: a job started by a
request names the request, and a ``gh`` process the job ran names the job. The current
span lives in a context variable, so ``asyncio.create_task`` and ``asyncio.to_thread``
carry it into the work they start.

**Records.** A span writes an ``end`` record when it finishes, carrying its duration,
measured on the monotonic clock, and its ``outcome``. A job also writes a ``start``
record, because what started it and when is the fact that matters when it never ends;
a request or process does not, which keeps quick work to one line. Any span still open
:data:`OPEN_AFTER_MS` after it began writes an ``open`` record, and another each time its
age doubles, so work that never finishes is on disk within seconds of being late, and a
hung job costs a handful of lines rather than one per second. At shutdown each span
still open ends ``abandoned``. The record's fields are documented on :func:`record`.

**Cost.** With no log open, a span is one global read and returns a shared no-op span.
With one open, an ``end`` record is one ``json.dumps`` and one ``os.write`` to a file
opened ``O_APPEND``. Measured 2026-11-19 on one macOS machine at load average 8, Python
3.14.7, by timing the request middleware around an application that answers at once,
20,000 requests in each of seven rounds: 5.3 µs a request without a log and 28.5 µs
with one, so the log adds about 23 µs to a request: under 0.3% of the median request
(8.3 ms) of the pull request page measured at :data:`MAX_FILE_BYTES`, and under a tenth
of its quickest (0.3 ms).

**Bounds.** A file rolls to a new segment past :data:`MAX_FILE_BYTES`, and every roll and
every open deletes the oldest files in the directory until the rest fit in
:data:`MAX_TOTAL_BYTES`, so several servers sharing the directory share one bound; the
segment each running server writes is never deleted, so each adds at most one segment
to it (:func:`prune`). A line is at most :data:`MAX_LINE_BYTES`.

**Failures.** Logging never fails the work it records: a record that cannot be encoded is
dropped, text that cannot be encoded is escaped, and a write that fails or is short
pauses the log, which tries a fresh segment after :data:`RETRY_FIRST_S`, doubling to
:data:`RETRY_MAX_S`. A segment deleted while open is replaced within a watch interval.

**Privacy.** The log is the user's own, owner-only (``0700`` directory, ``0600`` files,
through :mod:`metabrowser.home`), and holds request paths and the folders they name.
It never holds a token: command lines keep only the subcommand and its operands, the
values of ``gh`` fields and headers are dropped, and every text from a process is passed
through :func:`redact`.
"""

from __future__ import annotations

import asyncio
import collections
import contextlib
import itertools
import json
import logging
import os
import re
import threading
import time
import urllib.parse
from collections.abc import Awaitable, Callable, Coroutine, Generator, Iterable, Mapping
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final, Literal

from metabrowser.settings import SLOW_OPERATION_LOG_SECONDS

log = logging.getLogger(__name__)

# The version of the record's shape. A reader refuses a line with another version
# rather than guess; a change to a field's meaning, or a field removed, raises it.
SCHEMA_VERSION: Final = 1

Kind = Literal["request", "job", "subprocess", "browser", "lifecycle", "loop", "probe"]
EventType = Literal["start", "end", "open", "mark"]
Outcome = Literal["ok", "failed", "timeout", "cancelled", "abandoned", "never_completed"]
KINDS: Final[tuple[str, ...]] = (
    "request",
    "job",
    "subprocess",
    "browser",
    "lifecycle",
    "loop",
    "probe",
)
EVENT_TYPES: Final[tuple[str, ...]] = ("start", "end", "open", "mark")
OUTCOMES: Final[tuple[str, ...]] = (
    "ok",
    "failed",
    "timeout",
    "cancelled",
    "abandoned",
    "never_completed",
)

# A span still open this long after it began writes an ``open`` record: the slow-request
# warning's threshold (``SLOW_OPERATION_LOG_SECONDS``), so "slow" means one thing in the
# stderr log and here.
OPEN_AFTER_MS: Final[float] = SLOW_OPERATION_LOG_SECONDS * 1000
# How often the watcher thread looks for late spans and pings the event loop. An open
# record is written at most this long after its span crossed a threshold.
WATCH_INTERVAL_S: Final[float] = 1.0
# One segment's size before it rolls. Two MiB is the size below which Metabrowser's own
# JSONL view parses a file whole (``_LARGE_FILE_BYTES`` in ``jsonl_view.py``), so every
# segment opens in Metabrowser without truncation. Measured 2026-11-19 on this machine:
# serving jlevy/metabrowser#600 from a cached clone, startup and the first minute of its
# page (with GitHub unreachable, so three refreshes timed out) wrote 278 records, 72 KB,
# about 270 bytes a record; a folder's README page wrote 90 records, 24.5 KB. A segment
# holds about 29 such pull request visits.
MAX_FILE_BYTES: Final[int] = 2 * 1024 * 1024
# Every segment in the directory together, across the servers that share it: sixteen
# segments, about 460 pull request visits at the size above.
MAX_TOTAL_BYTES: Final[int] = 32 * 1024 * 1024
# The longest line written. A record past it keeps its core fields and drops ``attrs``,
# saying how long they were.
MAX_LINE_BYTES: Final[int] = 8 * 1024
# The longest text kept from a process's stderr or an error message: enough for gh's or
# Git's last error lines.
MAX_TEXT_CHARS: Final[int] = 600
# How far back recent_failures counts, and the most failures it remembers: a message
# can say a failure is one of many in the last hour. An hour of gh calls failing at the
# measured worst (one refresh every few seconds) is well under the kept count.
RECENT_WINDOW_S: Final[float] = 3600.0
RECENT_FAILURES_KEPT: Final[int] = 2048
# The most words of a ``git`` or ``gh`` command line a record keeps.
MAX_LOGGED_ARGS: Final = 24
# A record's name past this many characters is cut when the record is too long to keep
# whole (:data:`MAX_LINE_BYTES`), so the line that says so fits.
_FALLBACK_NAME_CHARS: Final = 200
# After a write fails, the log tries a fresh segment after this long, doubling to the
# most, so a full disk that clears or a directory recreated brings it back.
RETRY_FIRST_S: Final[float] = 1.0
RETRY_MAX_S: Final[float] = 60.0
# Where the log's files live below the state directory, and how they are named:
# ``events-<UTC start>-p<pid>-<segment>.jsonl``, so names sort by start, then segment.
EVENTS_DIRECTORY: Final = "events"
FILE_PREFIX: Final = "events-"
FILE_SUFFIX: Final = ".jsonl"
_FILE_NAME = re.compile(r"^events-(\d{8}T\d{6}Z)-p(\d{1,10})-(\d{3,6})\.jsonl$")
# The environment variable that turns the log off for a served process: 0, false, no,
# or off. The test suite sets it, so a server a test starts writes nothing in a home.
ENABLE_ENV: Final = "METABROWSER_EVENT_LOG"
_OFF: Final = frozenset({"0", "false", "no", "off"})
# The request header a page names its request by, which the request's record carries as
# its ``client``, and the work the request starts inherits (static/event-reports.js). A
# page's ID is ``<page>``, and each of its requests ``<page>-<n>``, so a filter on the
# page's ID finds all of them (``event_log_route``).
CLIENT_HEADER: Final = "x-metabrowser-client"
# What a client ID may be: letters, digits, and ``-_.:``, at most 64 characters, the
# longest the log route filters on. Anything else is not recorded.
_CLIENT_ID: Final = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}")

_ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
# GitHub's token prefixes (ghp_, gho_, ghu_, ghs_, ghr_) and fine-grained tokens.
_TOKEN = re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{16,}|github_pat_[A-Za-z0-9_]{16,})\b")
# To the last ``@`` before the host, as ``cache.lender.redact_userinfo`` reads a userinfo:
# in ``https://me@example.com:token@host/`` the token is the userinfo's.
_URL_CREDENTIALS = re.compile(r"\b([a-z][a-z0-9+.-]*://)[^/\s]+@", re.IGNORECASE)
# A header's whole value; a scheme's credential; a named secret's value after : or =.
_AUTH_HEADER = re.compile(r"(?i)\b((?:proxy-)?authorization)(\s*[:=]\s*)[^\r\n,;]*")
_SCHEME_CREDENTIAL = re.compile(r"(?i)\b(bearer|basic)\s+[A-Za-z0-9._~+/=-]{4,}")
# The name may be compound (``access_token``, ``client_secret``, ``GITHUB_TOKEN``,
# ``x-api-key``): any word around the secret's own.
_SECRET_FIELD = re.compile(
    r"(?i)(?<![\w-])([\w-]*(?:token|password|passwd|secret|api[_-]?key)[\w-]*)(\s*[:=]\s*)[^\s,;]+"
)


def client_id(raw: str | bytes | None) -> str | None:
    """*raw* as a client ID, or ``None`` when it is not one (:data:`CLIENT_HEADER`)."""

    if raw is None:
        return None
    text = raw.decode("latin-1") if isinstance(raw, bytes) else raw
    return text if _CLIENT_ID.fullmatch(text) else None


def redact(text: str, *, limit: int = MAX_TEXT_CHARS) -> str:
    """*text* without tokens, URL credentials, escape codes, or control characters.

    Keeps the end of a long text, where a process writes the error that explains it.
    """

    cleaned = _ANSI.sub("", text)
    cleaned = _CONTROL.sub(" ", cleaned)
    cleaned = _TOKEN.sub("[token]", cleaned)
    cleaned = _URL_CREDENTIALS.sub(r"\1[credentials]@", cleaned)
    cleaned = _AUTH_HEADER.sub(r"\1\2[redacted]", cleaned)
    cleaned = _SCHEME_CREDENTIAL.sub(r"\1 [redacted]", cleaned)
    cleaned = _SECRET_FIELD.sub(r"\1\2[redacted]", cleaned)
    cleaned = cleaned.strip()
    if len(cleaned) > limit:
        cleaned = "…" + cleaned[-(limit - 1) :]
    return cleaned


def describe_error(exc: BaseException) -> str:
    """``Type: message``, redacted and bounded, for a record's ``error``."""

    message = str(exc)
    return redact(f"{type(exc).__name__}: {message}" if message else type(exc).__name__)


def stderr_tail(data: bytes) -> str:
    """The end of a process's stderr, decoded and redacted."""

    return redact(data[-4 * MAX_TEXT_CHARS :].decode("utf-8", errors="replace"))


class Span:
    """One unit of work being timed. Ended once; a second end changes nothing."""

    __slots__ = (
        "_ended",
        "_next_open_ms",
        "_stopped",
        "attrs",
        "client",
        "id",
        "kind",
        "min_ms",
        "name",
        "parent",
        "started",
        "started_wall",
    )

    def __init__(
        self,
        span_id: int,
        parent: int | None,
        kind: Kind,
        name: str,
        attrs: dict[str, Any],
        *,
        client: str | None,
        min_ms: float,
    ) -> None:
        self.id = span_id
        self.parent = parent
        self.kind = kind
        self.name = name
        self.attrs = attrs
        self.client = client
        self.min_ms = min_ms
        self.started = time.perf_counter()
        self.started_wall = time.time()
        self._next_open_ms = OPEN_AFTER_MS
        self._stopped: float | None = None
        self._ended = False

    @property
    def ended(self) -> bool:
        return self._ended

    def age_ms(self, now: float | None = None) -> float:
        if self._stopped is not None:
            return (self._stopped - self.started) * 1000
        return ((time.perf_counter() if now is None else now) - self.started) * 1000

    def stop(self) -> None:
        """Stop the span's clock: its duration ends here, however much later it ends.

        Work that reads what the span's work returned, to add it to the span's record,
        stops the clock first, so the reading is not counted as the work's time: a ``gh``
        span reads GitHub's answer after gh exits (``builtin_plugins/github/gh.py``).
        """

        if self._stopped is None:
            self._stopped = time.perf_counter()

    def set(self, **attrs: Any) -> None:
        """Add *attrs* to what the span's end record carries."""

        self.attrs.update(attrs)

    def note_failure(self, state: str, message: str | None = None) -> None:
        """Say the work failed although its code returns normally, as a job that records
        its own failure does: its end is ``failed`` rather than ``ok``, with *state*."""

        self.attrs["failure"] = state
        if message:
            self.attrs["failure_message"] = redact(message)

    def end(self, outcome: Outcome = "ok", **attrs: Any) -> None:
        """Finish the span with *outcome*, writing its end record."""

        sink = _sink
        if self._ended:
            return
        self._ended = True
        if attrs:
            self.attrs.update(attrs)
        if outcome == "ok" and "failure" in self.attrs:
            outcome = "failed"
        if sink is not None:
            sink.finish(self, outcome)


class _NullSpan(Span):
    """What a span is with no log open: every method does nothing."""

    def __init__(self) -> None:
        super().__init__(0, None, "lifecycle", "", {}, client=None, min_ms=0)
        self._ended = True

    def set(self, **attrs: Any) -> None:
        return None

    def note_failure(self, state: str, message: str | None = None) -> None:
        return None

    def stop(self) -> None:
        return None

    def end(self, outcome: Outcome = "ok", **attrs: Any) -> None:
        return None


NULL_SPAN: Final[Span] = _NullSpan()
_CURRENT: ContextVar[Span | None] = ContextVar("metabrowser_event_span", default=None)


def current() -> Span:
    """The span the calling code runs inside, or :data:`NULL_SPAN`."""

    return _CURRENT.get() or NULL_SPAN


def enabled() -> bool:
    """Whether this process writes an event log."""

    return _sink is not None


def begin(
    kind: Kind,
    name: str,
    *,
    attrs: Mapping[str, Any] | None = None,
    client: str | None = None,
    announce: bool = False,
    min_ms: float = 0.0,
    parent: Span | None = None,
) -> Span:
    """Start a span; the caller ends it with :meth:`Span.end`.

    *announce* writes a ``start`` record now, as a job does. *min_ms* drops the end
    record of a span quicker than it, and its open records still go out. *parent*
    defaults to the current span. *client* defaults to the parent's, so the job a
    page's request starts, and the processes the job runs, carry the request's client
    ID; a job that another request joins keeps the first one's.
    """

    sink = _sink
    if sink is None:
        return NULL_SPAN
    above = parent if parent is not None else _CURRENT.get()
    span = Span(
        next(sink.ids),
        above.id if above is not None and above.id else None,
        kind,
        name,
        dict(attrs) if attrs else {},
        client=client if client is not None or above is None else above.client,
        min_ms=min_ms,
    )
    sink.started(span, announce=announce)
    return span


@contextlib.contextmanager
def within(span: Span) -> Generator[Span]:
    """Make *span* current for the block, so the work started in it names it as parent."""

    if span is NULL_SPAN:
        yield span
        return
    token = _CURRENT.set(span)
    try:
        yield span
    finally:
        _CURRENT.reset(token)


@contextlib.contextmanager
def span(
    kind: Kind,
    name: str,
    *,
    attrs: Mapping[str, Any] | None = None,
    announce: bool = False,
    min_ms: float = 0.0,
) -> Generator[Span]:
    """Time the block as a span, current inside it, and end it by how the block ended.

    A block that ends the span itself, with an outcome it knows better, keeps that one.
    Otherwise a return is ``ok``, a cancellation ``cancelled``, a ``TimeoutError``
    ``timeout``, and any other exception ``failed`` with the exception described.
    """

    if _sink is None:
        yield NULL_SPAN
        return
    started = begin(kind, name, attrs=attrs, announce=announce, min_ms=min_ms)
    token = _CURRENT.set(started)
    try:
        yield started
    except BaseException as exc:
        outcome, extra = _outcome_of(exc)
        started.end(outcome, **extra)
        raise
    else:
        started.end("ok")
    finally:
        _CURRENT.reset(token)


def _outcome_of(exc: BaseException) -> tuple[Outcome, dict[str, Any]]:
    if isinstance(exc, asyncio.CancelledError):
        return "cancelled", {}
    if isinstance(exc, TimeoutError):
        return "timeout", {"error": describe_error(exc)}
    return "failed", {"error": describe_error(exc)}


def job[T](
    work: Awaitable[T], name: str, *, attrs: Mapping[str, Any] | None = None
) -> Coroutine[Any, Any, T]:
    """*work* as a background job: a span that writes its start when the job first runs
    and ends with it.

    Wrap the coroutine handed to ``asyncio.create_task``. The job's parent is the span
    current here, usually the request that started it; work the job starts names the
    job. A task cancelled before its first step runs nothing, so it leaves no span open.
    With no log open, *work* is awaited as it is.
    """

    if _sink is None and asyncio.iscoroutine(work):
        return work
    parent = _CURRENT.get()

    async def run() -> T:
        started = begin("job", name, attrs=attrs, announce=True, parent=parent)
        if started is NULL_SPAN:
            return await work
        token = _CURRENT.set(started)
        try:
            result = await work
        except BaseException as exc:
            outcome, extra = _outcome_of(exc)
            started.end(outcome, **extra)
            raise
        finally:
            _CURRENT.reset(token)
        started.end("ok")
        return result

    return run()


def job_name(work: Callable[..., Any]) -> str:
    """A job's name from the function it runs: ``module.qualified_name``."""

    function = getattr(work, "func", work)
    module = getattr(function, "__module__", "") or ""
    qualified = getattr(function, "__qualname__", None) or type(function).__name__
    # A function defined inside another is named for itself, not the path to it.
    qualified = qualified.rpartition("<locals>.")[2]
    return f"{module.rpartition('.')[2]}.{qualified}" if module else qualified


def mark(kind: Kind, name: str, **attrs: Any) -> None:
    """Write a ``mark`` record: a fact with no duration, such as a server starting."""

    sink = _sink
    if sink is not None:
        sink.write(sink.record("mark", kind, name, attrs=attrs))


def report(
    event: EventType,
    name: str,
    *,
    client: str | None,
    dur_ms: float | None,
    outcome: Outcome | None,
    attrs: Mapping[str, Any],
) -> bool:
    """Write a ``browser`` record of what a page reported; whether a log took it.

    The record has no span: the page timed the work, and its ``client`` ties it to the
    server's records of the page's requests. The caller validates and bounds what the
    page sent (``event_log_reports``).
    """

    sink = _sink
    if sink is None:
        return False
    sink.write(
        sink.record(
            event,
            "browser",
            name,
            client=client,
            outcome=outcome,
            dur_ms=dur_ms,
            attrs=attrs,
        )
    )
    return True


@dataclass(frozen=True, slots=True)
class RecentFailure:
    """A span that failed naming a cause, kept for :func:`recent_failures`: when
    (monotonic), its kind and cause, and the ``host`` and ``address`` it recorded."""

    at: float
    kind: str
    cause: str
    host: str | None
    address: str | None


def _recent(
    causes: Iterable[str] | None,
    kind: str,
    window_s: float,
    host: Callable[[str | None], bool] | None,
) -> list[RecentFailure]:
    sink = _sink
    if sink is None:
        return []
    wanted = None if causes is None else frozenset(causes)
    since = time.monotonic() - window_s
    return [
        f
        for f in sink.failures()
        if f.at >= since
        and f.kind == kind
        and (wanted is None or f.cause in wanted)
        and (host is None or host(f.host))
    ]


def recent_failures(
    *,
    causes: Iterable[str] | None = None,
    kind: str = "subprocess",
    window_s: float = RECENT_WINDOW_S,
    host: Callable[[str | None], bool] | None = None,
) -> int:
    """How many *kind* spans failed with one of *causes* in the last *window_s* seconds,
    counting only those whose recorded host *host* accepts, when it is given.

    The count is this process's, since its log opened; with no log open it is 0. The
    default counts processes, one per failed gh or git call, so a job and the call it
    failed on are not counted twice.
    """

    return len(_recent(causes, kind, window_s, host))


def recent_failed_addresses(
    *,
    causes: Iterable[str] | None = None,
    kind: str = "subprocess",
    window_s: float = RECENT_WINDOW_S,
    host: Callable[[str | None], bool] | None = None,
) -> tuple[str, ...]:
    """The addresses the failures :func:`recent_failures` counts were to, newest first."""

    found = [f.address for f in reversed(_recent(causes, kind, window_s, host)) if f.address]
    return tuple(dict.fromkeys(found))


@dataclass(frozen=True, slots=True)
class OpenSpan:
    """A span this process has not ended yet, as the log route reports it."""

    span: int
    parent: int | None
    kind: str
    name: str
    age_ms: float
    attrs: dict[str, Any]
    client: str | None = None


def open_spans() -> list[OpenSpan]:
    """The spans this process has started and not ended, oldest first."""

    sink = _sink
    return [] if sink is None else sink.open_now()


def current_file() -> Path | None:
    """The file this process writes now, or ``None`` with no log open."""

    sink = _sink
    return None if sink is None else sink.path


class EventLog:
    """One process's writer: the open file, the open spans, and the watcher thread."""

    def __init__(
        self,
        directory: Path,
        home: Path,
        *,
        max_file_bytes: int = MAX_FILE_BYTES,
        max_total_bytes: int = MAX_TOTAL_BYTES,
        watch_interval_s: float = WATCH_INTERVAL_S,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.directory = directory
        self._home = home
        self._relative = directory.relative_to(home).as_posix()
        self._max_file_bytes = max_file_bytes
        self._max_total_bytes = max_total_bytes
        self._watch_interval_s = watch_interval_s
        self._clock = clock
        self.ids = itertools.count(1)
        self._pid = os.getpid()
        stamp = datetime.fromtimestamp(clock(), UTC).strftime("%Y%m%dT%H%M%SZ")
        self._base = f"{FILE_PREFIX}{stamp}-p{self._pid}"
        self._segment = -1
        self._fd: int | None = None
        self._size = 0
        self.path: Path | None = None
        self._write_lock = threading.Lock()
        self._open_lock = threading.Lock()
        self._open: dict[int, Span] = {}
        self._stop = threading.Event()
        self._watcher: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._ping: Span | None = None
        # The recent failures that named a cause, for recent_failures. Bounded, so a long
        # outage costs a fixed amount of memory.
        self._failures: collections.deque[RecentFailure] = collections.deque(
            maxlen=RECENT_FAILURES_KEPT
        )
        self._closed = False
        self._retry_s = RETRY_FIRST_S
        self._retry_at = 0.0
        self._roll()

    # ── writing ─────────────────────────────────────────────────

    def record(
        self,
        event: EventType,
        kind: str,
        name: str,
        *,
        span: Span | None = None,
        outcome: Outcome | None = None,
        dur_ms: float | None = None,
        attrs: Mapping[str, Any] | None = None,
        wall: float | None = None,
        client: str | None = None,
    ) -> dict[str, Any]:
        """One record. Its fields, in order:

        ``v`` the schema version; ``ts`` when it was written, UTC to the millisecond;
        ``event`` (``start``, ``end``, ``open``, ``mark``); ``kind``; ``name``; ``span``
        and ``parent`` IDs; ``client``, the browser's ID for the request it sent, or
        for the page, on a ``browser`` record; ``dur_ms``, monotonic, which on an
        ``open`` record is the age so far; ``outcome`` on an end; ``pid``; and
        ``attrs``, the kind's own detail.
        """

        moment = self._clock() if wall is None else wall
        out: dict[str, Any] = {
            "v": SCHEMA_VERSION,
            "ts": datetime.fromtimestamp(moment, UTC).isoformat(timespec="milliseconds")[:-6] + "Z",
            "event": event,
            "kind": kind,
            "name": name,
        }
        if span is not None:
            out["span"] = span.id
            if span.parent is not None:
                out["parent"] = span.parent
            if span.client is not None:
                out["client"] = span.client
        elif client is not None:
            out["client"] = client
        if dur_ms is not None:
            out["dur_ms"] = round(dur_ms, 1)
        if outcome is not None:
            out["outcome"] = outcome
        out["pid"] = self._pid
        if attrs:
            out["attrs"] = dict(attrs)
        return out

    @staticmethod
    def _encode(record: Mapping[str, Any]) -> bytes:
        """*record* as one line. Text Python cannot encode, such as a lone surrogate from
        output decoded with ``surrogateescape``, is written as its escape."""

        line = json.dumps(record, ensure_ascii=False, separators=(",", ":"), default=str)
        data = line.encode("utf-8", errors="backslashreplace") + b"\n"
        if len(data) > MAX_LINE_BYTES:
            trimmed = {key: value for key, value in record.items() if key != "attrs"}
            trimmed["name"] = str(trimmed.get("name", ""))[:_FALLBACK_NAME_CHARS]
            if isinstance(trimmed.get("client"), str):
                trimmed["client"] = trimmed["client"][:_FALLBACK_NAME_CHARS]
            trimmed["attrs"] = {"dropped_bytes": len(data)}
            line = json.dumps(trimmed, ensure_ascii=False, separators=(",", ":"), default=str)
            data = line.encode("utf-8", errors="backslashreplace") + b"\n"
        return data

    def write(self, record: Mapping[str, Any]) -> None:
        """Append *record*. Never raises: logging must not fail the work it records."""

        try:
            data = self._encode(record)
        except Exception as exc:  # a value json cannot write, such as a cycle
            log.debug("event log dropped a record it could not encode: %s", exc)
            return
        with self._write_lock:
            self._append(data)

    def _descriptor(self) -> int | None:
        """The open segment's descriptor, read afresh: a roll replaces or clears it."""

        return self._fd

    def _append(self, data: bytes) -> None:
        """Append one encoded line; the caller holds the write lock."""

        if self._fd is None and not self._retry_due():
            return
        if self._fd is None or (self._size and self._size + len(data) > self._max_file_bytes):
            self._roll()
        fd = self._descriptor()
        if fd is None:  # the roll could not open the next segment
            self._failed()
            return
        try:
            written = os.write(fd, data)
        except OSError as exc:
            # A full disk or a removed directory pauses the log, never the server.
            log.warning("event log paused: could not write %s: %s", self.path, exc)
            self._failed()
            return
        if written != len(data):
            log.warning("event log paused: %s took %d of %d bytes", self.path, written, len(data))
            self._failed()
            return
        self._size += len(data)
        self._retry_s = RETRY_FIRST_S

    def _failed(self) -> None:
        """Close the segment and try a fresh one after the backoff; the caller holds the
        write lock. Until then :attr:`path` is ``None``, so the route names no file."""

        self._close_file()
        self.path = None
        self._retry_at = time.monotonic() + self._retry_s
        self._retry_s = min(self._retry_s * 2, RETRY_MAX_S)

    def _retry_due(self) -> bool:
        return not self._closed and time.monotonic() >= self._retry_at

    def check_file(self) -> None:
        """Start a fresh segment when this one's name is gone from the directory, as
        when another process's prune or a person deleted it: writing on would land in a
        file no reader can find. The watcher calls this every interval."""

        with self._write_lock:
            fd = self._fd
            if fd is None or self._closed:
                return
            try:
                unlinked = os.fstat(fd).st_nlink == 0
            except OSError:
                unlinked = True
            if unlinked:
                log.info("event log: %s was removed; starting a fresh segment", self.path)
                self._roll()
                if self._fd is None:
                    self._failed()

    def close_from_signal_handler(self) -> None:
        """What :meth:`close` writes, from a handler that stops the process on the spot.

        A signal handler runs between two bytecodes of the main thread, which may hold
        either lock, so each is only tried: when one is held, the records it guards are
        left unwritten rather than deadlocking the stop. Nothing here logs or imports.
        """

        self._closed = True
        if not self._write_lock.acquire(blocking=False):
            return
        try:
            remaining: list[Span] = []
            if self._open_lock.acquire(blocking=False):
                try:
                    remaining = sorted(self._open.values(), key=lambda s: s.started)
                    self._open.clear()
                finally:
                    self._open_lock.release()
            for s in remaining:
                if s.kind == "loop" or s._ended:
                    continue
                s._ended = True
                self._append(
                    self._encode(
                        self.record(
                            "end",
                            s.kind,
                            s.name,
                            span=s,
                            outcome="abandoned",
                            dur_ms=s.age_ms(),
                            attrs=s.attrs,
                        )
                    )
                )
            self._append(self._encode(self.record("mark", "lifecycle", "server.stop")))
            self._close_file()
        finally:
            self._write_lock.release()

    def _roll(self) -> None:
        from metabrowser import home as home_module

        self._close_file()
        self._segment += 1
        name = f"{self._base}-{self._segment:03d}{FILE_SUFFIX}"
        try:
            self._fd = home_module.open_private_file(
                self._home,
                f"{self._relative}/{name}",
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_APPEND,
            )
        except (OSError, home_module.PrivateStorageError) as exc:
            log.warning("event log paused: could not create %s: %s", name, exc)
            self._fd = None
            self.path = None
            return
        self.path = self.directory / name
        self._size = 0
        prune(self.directory, self._max_total_bytes, keep=self.path)

    def _close_file(self) -> None:
        if self._fd is not None:
            with contextlib.suppress(OSError):
                os.close(self._fd)
            self._fd = None

    # ── spans ───────────────────────────────────────────────────

    def started(self, span: Span, *, announce: bool) -> None:
        with self._open_lock:
            self._open[span.id] = span
        if announce:
            self.write(
                self.record(
                    "start",
                    span.kind,
                    span.name,
                    span=span,
                    attrs=span.attrs,
                    wall=span.started_wall,
                )
            )

    def finish(self, span: Span, outcome: Outcome) -> None:
        cause = span.attrs.get("cause")
        if outcome != "ok" and isinstance(cause, str):
            host, address = span.attrs.get("host"), span.attrs.get("address")
            self._failures.append(
                RecentFailure(
                    time.monotonic(),
                    span.kind,
                    cause,
                    host if isinstance(host, str) else None,
                    address if isinstance(address, str) else None,
                )
            )
        with self._open_lock:
            self._open.pop(span.id, None)
        duration = span.age_ms()
        if duration < span.min_ms:
            return
        self.write(
            self.record(
                "end",
                span.kind,
                span.name,
                span=span,
                outcome=outcome,
                dur_ms=duration,
                attrs=span.attrs,
            )
        )

    def failures(self) -> list[RecentFailure]:
        """The failures kept for recent_failures, oldest first."""

        return list(self._failures)

    def open_now(self) -> list[OpenSpan]:
        now = time.perf_counter()
        with self._open_lock:
            spans = sorted(self._open.values(), key=lambda s: s.started)
        return [
            OpenSpan(
                s.id, s.parent, s.kind, s.name, round(s.age_ms(now), 1), dict(s.attrs), s.client
            )
            for s in spans
        ]

    def check_open(self, now: float | None = None) -> None:
        """Write an ``open`` record for each span past its next threshold."""

        moment = time.perf_counter() if now is None else now
        with self._open_lock:
            late = [s for s in self._open.values() if s.age_ms(moment) >= s._next_open_ms]
            for s in late:
                while s._next_open_ms <= s.age_ms(moment):
                    s._next_open_ms *= 2
        for s in sorted(late, key=lambda item: item.started):
            self.write(
                self.record("open", s.kind, s.name, span=s, dur_ms=s.age_ms(moment), attrs=s.attrs)
            )

    # ── the watcher ─────────────────────────────────────────────

    def watch(self) -> None:
        """Start the thread that writes open records and pings the event loop."""

        if self._watcher is not None:
            return
        self._watcher = threading.Thread(
            target=self._watch, name="metabrowser-event-log", daemon=True
        )
        self._watcher.start()

    def watch_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Ping *loop* every interval; a turn it takes too long to run is a ``loop`` span."""

        self._loop = loop

    def _watch(self) -> None:
        while not self._stop.wait(self._watch_interval_s):
            try:
                self._ping_loop()
                self.check_file()
                self.check_open()
            except Exception:  # pragma: no cover - the watcher must outlive a bad record
                log.exception("event log watcher failed")

    def _ping_loop(self) -> None:
        loop = self._loop
        if loop is None or loop.is_closed() or self._ping is not None:
            return
        ping = Span(
            next(self.ids),
            None,
            "loop",
            "event_loop.turn",
            {},
            client=None,
            min_ms=OPEN_AFTER_MS,
        )
        self._ping = ping
        with self._open_lock:
            self._open[ping.id] = ping

        def pong() -> None:
            self._ping = None
            ping.end("ok")

        try:
            loop.call_soon_threadsafe(pong)
        except RuntimeError:  # the loop closed between the check and the call
            self._ping = None
            with self._open_lock:
                self._open.pop(ping.id, None)

    def close(self) -> None:
        """End every open span ``abandoned``, write the stop mark, and close the file."""

        self._stop.set()
        watcher = self._watcher
        if watcher is not None and watcher is not threading.current_thread():
            watcher.join(timeout=2 * self._watch_interval_s)
        self._closed = True
        with self._open_lock:
            remaining = sorted(self._open.values(), key=lambda s: s.started)
        for s in remaining:
            if s.kind == "loop" or s._ended:
                with self._open_lock:
                    self._open.pop(s.id, None)
                continue
            # Through this log, not the process's: a log being replaced, or installed
            # for a test, ends its own spans.
            s._ended = True
            self.finish(s, "abandoned")
        self.write(self.record("mark", "lifecycle", "server.stop"))
        with self._write_lock:
            self._close_file()


_sink: EventLog | None = None


def enabled_by_environment(environ: Mapping[str, str] | None = None) -> bool:
    """Whether :data:`ENABLE_ENV` leaves the log on: anything but 0, false, no, or off."""

    variables = os.environ if environ is None else environ
    return variables.get(ENABLE_ENV, "").strip().lower() not in _OFF


def log_directory(environ: Mapping[str, str] | None = None) -> tuple[Path, Path]:
    """``(state home, events directory)``: where the log lives, without creating it.

    The state home is ``METABROWSER_STATE_DIR``, or ``$XDG_STATE_HOME/metabrowser``, or
    ``~/.local/state/metabrowser``: the XDG directory for logs and history, which a
    reboot keeps and a cache clear does not touch.
    """

    from metabrowser.home import state_directory

    home = state_directory(environ)
    return home, home / EVENTS_DIRECTORY


# Why this process writes no log, for the page's Details and the log that is not written: ``None``
# while a log is open or no reason has been given. A served process sets it when it opens none.
_off_reason: str | None = None
# The folder served and the events directory, both resolved, when the folder holds the
# directory without being inside it: what a request's target is judged against by
# :func:`quiet_request`.
_quiet: tuple[Path, Path] | None = None


def off_reason() -> str | None:
    """Why this server writes no event log, in words a page can say, or ``None``."""

    return _off_reason


def quiet_request(path: str, query: str) -> bool:
    """Whether a request is for something inside the events directory, so it is not recorded.

    A server whose folder holds the events directory (``metab ~``, the folder above the
    state directory) shows the log as it shows any file. Recording each request for a
    segment into that segment would change it, which the page shows, which asks again; so
    a request whose target (the ``path`` it names, or ``/raw/<path>`` or ``/view/<path>``
    for a file) is inside the events directory writes no record, and every other request
    is recorded as usual. Only a server in that position pays for the lookup.
    """

    quiet = _quiet
    if quiet is None:
        return False
    root, events = quiet
    targets = list(urllib.parse.parse_qs(query).get("path", []))
    for prefix in ("/raw/", "/view/"):
        if path.startswith(prefix):
            targets.append(path[len(prefix) :])
    for target in targets:
        try:
            resolved = Path(os.path.realpath(root / target.lstrip("/")))
        except (OSError, ValueError):
            continue
        if resolved == events or resolved.is_relative_to(events):
            return True
    return False


def open_log(
    *,
    served: str,
    version: str,
    served_directory: Path | None = None,
    environ: Mapping[str, str] | None = None,
    **options: Any,
) -> EventLog | None:
    """Open this process's log and start its watcher, or say why not and return None.

    A log that cannot be opened is a warning: the server serves without one, and
    :func:`off_reason` says why. A server whose folder (*served_directory*) is the events
    directory, or inside it, opens none: it would record each request for the files it shows
    into one of them, which changes them, which the page shows, which asks again, and a
    process that records nothing says so, as a warning and in the page's Details. A server
    whose folder holds the directory, such as ``metab ~``, records as usual, except the
    requests for what is inside the directory (:func:`quiet_request`).
    """

    global _sink, _off_reason, _quiet
    from metabrowser import home as home_module

    if _sink is not None:
        return _sink
    _quiet = None
    if not enabled_by_environment(environ):
        _off_reason = f"{ENABLE_ENV} turns it off"
        return None
    try:
        state, directory = log_directory(environ)
        if served_directory is not None:
            root, events = served_directory.resolve(), directory.resolve()
            if root == events or root.is_relative_to(events):
                _off_reason = (
                    "the folder this server shows is the event log's own, and recording "
                    "its requests would change the files on screen"
                )
                log.warning("serving without an event log: %s", _off_reason)
                return None
            if events.is_relative_to(root):
                _quiet = (root, events)
        home_module.ensure_storage_root(state)
        home_module.ensure_private_directory(state, EVENTS_DIRECTORY)
        sink = EventLog(directory, state, **options)
    except (OSError, ValueError, home_module.PrivateStorageError) as exc:
        _quiet = None
        _off_reason = f"it could not be opened: {exc}"
        log.warning("serving without an event log: %s", exc)
        return None
    if sink.path is None:
        _quiet = None
        _off_reason = "it could not be opened"
        return None
    _sink = sink
    _off_reason = None
    mark("lifecycle", "server.start", served=served, version=version)
    sink.watch()
    return sink


def watch_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Have the open log ping *loop*, so a blocked event loop is on record."""

    sink = _sink
    if sink is not None:
        sink.watch_loop(loop)


def close_log() -> None:
    """Close this process's log, if it has one."""

    global _sink, _quiet, _off_reason
    _quiet = None
    _off_reason = None
    sink = _sink
    if sink is None:
        return
    sink.close()
    _sink = None


def close_from_signal_handler() -> None:
    """End open spans ``abandoned`` and mark the stop, from a stopping signal handler."""

    global _sink
    sink = _sink
    if sink is None:
        return
    _sink = None
    sink.close_from_signal_handler()


@contextlib.contextmanager
def installed(sink: EventLog) -> Generator[EventLog]:
    """Use *sink* as this process's log for the block: for tests and measurements."""

    global _sink
    previous = _sink
    _sink = sink
    try:
        yield sink
    finally:
        _sink = previous


# ── files ───────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class LogFile:
    """One segment in the directory."""

    name: str
    bytes: int
    modified: float
    pid: int
    started: str
    segment: int


def parse_file_name(name: str) -> tuple[str, int, int] | None:
    """``(UTC start, pid, segment)`` from a segment's name, or None for another file."""

    match = _FILE_NAME.match(name)
    if match is None:
        return None
    return match.group(1), int(match.group(2)), int(match.group(3))


def list_files(directory: Path) -> list[LogFile]:
    """The segments in *directory*, newest first; none when it does not exist."""

    try:
        entries = list(os.scandir(directory))
    except FileNotFoundError:
        return []
    files: list[LogFile] = []
    for entry in entries:
        parsed = parse_file_name(entry.name)
        if parsed is None:
            continue
        try:
            status = entry.stat(follow_symlinks=False)
        except FileNotFoundError:
            continue
        if not entry.is_file(follow_symlinks=False):
            continue
        started, pid, segment = parsed
        files.append(LogFile(entry.name, status.st_size, status.st_mtime, pid, started, segment))
    files.sort(key=lambda f: (f.modified, f.name), reverse=True)
    return files


def _alive(pid: int) -> bool:
    """Whether a process with *pid* runs now. A process of another user counts; a pid
    reused since is taken as alive, which only keeps one more segment."""

    if pid == os.getpid():
        return True
    if os.name != "posix":  # pragma: no cover - served processes run on macOS and Linux
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except (OverflowError, ValueError):
        return False
    except OSError:  # PermissionError: it exists and is someone else's
        return True
    return True


def _writing_now(files: list[LogFile]) -> set[str]:
    """The segment each live process writes: the newest of each writer, named by its
    start and pid, whose process still runs."""

    newest: dict[tuple[str, int], LogFile] = {}
    for f in files:
        held = newest.get((f.started, f.pid))
        if held is None or f.segment > held.segment:
            newest[(f.started, f.pid)] = f
    return {f.name for f in newest.values() if _alive(f.pid)}


def prune(directory: Path, max_total_bytes: int, *, keep: Path | None = None) -> list[str]:
    """Delete the oldest segments until the rest fit in *max_total_bytes*; their names.

    The segment each live server writes is kept, however old: an idle server's file has
    the oldest time, and deleting it would leave that server writing to a name no reader
    finds. So the bound holds for closed segments, and each running server adds at most
    one segment, :data:`MAX_FILE_BYTES`, to it.
    """

    files = list_files(directory)
    total = sum(f.bytes for f in files)
    removed: list[str] = []
    live = _writing_now(files)
    for old in reversed(files):
        if total <= max_total_bytes:
            break
        if (keep is not None and old.name == keep.name) or old.name in live:
            continue
        with contextlib.suppress(FileNotFoundError):
            (directory / old.name).unlink()
            removed.append(old.name)
        total -= old.bytes
    return removed


def parse_lines(data: bytes) -> Iterable[dict[str, Any]]:
    """The records in *data*, skipping a torn last line and lines of another version.

    A line no JSON reader will take is skipped as a torn one is: text that is not UTF-8,
    an integer of more than Python's 4,300 digits (a ``ValueError``), or arrays nested past
    the recursion limit (a ``RecursionError``), which a file the log did not write can hold.
    """

    for raw in data.splitlines():
        if not raw.strip():
            continue
        try:
            decoded = json.loads(raw)
        except (ValueError, RecursionError):
            continue
        if isinstance(decoded, dict) and decoded.get("v") == SCHEMA_VERSION:
            yield decoded


__all__ = [
    "CLIENT_HEADER",
    "ENABLE_ENV",
    "EVENTS_DIRECTORY",
    "EVENT_TYPES",
    "KINDS",
    "MAX_FILE_BYTES",
    "MAX_LINE_BYTES",
    "MAX_LOGGED_ARGS",
    "MAX_TEXT_CHARS",
    "RECENT_FAILURES_KEPT",
    "RECENT_WINDOW_S",
    "MAX_TOTAL_BYTES",
    "NULL_SPAN",
    "OPEN_AFTER_MS",
    "OUTCOMES",
    "RETRY_FIRST_S",
    "RETRY_MAX_S",
    "SCHEMA_VERSION",
    "WATCH_INTERVAL_S",
    "EventLog",
    "LogFile",
    "OpenSpan",
    "RecentFailure",
    "Span",
    "begin",
    "client_id",
    "close_log",
    "current",
    "current_file",
    "describe_error",
    "enabled",
    "enabled_by_environment",
    "off_reason",
    "quiet_request",
    "installed",
    "job",
    "job_name",
    "list_files",
    "log_directory",
    "mark",
    "recent_failed_addresses",
    "recent_failures",
    "report",
    "open_log",
    "open_spans",
    "parse_file_name",
    "parse_lines",
    "prune",
    "redact",
    "span",
    "stderr_tail",
    "watch_loop",
    "within",
]
