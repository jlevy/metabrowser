"""The table source protocol: the types, wire contract, and bounds every table shares.

A *source* answers a small set of questions about one file that holds tables: what
tables it has, what their fields are, which rows match a query, what one record holds,
and a short card for one record. The built-in ``table`` plugin owns the routes that ask
them (``/api/plugin/table/{tables,schema,rows,record,card}``); a *source plugin*
declares, in its manifest, the adapter that answers them for one of its kinds::

    [plugin]
    requires = ["table"]

    [[table_source]]
    kind = "delimited"
    adapter = "metabrowser.builtin_plugins.delimited.source:adapter"

The adapter is a callable that takes a :class:`TableHandle` and returns a
:class:`TableSource`. It is recorded as text, imported on first use, and called
synchronously on the route threadpool, once per request, so a source keeps whatever it
caches in its own module, keyed by :meth:`TableSource.generation`.

This module is core so that core imports no plugin, and is re-exported from
:mod:`metabrowser.plugin_api` as SDK surface. The table routes and the CLI meet here:
:func:`open_table_source` resolves a path to its kind's adapter, and the ``*_wire``
functions are the JSON every route answers. The plan that specifies the protocol is
``docs/project/specs/active/plan-2026-11-19-tabular-data-and-live-sqlite.md``; the
author's reference is ``docs/plugins.md`` ("Table Sources").
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import hashlib
import importlib
import json
import math
import os
import re
import time
from collections.abc import Awaitable, Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol, cast, get_args

from metabrowser.content_errors import ContentReadError
from metabrowser.settings import SLOW_OPERATION_LOG_SECONDS
from metabrowser.source import (
    ContentRef,
    ContentWindow,
    get_source_session,
    read_content_window,
    resolve_content,
    resolve_content_container,
    resolve_session_identity,
)

# ── Bounds ─────────────────────────────────────────────────────
#
# Each bound caps one cost of one request. The numbers beside them were measured with
# `devtools/bench_table_source.py` on a shared 4-processor Linux container (Python 3.12,
# 2026-11-20), over synthetic CSV files; rerun it for the current numbers. What a
# browser pays to draw a page belongs to the table view, which measures it when it
# arrives.

# Rows per page when a query names no `limit`, and the most a `limit` may ask for.
# Encoding a page is linear in its rows: 100 short rows encoded in 4 to 10 ms as 25 KB
# of JSON, and 1,000 in 13 to 29 ms as 0.25 MB. A table view windows its rows and asks
# for about a screen at a time; the maximum is for a reader paging from the CLI.
TABLE_PAGE_ROWS_DEFAULT = 100
TABLE_PAGE_ROWS_MAX = 1000

# Cells in one page: a page of wide rows carries fewer of them (`page_row_limit`), and
# the envelope's `limit` says how many it allowed. A page's cost follows its cells, not
# its rows: 1,000 rows of 12 cells, each cell cut at the preview bound, is this many
# cells, and it encoded in 24 to 39 ms as 5.3 MB of JSON, the largest page the row
# bounds above admit at that width; a wider table pays no more per page.
TABLE_PAGE_CELLS_MAX = 12_000

# Characters of one text cell a page carries; a longer value is a `{text, length}`
# envelope cut here, and the record shows more. A page of 1,000 rows whose 12 cells all
# passed this bound encoded in 24 to 30 ms as 5.3 MB of JSON, so the bound keeps the
# largest page of long text within about 20 times a page of short cells, while still
# carrying more than a two-line clamp shows.
TABLE_CELL_PREVIEW_CHARS = 400

# UTF-8 bytes of one value a record carries; a longer value is cut here, never inside a
# character. A record of 12 values all past this bound encoded in 1 to 2 ms as 0.79 MB.
TABLE_RECORD_VALUE_BYTES = 64 * 1024

# Characters in a key or cursor token. A token travels in a URL's query, and uvicorn's
# HTTP/1.1 parser (h11) refuses a request whose line and headers pass 16 KiB, so this
# leaves a link room for several tokens, a path, and filters. A key or cursor that would
# encode longer is named by position instead, valid for one generation.
TABLE_TOKEN_MAX_CHARS = 1024

# Wall-clock budget for the work of one request: a scan stops at it and answers
# `complete: false` with the rows it examined, and a sort whose index is not built yet
# is refused past it (`sort_budget`), instead of holding a threadpool worker. It counts
# from when the route accepts the request, so a parse spends from it too. It is the
# server's slow-request threshold, the latency the server already reports as too long;
# what a delimited file can cost within it is measured beside that source's bounds.
TABLE_REQUEST_DEADLINE_SECONDS = SLOW_OPERATION_LOG_SECONDS

# Fields a hover card shows besides its label: a summary, not the record. It is set by
# what a card shows, not by cost: a card's cells are previewed as a page's are, so one
# card costs no more than one row of a page seven fields wide.
TABLE_CARD_MAX_FIELDS = 6

# The largest integer a browser number holds exactly; a larger one travels as
# `{int: "<decimal>"}`.
MAX_SAFE_INTEGER = 2**53 - 1

# ── Vocabulary ─────────────────────────────────────────────────

FieldType = Literal[
    "text", "integer", "real", "boolean", "date", "datetime", "json", "blob", "unknown"
]
FIELD_TYPES: tuple[FieldType, ...] = get_args(FieldType)
TableGroup = Literal["tables", "views", "virtual", "internal"]
TABLE_GROUPS: tuple[TableGroup, ...] = get_args(TableGroup)
FilterOp = Literal["eq", "ne", "lt", "le", "gt", "ge", "null", "notnull", "contains"]
FILTER_OPS: tuple[FilterOp, ...] = get_args(FilterOp)
# Operators that take no value: `f.x=null:` and `f.x=null` both mean "x is null".
VALUELESS_OPS: frozenset[FilterOp] = frozenset({"null", "notnull"})
Order = Literal["asc", "desc"]

# Why a page is not complete, or why it has no rows.
#  - `budget`: a filter or search on a query with no `sort` ran out of
#    `TABLE_REQUEST_DEADLINE_SECONDS`; the rows it found come back in the query's order
#    with the number it examined, and `next_after` continues among them.
#  - `sort_budget`: the query's sort could not be done within the budget, because the
#    scan before it or the sort itself ran out. A sort cannot be returned in part, so
#    the page has no rows and `sort_refused` names the field.
#  - `source_truncated`: the source read only part of its content (a delimited file past
#    one of its parse bounds), so a count, sort, or filter covers only that part.
#  - `cursor_expired`: a positional cursor was minted under an earlier generation.
PageReason = Literal["budget", "sort_budget", "source_truncated", "cursor_expired"]

# A JSON value: a scalar cell, or one of the envelopes the cell helpers below build.
Cell = Any

# A generation is an opaque token of these characters, so it can follow a positional
# cursor's `.` without escaping.
_GENERATION = re.compile(r"^[A-Za-z0-9_-]+$")


# ── Errors ─────────────────────────────────────────────────────


class TableSourceError(Exception):
    """A request a source cannot answer, with the code and status the route sends."""

    code = "table_error"
    http_status = 400

    def __init__(self, message: str, **details: Any) -> None:
        super().__init__(message)
        self.details = details


class TableNotFoundError(TableSourceError):
    code = "table_not_found"
    http_status = 404


class RecordNotFoundError(TableSourceError):
    code = "record_not_found"
    http_status = 404


class TableQueryError(TableSourceError):
    """A query parameter is malformed, or names a field the schema refuses it for."""

    code = "bad_query"
    http_status = 400


class SourceUnreadableError(TableSourceError):
    """The content is there, but the source cannot read it as tables."""

    code = "source_unreadable"
    http_status = 422


class TablePathNotFoundError(TableSourceError):
    """Nothing readable is at the path."""

    code = "not_found"
    http_status = 404


class NoTableSourceError(TableSourceError):
    """The file at the path is of a kind no plugin serves as tables."""

    code = "not_a_table_source"
    http_status = 404


# ── Protocol types ─────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class FieldRef:
    """A reference between tables: `fields` on one side name the rows whose `to` fields
    hold the same values on `table`. Field lists on both sides, so a composite foreign key
    is one reference. An incoming reference lists the referring table and its fields."""

    table: str
    fields: tuple[str, ...]
    to: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TableField:
    """One field descriptor, which decides a column, its sort and filter, its formatting,
    and its place in the record. A source fills in what it knows and leaves the rest None,
    and the client derives nothing a source could have stated."""

    name: str
    type: FieldType
    title: str | None = None
    declared_type: str | None = None
    nullable: bool | None = None
    key: bool = False
    hidden: bool | None = None
    generated: bool | None = None
    list: bool = False
    enum: tuple[str, ...] | None = None
    format: str | None = None
    ref: FieldRef | None = None
    sortable: bool = False
    sort_note: str | None = None
    filterable: bool = False
    numeric: bool = False
    description: str | None = None


@dataclass(frozen=True, slots=True)
class TableInfo:
    """One table a source holds. `id` is "" for a source that is its own single table.
    `keyed` says whether rows have a stable key; a keyless table names rows by position.
    `estimate` is a cheap row count where the source has one, never a count."""

    id: str
    label: str
    group: TableGroup
    keyed: bool
    estimate: int | None = None


@dataclass(frozen=True, slots=True)
class TableSchema:
    table: str
    fields: tuple[TableField, ...]
    key: tuple[str, ...]
    default_columns: tuple[str, ...]
    references: tuple[FieldRef, ...] = ()
    referenced_by: tuple[FieldRef, ...] = ()

    def field_named(self, name: str) -> TableField | None:
        return next((item for item in self.fields if item.name == name), None)


@dataclass(frozen=True, slots=True)
class Filter:
    field: str
    op: FilterOp
    value: str | None


@dataclass(frozen=True, slots=True)
class RefFilter:
    """Rows that reference one record, optionally through one declared relationship."""

    table: str
    key: str
    via: tuple[tuple[str, ...], tuple[str, ...]] | None = None

    def matches(self, reference: FieldRef) -> bool:
        return reference.table == self.table and (
            self.via is None or self.via == (reference.fields, reference.to)
        )


@dataclass(frozen=True, slots=True)
class TableQuery:
    """One wire shape for every source. Sort is one sortable field, with the row key (or
    position) as a tie-breaker in the same direction, so paging is stable."""

    sort: str | None = None
    order: Order = "asc"
    q: str | None = None
    filters: tuple[Filter, ...] = ()
    ref: RefFilter | None = None
    cols: tuple[str, ...] | None = None
    after: str | None = None
    limit: int = TABLE_PAGE_ROWS_DEFAULT


@dataclass(frozen=True, slots=True)
class TableRow:
    """One row: its key token (`@<n>` when named by position) and its cells by field.
    A field missing from `cells` is absent, which a source distinguishes from null."""

    key: str
    cells: Mapping[str, Cell]


@dataclass(frozen=True, slots=True)
class TablePage:
    """One page in the collection envelope.

    `complete` says whether the rows this query defines were all considered: false when
    a budget ran out, when the source read only part of its content, or when a cursor
    expired, and `reason` says which. `truncated` says the source's content was cut.
    `count` is exact when `count_complete`, and otherwise a lower bound; `estimate` is a
    cheap approximate total a source may send beside or instead of it. `skipped` counts
    values a filter or search could not examine, and `examined` the rows a scan reached
    before its budget ran out. `searched` names the fields a search looked in.

    Rows always come in the order the query asked for: a page whose sort could not be
    done has none (`reason == "sort_budget"`, with `sort_refused` naming the field).
    `limit` is the number of rows the page allowed, which is less than the query's when
    `TABLE_PAGE_ROWS_MAX` or `TABLE_PAGE_CELLS_MAX` bound it."""

    rows: tuple[TableRow, ...]
    columns: tuple[str, ...]
    next_after: str | None
    complete: bool
    truncated: bool
    generation: str
    count: int | None
    count_complete: bool
    estimate: int | None = None
    skipped: int = 0
    examined: int | None = None
    searched: tuple[str, ...] | None = None
    reason: PageReason | None = None
    sort_refused: str | None = None
    limit: int | None = None


@dataclass(frozen=True, slots=True)
class BackrefCount:
    """How many rows of one referring table point at a record."""

    ref: FieldRef
    count: int
    count_complete: bool


@dataclass(frozen=True, slots=True)
class TableRecord:
    key: str
    cells: Mapping[str, Cell]
    generation: str
    positional: bool
    referenced_by: tuple[BackrefCount, ...] = ()
    label: str | None = None
    source_path: str | None = None
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class TableCard:
    key: str
    label: Cell
    cells: Mapping[str, Cell]
    generation: str


@dataclass(frozen=True, slots=True)
class Budget:
    """The wall-clock budget of one request, counted from when the route accepted it."""

    deadline: float

    @classmethod
    def start(cls, seconds: float = TABLE_REQUEST_DEADLINE_SECONDS) -> Budget:
        return cls(deadline=time.monotonic() + seconds)

    def expired(self) -> bool:
        return time.monotonic() >= self.deadline


@dataclass(frozen=True, slots=True)
class TableHandle:
    """The bounded handle an adapter reads one file through.

    `ref` is the content reference every data hook reads through, on a served folder and
    on a Git pin alike. `name` is the file's name as the reader sees it, the last segment
    of its path, for a label. `local_path` is the resolved real path of a file on the served
    folder, for a source that must open the file itself; it is None on a pin.
    :meth:`read_window` is the synchronous form of
    :func:`~metabrowser.source.read_content_window` for an adapter running on the route
    threadpool: it runs the read on the server's event loop and waits for it.
    """

    ref: ContentRef
    name: str
    local_path: Path | None
    loop: asyncio.AbstractEventLoop = field(repr=False, compare=False)

    def read_window(self, *, offset: int = 0, max_bytes: int) -> ContentWindow:
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is self.loop:
            raise RuntimeError("TableHandle.read_window blocks; call it off the event loop")
        future = asyncio.run_coroutine_threadsafe(
            read_content_window(self.ref, offset=offset, max_bytes=max_bytes), self.loop
        )
        return future.result()


@dataclass(frozen=True, slots=True)
class FolderTableHandle:
    """A served directory selected for a folder table source."""

    identity: str
    path: Path
    root: Path
    wait: bool = False


class TableSource(Protocol):
    """What a source answers for one file. Every method is synchronous and bounded."""

    def generation(self) -> str:
        """An opaque token that changes whenever the content may have changed. It only
        stats files and reads bounded headers; every other method samples it before
        reading, so a change during a read costs one extra refetch, never a lost one."""
        ...

    def tables(self) -> Sequence[TableInfo]: ...

    def schema(self, table: str) -> TableSchema: ...

    def rows(self, table: str, query: TableQuery, budget: Budget) -> TablePage: ...

    def record(self, table: str, key: str, budget: Budget) -> TableRecord: ...

    def card(self, table: str, key: str, budget: Budget) -> TableCard: ...


TableSourceAdapter = Callable[[TableHandle], TableSource]
FolderTableSourceAdapter = Callable[[FolderTableHandle], TableSource]


# ── Generations ────────────────────────────────────────────────


def stat_generation(path: Path) -> str:
    """A generation from one ``stat``: the file's identity, size, and modification time.

    Identity (device and inode) catches a file replaced by a rename that kept its size
    and time. Raises ``OSError`` when the file is gone.
    """

    info = os.stat(path)
    material = f"{info.st_dev}:{info.st_ino}:{info.st_size}:{info.st_mtime_ns}"
    return hashlib.sha256(material.encode()).hexdigest()[:16]


def content_generation(handle: TableHandle) -> str:
    """The generation of a handle's content as one file: :func:`stat_generation` on the
    served folder, and the blob's object id on a pin, whose content cannot change."""

    if handle.local_path is not None:
        try:
            return stat_generation(handle.local_path)
        except OSError as exc:
            raise SourceUnreadableError("This file is no longer available.") from exc
    fingerprint = re.sub(r"[^A-Za-z0-9_-]", "_", handle.ref.fingerprint)
    return fingerprint or "0"


# ── Cells ──────────────────────────────────────────────────────


def integer_cell(value: int) -> Cell:
    """An integer, or `{int: "<decimal>"}` past what a browser number holds exactly."""

    if -MAX_SAFE_INTEGER <= value <= MAX_SAFE_INTEGER:
        return value
    return {"int": str(value)}


def real_cell(value: float) -> Cell:
    """A real, or `{real: "inf" | "-inf" | "nan"}` for a value JSON cannot carry."""

    if math.isfinite(value):
        return value
    if math.isnan(value):
        return {"real": "nan"}
    return {"real": "inf" if value > 0 else "-inf"}


def cut_utf8(text: str, max_bytes: int) -> str:
    """The longest prefix of *text* whose UTF-8 encoding fits *max_bytes*, never ending
    inside a character: an incomplete trailing sequence is dropped."""

    encoded = text.encode("utf-8", errors="surrogatepass")
    if len(encoded) <= max_bytes:
        return text
    return encoded[:max_bytes].decode("utf-8", errors="ignore")


def text_cell(
    text: str,
    *,
    max_chars: int | None = None,
    max_bytes: int | None = None,
    invalid_utf8: bool = False,
) -> Cell:
    """A text value, cut at *max_chars* characters or *max_bytes* UTF-8 bytes.

    A value that fits and was valid is the plain string. Otherwise it is
    `{text, length?, invalid_utf8?}`: `length` (the whole value's length in characters)
    is present when the value was cut, and `invalid_utf8` when its bytes were not valid
    in their encoding and were decoded with replacement characters.
    """

    shown = text
    if max_chars is not None and len(shown) > max_chars:
        shown = shown[:max_chars]
    if max_bytes is not None:
        shown = cut_utf8(shown, max_bytes)
    cut = len(shown) < len(text)
    if not cut and not invalid_utf8:
        return text
    envelope: dict[str, Any] = {"text": shown}
    if cut:
        envelope["length"] = len(text)
    if invalid_utf8:
        envelope["invalid_utf8"] = True
    return envelope


def blob_cell(data: bytes, *, length: int | None = None, max_bytes: int) -> Cell:
    """Bytes as `{blob: true, length, hex}`: the hex of at most *max_bytes* of them, and
    `length`, the whole value's size in bytes, which is *length* when *data* is already
    only a part of it."""

    return {
        "blob": True,
        "length": len(data) if length is None else length,
        "hex": data[:max_bytes].hex(),
    }


def stored_cell(value: Cell, stored: FieldType) -> Cell:
    """A value whose stored type differs from its field's declared type, shown as stored
    rather than coerced: `{value, stored}`."""

    return {"value": value, "stored": stored}


# ── Tokens: keys, positions, and cursors ───────────────────────
#
# A key or cursor is stateless and deterministic: the same key value or sort position
# encodes to the same token under any generation and any server process, so a link
# holding one reproduces the view. Formats, each opaque to the client:
#   `k.<base64url JSON>`   a record key a keyed source minted
#   `c.<base64url JSON>`   a cursor naming a position in sort order
#   `@<n>`                 a row named by its 1-based position
#   `@<n>.<generation>`    a cursor past `TABLE_TOKEN_MAX_CHARS`, valid for one generation


# Digits of a position or a count in a token or a `limit`: a 64-bit integer's. A longer
# digit string names nothing a source holds, and is refused before `int()`, whose cost
# grows with the digits and which refuses past the interpreter's digit limit.
_MAX_DIGITS = 18


def _pack(prefix: str, values: Sequence[Any]) -> str | None:
    payload = json.dumps(list(values), separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    token = prefix + base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii").rstrip("=")
    return token if len(token) <= TABLE_TOKEN_MAX_CHARS else None


def _unpack(prefix: str, token: str, what: str) -> list[Any]:
    if len(token) > TABLE_TOKEN_MAX_CHARS or not token.startswith(prefix):
        raise TableQueryError(f"{what} is not a token this server minted", param=what)
    body = token[len(prefix) :]
    try:
        raw = base64.urlsafe_b64decode(body + "=" * (-len(body) % 4))
        values = json.loads(raw.decode("utf-8"))
    except (binascii.Error, UnicodeDecodeError, ValueError) as exc:
        raise TableQueryError(f"{what} is not a token this server minted", param=what) from exc
    if not isinstance(values, list):
        raise TableQueryError(f"{what} is not a token this server minted", param=what)
    return cast(list[Any], values)


def encode_key(values: Sequence[Any]) -> str | None:
    """A record key token for a keyed row, or None when it would pass the bound and the
    row must be named by position instead."""

    return _pack("k.", values)


def decode_key(token: str) -> list[Any]:
    return _unpack("k.", token, "key")


def encode_cursor(values: Sequence[Any]) -> str | None:
    """A cursor naming a position in sort order, or None past the bound."""

    return _pack("c.", values)


def decode_cursor(token: str) -> list[Any]:
    return _unpack("c.", token, "after")


def position_key(position: int) -> str:
    """The name of the row at a 1-based position."""

    return f"@{position}"


def parse_position_key(key: str) -> int | None:
    """The 1-based position a `@<n>` key names, or None for any other token."""

    if not key.startswith("@"):
        return None
    digits = key[1:]
    if (
        not digits.isdigit()
        or not digits.isascii()
        or len(digits) > _MAX_DIGITS
        or (len(digits) > 1 and digits[0] == "0")
    ):
        raise RecordNotFoundError(f"{key!r} names no row", key=key)
    position = int(digits)
    if position < 1:
        raise RecordNotFoundError(f"{key!r} names no row", key=key)
    return position


def positional_cursor(served: int, generation: str) -> str:
    """A cursor past the token bound: the number of rows already served in the query's
    order, valid only under the generation it was minted in."""

    return f"@{served}.{generation}"


def parse_positional_cursor(after: str) -> tuple[int, str] | None:
    """`(served, generation)` from a positional cursor, or None for a `c.` cursor."""

    if not after.startswith("@"):
        return None
    served, dot, generation = after[1:].partition(".")
    if (
        not dot
        or not served.isdigit()
        or not served.isascii()
        or len(served) > _MAX_DIGITS
        or not _GENERATION.match(generation)
    ):
        raise TableQueryError("after is not a token this server minted", param="after")
    return int(served), generation


# ── Query grammar ──────────────────────────────────────────────

# Parameters the routes read; any other parameter except `f.<field>` is refused, so a
# misspelled one is an error rather than a silently ignored filter.
_QUERY_PARAMS = frozenset({"sort", "order", "q", "ref", "via", "cols", "after", "limit"})
_ROUTE_PARAMS = frozenset({"path", "table", "key", "generation", "wait"})


def parse_table_query(items: Iterable[tuple[str, str]]) -> TableQuery:
    """Parse the rows route's query: `sort`, `order`, `q`, `f.<field>=<op>:<value>`,
    `ref=<table>:<key>`, `via`, `cols`, `after`, and `limit`. Field names are checked against
    the schema by :func:`check_table_query`.

    `cols` names one field per parameter and repeats, in page order (`cols=a&cols=b`),
    since a field name may hold any character, a comma among them. Every other
    parameter is given at most once. `ref` splits at its last colon, since a key token
    has none and a table name may. `via` is a JSON array of the two field lists
    in a declared relationship and requires `ref`."""

    single: dict[str, str] = {}
    filters: list[Filter] = []
    cols_given: list[str] = []
    for name, value in items:
        if name.startswith("f."):
            filters.append(_parse_filter(name[2:], value))
            continue
        if name in _ROUTE_PARAMS:
            continue
        if name not in _QUERY_PARAMS:
            raise TableQueryError(f"unknown query parameter {name!r}", param=name)
        if name == "cols":
            if not value:
                raise TableQueryError("cols names no field", param="cols")
            cols_given.append(value)
            continue
        if name in single:
            raise TableQueryError(f"{name} is given more than once", param=name)
        single[name] = value
    order = single.get("order", "asc") or "asc"
    if order not in ("asc", "desc"):
        raise TableQueryError("order must be asc or desc", param="order")
    limit = _parse_limit(single.get("limit", ""))
    ref: RefFilter | None = None
    raw_ref = single.get("ref", "")
    if raw_ref:
        table, colon, key = raw_ref.rpartition(":")
        if not colon or not key:
            raise TableQueryError("ref must be <table>:<key>", param="ref")
        via = _parse_via(single["via"]) if "via" in single else None
        ref = RefFilter(table=table, key=key, via=via)
    elif "via" in single:
        raise TableQueryError("via requires a reference filter", param="via")
    cols = tuple(cols_given) if cols_given else None
    return TableQuery(
        sort=single.get("sort") or None,
        order=order,
        q=single.get("q") or None,
        filters=tuple(filters),
        ref=ref,
        cols=cols,
        after=single.get("after") or None,
        limit=limit,
    )


def _parse_via(raw: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    error = TableQueryError("via must contain the two field lists of a relationship", param="via")
    try:
        pair: Any = json.loads(raw)
    except (ValueError, RecursionError) as exc:
        raise error from exc
    if (
        not isinstance(pair, list)
        or len(pair) != 2
        or not all(isinstance(group, list) and group for group in pair)
        or not all(isinstance(name, str) for group in pair for name in group)
        or len(pair[0]) != len(pair[1])
    ):
        raise error
    return tuple(pair[0]), tuple(pair[1])


def _parse_limit(raw: str) -> int:
    """A `limit`: a positive integer, clamped to `TABLE_PAGE_ROWS_MAX`."""

    if not raw:
        return TABLE_PAGE_ROWS_DEFAULT
    digits = raw.lstrip("0")
    if not raw.isdigit() or not raw.isascii() or not digits:
        raise TableQueryError("limit must be a positive integer", param="limit")
    if len(digits) > _MAX_DIGITS:
        return TABLE_PAGE_ROWS_MAX
    return min(int(digits), TABLE_PAGE_ROWS_MAX)


def page_row_limit(limit: int, cells_per_row: int) -> int:
    """The rows a page may carry: the query's `limit`, fewer when rows of
    *cells_per_row* cells would pass `TABLE_PAGE_CELLS_MAX`, and always at least one."""

    return max(1, min(limit, TABLE_PAGE_CELLS_MAX // max(1, cells_per_row)))


def _parse_filter(field_name: str, raw: str) -> Filter:
    if not field_name:
        raise TableQueryError("a filter names no field", param="f.")
    op, colon, value = raw.partition(":")
    if op not in FILTER_OPS:
        raise TableQueryError(
            f"filter on {field_name!r} has no operator; use one of {', '.join(FILTER_OPS)}",
            param=f"f.{field_name}",
        )
    typed_op: FilterOp = op
    if typed_op in VALUELESS_OPS:
        if value:
            raise TableQueryError(f"{op} takes no value", param=f"f.{field_name}")
        return Filter(field=field_name, op=typed_op, value=None)
    if not colon:
        raise TableQueryError(f"{op} needs a value: {op}:<value>", param=f"f.{field_name}")
    return Filter(field=field_name, op=typed_op, value=value)


def check_table_query(query: TableQuery, schema: TableSchema) -> None:
    """Refuse a query that names a field the schema does not have, sorts a field that is
    not sortable, filters one that is not filterable, or asks for rows referencing a table
    no field of this one points at."""

    if query.sort is not None:
        sort_field = _known_field(schema, query.sort, "sort")
        if not sort_field.sortable:
            raise TableQueryError(
                f"field {query.sort!r} is not sortable"
                + (f": {sort_field.sort_note}" if sort_field.sort_note else ""),
                param="sort",
                field=query.sort,
            )
    for item in query.filters:
        target = _known_field(schema, item.field, f"f.{item.field}")
        if not target.filterable:
            raise TableQueryError(
                f"field {item.field!r} is not filterable", param=f"f.{item.field}"
            )
    for name in query.cols or ():
        _known_field(schema, name, "cols")
    if query.ref is not None and not any(query.ref.matches(ref) for ref in schema.references):
        if query.ref.via is not None:
            raise TableQueryError("via does not name a declared relationship", param="via")
        raise TableQueryError(f"no field of this table references {query.ref.table!r}", param="ref")


def _known_field(schema: TableSchema, name: str, param: str) -> TableField:
    found = schema.field_named(name)
    if found is None:
        raise TableQueryError(f"no field named {name!r}", param=param, field=name)
    return found


def coerce_filter_value(target: TableField, raw: str) -> str | int | float | bool:
    """A filter value typed by its field, so `gt:9` compares numbers on a numeric field.
    A value that is not of the field's type is refused."""

    param = f"f.{target.name}"
    if target.type == "integer":
        try:
            return int(raw)
        except ValueError as exc:
            raise TableQueryError(f"{raw!r} is not an integer", param=param) from exc
    if target.type == "real":
        try:
            return float(raw)
        except ValueError as exc:
            raise TableQueryError(f"{raw!r} is not a number", param=param) from exc
    if target.type == "boolean":
        lowered = raw.lower()
        if lowered not in ("true", "false"):
            raise TableQueryError(f"{raw!r} is not true or false", param=param)
        return lowered == "true"
    return raw


def page_columns(query: TableQuery, schema: TableSchema) -> tuple[str, ...]:
    """The fields a page carries: the query's `cols`, else the schema's defaults."""

    return query.cols if query.cols is not None else schema.default_columns


# ── Wire contract ──────────────────────────────────────────────


def _ref_wire(ref: FieldRef) -> dict[str, Any]:
    return {"table": ref.table, "fields": list(ref.fields), "to": list(ref.to)}


def field_wire(item: TableField) -> dict[str, Any]:
    return {
        "name": item.name,
        "title": item.title,
        "type": item.type,
        "declared_type": item.declared_type,
        "nullable": item.nullable,
        "key": item.key,
        "hidden": item.hidden,
        "generated": item.generated,
        "list": item.list,
        "enum": list(item.enum) if item.enum is not None else None,
        "format": item.format,
        "ref": _ref_wire(item.ref) if item.ref is not None else None,
        "sortable": item.sortable,
        "sort_note": item.sort_note,
        "filterable": item.filterable,
        "numeric": item.numeric,
        **({"description": item.description} if item.description else {}),
    }


def tables_wire(
    path: str, generation: str, tables: Sequence[TableInfo], *, folder: bool = False
) -> dict[str, Any]:
    return {
        "type": "table_list",
        "path": path,
        "generation": generation,
        "tables": [
            {
                "id": info.id,
                "label": info.label,
                "group": info.group,
                "keyed": info.keyed,
                "estimate": info.estimate,
                "path": path if folder else table_address(path, info.id),
            }
            for info in tables
        ],
    }


def schema_wire(path: str, generation: str, schema: TableSchema) -> dict[str, Any]:
    return {
        "type": "table_schema",
        "path": path,
        "table": schema.table,
        "generation": generation,
        "key": list(schema.key),
        "default_columns": list(schema.default_columns),
        "fields": [field_wire(item) for item in schema.fields],
        "references": [_ref_wire(ref) for ref in schema.references],
        "referenced_by": [_ref_wire(ref) for ref in schema.referenced_by],
    }


def page_wire(path: str, table: str, page: TablePage) -> dict[str, Any]:
    """The rows route's answer: the collection envelope's five keys (`rows`,
    `next_after`, `complete`, `truncated`, `generation`) and the table's own."""

    return {
        "type": "table_rows",
        "path": path,
        "table": table,
        "generation": page.generation,
        "columns": list(page.columns),
        "rows": [{"key": row.key, "cells": dict(row.cells)} for row in page.rows],
        "next_after": page.next_after,
        "complete": page.complete,
        "truncated": page.truncated,
        "reason": page.reason,
        "count": page.count,
        "count_complete": page.count_complete,
        "estimate": page.estimate,
        "skipped": page.skipped,
        "examined": page.examined,
        "searched": list(page.searched) if page.searched is not None else None,
        "sort_refused": page.sort_refused,
        "limit": page.limit,
    }


def record_wire(
    path: str, table: str, record: TableRecord, *, requested_generation: str | None
) -> dict[str, Any]:
    """The record route's answer. A record named by position is `positional`, and when
    the request names the generation its key was read under, `generation_moved` says
    whether the content has changed since, so the row at that position may be another."""

    return {
        "type": "table_record",
        "path": path,
        "table": table,
        "key": record.key,
        "positional": record.positional,
        "generation": record.generation,
        "generation_moved": (
            requested_generation != record.generation if requested_generation else None
        ),
        "cells": dict(record.cells),
        **({"label": record.label} if record.label else {}),
        **({"source_path": record.source_path} if record.source_path is not None else {}),
        **({"diagnostics": list(record.diagnostics)} if record.diagnostics else {}),
        "referenced_by": [
            {**_ref_wire(item.ref), "count": item.count, "count_complete": item.count_complete}
            for item in record.referenced_by
        ],
    }


def card_wire(path: str, table: str, card: TableCard) -> dict[str, Any]:
    return {
        "type": "table_card",
        "path": path,
        "table": table,
        "key": card.key,
        "generation": card.generation,
        "label": card.label,
        "cells": dict(card.cells),
    }


def error_wire(path: str, exc: TableSourceError) -> dict[str, Any]:
    """A refusal: the envelope's own keys, then its details, which cannot replace them."""

    wire: dict[str, Any] = {
        "type": "table_error",
        "path": path,
        "code": exc.code,
        "error": str(exc),
    }
    wire.update((name, value) for name, value in exc.details.items() if name not in wire)
    return wire


def table_address(path: str, table: str) -> str:
    """The address of one table: the source's own path for its single table (`""`)."""

    return path if not table else f"{path}/{table}"


# ── Registration ───────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class TableSourceDeclaration:
    """One `[[table_source]]`: the plugin that declared it, its kind, and its adapter."""

    plugin: str
    kind: str
    adapter: str
    offer: str | None = None


ContentKindClassifier = Callable[[ContentRef], Awaitable[str | None]]


@dataclass
class _Registry:
    declarations: dict[str, TableSourceDeclaration] = field(
        default_factory=dict[str, TableSourceDeclaration]
    )
    classify: ContentKindClassifier | None = None
    container_kinds: frozenset[str] = frozenset()
    adapters: dict[str, TableSourceAdapter] = field(default_factory=dict[str, TableSourceAdapter])
    folder_sources: tuple[TableSourceDeclaration, ...] = ()


_REGISTRY = _Registry()


def install_table_sources(
    declarations: Iterable[TableSourceDeclaration],
    classify: ContentKindClassifier,
    *,
    container_kinds: Iterable[str] = (),
) -> None:
    """Install the sources the server serves and the classifier that picks one.

    The server calls this once, after discovery, with the declarations of every plugin
    allowed to run Python. A later declaration for a kind replaces an earlier one, as a
    later view with an id replaces an earlier one. Only declared container kinds can
    address tables as file children.
    """

    sources = tuple(declarations)
    _REGISTRY.declarations = {item.kind: item for item in sources if item.kind != "folder"}
    _REGISTRY.folder_sources = tuple(item for item in sources if item.kind == "folder")
    _REGISTRY.classify = classify
    _REGISTRY.container_kinds = frozenset(container_kinds)
    _REGISTRY.adapters = {}


def load_adapter(declaration: TableSourceDeclaration) -> TableSourceAdapter:
    """Import a declaration's adapter once; an import failure propagates to the caller."""

    loaded = _REGISTRY.adapters.get(declaration.kind)
    if loaded is not None:
        return loaded
    module_name, _, attr = declaration.adapter.partition(":")
    adapter = getattr(importlib.import_module(module_name), attr)
    if not callable(adapter):
        raise TypeError(f"table source adapter {declaration.adapter} is not callable")
    typed = cast(TableSourceAdapter, adapter)
    _REGISTRY.adapters[declaration.kind] = typed
    return typed


@dataclass(frozen=True, slots=True)
class OpenedTableSource:
    """A path resolved to its content, its kind, and the source that kind's adapter made.
    `table` is the table the path names: "" for the content itself, and otherwise the
    inner path of a container child, `<file>/<table>`, as the source's table ids name
    its tables."""

    identity: str
    kind: str
    source: TableSource
    table: str
    folder: bool = False

    @property
    def address(self) -> str:
        """The address the path named: the table's own (:func:`table_address`)."""

        return self.identity if self.folder else table_address(self.identity, self.table)


def _open_folder_table_source(
    path: str, table: str | None, root: Path, wait: bool
) -> OpenedTableSource | None:
    target = resolve_session_identity(path)
    if target is None or not target.is_dir():
        return None
    handle = FolderTableHandle(path, target, root, wait)
    for declaration in _REGISTRY.folder_sources:
        if declaration.offer is None:
            continue
        module, _, name = declaration.offer.partition(":")
        offer = getattr(importlib.import_module(module), name)
        if not offer(target):
            continue
        module, _, name = declaration.adapter.partition(":")
        adapter = cast(FolderTableSourceAdapter, getattr(importlib.import_module(module), name))
        return OpenedTableSource(path, "folder", adapter(handle), table or "", folder=True)
    return None


async def open_table_source(
    path: str, *, selected_table: str | None = None, wait: bool = False
) -> OpenedTableSource:
    """Resolve *path* to a table source: the content there, the kind it classifies as,
    and that kind's adapter applied to a handle on it.

    A path under a file of a declared container kind, `<file>/<table>`, names a table
    inside that file as the tree addresses it. The file's kind picks the
    source, whatever its extension, and the source answers for `<table>` or refuses it
    with :class:`TableNotFoundError`. Raises :class:`TablePathNotFoundError` when nothing
    readable is there and :class:`NoTableSourceError` when its kind has no source, and
    lets a content read's :class:`~metabrowser.content_errors.ContentReadError`
    propagate.
    """

    root = get_source_session().subject.filesystem_root
    if root is not None and _REGISTRY.folder_sources:
        folder = await asyncio.to_thread(
            _open_folder_table_source, path, selected_table, root, wait
        )
        if folder is not None:
            return folder
    if selected_table is not None or wait:
        param = "table" if selected_table is not None else "wait"
        raise TableQueryError(f"{param} is only accepted for a folder table source", param=param)
    table = ""
    ref = await resolve_content(path)
    if ref is None:
        child = await resolve_content_container(path, suffixes=None)
        if child is None or not child[1]:
            raise TablePathNotFoundError("Not found")
        ref, table = child
    classify = _REGISTRY.classify
    kind = await classify(ref) if classify is not None else None
    declaration = _REGISTRY.declarations.get(kind or "")
    if table and (declaration is None or declaration.kind not in _REGISTRY.container_kinds):
        raise TablePathNotFoundError("Not found")
    if declaration is None:
        raise NoTableSourceError(f"files of kind {kind!r} are not tables", kind=kind)
    adapter = load_adapter(declaration)
    handle = TableHandle(
        ref=ref,
        name=_display_name(ref),
        # Resolving a real path stats the filesystem, so it runs off the event loop.
        local_path=await asyncio.to_thread(_local_path, ref),
        loop=asyncio.get_running_loop(),
    )
    return OpenedTableSource(
        identity=ref.identity, kind=kind or "", source=adapter(handle), table=table
    )


def _display_name(ref: ContentRef) -> str:
    if get_source_session().subject.filesystem_root is not None:
        return ref.identity.rsplit("/", 1)[-1]
    from metabrowser.git.tree_source import GitPath, GitPathError

    try:
        return GitPath.from_wire(ref.identity).display().rsplit("/", 1)[-1]
    except GitPathError:
        return ref.identity


def _local_path(ref: ContentRef) -> Path | None:
    if get_source_session().subject.filesystem_root is None:
        return None
    try:
        target = resolve_session_identity(ref.identity)
    except ContentReadError:
        return None
    return target.resolve() if target is not None else None


__all__ = [
    "FIELD_TYPES",
    "FILTER_OPS",
    "MAX_SAFE_INTEGER",
    "TABLE_CARD_MAX_FIELDS",
    "TABLE_CELL_PREVIEW_CHARS",
    "TABLE_GROUPS",
    "TABLE_PAGE_CELLS_MAX",
    "TABLE_PAGE_ROWS_DEFAULT",
    "TABLE_PAGE_ROWS_MAX",
    "TABLE_RECORD_VALUE_BYTES",
    "TABLE_REQUEST_DEADLINE_SECONDS",
    "TABLE_TOKEN_MAX_CHARS",
    "VALUELESS_OPS",
    "BackrefCount",
    "Budget",
    "Cell",
    "FieldRef",
    "FolderTableHandle",
    "FolderTableSourceAdapter",
    "FieldType",
    "Filter",
    "FilterOp",
    "NoTableSourceError",
    "OpenedTableSource",
    "Order",
    "PageReason",
    "RecordNotFoundError",
    "RefFilter",
    "SourceUnreadableError",
    "TableCard",
    "TableField",
    "TableGroup",
    "TableHandle",
    "TableInfo",
    "TableNotFoundError",
    "TablePathNotFoundError",
    "TablePage",
    "TableQuery",
    "TableQueryError",
    "TableRecord",
    "TableRow",
    "TableSchema",
    "TableSource",
    "TableSourceAdapter",
    "TableSourceDeclaration",
    "TableSourceError",
    "card_wire",
    "blob_cell",
    "check_table_query",
    "coerce_filter_value",
    "content_generation",
    "cut_utf8",
    "decode_cursor",
    "decode_key",
    "encode_cursor",
    "encode_key",
    "error_wire",
    "field_wire",
    "integer_cell",
    "open_table_source",
    "page_columns",
    "page_row_limit",
    "page_wire",
    "parse_position_key",
    "parse_positional_cursor",
    "parse_table_query",
    "position_key",
    "positional_cursor",
    "real_cell",
    "record_wire",
    "schema_wire",
    "stat_generation",
    "stored_cell",
    "table_address",
    "tables_wire",
    "text_cell",
]
