"""``POST /api/event-log/client``: what a page saw, written to the event log as ``browser`` records.

The server times every request and the work it starts (:mod:`metabrowser.event_log`),
but only the page knows what it waited for: a request the network held, a render that
froze it, a placeholder still pulsing after the work behind it should have ended. The
page reports those here (``static/event-reports.js``), and each accepted report becomes
one ``browser`` record, so the page's side and the server's are in one log, joined by
the page's client ID (:data:`metabrowser.event_log.CLIENT_HEADER`).

A report is evidence from the page, never more: the route takes only the fields named
below, of the types and sizes named, passes its text through
:func:`metabrowser.event_log.redact`, and refuses the rest, one report at a time, saying
why. It answers what it wrote, so ``metab --api /api/event-log/client --data FILE``
shows what a page's report becomes without a server. The same-origin guard in
``server.py`` (``_HostValidationMiddleware``) already keeps it from anything but the
application's own pages: a sandboxed document's ``Origin: null`` is refused, and so is
a body that is not JSON.

The body is ``{"page": ID, "path": PATH, "reports": [...], "dropped": N}``: the page's
ID, its address's path, at most :data:`MAX_REPORTS` reports, and how many the page
dropped itself, past its own bound. Each report is:

``type``
    ``fetch`` (a request to this server), ``render`` (the page could not paint), or
    ``wait`` (something the page shows as loading).
``event``
    ``open`` (still running, past its threshold) or ``end``.
``name``
    The request's method and path, the render's or wait's name; one longer than the
    record keeps is cut short, as the body's ``path`` is.
``client``
    The request's client ID, or the page's; always the page's or one of its requests'.
``dur_ms``
    How long it ran, or has run so far, on the page's monotonic clock.
``outcome``
    On an ``end``: ``ok``, ``failed``, ``cancelled``, or ``never_completed`` (the page
    was left first).
``attrs``
    Optional: ``status``, ``server_ms`` (the request's ``Server-Timing``),
    ``threshold_ms``, ``error``, ``hidden`` and ``hidden_ms`` (a wait the page spent
    some of hidden, and how long, which does not count toward its late threshold), and
    ``detail``, up to :data:`MAX_DETAIL_KEYS` short scalars.
"""

from __future__ import annotations

import json
import math
import re
import threading
import time
from typing import Any, Final, cast

from starlette.requests import Request
from starlette.responses import JSONResponse

from metabrowser import event_log

REPORT_ROUTE: Final = "/api/event-log/client"
# The most reports one body carries, and the most bytes it may be. The largest report
# the page sends is 286 bytes of JSON (a freeze with the script the browser blamed, the
# largest of tests/test_event_log_reports.py's largest report of each shape), so twenty
# fit in 6 KB and 16 KiB leaves room for long names. A keepalive request may carry at
# most 64 KiB in flight per document, which this keeps a page well under.
MAX_REPORTS: Final = 20
MAX_BODY_BYTES: Final = 16 * 1024
# The most reports the server takes in a window, from every page and tab together: past
# it the rest are refused and one mark says so, and a page's mark of what it dropped
# itself takes a place too. A page bounds itself at PAGE_REPORTS_PER_MINUTE, so this is
# four pages at their bound. The page's reports become records of about 270 bytes, 32 KB
# of log a minute at this bound; a report with every field at its bound becomes 3,130
# bytes (tests/test_event_log_reports.py, the largest record), so a page that sends
# nothing else can write at most 367 KiB a minute: a segment (event_log.MAX_FILE_BYTES)
# in six minutes, and the whole directory (event_log.MAX_TOTAL_BYTES) in about 90.
RATE_REPORTS: Final = 120
RATE_WINDOW_S: Final = 60.0
PAGE_REPORTS_PER_MINUTE: Final = 30
# A fetch is slow, and still pending, past the slow-request threshold
# (event_log.OPEN_AFTER_MS, SLOW_OPERATION_LOG_SECONDS): "slow" means one thing in the
# page's reports, the server's open records, and its stderr warning. Measured 2026-11-19
# from one machine's event log (13 segments, 2 h of the macOS app on pull requests): the
# slowest of 545 answers to GitHub routes took 801 ms (pull-files-summary), so 2 s is
# two and a half times that.
SLOW_MS: Final = event_log.OPEN_AFTER_MS
# A main-thread block this long is a freeze, which the page reports with what ran in it:
# perf.js's FREEZE_WARN_MS, past which it already warns in the console.
FREEZE_MS: Final = 500.0
# A wait the page shows as loading is late past this, when the page reports it and says
# so in place of the placeholder. From the same log: the Diff summary waits on a pull
# request's refresh (checkout._pull_job: 12 runs, median 3.0 s, longest 3.8 s), then its
# comparison's listing (comparison_cache.manifest, longest 0.1 s) and its read
# (pull-comparison, longest 0.24 s), with up to a 1 s poll between: about 5 s at most
# when GitHub answers. Ten seconds is twice that, and less than the 15 s a gh that never
# answers takes to give up (gh.GH_TIMEOUT_S), so the page says so before the failure does.
WAIT_LATE_MS: Final = 10_000.0
# How long the page gathers reports before it sends them, so a burst is one request.
FLUSH_MS: Final = 1000.0

REPORT_TYPES: Final = ("fetch", "render", "wait")
REPORT_EVENTS: Final = ("open", "end")
REPORT_OUTCOMES: Final = ("ok", "failed", "cancelled", "never_completed")
_MAX_NAME_CHARS: Final = 200
_MAX_PATH_CHARS: Final = 400
_MAX_TEXT_CHARS: Final = 200
MAX_DETAIL_KEYS: Final = 8
# A day: no page waits longer and reports it.
_MAX_DURATION_MS: Final = 24 * 3600 * 1000.0
_DETAIL_KEY: Final = re.compile(r"[a-z][a-z0-9_]{0,39}")
_ATTR_KEYS: Final = frozenset(
    {"status", "server_ms", "threshold_ms", "error", "hidden", "hidden_ms", "detail"}
)
_REPORT_KEYS: Final = frozenset({"type", "event", "name", "client", "dur_ms", "outcome", "attrs"})
_BODY_KEYS: Final = frozenset({"page", "path", "reports", "dropped"})


def browser_settings(*, long_lived: tuple[str, ...]) -> dict[str, Any]:
    """What ``static/event-reports.js`` reads as ``METABROWSER_SETTINGS.EVENT_REPORTS``.

    ``log`` says whether this server writes an event log; without one the page sends no
    header and no report, and still says when a wait is late, and ``off_reason`` says why
    there is none (Details shows it). *long_lived* are the paths whose requests stay open
    by design, which the server does not time either.
    """

    return {
        "log": event_log.enabled(),
        "off_reason": None if event_log.enabled() else event_log.off_reason(),
        "route": REPORT_ROUTE,
        "header": event_log.CLIENT_HEADER,
        "slow_ms": SLOW_MS,
        "freeze_ms": FREEZE_MS,
        "late_ms": WAIT_LATE_MS,
        "flush_ms": FLUSH_MS,
        "max_batch": MAX_REPORTS,
        "per_minute": PAGE_REPORTS_PER_MINUTE,
        "long_lived": list(long_lived),
        "failure_window_s": event_log.RECENT_WINDOW_S,
    }


class ReportError(ValueError):
    """A report, or a body, the route refuses; the message says which field and why."""


def _text(value: Any, field: str, *, limit: int, cut: bool = False) -> str:
    """*value* as text the log keeps, redacted. Past *limit* it is refused, or, with
    *cut*, kept to its first *limit* characters: a page's address or a request's path
    can be any length, and a long one should not cost the report, or the whole body."""

    if not isinstance(value, str) or not value.strip():
        raise ReportError(f"{field} must be text")
    if len(value) > limit:
        if not cut:
            raise ReportError(f"{field} is longer than {limit} characters")
        value = value[: limit - 1] + "…"
    return event_log.redact(value, limit=limit)


def _number(value: Any, field: str, *, high: float) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ReportError(f"{field} must be a number")
    number = float(value)
    if not math.isfinite(number) or not 0 <= number <= high:
        raise ReportError(f"{field} must be from 0 to {high:g}")
    return round(number, 1)


def _detail(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ReportError("attrs.detail must be an object")
    entries = cast(dict[Any, Any], value)
    if len(entries) > MAX_DETAIL_KEYS:
        raise ReportError(f"attrs.detail has more than {MAX_DETAIL_KEYS} entries")
    out: dict[str, Any] = {}
    for key, item in entries.items():
        if not isinstance(key, str) or _DETAIL_KEY.fullmatch(key) is None:
            raise ReportError("attrs.detail's names must be lowercase words")
        if item is None or isinstance(item, bool):
            out[key] = item
        elif isinstance(item, int | float):
            if not math.isfinite(item):
                raise ReportError(f"attrs.detail.{key} must be a finite number")
            out[key] = item
        elif isinstance(item, str):
            out[key] = _text(item, f"attrs.detail.{key}", limit=_MAX_TEXT_CHARS)
        else:
            raise ReportError(f"attrs.detail.{key} must be text, a number, true, false, or null")
    return out


def _attrs(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ReportError("attrs must be an object")
    given = cast(dict[str, Any], value)
    unknown = sorted(set(given) - _ATTR_KEYS)
    if unknown:
        raise ReportError(f"attrs.{unknown[0]} is not a field a report has")
    out: dict[str, Any] = {}
    if "status" in given:
        status = given["status"]
        if isinstance(status, bool) or not isinstance(status, int) or not 0 <= status <= 999:
            raise ReportError("attrs.status must be an HTTP status, or 0 for none")
        out["status"] = status
    for key in ("server_ms", "threshold_ms", "hidden_ms"):
        if given.get(key) is not None:
            out[key] = _number(given[key], f"attrs.{key}", high=_MAX_DURATION_MS)
    if "error" in given:
        out["error"] = _text(given["error"], "attrs.error", limit=_MAX_TEXT_CHARS)
    if "hidden" in given:
        if not isinstance(given["hidden"], bool):
            raise ReportError("attrs.hidden must be true or false")
        out["hidden"] = given["hidden"]
    if "detail" in given:
        out["detail"] = _detail(given["detail"])
    return out


def parse_report(raw: Any, *, page: str) -> dict[str, Any]:
    """One report, checked and bounded, as the record it becomes; or :class:`ReportError`.

    The record's fields are those :func:`metabrowser.event_log.report` writes: ``event``,
    ``kind``, ``name`` (the report's type, then its name), ``client``, ``dur_ms``,
    ``outcome``, and ``attrs``.
    """

    if not isinstance(raw, dict):
        raise ReportError("a report must be an object")
    given = cast(dict[str, Any], raw)
    unknown = sorted(set(given) - _REPORT_KEYS)
    if unknown:
        raise ReportError(f"{unknown[0]} is not a field a report has")
    kind = given.get("type")
    if kind not in REPORT_TYPES:
        raise ReportError(f"type must be one of {', '.join(REPORT_TYPES)}")
    event = given.get("event")
    if event not in REPORT_EVENTS:
        raise ReportError(f"event must be one of {', '.join(REPORT_EVENTS)}")
    name = _text(given.get("name"), "name", limit=_MAX_NAME_CHARS, cut=True)
    client = given.get("client", page)
    if (
        not isinstance(client, str)
        or event_log.client_id(client) is None
        or (client != page and not client.startswith(f"{page}-"))
    ):
        raise ReportError("client must be the page's ID or one of its requests'")
    duration = _number(given.get("dur_ms"), "dur_ms", high=_MAX_DURATION_MS)
    outcome = given.get("outcome")
    if event == "end" and outcome not in REPORT_OUTCOMES:
        raise ReportError(f"an end's outcome must be one of {', '.join(REPORT_OUTCOMES)}")
    if event == "open" and outcome is not None:
        raise ReportError("an open report has no outcome")
    return {
        "event": event,
        "kind": "browser",
        "name": f"{kind} {name}",
        "client": client,
        "dur_ms": duration,
        "outcome": outcome,
        "attrs": _attrs(given.get("attrs")),
    }


class RateLimit:
    """At most *limit* reports in each *window_s*, across every page."""

    def __init__(self, limit: int = RATE_REPORTS, window_s: float = RATE_WINDOW_S) -> None:
        self.limit = limit
        self.window_s = window_s
        self._lock = threading.Lock()
        self._started = -math.inf
        self._taken = 0
        self._refused = 0

    def take(self, wanted: int, *, now: float | None = None) -> tuple[int, bool]:
        """How many of *wanted* reports fit now, and whether this is the window's first
        refusal, which the caller marks in the log."""

        moment = time.monotonic() if now is None else now
        with self._lock:
            if moment - self._started >= self.window_s:
                self._started = moment
                self._taken = 0
                self._refused = 0
            granted = max(0, min(wanted, self.limit - self._taken))
            self._taken += granted
            first_refusal = granted < wanted and self._refused == 0
            self._refused += wanted - granted
            return granted, first_refusal


RATE_LIMIT: Final = RateLimit()


def parse_body(data: bytes) -> tuple[str, str | None, list[Any], int]:
    """``(page, path, reports, dropped)`` from a body, or :class:`ReportError`."""

    try:
        decoded = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReportError("the body must be JSON") from exc
    if not isinstance(decoded, dict):
        raise ReportError("the body must be an object")
    body = cast(dict[str, Any], decoded)
    unknown = sorted(set(body) - _BODY_KEYS)
    if unknown:
        raise ReportError(f"{unknown[0]} is not a field of a report's body")
    page = body.get("page")
    if not isinstance(page, str) or event_log.client_id(page) is None or "-" in page:
        raise ReportError("page must be the page's ID: letters and digits")
    path = body.get("path")
    if path is not None:
        if not isinstance(path, str) or not path.startswith("/"):
            raise ReportError("path must be the page's path, from its first /")
        path = _text(path, "path", limit=_MAX_PATH_CHARS, cut=True)
    reports = body.get("reports")
    if not isinstance(reports, list):
        raise ReportError("reports must be a list")
    listed = cast(list[Any], reports)
    if len(listed) > MAX_REPORTS:
        raise ReportError(f"a body carries at most {MAX_REPORTS} reports")
    dropped = body.get("dropped", 0)
    if isinstance(dropped, bool) or not isinstance(dropped, int) or not 0 <= dropped <= 10**6:
        raise ReportError("dropped must be a count")
    return page, path, listed, dropped


def accept(data: bytes, *, limit: RateLimit = RATE_LIMIT) -> tuple[int, dict[str, Any]]:
    """``(status, answer)`` for a body: each report checked, and those that fit written."""

    try:
        page, path, reports, dropped = parse_body(data)
    except ReportError as exc:
        return 400, {"error": str(exc), "code": "invalid_report"}
    parsed: list[dict[str, Any]] = []
    refused: list[dict[str, Any]] = []
    for index, raw in enumerate(reports):
        try:
            parsed.append(parse_report(raw, page=page))
        except ReportError as exc:
            refused.append({"index": index, "error": str(exc)})
    # The mark that says how many the page dropped is a record too, and takes its place in
    # the window after the reports: a page past its own bound cannot write past the
    # server's by sending bodies of nothing but that count.
    granted, first_refusal = limit.take(len(parsed) + (1 if dropped else 0))
    kept = min(granted, len(parsed))
    logged = event_log.enabled()
    written: list[dict[str, Any]] = []
    for record in parsed[:kept]:
        attrs: dict[str, Any] = {**record["attrs"], "path": path} if path else record["attrs"]
        event_log.report(
            record["event"],
            record["name"],
            client=record["client"],
            dur_ms=record["dur_ms"],
            outcome=record["outcome"],
            attrs=attrs,
        )
        written.append({**record, "attrs": attrs})
    if first_refusal:
        event_log.mark(
            "browser",
            "browser.reports_rate_limited",
            limit=limit.limit,
            window_s=limit.window_s,
        )
    if dropped and granted > len(parsed):
        event_log.mark("browser", "browser.reports_dropped", client=page, dropped=dropped)
    return 200, {
        "accepted": len(written),
        "refused": refused,
        "rate_limited": len(parsed) - kept,
        "dropped_by_page": dropped,
        "logged": logged,
        "records": written,
    }


async def _bounded_body(request: Request) -> bytes | None:
    """The body, or ``None`` when it is longer than :data:`MAX_BODY_BYTES`."""

    declared = request.headers.get("content-length")
    if (
        declared is not None
        and declared.isascii()
        and declared.isdigit()
        and int(declared) > MAX_BODY_BYTES
    ):
        return None
    chunks: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > MAX_BODY_BYTES:
            return None
        chunks.append(chunk)
    return b"".join(chunks)


async def api_event_log_client(request: Request) -> JSONResponse:
    """Write a page's reports to the event log as ``browser`` records."""

    data = await _bounded_body(request)
    if data is None:
        return JSONResponse(
            {"error": f"a body is at most {MAX_BODY_BYTES} bytes", "code": "report_too_large"},
            status_code=413,
        )
    status, answer = accept(data)
    return JSONResponse(answer, status_code=status)


__all__ = [
    "FLUSH_MS",
    "FREEZE_MS",
    "MAX_BODY_BYTES",
    "MAX_DETAIL_KEYS",
    "MAX_REPORTS",
    "PAGE_REPORTS_PER_MINUTE",
    "RATE_LIMIT",
    "RATE_REPORTS",
    "RATE_WINDOW_S",
    "REPORT_EVENTS",
    "REPORT_OUTCOMES",
    "REPORT_ROUTE",
    "REPORT_TYPES",
    "SLOW_MS",
    "WAIT_LATE_MS",
    "RateLimit",
    "ReportError",
    "accept",
    "api_event_log_client",
    "browser_settings",
    "parse_body",
    "parse_report",
]
