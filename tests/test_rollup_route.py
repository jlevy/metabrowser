"""Provider-neutral ``/api/rollup`` route contract."""

from __future__ import annotations

import asyncio
import json
import re
import threading
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from metabrowser import server
from metabrowser.http_caching import BUILD_TAG
from metabrowser.inventory_engine.contract import (
    DiscoveryBudget,
    EngineVersion,
    IndexState,
    ObservationKind,
    ReadRequest,
    RefreshObservation,
    RefreshRequest,
    RollupQuery,
    VersionUnavailableError,
)
from metabrowser.inventory_engine.coordinator import CoordinatedRead, HostCursor, HostVersion
from metabrowser.inventory_engine.runtime import default_inventory_config
from metabrowser.settings import ROLLUP_DEFAULT_NODES, ROLLUP_MAX_DEPTH, ROLLUP_MAX_TOP
from metabrowser.wire_models import validate_rollup_envelope, validate_rollup_node
from tests.inventory_harness import InventoryHarness, inventory_harness
from tests.loop_gate import held_until
from tests.test_inventory_rollup import _by_path, _decode_compact, _walk, _without_ignored

# Tests that compare validators across requests hold the inventory version still.
# A live watcher can move it at any moment -- even a verified refresh of an
# unchanged file advances the sequence -- and a late event on a busy host would
# change a tag without anything being wrong in the route.
_WATCH_OFF = replace(default_inventory_config(), watch_mode="off")


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


async def _engine_version(harness: InventoryHarness) -> EngineVersion:
    _cursor, version, _state = await harness.runtime.coordinator.checkpoint()
    return version.engine


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


def test_rollup_route_reports_a_truncated_index(tmp_path: Path) -> None:
    """The discovery budget stops the walk: the envelope says so and counts what it kept."""
    for index in range(5):
        (tmp_path / f"file-{index}.py").write_text("x" * 8)
    server._set_root_dir(tmp_path)
    config = replace(_WATCH_OFF, budget=DiscoveryBudget(max_files=2))

    async def run() -> dict[str, Any]:
        async with inventory_harness(tmp_path, config=config) as harness:
            return await _body(harness, {"path": ""})

    body = asyncio.run(run())
    validate_rollup_envelope(body)
    assert body["truncated"] is True
    assert body["index_status"] == "truncated"
    assert body["max_files"] == 2
    assert body["indexed_files"] == 2
    assert body["node"]["total_files"] == 2


def test_tree_and_recent_report_a_truncated_index(tmp_path: Path) -> None:
    """The other two routes that read the same status, and what the file tree's note needs."""
    for index in range(5):
        (tmp_path / f"file-{index}.py").write_text("x" * 8)
    server._set_root_dir(tmp_path)
    config = replace(_WATCH_OFF, budget=DiscoveryBudget(max_files=2))

    async def run() -> tuple[dict[str, Any], dict[str, Any]]:
        async with inventory_harness(tmp_path, config=config) as harness:
            tree = await server.api_tree(_request(harness.app, {"depth": "0"}))
            recent = await server.api_recent(_request(harness.app, {"window": "all"}))
            return json.loads(bytes(tree.body)), json.loads(bytes(recent.body))

    tree, recent = asyncio.run(run())
    assert tree["tally_cache_status"] == "truncated"
    assert tree["tally_cache_max_files"] == 2
    assert recent["tally_cache_status"] == "truncated"


def test_rollup_route_runs_aggregation_off_the_event_loop(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    (tmp_path / "one.py").write_text("x")
    server._set_root_dir(tmp_path)

    async def run() -> list[int]:
        import metabrowser.inventory_engine.providers.python_inventory as provider

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


def test_rollup_route_resolves_max_to_the_bounds(tmp_path: Path) -> None:
    folder = tmp_path
    for level in range(ROLLUP_MAX_DEPTH + 2):
        folder = folder / f"d{level}"
        folder.mkdir()
        (folder / "f.py").write_text("x")
    server._set_root_dir(tmp_path)

    async def run(query: dict[str, str]) -> dict[str, Any]:
        async with inventory_harness(tmp_path) as harness:
            return await _body(harness, {"path": "", **query})

    def deepest(node: dict[str, Any], level: int = 0) -> int:
        dirs = [child for child in node.get("children") or [] if child["type"] == "dir"]
        return max([level, *(deepest(child, level + 1) for child in dirs)])

    asked_max = asyncio.run(run({"depth": "max", "top": "max"}))
    asked_bound = asyncio.run(run({"depth": str(ROLLUP_MAX_DEPTH), "top": str(ROLLUP_MAX_TOP)}))
    assert deepest(asked_max["node"]) == ROLLUP_MAX_DEPTH
    assert asked_max["node"] == asked_bound["node"]


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


def test_rollup_route_rejects_unknown_ignored_and_encoding(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    app = SimpleNamespace(state=SimpleNamespace())
    for name, value in (("ignored", "only"), ("encoding", "msgpack")):
        response = asyncio.run(server.api_rollup(_request(app, {"path": "", name: value})))
        assert response.status_code == 400
        assert json.loads(bytes(response.body)) == {"error": f"Unknown {name}: {value!r}"}


def test_rollup_route_node_budget_defaults_clamps_and_resolves_max(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``nodes`` is the budget a request names, clamped to 1 and ROLLUP_MAX_NODES.

    The bounds are lowered here so a small folder shows each of them: an unnamed budget
    is ROLLUP_DEFAULT_NODES, ``0`` is one node (the root, unexpanded), and a budget past
    the bound or ``max`` is the bound.
    """

    for index in range(12):
        (tmp_path / f"f{index:02d}.py").write_text("x" * (index + 1))
    server._set_root_dir(tmp_path)
    monkeypatch.setattr(server, "ROLLUP_DEFAULT_NODES", 4)
    monkeypatch.setattr(server, "ROLLUP_MAX_NODES", 9)

    def emitted(node: dict[str, Any]) -> int:
        return 1 + sum(emitted(child) for child in node.get("children") or [])

    async def run() -> dict[str, int]:
        async with inventory_harness(tmp_path, config=_WATCH_OFF) as harness:
            counts: dict[str, int] = {}
            for nodes in ("", "0", "6", "999999", "max"):
                body = await _body(harness, {"path": "", **({"nodes": nodes} if nodes else {})})
                validate_rollup_envelope(body)
                counts[nodes] = emitted(body["node"])
            return counts

    assert asyncio.run(run()) == {"": 4, "0": 1, "6": 6, "999999": 9, "max": 9}


def test_rollup_route_validator_names_the_budget_scope_and_encoding(tmp_path: Path) -> None:
    """Each of ``nodes``, ``ignored``, and ``encoding`` names a different body, and the
    defaults asked for by name are the body asked for without them."""

    (tmp_path / "a.py").write_text("x" * 8)
    server._set_root_dir(tmp_path)

    async def run() -> list[str]:
        async with inventory_harness(tmp_path, config=_WATCH_OFF) as harness:
            tags: list[str] = []
            for params in (
                {},
                {"nodes": str(ROLLUP_DEFAULT_NODES), "ignored": "include", "encoding": "json"},
                {"nodes": "5"},
                {"ignored": "exclude"},
                {"encoding": "compact"},
            ):
                response = await _response(harness, {"path": "", **params})
                tags.append(response.headers["etag"])
            return tags

    tags = asyncio.run(run())
    assert tags[0] == tags[1]
    assert len({tags[0], *tags[2:]}) == 4


def _dense_fixture(root: Path) -> None:
    """Gitignored folders and files beside unignored ones, with names a path must keep."""

    (root / ".git").mkdir()
    (root / ".gitignore").write_text("build/\n*.log\n")
    for relative, size in {
        "build/out.bin": 5_000,
        "build/deep/map.txt": 90,
        "app.log": 700,
        "top.md": 32,
        "src/main.py": 640,
        "src/notes v2.md": 16,
        "src/#hash.txt": 8,
        "src/a'b\"c.py": 2,
        "src/run.log": 60,
        "src/ü dir/雪 snow.txt": 4,
        "src/ü dir/Makefile": 40,
        "src/mixed/a.py": 10,
        "src/mixed/huge.log": 3_000,
    }.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x" * size)


def test_rollup_route_exclude_is_the_same_envelope_less_the_ignored_nodes(
    tmp_path: Path,
) -> None:
    """``ignored=exclude`` leaves out the ignored nodes and changes nothing else.

    The fully ignored ``build/`` is not among the children, and the tallies, breakdown,
    legend, index status, and every remaining folder's totals and ``dominant_ext`` are the
    included body's. ``src/mixed`` keeps ``.log`` as its dominant extension: it ranks every
    file beneath the folder, ignored ones too.
    """

    _dense_fixture(tmp_path)
    server._set_root_dir(tmp_path)
    query = {"path": "", "depth": "max", "top": "max", "nodes": "max"}

    async def run() -> tuple[dict[str, Any], dict[str, Any]]:
        async with inventory_harness(tmp_path, config=_WATCH_OFF) as harness:
            included = await _body(harness, query)
            excluded = await _body(harness, {**query, "ignored": "exclude"})
            return included, excluded

    included, excluded = asyncio.run(run())
    validate_rollup_envelope(excluded)
    assert {k: v for k, v in excluded.items() if k != "node"} == {
        k: v for k, v in included.items() if k != "node"
    }
    assert _by_path(excluded["node"]) == _by_path(_without_ignored(included["node"]))
    assert "build" not in {child["path"] for child in excluded["node"]["children"]}
    assert "build" in {child["path"] for child in included["node"]["children"]}
    src = next(child for child in excluded["node"]["children"] if child["path"] == "src")
    mixed = next(child for child in src["children"] if child["path"] == "src/mixed")
    assert (mixed["dominant_ext"], mixed["total_files"], mixed["unignored_files"]) == (".log", 2, 1)


def test_rollup_route_compact_decodes_to_the_json_body(tmp_path: Path) -> None:
    """A compact body is the JSON body with each folder's files written as entries.

    Its file paths, derived as the folder's path, a `/`, and the name, are the paths the
    walker gave the files, names with spaces, quotes, ``#``, and non-ASCII letters among
    them; at the root and below it, with and without the ignored nodes. Only the compact
    envelope says ``"encoding": "compact"``.
    """

    _dense_fixture(tmp_path)
    server._set_root_dir(tmp_path)

    async def run() -> list[tuple[dict[str, Any], dict[str, Any]]]:
        async with inventory_harness(tmp_path, config=_WATCH_OFF) as harness:
            pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
            for path in ("", "src"):
                for ignored in ("include", "exclude"):
                    query = {"path": path, "depth": "max", "top": "max", "ignored": ignored}
                    json_body = await _body(harness, query)
                    compact_body = await _body(harness, {**query, "encoding": "compact"})
                    pairs.append((json_body, compact_body))
            return pairs

    decoded_names: set[str] = set()
    for json_body, compact_body in asyncio.run(run()):
        validate_rollup_envelope(json_body)
        validate_rollup_envelope(compact_body)
        assert "encoding" not in json_body
        assert compact_body.pop("encoding") == "compact"
        assert {k: v for k, v in compact_body.items() if k != "node"} == {
            k: v for k, v in json_body.items() if k != "node"
        }
        decoded = _decode_compact(compact_body["node"])
        assert decoded == _by_path(json_body["node"])
        decoded_names.update(node["path"] for node in _walk(decoded))
    assert {"src/ü dir/雪 snow.txt", "src/a'b\"c.py", "src/notes v2.md"} <= decoded_names


def test_rollup_body_cache_evicts_by_bytes(monkeypatch: pytest.MonkeyPatch) -> None:
    """The oldest bodies go until the bytes fit, and a body past the bound is not kept."""

    monkeypatch.setattr(server, "ROLLUP_BODY_CACHE_BYTES", 100)
    monkeypatch.setattr(server, "ROLLUP_BODY_CACHE_ENTRIES", 8)
    server.reset_response_caches_for_tests()
    try:
        for etag in ("a", "b", "c"):
            server._remember_rollup_body(etag, b"x" * 40)
        assert list(server._ROLLUP_BODY_CACHE) == ["b", "c"]
        server._remember_rollup_body("oversized", b"x" * 101)
        assert list(server._ROLLUP_BODY_CACHE) == ["b", "c"]
        server._remember_rollup_body("full", memoryview(b"x" * 100))
        assert list(server._ROLLUP_BODY_CACHE) == ["full"]
    finally:
        server.reset_response_caches_for_tests()


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
        async with inventory_harness(tmp_path, config=_WATCH_OFF) as harness:
            before = await _engine_version(harness)
            first = await _response(harness, {"path": ""})
            etag = first.headers["etag"]
            revalidated = await _response(harness, {"path": ""}, etag)
            assert revalidated.status_code == 304
            cached = await _response(harness, {"path": ""})
            assert bytes(cached.body) == bytes(first.body)
            deeper = await _response(harness, {"path": "", "depth": "1"})
            assert await _engine_version(harness) == before, "the version must hold"
            return etag, cached.headers["etag"], deeper.headers["etag"]

    etag, cached_etag, deeper_etag = asyncio.run(run())
    assert cached_etag == etag
    assert deeper_etag != etag
    assert etag in server._ROLLUP_BODY_CACHE


def test_unicode_root_and_subfolder_rollups_revalidate_independently(tmp_path: Path) -> None:
    root = tmp_path / "资料"
    child = root / "子目录"
    child.mkdir(parents=True)
    (root / "README.md").write_text("root\n")
    (child / "雪.txt").write_text("nested\n")
    server._set_root_dir(root)

    async def run() -> None:
        async with inventory_harness(root, config=_WATCH_OFF) as harness:
            tags: list[str] = []
            for path, files, size in (("", 2, 12), ("子目录", 1, 7)):
                params = {"path": path, "depth": "0"}
                first = await _response(harness, params)
                assert first.status_code == 200
                body = json.loads(bytes(first.body))
                validate_rollup_envelope(body)
                assert body["path"] == path
                assert body["node"]["total_files"] == files
                assert body["node"]["total_size"] == size
                tag = first.headers["etag"]
                assert re.fullmatch(rf'"{BUILD_TAG}-[0-9a-f]{{64}}"', tag)
                tags.append(tag)
                repeated = await _response(harness, params)
                assert repeated.headers["etag"] == tag
                assert bytes(repeated.body) == bytes(first.body)
                revalidated = await _response(harness, params, tag)
                assert revalidated.status_code == 304
                assert bytes(revalidated.body) == b""
                deeper = await _response(harness, {"path": path, "depth": "1"}, tag)
                assert deeper.status_code == 200
                assert deeper.headers["etag"] != tag
            assert tags[0] != tags[1]
            different_path = await _response(harness, {"path": "子目录", "depth": "0"}, tags[0])
            assert different_path.status_code == 200
            assert different_path.headers["etag"] == tags[1]

    asyncio.run(run())


def test_simultaneous_identical_rollups_compute_once(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    """Requests for one answer at one inventory version share one build.

    Coalescing is keyed on the version, so the test holds the version still: with
    the watcher off, a settled walk leaves nothing that can write to the
    inventory. With it on, an observation landing mid-gather -- a late event on a
    busy host -- splits the requests across two versions and two correct builds,
    and fails the test with nothing wrong in coalescing.
    """
    (tmp_path / "src").mkdir()
    for index in range(5):
        (tmp_path / "src" / f"f{index}.py").write_text("x" * 32)
    server._set_root_dir(tmp_path)

    async def run() -> tuple[int, list[bytes], EngineVersion, EngineVersion]:
        import metabrowser.inventory_engine.providers.python_inventory as provider

        calls = 0
        real_build = provider.build_rollup

        def counting_build(*args: Any, **kwargs: Any) -> Any:
            nonlocal calls
            calls += 1
            return real_build(*args, **kwargs)

        monkeypatch.setattr(provider, "build_rollup", counting_build)
        async with inventory_harness(tmp_path, config=_WATCH_OFF) as harness:
            before = await _engine_version(harness)
            responses = await asyncio.gather(
                *(_response(harness, {"path": ""}) for _index in range(6))
            )
            after = await _engine_version(harness)
            return calls, [bytes(response.body) for response in responses], before, after

    calls, bodies, before, after = asyncio.run(run())
    assert after == before, "the inventory must hold one version for the gather"
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
        import metabrowser.inventory_engine.providers.python_inventory as provider

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
            await held_until(started, 5.0)
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
        import metabrowser.inventory_engine.providers.python_inventory as provider

        started = threading.Event()
        release = threading.Event()
        real_build = provider.build_rollup

        def gated_build(*args: Any, **kwargs: Any) -> Any:
            started.set()
            assert release.wait(timeout=5.0)
            return real_build(*args, **kwargs)

        monkeypatch.setattr(provider, "build_rollup", gated_build)
        async with inventory_harness(tmp_path, config=_WATCH_OFF) as harness:
            first_task = asyncio.create_task(_response(harness, {"path": ""}))
            await held_until(started, 5.0)
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
            served = await _engine_version(harness)
            first_body = json.loads(bytes(first.body))
            second = await _response(harness, {"path": ""}, first.headers["etag"])
            assert await _engine_version(harness) == served, "the version must hold"
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


def test_rollup_falls_back_to_a_current_read_when_its_pinned_version_expires(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    """A version that moves before the pinned read starts is served, not failed.

    The route pins its build to the version it checked so the body matches its
    tag. When discovery moves on between that check and the pinned read, the
    provider refuses the read, and the route answers with one unpinned read
    under that read's own tag. `test_rollup_payload_and_etag_share_one_version`
    moves the version during the build instead.
    """
    (tmp_path / "a.txt").write_text("a")
    server._set_root_dir(tmp_path)

    async def run() -> tuple[list[tuple[bool, str]], int, int, int]:
        async with inventory_harness(tmp_path, config=_WATCH_OFF) as harness:
            coordinator = harness.runtime.coordinator
            real_checkpoint = coordinator.checkpoint
            real_read = coordinator.read
            rollup_reads: list[tuple[bool, str]] = []

            async def checkpoint_then_move() -> tuple[HostCursor, HostVersion, IndexState]:
                checked = await real_checkpoint()
                monkeypatch.setattr(coordinator, "checkpoint", real_checkpoint)
                (tmp_path / "b.txt").write_text("b")
                await coordinator.refresh(
                    RefreshRequest(
                        observations=(
                            RefreshObservation(path="b.txt", kind=ObservationKind.CREATED),
                        )
                    )
                )
                return checked

            async def recording_read(request: ReadRequest, **kwargs: Any) -> CoordinatedRead:
                if not any(isinstance(query, RollupQuery) for query in request.queries):
                    return await real_read(request, **kwargs)
                pinned = request.at_version is not None
                try:
                    result = await real_read(request, **kwargs)
                except VersionUnavailableError:
                    rollup_reads.append((pinned, "expired"))
                    raise
                rollup_reads.append((pinned, "served"))
                return result

            monkeypatch.setattr(coordinator, "read", recording_read)
            monkeypatch.setattr(coordinator, "checkpoint", checkpoint_then_move)
            response = await _response(harness, {"path": ""})
            files = json.loads(bytes(response.body))["node"]["total_files"]
            revalidated = await _response(harness, {"path": ""}, response.headers["etag"])
            return rollup_reads, response.status_code, files, revalidated.status_code

    rollup_reads, status, files, revalidated_status = asyncio.run(run())
    assert rollup_reads == [(True, "expired"), (False, "served")]
    assert (status, files) == (200, 2)
    assert revalidated_status == 304, "the fallback's tag must name the version it served"


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
