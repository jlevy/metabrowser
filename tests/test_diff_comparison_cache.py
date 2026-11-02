"""A comparison of two commit IDs is kept, and validated; anything else is asked again.

The transcript this writes, ``tests/golden/cli-diff-comparison-cache.txt``, is what the route
answers through the real request stack: `--api` prints a status and a body, and what is
pinned here is the headers, so each block is one request with the ones that matter.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
from httpx2 import Response
from starlette.testclient import TestClient

from metabrowser import server
from metabrowser.builtin_plugins.diff import sidekick
from metabrowser.builtin_plugins.diff.comparison_cache import ComparisonCache, ResolvedManifest
from metabrowser.diff.adapters.git import GitDiffSource
from metabrowser.http_caching import BUILD_TAG
from tests.diff_fixture_repo import build_diff_fixture, git
from tests.git_pin_harness import pinned_client
from tests.golden_harness import check_golden
from tests.required_tools import needs_git

pytestmark = needs_git


def _store(tmp_path: Path) -> tuple[Path, str, str]:
    """A bare store of the diff fixture's two commits."""
    work = tmp_path / "work"
    work.mkdir()
    base, target = build_diff_fixture(work)
    store = tmp_path / "store.git"
    git(work.parent, "clone", "-q", "--bare", "--template=", str(work), str(store))
    return store, base, target


def _route(*query: tuple[str, str]) -> str:
    joined = "&".join(f"{name}={value}" for name, value in query)
    return f"/api/plugin/diff/comparison?{joined}"


class _Spy:
    """Counts the Git runs of a request, by the adapter's two costly steps."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.manifests = 0
        self.patches = 0
        real_manifest = GitDiffSource.manifest
        real_patch = GitDiffSource._patch

        async def manifest(source: GitDiffSource, resolved: Any) -> Any:
            self.manifests += 1
            return await real_manifest(source, resolved)

        async def patch(source: GitDiffSource, *args: Any, **kwargs: Any) -> bytes:
            self.patches += 1
            return await real_patch(source, *args, **kwargs)

        monkeypatch.setattr(GitDiffSource, "manifest", manifest)
        monkeypatch.setattr(GitDiffSource, "_patch", patch)


def _block(title: str, route: str, response: Response, spy: _Spy) -> str:
    """One request of the transcript: what it asked, and the headers that say what is kept."""
    shown = route.replace(BUILD_TAG, "<BUILD>")
    lines = [f"## {title}", f"GET {shown}", f"status: {response.status_code}"]
    for name in ("cache-control", "etag", "content-encoding", "vary"):
        value = response.headers.get(name)
        if value is not None:
            shown_value = value.replace(BUILD_TAG, "<BUILD>")
            lines.append(f"{name}: {shown_value}")
    lines.append(f"work: {spy.manifests} manifest, {spy.patches} patch")
    spy.manifests = spy.patches = 0
    return "\n".join(lines)


def test_what_a_store_keeps_and_says(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store, base, target = _store(tmp_path)
    spy = _Spy(monkeypatch)
    # The fixture pins identity and dates, so its commit IDs and these tags are fixed.
    two = (("left", base), ("right", target), ("base_policy", "merge_base"))
    named = (*two, ("build", BUILD_TAG))
    blocks: list[str] = []

    async def run() -> None:
        async with pinned_client(store, target) as (client, _subject):

            async def ask(
                title: str, route: str, headers: dict[str, str] | None = None
            ) -> Response:
                response = await client.get(route, headers=headers or {})
                blocks.append(_block(title, route, response, spy))
                return response

            first = await ask("Two commit IDs, naming this build: computed", _route(*named))
            assert first.status_code == 200
            document = first.json()
            again = await ask("The same address again: no Git at all", _route(*named))
            assert again.json() == document
            etag = first.headers["etag"]
            conditional = await ask(
                "A reload with what it holds: no body", _route(*named), {"if-none-match": etag}
            )
            assert conditional.status_code == 304 and conditional.content == b""
            unnamed = await ask("Not naming a build: the browser must ask", _route(*two))
            assert unnamed.headers["etag"] == etag and unnamed.json() == document
            other_build = await ask(
                "Naming an older build: the browser must ask too",
                _route(*two, ("build", "000000000000")),
            )
            assert other_build.headers["cache-control"] == "no-cache"
            direct = await ask(
                "Another base policy is another answer",
                _route(("left", base), ("right", target), ("base_policy", "direct"), named[-1]),
            )
            assert direct.headers["etag"] != etag
            one = await ask(
                "One deferred file: its manifest is kept, so one path-limited diff",
                _route(*named, ("file", "a.py")),
            )
            assert one.headers["etag"] != etag
            assert [c["new"]["path"] for c in one.json()["manifest"]["files"]] == ["a.py"]
            await ask("That file again: no Git at all", _route(*named, ("file", "a.py")))
            revision = await ask(
                "A commit against its parent, by ID", _route(("revision", target), named[-1])
            )
            assert revision.json()["resolved"]["base_policy"] == "first_parent"
            symbolic = await ask(
                "A name can move: asked every time, and nothing is said",
                _route(("left", "main~1"), ("right", "main")),
            )
            assert "etag" not in symbolic.headers and "cache-control" not in symbolic.headers
            head = await ask("HEAD is the pin, which a switch moves", _route(("revision", "HEAD")))
            assert "etag" not in head.headers
            refused = await ask(
                "A commit the store lacks is a refusal, never kept",
                _route(("left", "0" * 40), ("right", target), named[-1]),
            )
            assert refused.status_code == 404
            assert refused.json()["error"] == "diff_comparison"

    asyncio.run(run())
    check_golden("cli-diff-comparison-cache.txt", "\n\n".join(blocks) + "\n")


def test_a_kept_answer_is_the_bytes_of_a_computed_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Over gzip and without it, first and repeated, against the route with nothing kept."""
    store, base, target = _store(tmp_path)
    two = (("left", base), ("right", target), ("base_policy", "merge_base"))

    async def run() -> None:
        async with pinned_client(store, target) as (client, _subject):
            plain = await client.get(_route(*two), headers={"accept-encoding": "identity"})
            assert "content-encoding" not in plain.headers
            zipped = await client.get(_route(*two), headers={"accept-encoding": "gzip"})
            assert zipped.headers["content-encoding"] == "gzip"
            assert zipped.content == plain.content, "httpx decodes it; the JSON must be the same"
            monkeypatch.setattr(sidekick, "_kept_key", lambda *_args: None)
            computed = await client.get(_route(*two), headers={"accept-encoding": "identity"})
            assert "etag" not in computed.headers
            assert computed.content == plain.content

    asyncio.run(run())


def test_a_folder_is_never_kept_because_its_working_tree_is_an_input(tmp_path: Path) -> None:
    """Commit IDs are not all a folder's answer depends on: an edit to `.gitattributes` moves it."""
    root = tmp_path / "repo"
    root.mkdir()
    base, target = build_diff_fixture(root)
    server._set_root_dir(root)

    def ask() -> tuple[Any, dict[str, Any]]:
        request = _plain_request(left=base, right=target, build=BUILD_TAG)
        response = asyncio.run(sidekick.comparison_handler(request))
        return response, json.loads(bytes(response.body))

    before_response, before = ask()
    assert "etag" not in before_response.headers
    assert "cache-control" not in before_response.headers
    by_path = {c["new"]["path"]: c for c in before["manifest"]["files"] if c.get("new")}
    assert by_path["a.py"]["additions"] == 1

    (root / ".gitattributes").write_text("a.py -diff\n")

    after_response, after = ask()
    assert "etag" not in after_response.headers
    by_path = {c["new"]["path"]: c for c in after["manifest"]["files"] if c.get("new")}
    assert by_path["a.py"]["availability"] == "binary", "the same two commits, another answer"


def _plain_request(**params: str) -> Any:
    class _Query:
        def get(self, key: str, default: str = "") -> str:
            return params.get(key, default)

    class _Request:
        query_params = _Query()
        headers: dict[str, str] = {}

    return _Request()


def test_a_stores_default_branch_attributes_change_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A fetch moves a store's HEAD, so if its `.gitattributes` counted the key would be wrong."""
    work = tmp_path / "work"
    work.mkdir()
    base, target = build_diff_fixture(work)
    store = tmp_path / "store.git"
    git(work.parent, "clone", "-q", "--bare", "--template=", str(work), str(store))
    two = (("left", base), ("right", target), ("base_policy", "direct"))

    async def ask() -> dict[str, Any]:
        monkeypatch.setattr(sidekick, "_COMPARISONS", ComparisonCache())
        async with pinned_client(store, target) as (client, _subject):
            response = await client.get(_route(*two))
            assert response.status_code == 200
            return response.json()

    before = asyncio.run(ask())
    (work / ".gitattributes").write_text("* -diff\n")
    git(work, "add", "-A")
    git(work, "commit", "-qm", "attributes on the default branch")
    git(store, "fetch", "-q", str(work), "main:main")
    assert b"-diff" in git(store, "show", "HEAD:.gitattributes")
    assert asyncio.run(ask()) == before


def test_one_computation_however_many_ask_together() -> None:
    computed = 0

    async def run() -> None:
        cache = ComparisonCache()
        release = asyncio.Event()

        async def compute() -> ResolvedManifest:
            nonlocal computed
            computed += 1
            await release.wait()
            return ResolvedManifest("resolved", "manifest")  # pyright: ignore[reportArgumentType]

        waiters = [asyncio.ensure_future(cache.manifest(("k",), compute)) for _ in range(3)]
        await asyncio.sleep(0)
        # A reader who leaves cancels their own wait and not the work the others wait on.
        waiters[0].cancel()
        await asyncio.sleep(0)
        release.set()
        answers = await asyncio.gather(*waiters[1:])
        assert all(answer.manifest == "manifest" for answer in answers)
        assert (await cache.manifest(("k",), compute)).manifest == "manifest"

    asyncio.run(run())
    assert computed == 1


def test_a_failure_is_not_kept() -> None:
    attempts = 0

    async def run() -> None:
        cache = ComparisonCache()

        async def compute() -> ResolvedManifest:
            nonlocal attempts
            attempts += 1
            raise ValueError("not yet")

        for _ in range(2):
            with pytest.raises(ValueError, match="not yet"):
                await cache.manifest(("k",), compute)
        assert cache.sizes()["manifests"] == 0

    asyncio.run(run())
    assert attempts == 2


def test_the_bounds_hold_and_evict_the_oldest() -> None:
    async def run() -> None:
        cache = ComparisonCache(max_manifests=2, max_body_bytes=10, max_body_entry_bytes=6)

        async def compute() -> ResolvedManifest:
            return ResolvedManifest("r", "m")  # pyright: ignore[reportArgumentType]

        for name in ("a", "b"):
            await cache.manifest((name,), compute)
        await cache.manifest(("a",), compute)  # `a` is now the newer of the two
        await cache.manifest(("c",), compute)
        assert cache.sizes()["manifests"] == 2
        assert set(cache._manifests) == {("a",), ("c",)}

        cache.remember_body(("one",), b"12345")
        cache.remember_body(("two",), b"12345")
        assert cache.body(("one",)) == b"12345"  # `one` is now the newer
        cache.remember_body(("three",), b"12345")
        assert cache.body(("two",)) is None and cache.body(("one",)) is not None
        assert cache.sizes()["body_bytes"] == 10
        cache.remember_body(("huge",), b"1234567")
        assert cache.body(("huge",)) is None, "past the entry bound: served and not kept"

    asyncio.run(run())


def test_the_shell_names_its_build_for_the_plugin(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    assert f'"BUILD_TAG": "{BUILD_TAG}"' in _client_settings()


def _client_settings() -> str:
    with TestClient(server.app) as client:
        return client.get("/").text
