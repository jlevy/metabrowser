"""The table routes: ``/api/plugin/table/{tables,schema,rows,record,card}``.

Every route takes ``?path=``, the address of a table: a file that is its own single
table, such as a CSV file, or one table inside a file, ``<file>/<table>``, as a
database's tables are its container children. The tables route answers for the file
either way. The kind of the file there selects its source's adapter
(:func:`metabrowser.table_source.open_table_source`), the adapter's synchronous calls
run on the route threadpool under one request's budget, and the answer is the wire
contract :mod:`metabrowser.table_source` defines, so the routes know nothing about any
source.

A refusal is a ``table_error`` body with a ``code``: ``not_found`` and
``not_a_table_source`` (404) for the path, ``bad_query`` (400) for a parameter,
``table_not_found`` and ``record_not_found`` (404), ``source_unreadable`` (422) for
content the source cannot read as tables, and a content read's own code and status.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import JSONResponse

from metabrowser.content_errors import ContentReadError, content_error_wire
from metabrowser.table_source import (
    Budget,
    OpenedTableSource,
    TableQueryError,
    TableSourceError,
    card_wire,
    check_table_query,
    error_wire,
    open_table_source,
    page_wire,
    parse_table_query,
    record_wire,
    schema_wire,
    tables_wire,
)

Answer = Callable[[OpenedTableSource, Budget], dict[str, Any]]


async def _answer(request: Request, answer: Answer) -> JSONResponse:
    path = request.query_params.get("path", "")
    budget = Budget.start()
    try:
        selected = request.query_params.getlist("table")
        if len(selected) > 1 or (selected and not selected[0]):
            raise TableQueryError("table must name one table", param="table")
        waiting = request.query_params.getlist("wait")
        if waiting and waiting != ["1"]:
            raise TableQueryError("wait must be 1", param="wait")
        opened = await open_table_source(
            path,
            selected_table=selected[0] if selected else None,
            wait=bool(waiting),
        )
        if waiting:
            budget = Budget.start()
        payload = await run_in_threadpool(answer, opened, budget)
    except TableSourceError as exc:
        return JSONResponse(error_wire(path, exc), status_code=exc.http_status)
    except ContentReadError as exc:
        return JSONResponse(
            {"type": "table_error", "path": path, **content_error_wire(exc)},
            status_code=exc.http_status,
        )
    return JSONResponse(payload)


def _required(request: Request, name: str) -> str:
    value = request.query_params.get(name, "")
    if not value:
        raise TableQueryError(f"{name} is required", param=name)
    return value


async def tables_handler(request: Request) -> JSONResponse:
    """``GET /api/plugin/table/tables?path=``: the source's tables, with their groups,
    whether rows have a key, and a cheap estimate where the source has one."""

    def answer(opened: OpenedTableSource, _budget: Budget) -> dict[str, Any]:
        generation = opened.source.generation()
        return tables_wire(
            opened.identity, generation, opened.source.tables(), folder=opened.folder
        )

    return await _answer(request, answer)


async def schema_handler(request: Request) -> JSONResponse:
    """``GET /api/plugin/table/schema?path=``: field descriptors, keys, default columns,
    and references in both directions."""

    def answer(opened: OpenedTableSource, _budget: Budget) -> dict[str, Any]:
        generation = opened.source.generation()
        return schema_wire(opened.address, generation, opened.source.schema(opened.table))

    return await _answer(request, answer)


async def rows_handler(request: Request) -> JSONResponse:
    """``GET /api/plugin/table/rows?path=&sort=&order=&q=&f.<field>=<op>:<value>&ref=
    &cols=&after=&limit=``: one page in the collection envelope."""

    try:
        query = parse_table_query(request.query_params.multi_items())
    except TableQueryError as exc:
        path = request.query_params.get("path", "")
        return JSONResponse(error_wire(path, exc), status_code=exc.http_status)

    def answer(opened: OpenedTableSource, budget: Budget) -> dict[str, Any]:
        check_table_query(query, opened.source.schema(opened.table))
        page = opened.source.rows(opened.table, query, budget)
        return page_wire(opened.address, opened.table, page)

    return await _answer(request, answer)


async def record_handler(request: Request) -> JSONResponse:
    """``GET /api/plugin/table/record?path=&key=[&generation=]``: one record in full,
    each value previewed past the record bound, with back-references counted. A key
    named by position (`@<n>`) names whatever row is at that position now; the
    generation it was read under, when given, says whether that may have changed."""

    def answer(opened: OpenedTableSource, budget: Budget) -> dict[str, Any]:
        record = opened.source.record(opened.table, _required(request, "key"), budget)
        return record_wire(
            opened.address,
            opened.table,
            record,
            requested_generation=request.query_params.get("generation") or None,
        )

    return await _answer(request, answer)


async def card_handler(request: Request) -> JSONResponse:
    """``GET /api/plugin/table/card?path=&key=``: a hover card's label and a few fields."""

    def answer(opened: OpenedTableSource, budget: Budget) -> dict[str, Any]:
        card = opened.source.card(opened.table, _required(request, "key"), budget)
        return card_wire(opened.address, opened.table, card)

    return await _answer(request, answer)
