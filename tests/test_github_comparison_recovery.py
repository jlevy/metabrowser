"""Explicit repair belongs to the displayed PR selection, even after metadata advances."""

from __future__ import annotations

import asyncio
import subprocess
from collections import OrderedDict
from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient

from metabrowser.builtin_plugins.diff import sidekick as diff
from metabrowser.builtin_plugins.diff.comparison_cache import ComparisonCache
from metabrowser.builtin_plugins.github import pulls
from metabrowser.builtin_plugins.github.pull_record import PullRecord, write_pull_record
from metabrowser.builtin_plugins.github.pull_route import PullHost, RefreshRequest, start_refresh
from metabrowser.builtin_plugins.github.served_pull import (
    MAX_ISSUED_COMPARISONS,
    ServedPull,
    ServedPulls,
)
from metabrowser.cache.paths import source_pull_record
from metabrowser.git.object_failures import observed_object_failures
from metabrowser.git.process import repository_store_target
from tests.diff_fixture_repo import git
from tests.git_pin_harness import git_env
from tests.github_pull_fixture import ok, scenario
from tests.golden_harness import JSON_BODY, settle
from tests.test_github_pulls import _Stand
from tests.test_github_pulls import pinned_pull as pinned_pull
from tests.test_github_pulls import stand as stand


@pytest.mark.parametrize("first_fails", [False, True])
def test_explicit_retry_joining_active_metadata_job_is_consumed(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch, first_fails: bool
) -> None:
    record = stand.refresh(7)
    assert record.comparison is not None
    pair = (record.comparison.base, record.comparison.head)
    calls: list[dict[str, Any]] = []

    async def run() -> None:
        entered, release = asyncio.Event(), asyncio.Event()
        held = ServedPull(stand.published, 7)
        held.note_comparison(pair, displayed=True)
        kept = ServedPulls(stand.published, _kept=OrderedDict({7: held}))
        host = PullHost(kept, lambda _number: held.refreshing, lambda _number: "started")

        async def refresh(_published: Any, _number: int, **kwargs: Any) -> PullRecord:
            calls.append(kwargs)
            if len(calls) == 1:
                entered.set()
                await release.wait()
                if first_fails:
                    raise pulls.PullDataError("network_error", "offline")
            return record

        monkeypatch.setattr(pulls, "refresh_pull_request", refresh)
        task = asyncio.create_task(held.refresh())
        await entered.wait()
        assert await start_refresh(host, RefreshRequest(7, True, recovery=pair)) == "joined"
        assert await start_refresh(host, RefreshRequest(7, True, recovery=pair)) == "joined"
        release.set()
        await task
        assert calls == [{}, {"recover": True, "recovery_pair": pair}]
        assert held.last is not None and held.last["outcome"] == "succeeded"
        assert not held.refreshing

    asyncio.run(run())


def test_displayed_selection_survives_many_metadata_advances(stand: _Stand) -> None:
    held = ServedPull(stand.published, 7)
    displayed = ("a" * 40, "b" * 40)
    held.note_comparison(displayed, displayed=True)
    for index in range(MAX_ISSUED_COMPARISONS * 3):
        held.note_comparison(("a" * 40, f"{index:040x}"))
    assert held.issued_comparison(displayed)
    assert len(held._issued) == MAX_ISSUED_COMPARISONS
    assert not held.issued_comparison(("a" * 40, "0" * 40))


@pytest.mark.parametrize(
    "recovery",
    [
        {"base": "HEAD", "head": "a" * 40},
        {"base": "a" * 40, "head": "b" * 40, "path": "ignored"},
        {"base": "a" * 40, "head": "b" * 40},
        "a" * 40,
    ],
)
def test_repair_refuses_malformed_or_unissued_pairs_before_network(
    pinned_pull: tuple[_Stand, TestClient], recovery: object
) -> None:
    stand, client = pinned_pull
    stand.calls()
    refused = client.post(
        "/api/plugin/github/pull-refresh",
        headers=JSON_BODY,
        json={"number": 7, "retry": True, "recovery": recovery},
    )
    assert refused.status_code == 400
    assert refused.json()["code"] == "invalid_request"
    assert stand.calls() == []


def _unpack(store: Path, temporary: Path) -> None:
    packs = tuple((store / "objects" / "pack").glob("*.pack"))
    payloads = [pack.read_bytes() for pack in packs]
    for pack in packs:
        pack.unlink()
        pack.with_suffix(".idx").unlink()
    for payload in payloads:
        subprocess.run(
            ["git", "--git-dir", str(store), "unpack-objects"],
            input=payload,
            capture_output=True,
            check=True,
            env=git_env(temporary),
        )


@pytest.mark.parametrize("record_disappears", [False, True])
def test_displayed_missing_blob_repairs_after_record_and_head_advance(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch, record_disappears: bool
) -> None:
    stand, client = pinned_pull
    monkeypatch.setattr(diff, "_COMPARISONS", ComparisonCache())
    envelope = client.get("/api/plugin/github/pull?number=7").json()
    route = envelope["comparison_route"]
    old = stand.record(7)
    assert isinstance(old, PullRecord) and old.comparison is not None
    pair = (old.comparison.base, old.comparison.head)
    _unpack(stand.published.git_dir, stand.tmp_path)
    oid = git(stand.published.git_dir, "rev-parse", f"{pair[1]}:src/app.txt").decode().strip()
    loose = stand.published.git_dir / "objects" / oid[:2] / oid[2:]
    assert loose.is_file()
    loose.unlink()
    refused = client.get(route)
    assert refused.status_code == 409, refused.text
    target = repository_store_target(git_dir=stand.published.git_dir)
    assert [failure.oid for failure in observed_object_failures.pending(target, pair)] == [oid]

    new_head = stand.origin["draft_head"]
    git(stand.origin.path, "update-ref", "refs/pull/7/head", new_head)
    newer = old.model_copy(
        update={
            "pull": old.pull.model_copy(
                update={"head": old.pull.head.model_copy(update={"sha": new_head})}
            ),
            "comparison": old.comparison.model_copy(update={"head": new_head}),
        }
    )
    write_pull_record(stand.published.home, stand.published.slug, newer)
    assert (
        client.get("/api/plugin/github/pull?number=7").json()["record"]["comparison"]["head"]
        == new_head
    )
    answers = scenario(stand.origin)
    path = "repos/octo/demo/pulls/7"
    answers["api"][path]["body"]["head"]["sha"] = new_head
    answers["api"][path] = ok(path, answers["api"][path]["body"])
    stand.answer(answers)
    stand.calls()
    if record_disappears:
        (stand.published.home / source_pull_record(stand.published.slug, 7)).unlink()
    started = client.post(
        "/api/plugin/github/pull-refresh",
        headers=JSON_BODY,
        json={"number": 7, "retry": True, "recovery": {"base": pair[0], "head": pair[1]}},
    )
    assert started.status_code == 202, started.text
    settle(client)
    refreshed = client.get("/api/plugin/github/pull?number=7").json()
    assert refreshed["last_refresh"]["outcome"] == "succeeded", refreshed["last_refresh"]
    assert git(stand.published.git_dir, "cat-file", "-t", oid) == b"blob\n"
    assert observed_object_failures.pending(target, pair) == ()
    repaired = client.get(route)
    assert repaired.status_code == 200, repaired.text
    assert repaired.json()["resolved"]["right"]["id"] == pair[1]
    assert refreshed["record"]["comparison"]["head"] == new_head


def test_missing_pinned_root_tree_refuses_startup_without_clone_or_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from metabrowser.cache import acquire
    from tests.golden_harness import isolate_cli
    from tests.test_cli_git_pin_golden import _origin, _Pin

    home = isolate_cli(tmp_path, monkeypatch).home
    origin, commit = _origin(tmp_path, "startup.git", ((b"100644", (b"note.txt",), b"text\n"),))
    pin = _Pin(tmp_path)
    pin.use(origin)
    pin.api("/api/tree")
    store = next((home / "repository-stores").glob("*/repository.git"))
    _unpack(store, tmp_path)
    root = git(store, "rev-parse", f"{commit}^{{tree}}").decode().strip()
    (store / "objects" / root[:2] / root[2:]).unlink()

    async def forbidden(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("damaged cached startup must not clone")

    monkeypatch.setattr(acquire, "acquire_into_staging", forbidden)
    origin.rename(origin.with_name("origin-offline.git"))
    refused = pin.api("/api/tree", fails=True)
    assert "Traceback" not in refused.stderr
    assert str(tmp_path) not in refused.stderr
    assert "Error:" in refused.stderr
    assert "opening the pinned revision" in refused.stderr


def test_corrupt_read_discards_persisted_manifest_before_successful_repair(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    from metabrowser.builtin_plugins.github import pull_manifest
    from metabrowser.diff.adapters.git import GitDiffSource
    from metabrowser.git.tree_source import GitObjectCorruptError

    stand, client = pinned_pull
    monkeypatch.setattr(diff, "_COMPARISONS", ComparisonCache())
    envelope = client.get("/api/plugin/github/pull?number=7").json()
    pair = envelope["record"]["comparison"]
    bank = next((stand.published.home / pull_manifest._directory(stand.published)).glob("*.json"))
    assert bank.read_bytes() != b"{}"
    oid = git(stand.published.git_dir, "rev-parse", f"{pair['head']}:src/app.txt").decode().strip()
    hydrate = GitDiffSource.hydrate

    async def corrupt(*_args: Any, **_kwargs: Any) -> Any:
        # The lower-layer replica tests forge real loose and packed bytes. This injects
        # that same typed result to isolate the provider-owned persistent cache bridge.
        raise GitObjectCorruptError(oid)

    monkeypatch.setattr(GitDiffSource, "hydrate", corrupt)
    assert client.get(envelope["comparison_route"]).status_code == 409
    assert bank.read_bytes() == b"{}"
    assert diff._COMPARISONS.sizes()["manifests"] == 0
    monkeypatch.setattr(GitDiffSource, "hydrate", hydrate)
    repaired = client.post(
        "/api/plugin/github/pull-refresh",
        headers=JSON_BODY,
        json={"number": 7, "retry": True, "recovery": {"base": pair["base"], "head": pair["head"]}},
    )
    assert repaired.status_code == 202
    settle(client)
    assert client.get(envelope["comparison_route"]).status_code == 200
    assert bank.read_bytes() != b"{}"


def test_read_only_cross_pr_link_does_not_authorize_network_repair(
    pinned_pull: tuple[_Stand, TestClient],
) -> None:
    stand, client = pinned_pull
    other = stand.refresh(8)
    assert other.comparison is not None
    pair = {"base": other.comparison.base, "head": other.comparison.head}
    route = (
        f"/api/plugin/github/pull-comparison?number=7&left={pair['base']}"
        f"&right={pair['head']}&base_policy=merge_base"
    )
    stand.calls()
    assert client.get(route).status_code == 200, "existing full-endpoint reads remain compatible"
    refused = client.post(
        "/api/plugin/github/pull-refresh",
        headers=JSON_BODY,
        json={"number": 7, "retry": True, "recovery": pair},
    )
    assert refused.status_code == 400
    assert stand.calls() == []


def test_refused_job_cannot_leave_repair_for_a_later_automatic_refresh(stand: _Stand) -> None:
    async def run() -> None:
        held = ServedPull(stand.published, 7)
        pair = ("a" * 40, "b" * 40)
        held.note_comparison(pair)
        kept = ServedPulls(stand.published, _kept=OrderedDict({7: held}))
        host = PullHost(kept, lambda _number: False, lambda _number: "too_many")
        assert await start_refresh(host, RefreshRequest(7, True, recovery=pair)) == "too_many"
        assert not held._recoveries

    asyncio.run(run())
