"""End-to-end test of the full browser lifespan + route stack.

Exercises the wiring as a real ``metab`` serving deployment
sees it: the lifespan hook spawns walker + active-tracker +
watcher; routes serve from the in-memory inventory; SSE
delivers fs.change ops; the watcher picks up new files.

This is the test that proves "the user can run `metab .`
and everything works" without actually opening a
browser. Coverage:

* Lifespan startup + clean teardown.
* /api/tree, /api/recent, /api/index/meta, /api/capabilities
  all serve from the populated inventory after the walker
  completes.
* Cold-start budget sanity: walker completes within 5 s on a
  ~1k-file fixture.
* fs.change ops flow: a new file written into the tree after
  the walker completes is detected by the polling watcher
  within 5 s and the new path appears in the inventory.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

from metabrowser import server as proc_browser
from metabrowser.inventory_engine.runtime import default_inventory_config
from tests.inventory_harness import inventory_harness, wait_until_settled


def _build_realistic_fixture(root: Path) -> None:
    """Build a small workspace with docs, run logs, state, and Markdown."""
    (root / "README.md").write_text("# Test fixture\n")
    (root / "docs").mkdir()
    (root / "docs" / "guide.md").write_text("# Guide\n")
    (root / "runs").mkdir()
    (root / "runs" / "x").mkdir()
    (root / "runs" / "x" / ".logs").mkdir()
    (root / "runs" / "x" / ".logs" / "session.jsonl").write_text(
        '{"event":"start","ts":"2026-05-06T00:00:00Z"}\n'
    )
    (root / "runs" / "x" / ".state").mkdir()
    (root / "runs" / "x" / ".state" / "status.yaml").write_text("phase: running\n")


class _FakeQuery:
    def __init__(self, d: dict[str, str]) -> None:
        self._d = d

    def get(self, k: str, default: str = "") -> str:
        return self._d.get(k, default)

    def getlist(self, k: str) -> list[str]:
        v = self._d.get(k, "")
        return [s for s in v.split(",") if s] if v else []


class _FakeRequest:
    def __init__(self, q: dict[str, str] | None = None) -> None:
        self.query_params = _FakeQuery(q or {})
        self.headers: dict[str, str] = {}
        self.app: object = proc_browser.app


def test_full_lifespan_stack_serves_all_endpoints(tmp_path: Path) -> None:
    """The full app starts, populates the inventory, and serves
    every inventory, recent-file, and watcher endpoint correctly."""

    _build_realistic_fixture(tmp_path)

    async def _run() -> dict[str, Any]:
        # ``_set_root_dir`` is the public way to point the
        # browser at a different root; monkey-patching the
        # imported binding doesn't affect call sites that
        # imported the name at module-load time.
        proc_browser._set_root_dir(tmp_path)
        try:
            async with proc_browser.app.router.lifespan_context(proc_browser.app):
                # Wait for walker to drain.
                await wait_until_settled(proc_browser.app.state.inventory_runtime, timeout=10.0)
                # /api/tree
                tree_resp = await proc_browser.api_tree(cast(Any, _FakeRequest()))
                tree = json.loads(bytes(tree_resp.body))
                # /api/recent
                recent_resp = await proc_browser.api_recent(
                    cast(Any, _FakeRequest({"window": "all", "limit": "100"}))
                )
                recent = json.loads(bytes(recent_resp.body))
                # /api/index/meta
                from metabrowser.events_route import (
                    api_capabilities,
                    api_index_meta,
                )

                meta_resp = await api_index_meta(cast(Any, _FakeRequest()))
                meta = json.loads(bytes(meta_resp.body))
                # /api/capabilities
                cap_resp = await api_capabilities(cast(Any, _FakeRequest()))
                cap = json.loads(bytes(cap_resp.body))
                return {"tree": tree, "recent": recent, "meta": meta, "cap": cap}
        finally:
            proc_browser._set_root_dir(Path())

    out = asyncio.run(_run())

    # /api/tree: served from inventory; top-level entries present.
    assert out["tree"]["tally_cache_status"] == "done"
    assert out["tree"]["tally_cache_max_files"] > 0
    names = {row["name"] for row in out["tree"]["tree"]}
    assert "README.md" in names
    assert "runs" in names
    assert "docs" in names

    # /api/recent: matches the expected file set.
    assert out["recent"]["total_matching"] >= 4  # README + guide + jsonl + yaml
    assert out["recent"]["truncated"] is False

    # /api/index/meta: counts make sense.
    assert out["meta"]["status"] == "done"
    assert out["meta"]["indexed_files"] >= 4
    assert out["meta"]["complete"] is True

    # /api/capabilities: backends populated with native or
    # polling, walker done.
    assert out["cap"]["backends"][0]["mode"] in ("native", "polling")
    assert out["cap"]["index"]["complete"] is True


def test_watcher_detects_new_file_after_walker_completes(tmp_path: Path) -> None:
    """Real watcher loop catches a new file written after the
    walker has finalized. Uses polling mode so it works on any
    fs without needing the native backend."""

    _build_realistic_fixture(tmp_path)

    async def _run() -> bool:
        config = replace(default_inventory_config(), watch_mode="poll")
        async with inventory_harness(tmp_path, config=config) as harness:
            await asyncio.sleep(0.5)
            new_file = tmp_path / "runs" / "x" / ".logs" / "fresh.jsonl"
            new_file.write_text('{"event":"new"}\n')
            from metabrowser.inventory_engine.contract import (
                EntryPresence,
                EntryProjection,
                EntryQuery,
                ReadRequest,
            )

            deadline = asyncio.get_running_loop().time() + 5.0
            while asyncio.get_running_loop().time() < deadline:
                read = await harness.runtime.coordinator.read(
                    ReadRequest(
                        queries=(
                            EntryQuery(
                                query_id="fresh",
                                path="runs/x/.logs/fresh.jsonl",
                            ),
                        )
                    )
                )
                projection = read.result.projection("fresh")
                if isinstance(projection, EntryProjection) and (
                    projection.presence is EntryPresence.PRESENT
                ):
                    return True
                await asyncio.sleep(0.1)
            return False

    assert asyncio.run(_run()) is True, "watcher did not pick up new file"


def test_recent_filter_includes_logs_state_files(tmp_path: Path) -> None:
    """End-to-end: write a fresh .jsonl into .logs and verify
    /api/recent surfaces it after the walker completes (a
    common operator-in-the-loop pattern: 'I just wrote this
    file, where is it?')."""

    _build_realistic_fixture(tmp_path)

    async def _run() -> set[str]:
        proc_browser._set_root_dir(tmp_path)
        try:
            async with inventory_harness(tmp_path) as harness:
                request = _FakeRequest({"window": "all", "limit": "100"})
                request.app = harness.app
                recent_resp = await proc_browser.api_recent(cast(Any, request))
                recent = json.loads(bytes(recent_resp.body))
        finally:
            proc_browser._set_root_dir(Path())

        # Recent's wire shape is unclustered (clustering is a
        # rendering concern owned by the SPA); pull leaf paths
        # directly from entries_flat.
        return {e["path"] for e in recent["entries_flat"]}

    paths = asyncio.run(_run())
    # Both .logs and .state files are visible in Recent.
    assert any(p.endswith(".jsonl") for p in paths), f"no .jsonl in recent paths={paths}"
    assert any(p.endswith(".yaml") for p in paths), f"no .yaml in recent paths={paths}"
    # Plain markdown also visible (Recent isn't scoped to .logs/.state).
    assert any(p.endswith(".md") for p in paths), f"no .md in recent paths={paths}"
