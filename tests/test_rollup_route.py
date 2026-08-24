"""Provider-neutral ``/api/rollup`` route contract."""

from __future__ import annotations

import asyncio
import json
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from metabrowser import server
from metabrowser.inventory_engine.contract import (
    ObservationKind,
    RefreshObservation,
    RefreshRequest,
)
from metabrowser.settings import ROLLUP_MAX_TOP
from metabrowser.wire_models import validate_rollup_node
from tests.inventory_harness import InventoryHarness, inventory_harness


class _FakeQuery:
    def __init__(self, params: dict[str, str]) -> None:
        self._params = params

    def get(self, key: str, default: str = "") -> str:
        return self._params.get(key, default)


def _request(
    app: object,
    params: dict[str, str],
    if_none_match: str | None = None,
) -> Any:
    return SimpleNamespace(
        app=app,
        query_params=_FakeQuery(params),
        headers={"if-none-match": if_none_match} if if_none_match else {},
    )


async def _response(
    harness: InventoryHarness,
    params: dict[str, str],
    if_none_match: str | None = None,
) -> Any:
    return await server.api_rollup(_request(harness.app, params, if_none_match))


async def _body(harness: InventoryHarness, params: dict[str, str]) -> dict[str, Any]:
    response = await _response(harness, params)
    return json.loads(bytes(response.body))


def test_rollup_route_envelope_and_wire_shape(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.py").write_text("x" * 64)
    (tmp_path / "top.md").write_text("y" * 16)
    server._set_root_dir(tmp_path)

    async def run() -> dict[str, Any]:
        async with inventory_harness(tmp_path) as harness:
            return await _body(harness, {"path": ""})

    body = asyncio.run(run())
    assert body["path"] == ""
    assert body["index_status"] in ("done", "truncated")
    assert body["indexed_files"] >= 2
    assert body["truncated"] is False
    node = body["node"]
    validate_rollup_node(node)
    assert node["total_files"] == 2
    assert body["ext_tallies"][0][0] in (".py", ".md")
    assert {
        family["id"]
        for group in body["file_type_breakdown"]["groups"]
        for family in group["families"]
    } == {"markdown", "python"}


def test_rollup_route_runs_aggregation_off_the_event_loop(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    (tmp_path / "one.py").write_text("x")
    server._set_root_dir(tmp_path)

    async def run() -> list[int]:
        import metabrowser.inventory_engine.providers.python as provider

        event_loop_thread = threading.get_ident()
        worker_threads: list[int] = []
        real_build = provider.build_rollup

        def recording_build(*args: Any, **kwargs: Any) -> Any:
            worker_threads.append(threading.get_ident())
            return real_build(*args, **kwargs)

        monkeypatch.setattr(provider, "build_rollup", recording_build)
        async with inventory_harness(tmp_path) as harness:
            response = await _response(harness, {"path": ""})
            assert response.status_code == 200
        assert worker_threads[0] != event_loop_thread
        return worker_threads

    assert asyncio.run(run())


def test_rollup_route_rejects_unsafe_path_without_opening_inventory(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    app = SimpleNamespace(state=SimpleNamespace())

    response = asyncio.run(server.api_rollup(_request(app, {"path": "../.."})))
    assert response.status_code == 404


def test_rollup_route_uses_provider_presence_for_missing_or_non_directory_paths(
    tmp_path: Path,
) -> None:
    server._set_root_dir(tmp_path)
    (tmp_path / "plain.txt").write_text("x")

    async def run() -> tuple[int, int, int]:
        async with inventory_harness(tmp_path) as harness:
            plain = await _response(harness, {"path": "plain.txt"})
            absent = await _response(harness, {"path": "absent"})
            (tmp_path / "appeared-without-observation").mkdir()
            unobserved = await _response(
                harness,
                {"path": "appeared-without-observation"},
            )
            return plain.status_code, absent.status_code, unobserved.status_code

    assert asyncio.run(run()) == (404, 404, 404)


def test_rollup_route_clamps_params(tmp_path: Path) -> None:
    for index in range(5):
        (tmp_path / f"f{index}.e{index}").write_text("x" * (10 + index))
    server._set_root_dir(tmp_path)

    async def run() -> dict[str, Any]:
        async with inventory_harness(tmp_path) as harness:
            return await _body(
                harness,
                {
                    "path": "",
                    "depth": "999",
                    "top": "999999",
                    "ext_top": "-3",
                    "remaining_top": "-3",
                },
            )

    body = asyncio.run(run())
    node = body["node"]
    validate_rollup_node(node)
    assert len(node["children"]) == 5 <= ROLLUP_MAX_TOP
    assert all(row[0] == "" for row in body["ext_tallies"])
    remaining = body["file_type_breakdown"]["remaining_types"]
    assert remaining["extensions"] == []
    assert remaining["others"]["omitted_distinct_values"] == 5


def test_rollup_route_supports_summary_only_dual_rank(tmp_path: Path) -> None:
    for index in range(20):
        (tmp_path / f"tiny-{index}.txt").write_text("x")
    (tmp_path / "large.bin").write_text("x" * 10_000)
    server._set_root_dir(tmp_path)

    async def run() -> dict[str, Any]:
        async with inventory_harness(tmp_path) as harness:
            return await _body(
                harness,
                {
                    "path": "",
                    "depth": "0",
                    "top": "0",
                    "ext_top": "2",
                    "ext_rank": "dual",
                },
            )

    body = asyncio.run(run())
    assert body["node"]["children"] is None
    assert [row[0] for row in body["ext_tallies"]] == [".bin", ".txt"]


def test_rollup_route_rejects_unknown_rank(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    app = SimpleNamespace(state=SimpleNamespace())
    response = asyncio.run(server.api_rollup(_request(app, {"path": "", "ext_rank": "popularity"})))
    assert response.status_code == 400
    assert json.loads(bytes(response.body)) == {"error": "Unknown ext_rank: 'popularity'"}


def test_rollup_route_cold_index_is_coherent(tmp_path: Path) -> None:
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "x.txt").write_text("x")
    server._set_root_dir(tmp_path)

    async def run() -> dict[str, Any]:
        async with inventory_harness(tmp_path, settle=False) as harness:
            return await _body(harness, {"path": "nested"})

    body = asyncio.run(run())
    if body["node"] is not None:
        validate_rollup_node(body["node"])
    else:
        assert body["ext_tallies"] == []
        assert body["file_type_breakdown"] is None


def test_rollup_revalidates_and_reuses_unchanged_body(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("x" * 64)
    server._set_root_dir(tmp_path)

    async def run() -> tuple[str, str, str]:
        async with inventory_harness(tmp_path) as harness:
            first = await _response(harness, {"path": ""})
            etag = first.headers["etag"]
            revalidated = await _response(harness, {"path": ""}, etag)
            assert revalidated.status_code == 304
            cached = await _response(harness, {"path": ""})
            assert bytes(cached.body) == bytes(first.body)
            deeper = await _response(harness, {"path": "", "depth": "1"})
            return etag, cached.headers["etag"], deeper.headers["etag"]

    etag, cached_etag, deeper_etag = asyncio.run(run())
    assert cached_etag == etag
    assert deeper_etag != etag
    assert etag in server._ROLLUP_BODY_CACHE


def test_simultaneous_identical_rollups_compute_once(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    (tmp_path / "src").mkdir()
    for index in range(5):
        (tmp_path / "src" / f"f{index}.py").write_text("x" * 32)
    server._set_root_dir(tmp_path)

    async def run() -> tuple[int, list[bytes]]:
        import metabrowser.inventory_engine.providers.python as provider

        calls = 0
        real_build = provider.build_rollup

        def counting_build(*args: Any, **kwargs: Any) -> Any:
            nonlocal calls
            calls += 1
            return real_build(*args, **kwargs)

        monkeypatch.setattr(provider, "build_rollup", counting_build)
        async with inventory_harness(tmp_path) as harness:
            responses = await asyncio.gather(
                *(_response(harness, {"path": ""}) for _index in range(6))
            )
            return calls, [bytes(response.body) for response in responses]

    calls, bodies = asyncio.run(run())
    assert calls == 1
    assert len(set(bodies)) == 1
    assert json.loads(bodies[0])["node"]["total_files"] == 5


def test_disconnecting_client_does_not_cancel_shared_build(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    (tmp_path / "src").mkdir()
    for index in range(4):
        (tmp_path / "src" / f"f{index}.py").write_text("x" * 16)
    server._set_root_dir(tmp_path)

    async def run() -> tuple[bytes, bytes]:
        import metabrowser.inventory_engine.providers.python as provider

        started = threading.Event()
        release = threading.Event()
        real_build = provider.build_rollup

        def gated_build(*args: Any, **kwargs: Any) -> Any:
            started.set()
            assert release.wait(timeout=5.0)
            return real_build(*args, **kwargs)

        monkeypatch.setattr(provider, "build_rollup", gated_build)
        async with inventory_harness(tmp_path) as harness:
            leader = asyncio.create_task(_response(harness, {"path": ""}))
            await asyncio.to_thread(started.wait, 5.0)
            shared = next(iter(server._ROLLUP_IN_FLIGHT.values()))
            leader.cancel()
            release.set()
            body = await shared
            later = await _response(harness, {"path": ""})
            return body, bytes(later.body)

    body, later = asyncio.run(run())
    assert json.loads(body)["node"]["total_files"] == 4
    assert later == body


def test_rollup_payload_and_etag_share_one_version(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    """A mutation during aggregation cannot pair a stale tag with a new body."""

    (tmp_path / "a.txt").write_text("a")
    server._set_root_dir(tmp_path)

    async def run() -> tuple[str, int, str, int, int]:
        import metabrowser.inventory_engine.providers.python as provider

        started = threading.Event()
        release = threading.Event()
        real_build = provider.build_rollup

        def gated_build(*args: Any, **kwargs: Any) -> Any:
            started.set()
            assert release.wait(timeout=5.0)
            return real_build(*args, **kwargs)

        monkeypatch.setattr(provider, "build_rollup", gated_build)
        async with inventory_harness(tmp_path) as harness:
            first_task = asyncio.create_task(_response(harness, {"path": ""}))
            await asyncio.to_thread(started.wait, 5.0)
            (tmp_path / "b.txt").write_text("b")
            await harness.runtime.coordinator.refresh(
                RefreshRequest(
                    observations=(
                        RefreshObservation(
                            path="b.txt",
                            kind=ObservationKind.CREATED,
                        ),
                    )
                )
            )
            release.set()
            first = await first_task
            first_body = json.loads(bytes(first.body))
            second = await _response(harness, {"path": ""}, first.headers["etag"])
            return (
                first.headers["etag"],
                first_body["node"]["total_files"],
                second.headers["etag"],
                second.status_code,
                len(bytes(second.body)),
            )

    first_etag, first_files, second_etag, status, second_bytes = asyncio.run(run())
    assert first_files == 2
    assert status == 304
    assert second_bytes == 0
    assert second_etag == first_etag


def test_rollup_validator_identifies_served_root(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    (first / "a").write_text("x" * 10)
    (second / "a").write_text("x" * 999)

    async def serve(root: Path) -> tuple[str, int]:
        server._set_root_dir(root)
        async with inventory_harness(root) as harness:
            response = await _response(harness, {"path": ""})
            body = json.loads(bytes(response.body))
            return response.headers["etag"], body["node"]["total_size"]

    first_tag, first_size = asyncio.run(serve(first))
    second_tag, second_size = asyncio.run(serve(second))
    assert (first_size, second_size) == (10, 999)
    assert first_tag != second_tag
