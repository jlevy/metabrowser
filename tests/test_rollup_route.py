"""/api/rollup route contract.

Param clamping to the ROLLUP_* settings bounds, traversal and
non-directory rejection, the null-node cold envelope, envelope
metadata, and wire-shape validation of every emitted node.
"""

from __future__ import annotations

import asyncio
import json
import threading
from pathlib import Path
from typing import Any
from unittest.mock import Mock

from metabrowser import server
from metabrowser.events import FsEntry
from metabrowser.inventory import get_instance as get_inventory
from metabrowser.inventory import reset_instance_for_tests
from metabrowser.settings import ROLLUP_MAX_TOP
from metabrowser.wire_models import validate_rollup_node


class _FakeQuery:
    def __init__(self, params: dict[str, str]) -> None:
        self._params = params

    def get(self, key: str, default: str = "") -> str:
        return self._params.get(key, default)


def _rollup(params: dict[str, str]) -> tuple[dict[str, Any], Any]:
    request = Mock(spec=["query_params", "headers"])
    request.query_params = _FakeQuery(params)
    request.headers = {}
    response = asyncio.run(server.api_rollup(request))
    return json.loads(bytes(response.body)), response


def _rollup_after_walk(tmp_path: Path, params: dict[str, str]) -> dict[str, Any]:
    async def scenario() -> dict[str, Any]:
        inventory = get_inventory()
        inventory.start(tmp_path)
        await inventory.wait_until_done(10)
        request = Mock(spec=["query_params", "headers"])
        request.query_params = _FakeQuery(params)
        request.headers = {}
        response = await server.api_rollup(request)
        return json.loads(bytes(response.body))

    return asyncio.run(scenario())


def test_rollup_route_envelope_and_wire_shape(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.py").write_text("x" * 64)
    (tmp_path / "top.md").write_text("y" * 16)

    body = _rollup_after_walk(tmp_path, {"path": ""})
    assert body["path"] == ""
    assert body["index_status"] in ("done", "truncated")
    assert body["indexed_files"] >= 2
    assert body["truncated"] is False
    node = body["node"]
    assert node is not None
    validate_rollup_node(node)
    assert node["total_files"] == 2
    assert isinstance(body["ext_tallies"], list)
    assert body["ext_tallies"][0][0] in (".py", ".md")
    assert {
        family["id"]
        for group in body["file_type_breakdown"]["groups"]
        for family in group["families"]
    } == {"markdown", "python"}


def test_rollup_route_runs_aggregation_off_the_event_loop(tmp_path: Path, monkeypatch) -> None:
    server._set_root_dir(tmp_path)
    (tmp_path / "one.py").write_text("x")

    async def scenario() -> None:
        inventory = get_inventory()
        inventory.start(tmp_path)
        await inventory.wait_until_done(10)
        event_loop_thread = threading.get_ident()
        worker_threads: list[int] = []
        original_rollup = inventory.rollup

        def recording_rollup(*args: Any, **kwargs: Any) -> Any:
            worker_threads.append(threading.get_ident())
            return original_rollup(*args, **kwargs)

        monkeypatch.setattr(inventory, "rollup", recording_rollup)
        request = Mock(spec=["query_params", "headers"])
        request.query_params = _FakeQuery({"path": ""})
        request.headers = {}
        response = await server.api_rollup(request)
        assert response.status_code == 200
        assert worker_threads and worker_threads[0] != event_loop_thread

    asyncio.run(scenario())


def test_rollup_route_404s(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    (tmp_path / "plain.txt").write_text("x")
    _, escape_response = _rollup({"path": "../.."})
    assert escape_response.status_code == 404
    _, file_response = _rollup({"path": "plain.txt"})
    assert file_response.status_code == 404
    _, missing_response = _rollup({"path": "absent"})
    assert missing_response.status_code == 404


def test_rollup_route_clamps_params(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    for i in range(5):
        (tmp_path / f"f{i}.e{i}").write_text("x" * (10 + i))

    body = _rollup_after_walk(
        tmp_path,
        {
            "path": "",
            "depth": "999",
            "top": "999999",
            "ext_top": "-3",
            "remaining_top": "-3",
        },
    )
    node = body["node"]
    assert node is not None
    validate_rollup_node(node)
    # top clamps to ROLLUP_MAX_TOP (no crash, all five children emitted).
    assert len(node["children"]) == 5 <= ROLLUP_MAX_TOP
    # ext_top clamps to zero: only the remainder row remains.
    assert all(row[0] == "" for row in body["ext_tallies"])
    # remaining_top clamps to zero: the tail collapses into the exact Others row.
    remaining = body["file_type_breakdown"]["remaining_types"]
    assert remaining["extensions"] == []
    assert remaining["others"]["omitted_distinct_values"] == 5


def test_rollup_route_supports_summary_only_dual_rank(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    for index in range(20):
        (tmp_path / f"tiny-{index}.txt").write_text("x")
    (tmp_path / "large.bin").write_text("x" * 10_000)

    body = _rollup_after_walk(
        tmp_path,
        {"path": "", "depth": "0", "top": "0", "ext_top": "2", "ext_rank": "dual"},
    )
    assert body["node"]["children"] is None
    assert [row[0] for row in body["ext_tallies"]] == [".bin", ".txt"]


def test_rollup_route_rejects_unknown_rank(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    body, response = _rollup({"path": "", "ext_rank": "popularity"})
    assert response.status_code == 400
    assert body == {"error": "Unknown ext_rank: 'popularity'"}


def test_rollup_route_cold_index_returns_null_node(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "x.txt").write_text("x")
    # No explicit walk: the route may start one and serve whatever
    # landed within the cold-start grace; the contract is that ``node``
    # is either null (pending envelope) or a valid rollup — never a
    # fabricated shape.
    body, response = _rollup({"path": "nested"})
    assert response.status_code == 200
    if body["node"] is not None:
        validate_rollup_node(body["node"])
    else:
        assert body["ext_tallies"] == []
        assert body["file_type_breakdown"] is None


def test_rollup_revalidates_and_reuses_an_unchanged_body(tmp_path: Path) -> None:
    """An unchanged index answers a repeat request without rebuilding it.

    The body is a pure function of the index revision and the request's
    bounds. A client holding the tag gets a 304; one arriving without it (a
    second tab, a reconnect) gets the retained body rather than a second
    aggregation of the same answer.
    """

    server._set_root_dir(tmp_path)
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("x" * 64)

    async def scenario() -> None:
        inventory = get_inventory()
        inventory.start(tmp_path)
        await inventory.wait_until_done(10)

        first = await server.api_rollup(_mock_request({"path": ""}))
        etag = first.headers["etag"]
        assert etag
        assert first.status_code == 200

        revalidated = await server.api_rollup(_mock_request({"path": ""}, etag))
        assert revalidated.status_code == 304
        assert not bytes(revalidated.body)
        assert revalidated.headers["etag"] == etag

        cold = await server.api_rollup(_mock_request({"path": ""}))
        assert cold.status_code == 200
        assert etag in server._ROLLUP_BODY_CACHE

        # Byte equality alone would prove nothing: rebuilding produces the
        # same bytes. What has to hold is that no aggregation ran at all, so
        # count them rather than comparing the result.
        aggregations = 0
        real_rollup = inventory.rollup

        def counting_rollup(*args: Any, **kwargs: Any) -> Any:
            nonlocal aggregations
            aggregations += 1
            return real_rollup(*args, **kwargs)

        inventory.rollup = counting_rollup  # type: ignore[method-assign]
        try:
            reused = await server.api_rollup(_mock_request({"path": ""}))
        finally:
            del inventory.rollup  # type: ignore[attr-defined]
        assert bytes(reused.body) == bytes(cold.body)
        assert aggregations == 0, "the retained body was rebuilt instead of reused"

        # Different bounds must not share a validator: the shape differs.
        deeper = await server.api_rollup(_mock_request({"path": "", "depth": "1"}))
        assert deeper.headers["etag"] != etag

        # A write moves the revision, so the old tag stops matching.
        inventory.apply_live_entry(
            FsEntry.for_observed_file(
                path="src/b.py",
                parent="src",
                name="b.py",
                size=8,
                mtime_ns=1_700_000_000_000_000_000,
            )
        )
        after = await server.api_rollup(_mock_request({"path": ""}, etag))
        assert after.status_code == 200
        assert after.headers["etag"] != etag
        assert json.loads(bytes(after.body))["node"]["total_files"] == 2

    asyncio.run(scenario())


def _mock_request(params: dict[str, str], if_none_match: str | None = None) -> Any:
    request = Mock(spec=["query_params", "headers"])
    request.query_params = _FakeQuery(params)
    request.headers = {"if-none-match": if_none_match} if if_none_match else {}
    return request


def test_simultaneous_identical_rollups_compute_once(tmp_path: Path) -> None:
    """Clients that arrive together share one aggregation.

    The retained body only helps a request that arrives after one finished.
    Several tabs refreshing off the same inventory change arrive together, and
    each would otherwise aggregate the same answer.
    """

    server._set_root_dir(tmp_path)
    (tmp_path / "src").mkdir()
    for index in range(5):
        (tmp_path / "src" / f"f{index}.py").write_text("x" * 32)

    async def scenario() -> tuple[int, list[bytes]]:
        inventory = get_inventory()
        inventory.start(tmp_path)
        await inventory.wait_until_done(10)

        calls = 0
        real_rollup = inventory.rollup

        def counting_rollup(*args: Any, **kwargs: Any) -> Any:
            nonlocal calls
            calls += 1
            return real_rollup(*args, **kwargs)

        inventory.rollup = counting_rollup  # type: ignore[method-assign]
        try:
            bodies = await asyncio.gather(
                *(server.api_rollup(_mock_request({"path": ""})) for _ in range(6))
            )
        finally:
            del inventory.rollup  # type: ignore[method-assign]
        return calls, [bytes(response.body) for response in bodies]

    calls, bodies = asyncio.run(scenario())
    assert calls == 1, f"expected one shared aggregation, got {calls}"
    assert len(set(bodies)) == 1
    assert json.loads(bodies[0])["node"]["total_files"] == 5


async def _wait(event: asyncio.Event) -> None:
    await event.wait()


def test_a_disconnecting_client_does_not_cancel_the_shared_build(tmp_path: Path) -> None:
    """One client going away must not fail the others waiting on its build.

    Requests that arrive together share one aggregation. If that build were
    owned by whichever request happened to arrive first, the others would
    inherit its cancellation when that client disconnected — closing a tab
    would fail every other tab's in-flight request.
    """

    server._set_root_dir(tmp_path)
    (tmp_path / "src").mkdir()
    for index in range(4):
        (tmp_path / "src" / f"f{index}.py").write_text("x" * 16)

    async def scenario() -> tuple[bytes, Any]:
        inventory = get_inventory()
        inventory.start(tmp_path)
        await inventory.wait_until_done(10)

        # Hold the aggregation open so the build is provably still running when
        # the first client goes away. Gating on events rather than on loop turns
        # keeps the ordering independent of how many iterations a task needs.
        started = asyncio.Event()
        release = asyncio.Event()
        loop = asyncio.get_running_loop()
        real_rollup = inventory.rollup

        def gated_rollup(*args: Any, **kwargs: Any) -> Any:
            loop.call_soon_threadsafe(started.set)
            asyncio.run_coroutine_threadsafe(_wait(release), loop).result()
            return real_rollup(*args, **kwargs)

        inventory.rollup = gated_rollup  # type: ignore[method-assign]
        try:
            leader = asyncio.create_task(server.api_rollup(_mock_request({"path": ""})))
            await started.wait()
            # Registered before the aggregation began, so this is the build the
            # leader's own request would have returned.
            shared = next(iter(server._ROLLUP_IN_FLIGHT.values()))
            leader.cancel()
            release.set()
            # The build itself must survive the client that started it.
            body = await shared
        finally:
            del inventory.rollup  # type: ignore[method-assign]

        # And a request arriving afterwards is served the same answer.
        later = await server.api_rollup(_mock_request({"path": ""}))
        return body, later

    body, later = asyncio.run(scenario())
    assert json.loads(body)["node"]["total_files"] == 4
    assert later.status_code == 200
    assert bytes(later.body) == body


def test_rollup_validator_identifies_the_served_root(tmp_path: Path) -> None:
    """A tag identifies the resource it validates.

    "The rollup of this path" is a different resource under a different root.
    A validator that left the root out reused one root's body for another
    wherever their revisions lined up — which a fresh index makes easy, since
    a per-instance counter would restart at zero.
    """

    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    (first / "a").write_text("x" * 10)
    (second / "a").write_text("x" * 999)

    async def serve(root: Path) -> tuple[str, int]:
        server._set_root_dir(root)
        inventory = get_inventory()
        inventory.start(root)
        await inventory.wait_until_done(10)
        # Pin the revision so the two roots report the same one. Revisions come
        # from a process-wide counter, which already keeps two roots apart on
        # its own -- and would therefore carry this test whether or not the tag
        # named the root at all. Holding it fixed removes that second mechanism
        # so only the root component can separate the tags.
        inventory.rollup_revision = lambda: 4242  # type: ignore[method-assign]
        try:
            response = await server.api_rollup(_mock_request({"path": ""}))
        finally:
            del inventory.rollup_revision  # type: ignore[attr-defined]
        body = json.loads(bytes(response.body))
        return response.headers["etag"], body["node"]["total_size"]

    async def scenario() -> tuple[str, int, str, int]:
        first_tag, first_size = await serve(first)
        reset_instance_for_tests()  # what the autouse fixture does between tests
        second_tag, second_size = await serve(second)
        return first_tag, first_size, second_tag, second_size

    first_tag, first_size, second_tag, second_size = asyncio.run(scenario())
    assert first_size == 10
    assert second_size == 999, "the second root was served the first root's body"
    assert first_tag != second_tag
