"""Every multi-page inventory consumer answers a moved version with one retryable outcome.

`metabrowser/inventory_moved.py` defines it: a route answers 503 with ``Retry-After``
and a stable body, ``/api/events`` asks for a resync instead of failing its stream, and
``metab --walk`` stops with a typed error. The provider here is the one the environment
selects behind `tests/perturbed_provider.py`, whose ``unavailable`` perturbation makes
chosen reads raise `VersionUnavailableError` on every attempt, so each consumer
exhausts its bounded retries deterministically instead of racing real changes.

The routes run through the real application, its exception handlers included, with
`InProcessClient`, the transport ``metab --api`` uses; the golden that pins the same
outcome through ``metab --api`` is `tests/test_cli_inventory_moved_golden.py`.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any, cast

import pytest

from metabrowser import server
from metabrowser.cli.asgi_client import ApiResponse, InProcessClient, wait_for_index
from metabrowser.events_route import _stream_events, parse_sse_frames
from metabrowser.inventory_engine import runtime as runtime_module
from metabrowser.inventory_engine.contract import (
    CatalogQuery,
    InventoryBackend,
    InventoryConfig,
    ProviderFailureError,
    QueryKind,
    ReadQuery,
    ReadRequest,
)
from metabrowser.inventory_engine.factory import InventoryProvider
from metabrowser.inventory_engine.seams import ProviderSeams
from metabrowser.inventory_moved import (
    INVENTORY_MOVED_CODE,
    INVENTORY_PROVIDER_FAILED_CODE,
    INVENTORY_RETRY_AFTER_S,
    inventory_moved_message,
    inventory_moved_payload,
)
from tests.golden_harness import run_metab
from tests.inventory_harness import inventory_harness
from tests.perturbed_provider import (
    Perturbation,
    PerturbedBackend,
    PerturbedHandle,
    reads_asking_for,
)

type ReadSelector = Callable[[ReadRequest], bool]


def build_moved_fixture(root: Path) -> Path:
    """A small tree with several folders and kinds, so every tree route has rows."""

    (root / "docs").mkdir(parents=True)
    (root / "src").mkdir()
    (root / "README.md").write_text("# Moved\n")
    (root / "docs" / "guide.md").write_text("guide\n")
    (root / "docs" / "notes.md").write_text("notes\n")
    (root / "src" / "main.py").write_text("print('moved')\n")
    return root


def route_catalog(query: ReadQuery) -> bool:
    """The ``/api/catalog`` assembly's query, not the activity tracker's narrower one."""

    return isinstance(query, CatalogQuery) and not query.terminal_extensions


# Each consumer and the reads that make it run out of attempts when they always fail.
MOVED_ROUTES: tuple[tuple[str, ReadSelector], ...] = (
    ("/api/tree?depth=2", reads_asking_for(QueryKind.DIRECTORY)),
    ("/api/tree?types=.md&depth=2", reads_asking_for(QueryKind.FILTERED_TREE)),
    ("/api/tree?group_by=type&depth=2", reads_asking_for(QueryKind.GROUPED_TREE)),
    ("/api/catalog", reads_asking_for(QueryKind.CATALOG, matching=route_catalog)),
    ("/api/rollup?path=&depth=0", reads_asking_for(QueryKind.ROLLUP)),
)


def serve_unavailable(monkeypatch: pytest.MonkeyPatch, unavailable: ReadSelector) -> None:
    """Make every runtime the process opens serve its provider behind *unavailable*.

    The application lifespan and ``--walk`` both construct `InventoryRuntime` from a
    provider name, so the sealed factory it calls is the one seam that reaches both.
    """

    real = runtime_module.create_inventory_backend

    def perturbed(
        provider: InventoryProvider | str = InventoryProvider.PYTHON,
        *,
        seams: ProviderSeams | None = None,
    ) -> InventoryBackend:
        return PerturbedBackend(real(provider, seams=seams), Perturbation(unavailable=unavailable))

    monkeypatch.setattr(runtime_module, "create_inventory_backend", perturbed)


def request_settled(root: Path, route: str) -> ApiResponse:
    """Issue *route* through the real application, after discovery, as ``--api`` does."""

    async def run() -> ApiResponse:
        async with InProcessClient(server.app, label="moved") as client:
            settled = await wait_for_index(client)
            assert settled.completed, settled.detail
            return await client.get(route)

    server._set_root_dir(root)
    return asyncio.run(run())


def assert_moved(response: ApiResponse) -> None:
    assert response.status_code == 503, response.text()
    assert response.headers.get("retry-after") == str(INVENTORY_RETRY_AFTER_S)
    assert response.json() == inventory_moved_payload()
    assert response.json()["code"] == INVENTORY_MOVED_CODE


@pytest.mark.parametrize(("route", "unavailable"), MOVED_ROUTES, ids=[r for r, _ in MOVED_ROUTES])
def test_a_route_answers_an_exhausted_or_failed_read_with_a_retryable_503(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, route: str, unavailable: ReadSelector
) -> None:
    root = build_moved_fixture(tmp_path / "root")
    serve_unavailable(monkeypatch, unavailable)

    assert_moved(request_settled(root, route))


@pytest.mark.parametrize(
    ("route", "kind"),
    (
        ("/api/tree?depth=2", QueryKind.DIRECTORY),
        # A group's continuation pages are filtered trees pinned to the grouped read.
        ("/api/tree?group_by=type&depth=2", QueryKind.FILTERED_TREE),
    ),
)
def test_a_tree_whose_pinned_pages_keep_moving_answers_a_retryable_503(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, route: str, kind: QueryKind
) -> None:
    """The first page reads; every pinned continuation finds its version gone."""

    root = build_moved_fixture(tmp_path / "root")
    monkeypatch.setattr(server, "INVENTORY_TREE_PAGE_ROWS", 1)
    serve_unavailable(monkeypatch, reads_asking_for(kind, pinned_only=True))

    assert_moved(request_settled(root, route))


def test_the_rollup_still_answers_from_its_unpinned_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only an unpinned failure after the pinned one reaches the 503."""

    root = build_moved_fixture(tmp_path / "root")
    serve_unavailable(monkeypatch, reads_asking_for(QueryKind.ROLLUP, pinned_only=True))

    response = request_settled(root, "/api/rollup?path=&depth=0")
    assert response.status_code == 200, response.text()
    assert response.json()["node"]["total_files"] == 4


def test_an_unaffected_route_still_answers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = build_moved_fixture(tmp_path / "root")
    serve_unavailable(monkeypatch, reads_asking_for(QueryKind.DIRECTORY))

    response = request_settled(root, "/api/tree?types=.md&depth=2")
    assert response.status_code == 200, response.text()


class _StreamRequest:
    """The parts of a request `_stream_events` reads."""

    def __init__(self, app: object) -> None:
        self.app = app
        self.query_params: dict[str, str] = {}
        self.headers: dict[str, str] = {}

    async def is_disconnected(self) -> bool:
        return False


async def _frames(stream: AsyncIterator[bytes]) -> list[dict[str, str]]:
    body = b""
    async with asyncio.timeout(10):
        async for chunk in stream:
            body += chunk
    return list(parse_sse_frames(body))


def test_an_unassemblable_snapshot_asks_the_stream_to_resync(tmp_path: Path) -> None:
    """The stream sends one resync and ends, attaching no connection, rather than failing
    a response that has already started."""

    root = build_moved_fixture(tmp_path / "root")

    def wrap(backend: InventoryBackend) -> InventoryBackend:
        return PerturbedBackend(
            backend, Perturbation(unavailable=reads_asking_for(QueryKind.DIRECTORY))
        )

    async def run() -> tuple[list[dict[str, str]], int]:
        async with inventory_harness(root, wrap=wrap) as harness:
            frames = await _frames(_stream_events(cast(Any, _StreamRequest(harness.app))))
            return frames, harness.bus.connection_count()

    frames, connections = asyncio.run(run())
    assert [frame["event"] for frame in frames] == ["fs.resync_required"]
    assert json.loads(frames[0]["data"]) == {
        "reason": INVENTORY_MOVED_CODE,
        "type": "fs.resync_required",
    }
    assert connections == 0


def test_walk_reports_the_outcome_as_a_typed_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = build_moved_fixture(tmp_path / "root")
    serve_unavailable(monkeypatch, reads_asking_for(QueryKind.DIRECTORY))

    result = run_metab([str(root), "--walk", "--format", "json"])
    assert result.exit_code == 1, result.stdout + result.stderr
    assert result.stdout == ""
    assert result.stderr == f"Error: {inventory_moved_message()}\n"


def _failing_once(kind: QueryKind) -> Callable[[InventoryBackend], InventoryBackend]:
    """Wrap the backend so the first read of *kind* reports a provider failure (D14)."""

    def wrap(backend: InventoryBackend) -> InventoryBackend:
        perturbed = PerturbedBackend(backend, Perturbation())
        real_open = perturbed.open

        async def open_failing(root: Path, config: InventoryConfig) -> PerturbedHandle:
            handle = await real_open(root, config)
            if len(perturbed.handles) == 1:
                handle.fail_next_read(
                    ProviderFailureError("poisoned root"), matching=reads_asking_for(kind)
                )
            return handle

        perturbed.open = open_failing  # type: ignore[method-assign]
        return perturbed

    return wrap


def test_a_provider_failure_answers_a_retryable_503_under_its_own_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A read the provider fails is the same outcome, and once the supervisor has
    reopened the root the same request answers."""

    root = build_moved_fixture(tmp_path / "root")
    real = runtime_module.create_inventory_backend
    wrap = _failing_once(QueryKind.DIRECTORY)

    def failing(
        provider: InventoryProvider | str = InventoryProvider.PYTHON,
        *,
        seams: ProviderSeams | None = None,
    ) -> InventoryBackend:
        return wrap(real(provider, seams=seams))

    monkeypatch.setattr(runtime_module, "create_inventory_backend", failing)

    async def run() -> tuple[ApiResponse, ApiResponse]:
        async with InProcessClient(server.app, label="failed") as client:
            settled = await wait_for_index(client)
            assert settled.completed, settled.detail
            failed = await client.get("/api/tree?depth=2")
            settled = await wait_for_index(client)
            assert settled.completed, settled.detail
            return failed, await client.get("/api/tree?depth=2")

    server._set_root_dir(root)
    failed, retried = asyncio.run(run())
    assert failed.status_code == 503, failed.text()
    assert failed.headers.get("retry-after") == str(INVENTORY_RETRY_AFTER_S)
    assert failed.json() == inventory_moved_payload(INVENTORY_PROVIDER_FAILED_CODE)
    assert retried.status_code == 200, retried.text()


def test_a_provider_failure_during_the_snapshot_asks_the_stream_to_resync(
    tmp_path: Path,
) -> None:
    root = build_moved_fixture(tmp_path / "root")

    async def run() -> list[dict[str, str]]:
        async with inventory_harness(root, wrap=_failing_once(QueryKind.DIRECTORY)) as harness:
            return await _frames(_stream_events(cast(Any, _StreamRequest(harness.app))))

    frames = asyncio.run(run())
    assert [frame["event"] for frame in frames] == ["fs.resync_required"]
    assert json.loads(frames[0]["data"])["reason"] == INVENTORY_PROVIDER_FAILED_CODE
