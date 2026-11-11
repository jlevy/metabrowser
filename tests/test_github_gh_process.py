"""What the gh runner launches: one owned child per read, and read-only GraphQL only.

Review A5 removed the in-flight sharing of identical reads, for which a
measurement found nothing to share; the spawn cancellation it brought stays. Review C2
made the GraphQL read-only check read the document's definitions, not its first word.
"""

from __future__ import annotations

import asyncio
import sys
from typing import Any

import pytest

from metabrowser.builtin_plugins.github import (
    gh,
    pull_cores,
    pull_list_refresh,
    pull_timeline,
    pulls,
)

_PATH = "repos/octo/demo/commits/abc/status"


def test_a_cancelled_read_reaps_a_child_still_spawning(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gh, "gh_executable", lambda: sys.executable)
    real_spawn = asyncio.create_subprocess_exec

    async def check() -> None:
        started = asyncio.Event()
        return_child = asyncio.Event()
        children: list[asyncio.subprocess.Process] = []

        async def paused_spawn(*_args: str, **kwargs: Any) -> asyncio.subprocess.Process:
            child = await real_spawn(sys.executable, "-c", "import time; time.sleep(60)", **kwargs)
            children.append(child)
            started.set()
            await return_child.wait()
            return child

        monkeypatch.setattr(asyncio, "create_subprocess_exec", paused_spawn)
        reader = asyncio.create_task(gh.gh_api(_PATH))
        try:
            await asyncio.wait_for(started.wait(), timeout=5)
            reader.cancel()
            for _ in range(3):
                await asyncio.sleep(0)
            assert not reader.done(), "the read waits for the spawn it interrupted"
        finally:
            return_child.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(reader, timeout=5)
        (child,) = children
        assert child.returncode is not None

    asyncio.run(check())


def _production_queries() -> list[str]:
    listing = pull_list_refresh._QUERY  # pyright: ignore[reportPrivateUsage]
    filters = pull_list_refresh._FILTERS  # pyright: ignore[reportPrivateUsage]
    lists = [
        listing.replace("ORDER", order).replace("FILTER", text)
        for order in ("UPDATED_AT", "CREATED_AT")
        for text in filters.values()
    ]
    cores = [pull_cores._batch_query(count) for count in (1, 2, 25)]  # pyright: ignore[reportPrivateUsage]
    timeline = pull_timeline._QUERY  # pyright: ignore[reportPrivateUsage]
    return [timeline, pulls._CORE_QUERY, *lists, *cores]  # pyright: ignore[reportPrivateUsage]


def test_every_query_the_plugin_sends_is_admitted() -> None:
    for query in _production_queries():
        assert gh._is_one_read_only_query(query), query  # pyright: ignore[reportPrivateUsage]


@pytest.mark.parametrize(
    "document",
    [
        "  query Q { a } mutation M { b }",
        "query Q { a }\n# a comment\nmutation M { b }",
        "{ a } subscription S { b }",
        "queryish { a }",
        "mutation M { a }",
        "query A { a } query B { b }",
        "type Query { a: Int }",
        "query Q { a",
        "query Q { a } }",
        "query Q { a } \x00",
    ],
)
def test_a_document_that_is_not_one_query_is_refused_before_launch(
    monkeypatch: pytest.MonkeyPatch, document: str
) -> None:
    launched: list[object] = []

    async def launch(*args: object, **_kwargs: object) -> object:
        launched.append(args)
        raise AssertionError("a refused document reached gh")

    monkeypatch.setattr(gh, "_run", launch)
    with pytest.raises(ValueError, match="only a fixed GraphQL query"):
        asyncio.run(gh.gh_graphql(document, {}))
    assert launched == []


@pytest.mark.parametrize(
    "document",
    [
        'query Q { a(text: "mutation M { b }") }',
        'query Q { a(text: """ } mutation M { """) }',
        "query Q($n: Int = 3) { ...F } fragment F on Query { a }",
        "﻿{ a }",
    ],
)
def test_strings_comments_and_fragments_do_not_hide_or_add_operations(document: str) -> None:
    assert gh._is_one_read_only_query(document)  # pyright: ignore[reportPrivateUsage]


@pytest.mark.parametrize("name", ["query", "operationName"])
def test_gh_request_fields_are_not_variables(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    async def launch(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("a refused request reached gh")

    monkeypatch.setattr(gh, "_run", launch)
    with pytest.raises(ValueError, match="invalid GraphQL variable name"):
        asyncio.run(gh.gh_graphql("query Q { a }", {name: "M"}))
