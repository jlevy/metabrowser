"""``/_debug/inventory`` is the provider identity and work plane.

The parity table exempts this route from a golden transcript because its work
counters carry wall and CPU times, which no transcript can pin. That exemption
is only honest if something else holds the payload's shape, because two tools
already parse it: ``explorations/performance-loop/run.py`` reads ``provider``,
``contract``, and ``work`` to label every recorded run, and
``devtools/bench_serving.py`` reads named counters out of ``work`` to print the
attached and settled comparison.

The shape matters more than any single value. This is the surface that answers
"which engine served this measurement, and how much work did it do" — the
question a second provider exists to be measured against. A renamed key here
does not fail either tool; it silently blanks a column, and the comparison that
was supposed to justify the swap reports nothing while looking fine.

So these tests pin the keys and their types, and the identity values for the
one provider that ships. They deliberately do not pin the timings.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from metabrowser import server
from tests.inventory_harness import inventory_harness

# The keys each consumer names. Recorded here as data because the point is the
# contract with those two files, not this test's own idea of a good payload.
IDENTITY_KEYS: tuple[str, ...] = ("provider", "contract", "phase", "complete", "version")
# Named by `devtools/bench_serving.py` and the performance harness. Renaming one
# of these does not fail either tool; it blanks a column.
CONSUMER_KEYS: tuple[str, ...] = (
    "read_requests",
    "entries_visited",
    "cpu_time_ns",
    "binding_bytes_copied",
)
# Semantic counters shared with the native engine, so a comparison across the two
# describes the same work rather than two vocabularies.
SEMANTIC_KEYS: tuple[str, ...] = (
    "observations",
    "unchanged",
    "stale",
    "resource_refused",
    "rows_visited",
    "rows_returned",
    "maintained_index_work",
    "commits_visited",
    "commits_returned",
    "directories_read",
    "entries_visited",
    "files_visited",
    "bytes_visited",
)
TIMING_KEYS: tuple[str, ...] = (
    "binding_bytes_copied",
    "lock_wait_ns",
    "cpu_time_ns",
    "wall_time_ns",
)


async def _debug_payload(app: object) -> tuple[int, Any]:
    request = SimpleNamespace(app=app, query_params={}, headers={})
    response = await server._debug_inventory(cast(Any, request))
    return response.status_code, json.loads(bytes(response.body))


def _read(tmp_path: Path) -> tuple[int, Any]:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.md").write_text("nested\n")
    (tmp_path / "README.md").write_text("# Sample\n")

    async def _run() -> tuple[int, Any]:
        async with inventory_harness(tmp_path) as harness:
            return await _debug_payload(harness.app)

    return asyncio.run(_run())


def test_debug_plane_is_off_unless_asked_for(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """It reports internals, so it stays closed until a human opens it."""

    monkeypatch.delenv("METABROWSER_DEBUG", raising=False)
    status, body = _read(tmp_path)
    assert status == 404
    assert "METABROWSER_DEBUG" in body["error"]


def test_identity_names_the_provider_that_served_the_measurement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("METABROWSER_DEBUG", "1")
    status, body = _read(tmp_path)
    assert status == 200
    assert [key for key in IDENTITY_KEYS if key not in body] == []
    # The one shipped provider. A second one changes these two values and
    # nothing else about the shape, which is what makes the recorded runs
    # comparable across the swap.
    assert body["provider"] == "python"
    assert body["contract"] == "inventory-provider-v1"
    assert isinstance(body["version"], int)
    assert isinstance(body["complete"], bool)
    assert isinstance(body["phase"], str)


def test_work_counters_carry_every_name_the_benchmarks_print(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A renamed counter blanks a benchmark column instead of failing it."""

    monkeypatch.setenv("METABROWSER_DEBUG", "1")
    _status, body = _read(tmp_path)
    work = body["work"]
    assert [key for key in CONSUMER_KEYS if key not in work] == []
    assert [key for key in SEMANTIC_KEYS if key not in work] == []
    # Counts are exact integers. Times and copied bytes are integers or absent --
    # a provider that cannot measure its own CPU time says so with null rather
    # than reporting a zero that reads as "free".
    for key in ("read_requests", *SEMANTIC_KEYS):
        assert isinstance(work[key], int), key
        assert work[key] >= 0, key
    for key in TIMING_KEYS:
        assert work[key] is None or isinstance(work[key], int), key


def test_work_accumulates_across_reads(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Cumulative, not per-request: the benchmarks diff two samples.

    ``bench_serving`` prints an attached and a settled sample and reads the
    growth between them. A counter that reset per read would make that
    difference meaningless while every individual value still looked sane.
    """

    monkeypatch.setenv("METABROWSER_DEBUG", "1")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.md").write_text("nested\n")

    async def _run() -> tuple[Any, Any]:
        async with inventory_harness(tmp_path) as harness:
            _status, first = await _debug_payload(harness.app)
            await server.api_tree(
                cast(
                    Any,
                    SimpleNamespace(
                        app=harness.app,
                        query_params={"path": "", "depth": ""},
                        headers={},
                    ),
                )
            )
            _status, second = await _debug_payload(harness.app)
            return first, second

    first, second = asyncio.run(_run())
    assert second["work"]["read_requests"] > first["work"]["read_requests"]
    assert second["work"]["entries_visited"] >= first["work"]["entries_visited"]
