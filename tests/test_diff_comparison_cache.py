"""A comparison of two commit IDs is kept, and validated; anything else is asked again.

The transcript this writes, ``tests/golden/cli-diff-comparison-cache.txt``, is what the route
answers through the real request stack: `--api` prints a status and a body, and what is
pinned here is the headers, so each block is one request with the ones that matter.
"""

from __future__ import annotations

import asyncio
import json
import re
import threading
from pathlib import Path
from typing import Any
from unittest.mock import Mock
from urllib.parse import urlencode

import pytest
from httpx2 import Response
from starlette.requests import Request
from starlette.testclient import TestClient

from metabrowser import server
from metabrowser.builtin_plugins.diff import sidekick
from metabrowser.builtin_plugins.diff.comparison_cache import ComparisonCache, ResolvedManifest
from metabrowser.diff.adapters.git import GitDiffSource, PatchHydration
from metabrowser.diff.format import Availability
from metabrowser.git.process import GitLocation, repository_store_target
from metabrowser.http_caching import BUILD_TAG, store_tag
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


def _block(
    title: str,
    route: str,
    response: Response,
    spy: _Spy,
    store: str,
    tag_labels: dict[str, str],
) -> str:
    """One request of the transcript: what it asked, and the headers that say what is kept."""

    def shown(text: str) -> str:
        return text.replace(BUILD_TAG, "<BUILD>").replace(store, "<STORE>")

    lines = [f"## {title}", f"GET {shown(route)}", f"status: {response.status_code}"]
    for name in ("cache-control", "etag", "content-encoding", "vary"):
        value = response.headers.get(name)
        if value is not None:
            if name == "etag":
                assert re.fullmatch(rf'"{BUILD_TAG}-[0-9a-f]{{64}}"', value)
                # A digest contains the sandbox store identity. Keep its equality
                # relationships across this whole transcript, not its random spelling.
                value = tag_labels.setdefault(value, f'"<BUILD>-<ETAG-{len(tag_labels) + 1}>"')
            lines.append(f"{name}: {shown(value)}")
    lines.append(f"work: {spy.manifests} manifest, {spy.patches} patch")
    spy.manifests = spy.patches = 0
    return "\n".join(lines)


def test_what_a_store_keeps_and_says(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store, base, target = _store(tmp_path)
    spy = _Spy(monkeypatch)
    token = store_tag(store)
    # The fixture pins commit IDs. Tags also name the sandbox store, so the
    # transcript labels them after checking their real syntax and build scope.
    two = (("left", base), ("right", target), ("base_policy", "merge_base"))
    scoped = (("build", BUILD_TAG), ("store", token))
    named = (*two, *scoped)
    blocks: list[str] = []
    tag_labels: dict[str, str] = {}

    async def run() -> None:
        async with pinned_client(store, target) as (client, _subject):

            async def ask(
                title: str, route: str, headers: dict[str, str] | None = None
            ) -> Response:
                response = await client.get(route, headers=headers or {})
                blocks.append(_block(title, route, response, spy, token, tag_labels))
                return response

            first = await ask(
                "Two commit IDs, naming this build and this store: computed", _route(*named)
            )
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
                _route(*two, ("build", "000000000000"), scoped[1]),
            )
            assert other_build.headers["cache-control"] == "no-cache"
            other_store = await ask(
                "Naming this build and another store: the browser must ask too",
                _route(*two, scoped[0], ("store", "0000000000000000")),
            )
            assert other_store.headers["cache-control"] == "no-cache"
            no_store = await ask(
                "Naming this build and no store: the browser must ask too",
                _route(*two, scoped[0]),
            )
            assert no_store.headers["cache-control"] == "no-cache"
            direct = await ask(
                "Another base policy is another answer",
                _route(("left", base), ("right", target), ("base_policy", "direct"), *scoped),
            )
            assert direct.headers["etag"] != etag
            one = await ask(
                "One deferred file: its manifest is kept, so one path-limited diff",
                _route(*named, ("file", "a.py")),
            )
            assert one.headers["etag"] != etag
            assert [c["new"]["path"] for c in one.json()["manifest"]["files"]] == ["a.py"]
            await ask("That file again: no Git at all", _route(*named, ("file", "a.py")))
            unpacked = await ask(
                "A client that takes no gzip gets the same answer unpacked",
                _route(*named, ("file", "a.py")),
                {"accept-encoding": "identity"},
            )
            assert "content-encoding" not in unpacked.headers
            assert unpacked.json() == one.json()
            revision = await ask(
                "A commit against its parent, by ID", _route(("revision", target), *scoped)
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
                _route(("left", "0" * 40), ("right", target), *scoped),
            )
            assert refused.status_code == 404
            assert refused.json()["error"] == "diff_comparison"

    asyncio.run(run())
    check_golden("cli-diff-comparison-cache.txt", "\n\n".join(blocks) + "\n")


def test_two_stores_holding_the_same_commits_have_distinct_validators(tmp_path: Path) -> None:
    store, base, target = _store(tmp_path)
    other = tmp_path / "other.git"
    git(tmp_path, "clone", "-q", "--bare", "--template=", str(store), str(other))
    assert store_tag(store) != store_tag(other)
    two = (("left", base), ("right", target), ("base_policy", "merge_base"))

    async def run() -> None:
        async with pinned_client(store, target) as (client, _subject):
            first = await client.get(_route(*two))
            assert first.status_code == 200
            tag = first.headers["etag"]
            document = first.json()
        async with pinned_client(other, target) as (client, _subject):
            replayed = await client.get(_route(*two), headers={"if-none-match": tag})
            assert replayed.status_code == 200
            assert replayed.json() == document
            assert replayed.headers["etag"] != tag
            own = await client.get(
                _route(*two), headers={"if-none-match": replayed.headers["etag"]}
            )
            assert own.status_code == 304 and own.content == b""

    asyncio.run(run())


def test_another_store_on_the_same_origin_answers_for_itself(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A validator and an address name the store (review of #284, B1 and C2): a second
    store holding neither commit answers its plain refusal to the first store's tag, and a
    process that did not compute a comparison checks the store can answer before a 304."""
    store, base, target = _store(tmp_path)
    other = tmp_path / "other.git"
    work = tmp_path / "other-work"
    work.mkdir()
    git(work, "init", "-q", "-b", "main")
    (work / "unrelated.txt").write_text("unrelated\n")
    git(work, "add", "-A")
    git(work, "commit", "-qm", "unrelated")
    git(work.parent, "clone", "-q", "--bare", "--template=", str(work), str(other))
    unrelated = git(other, "rev-parse", "HEAD").decode().strip()
    two = (("left", base), ("right", target), ("base_policy", "merge_base"))
    assert store_tag(store) != store_tag(other)

    async def run() -> None:
        async with pinned_client(store, target) as (client, _subject):
            first = await client.get(
                _route(*two, ("build", BUILD_TAG), ("store", store_tag(store)))
            )
            assert first.headers["cache-control"].endswith("immutable")
            etag = first.headers["etag"]
        async with pinned_client(other, unrelated) as (client, _subject):
            plain = await client.get(_route(*two))
            assert plain.status_code == 404
            replayed = await client.get(_route(*two), headers={"if-none-match": etag})
            assert replayed.status_code == 404, "the other store's tag is not this store's"
            assert "etag" not in replayed.headers or replayed.headers["etag"] != etag
        # The same store in a process that holds nothing: the commits are checked first.
        monkeypatch.setattr(sidekick, "_COMPARISONS", ComparisonCache())
        async with pinned_client(store, target) as (client, _subject):
            again = await client.get(_route(*two), headers={"if-none-match": etag})
            assert again.status_code == 304
            gone = await client.get(
                _route(("left", "0" * 40), ("right", target), ("base_policy", "merge_base")),
                headers={"if-none-match": etag},
            )
            assert gone.status_code == 404

    asyncio.run(run())


def test_a_readers_global_attributes_do_not_reach_a_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`$XDG_CONFIG_HOME/git/attributes`, else `$HOME/.config/git/attributes`, is read
    whatever `GIT_CONFIG_*` say (review of #284, C4): a store's answer must not change with
    the reader's machine, since its key, its tag and its address do not name it."""
    store, base, target = _store(tmp_path)
    two = (("left", base), ("right", target), ("base_policy", "direct"))

    async def ask(*, fresh: bool = True) -> tuple[dict[str, str], str, str]:
        """What each file is, and the cache control, from a fresh process or this one."""
        if fresh:
            monkeypatch.setattr(sidekick, "_COMPARISONS", ComparisonCache())
        async with pinned_client(store, target) as (client, _subject):
            response = await client.get(
                _route(*two, ("build", BUILD_TAG), ("store", store_tag(store)))
            )
            assert response.status_code == 200
            return (
                {
                    (c.get("new") or c["old"])["path"]: c["availability"]
                    for c in response.json()["manifest"]["files"]
                },
                response.headers["cache-control"],
                response.headers["etag"],
            )

    before, _, _ = asyncio.run(ask())
    assert before["a.py"] == "ready"
    xdg = tmp_path / "xdg"
    (xdg / "git").mkdir(parents=True)
    (xdg / "git" / "attributes").write_text("*.py -diff\n")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
    assert asyncio.run(ask())[0] == before
    monkeypatch.delenv("XDG_CONFIG_HOME")
    home = tmp_path / "home"
    (home / ".config" / "git").mkdir(parents=True)
    (home / ".config" / "git" / "attributes").write_text("*.py -diff\n")
    monkeypatch.setenv("HOME", str(home))
    assert asyncio.run(ask())[0] == before
    # The store's own `info/attributes` is an input Git reads whatever else is isolated,
    # so it moves the store's token, and with it every address and tag, and the key in
    # memory (review of #284, D2): one process answers the edit as a fresh one would.
    # Before, the memory was keyed without the token, and a request at the new address
    # was answered with the old body, `immutable`.
    one_process = ComparisonCache()
    monkeypatch.setattr(sidekick, "_COMPARISONS", one_process)
    before_token = store_tag(store)
    kept, control, kept_etag = asyncio.run(ask(fresh=False))
    assert kept["a.py"] == "ready" and control.endswith("immutable")
    assert one_process.sizes()["bodies"] == 1
    (store / "info").mkdir(exist_ok=True)
    (store / "info" / "attributes").write_text("*.py -diff\n")
    assert store_tag(store) != before_token
    edited, control, edited_etag = asyncio.run(ask(fresh=False))
    assert edited["a.py"] == "binary" and control.endswith("immutable")
    assert edited_etag != kept_etag
    assert one_process.sizes()["bodies"] == 2, "the old answer is kept under its own key"
    assert asyncio.run(ask())[0] == edited, "what a fresh process answers"


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
            monkeypatch.setattr(sidekick, "comparison_cache_key", lambda *_args: None)
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

    request = Mock(spec=["query_params", "headers"])
    request.query_params = _Query()
    request.headers = {}
    return request


def test_a_stores_default_branch_attributes_change_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A fetch moves a store's HEAD, and nothing in the key, the tag or the address names
    HEAD, so its `.gitattributes` must not count. Git 2.43 reads a bare repository's
    attributes from HEAD and 2.50 reads no commit's (review of #284, D1: the admitted-git
    job on 2.43.7 answered one patch where it had answered every file), so a store read
    names the store's empty tree as its attributes source, and the same two commits answer
    the same bytes from a fresh process on each Git the Makefile admits."""
    work = tmp_path / "work"
    work.mkdir()
    base, target = build_diff_fixture(work)
    store = tmp_path / "store.git"
    git(work.parent, "clone", "-q", "--bare", "--template=", str(work), str(store))
    two = (("left", base), ("right", target), ("base_policy", "direct"))

    async def ask() -> tuple[dict[str, Any], str]:
        monkeypatch.setattr(sidekick, "_COMPARISONS", ComparisonCache())
        async with pinned_client(store, target) as (client, _subject):
            response = await client.get(_route(*two))
            assert response.status_code == 200
            return response.json(), response.headers["etag"]

    before, etag = asyncio.run(ask())
    assert all(c["availability"] == "ready" for c in before["manifest"]["files"][:1])
    (work / ".gitattributes").write_text("* -diff\n")
    git(work, "add", "-A")
    git(work, "commit", "-qm", "attributes on the default branch")
    git(store, "fetch", "-q", str(work), "main:main")
    assert b"-diff" in git(store, "show", "HEAD:.gitattributes")
    assert asyncio.run(ask()) == (before, etag)
    assert all(c["availability"] == "ready" for c in before["manifest"]["files"][:1])


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

        cache.remember_body(("one",), b"12345", generation=cache.body_generation())
        cache.remember_body(("two",), b"12345", generation=cache.body_generation())
        assert cache.body(("one",)) == b"12345"  # `one` is now the newer
        cache.remember_body(("three",), b"12345", generation=cache.body_generation())
        assert cache.body(("two",)) is None and cache.body(("one",)) is not None
        assert cache.sizes()["body_bytes"] == 10
        cache.remember_body(("huge",), b"1234567", generation=cache.body_generation())
        assert cache.body(("huge",)) is None, "past the entry bound: served and not kept"

    asyncio.run(run())


def test_the_shell_names_its_build_for_the_plugin(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    settings = _client_settings()
    assert f'"BUILD_TAG": "{BUILD_TAG}"' in settings
    assert "STORE_TAG" not in settings, "a folder's answers are never kept by the browser"


def test_the_shell_names_the_store_for_the_plugin(tmp_path: Path) -> None:
    """The token the page sends with every comparison address, for a pin alone."""
    store, _base, target = _store(tmp_path)

    async def run() -> str:
        async with pinned_client(store, target) as (client, _subject):
            return (await client.get("/view/")).text

    assert f'"STORE_TAG": "{store_tag(store)}"' in asyncio.run(run())


def test_the_routes_gzip_test_is_the_middlewares(tmp_path: Path) -> None:
    """A client declining gzip with `gzip;q=0` (review of #284, A14) is answered gzip by
    Starlette's middleware whatever the route sends, so the route makes the same test: read
    by its weights, it would unpack a kept body for the middleware to compress again."""
    from starlette.middleware.gzip import GZipMiddleware

    assert sidekick.middleware_sends_gzip("gzip;q=0")
    assert not sidekick.middleware_sends_gzip("identity")
    assert any(
        isinstance(m.cls, type) and m.cls is GZipMiddleware for m in server.app.user_middleware
    )
    store, base, target = _store(tmp_path)
    two = (("left", base), ("right", target), ("base_policy", "merge_base"))

    async def run() -> None:
        async with pinned_client(store, target) as (client, _subject):
            declined = await client.get(_route(*two), headers={"accept-encoding": "gzip;q=0"})
            assert declined.headers.get("content-encoding") == "gzip", "the middleware's doing"
            kept = await client.get(_route(*two), headers={"accept-encoding": "gzip;q=0"})
            assert kept.headers.get("content-encoding") == "gzip"
            assert kept.content == declined.content

    asyncio.run(run())


def _client_settings() -> str:
    with TestClient(server.app) as client:
        return client.get("/").text


def test_initial_page_policies_share_only_the_manifest_and_complete_to_the_same_document(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """PR pages and generic comparisons cannot replay one another's partial bodies."""
    store, base, target = _store(tmp_path)
    location = GitLocation.revision(repository_store_target(git_dir=store), target)
    monkeypatch.setattr(sidekick, "_COMPARISONS", ComparisonCache())
    spy = _Spy(monkeypatch)

    def request(*, file: str = "", etag: str = "") -> Request:
        query = urlencode(
            {"left": base, "right": target, "base_policy": "merge_base", "file": file}
        )
        return Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/comparison",
                "query_string": query.encode(),
                "headers": [(b"if-none-match", etag.encode())] if etag else [],
            }
        )

    async def run() -> None:
        generic = await sidekick.comparison_at(request(), location)
        limited = await sidekick.comparison_at(request(), location, max_initial_files=8)
        one = await sidekick.comparison_at(request(), location, max_initial_files=1)
        whole = json.loads(bytes(generic.body))
        partial = json.loads(bytes(limited.body))
        assert len(whole["patches"]) > 8
        assert len(partial["patches"]) == 8
        assert len(json.loads(bytes(one.body))["patches"]) == 1
        assert len({generic.headers["etag"], limited.headers["etag"], one.headers["etag"]}) == 3
        assert (await sidekick.comparison_at(request(), location)).body == generic.body
        assert (
            await sidekick.comparison_at(request(), location, max_initial_files=8)
        ).body == limited.body
        assert (
            await sidekick.comparison_at(
                request(etag=generic.headers["etag"]), location, max_initial_files=8
            )
        ).status_code == 200
        assert (
            await sidekick.comparison_at(
                request(etag=limited.headers["etag"]), location, max_initial_files=8
            )
        ).status_code == 304
        patches = dict(partial["patches"])
        completed = []
        for change in partial["manifest"]["files"]:
            if change["availability"] == "deferred":
                path = (change.get("new") or change["old"])["path"]
                response = await sidekick.comparison_at(
                    request(file=path), location, max_initial_files=8
                )
                answer = json.loads(bytes(response.body))
                change = answer["manifest"]["files"][0]
                patches.update(answer["patches"])
            completed.append(change)
        partial["manifest"]["files"] = completed
        partial["patches"] = patches
        assert json.dumps(partial, sort_keys=True) == json.dumps(whole, sort_keys=True)
        assert spy.manifests == 1
        for count in (0, 51):
            with pytest.raises(ValueError, match="max_initial_files"):
                await sidekick.comparison_at(request(), location, max_initial_files=count)

    asyncio.run(run())


def test_a_small_initial_page_skips_binary_entries_and_leaves_large_files_declared(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, base, target = _store(tmp_path)
    location = GitLocation.revision(repository_store_target(git_dir=store), target)
    real_manifest = GitDiffSource.manifest
    real_hydrate = GitDiffSource.hydrate

    async def binary_first(source: GitDiffSource, resolved: Any) -> Any:
        manifest = await real_manifest(source, resolved)
        ordered = tuple(sorted(manifest.files, key=lambda change: not change.binary))
        return manifest.model_copy(update={"files": ordered})

    async def too_large(source: GitDiffSource, resolved: Any, ids: Any, *, manifest: Any) -> Any:
        first_ready = next(
            change.id for change in manifest.files if change.availability is Availability.ready
        )
        if ids == [first_ready]:
            return PatchHydration({}, too_large=(first_ready,))
        return await real_hydrate(source, resolved, ids, manifest=manifest)

    monkeypatch.setattr(GitDiffSource, "manifest", binary_first)
    monkeypatch.setattr(GitDiffSource, "hydrate", too_large)
    monkeypatch.setattr(sidekick, "_COMPARISONS", ComparisonCache())

    def request(left: str = base) -> Request:
        return Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/comparison",
                "query_string": urlencode(
                    {"left": left, "right": target, "base_policy": "merge_base"}
                ).encode(),
                "headers": [],
            }
        )

    async def run() -> None:
        response = await sidekick.comparison_at(request(), location, max_initial_files=1)
        answer = json.loads(bytes(response.body))
        files = answer["manifest"]["files"]
        assert files[0]["availability"] == "binary"
        assert sum(change["availability"] == "too_large" for change in files) == 1
        assert any(change["availability"] == "deferred" for change in files)
        response = await sidekick.comparison_at(request(target), location, max_initial_files=1)
        empty = json.loads(bytes(response.body))
        assert empty["manifest"]["files"] == [] and empty["patches"] == {}

    asyncio.run(run())


def test_a_binary_only_comparison_needs_no_hydration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, _base, target = _store(tmp_path)
    work = tmp_path / "work"
    (work / "logo.bin").write_bytes(b"\x00another binary image\x00")
    git(work, "add", "logo.bin")
    git(work, "commit", "-qm", "binary only")
    right = git(work, "rev-parse", "HEAD").decode().strip()
    git(tmp_path, "--git-dir", str(store), "fetch", "--no-tags", str(work), right)
    location = GitLocation.revision(repository_store_target(git_dir=store), right)
    monkeypatch.setattr(sidekick, "_COMPARISONS", ComparisonCache())

    async def forbidden(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("a binary-only comparison asked for a patch")

    monkeypatch.setattr(GitDiffSource, "hydrate", forbidden)
    query = urlencode({"left": target, "right": right, "base_policy": "merge_base"}).encode()
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/comparison",
            "query_string": query,
            "headers": [],
        }
    )
    answer = asyncio.run(sidekick.comparison_at(request, location, max_initial_files=1))
    document = json.loads(bytes(answer.body))
    assert document["manifest"]["totals"]["files"] == 1
    assert document["manifest"]["files"][0]["availability"] == "binary"
    assert document["patches"] == {}


def test_corrupt_comparison_invalidation_drops_bodies_and_inflight_admission() -> None:
    async def run() -> None:
        cache = ComparisonCache()
        key = ("store", "token", "left", "right", "merge_base")
        other = ("another", "token", "left", "right", "merge_base")
        entered, release = asyncio.Event(), asyncio.Event()
        answer = Mock(spec=ResolvedManifest)

        async def listing() -> ResolvedManifest:
            entered.set()
            await release.wait()
            return answer

        task = asyncio.create_task(cache.manifest(key, listing))
        await entered.wait()
        cache.remember_body((*key, "one", "8"), b"corrupt", generation=cache.body_generation())
        cache.remember_body(
            (*key, "one", "50"), b"also corrupt", generation=cache.body_generation()
        )
        cache.remember_body((*other, "two"), b"valid", generation=cache.body_generation())
        cache.invalidate(key)
        release.set()
        await task
        await asyncio.sleep(0)
        assert not cache.has_manifest(key)
        assert cache.body((*key, "one", "8")) is None
        assert cache.body((*key, "one", "50")) is None
        assert cache.body((*other, "two")) == b"valid"
        assert cache.sizes()["body_bytes"] == len(b"valid")

    asyncio.run(run())


def test_invalidated_task_reaps_failure_after_its_waiter_cancels() -> None:
    import gc

    async def run() -> None:
        cache = ComparisonCache()
        entered, release, finished = asyncio.Event(), asyncio.Event(), asyncio.Event()
        errors: list[dict[str, Any]] = []
        loop = asyncio.get_running_loop()
        loop.set_exception_handler(lambda _loop, context: errors.append(context))

        async def listing() -> ResolvedManifest:
            entered.set()
            await release.wait()
            finished.set()
            raise RuntimeError("detached listing failed")

        key = ("store", "selection")
        waiting = asyncio.create_task(cache.manifest(key, listing))
        await entered.wait()
        waiting.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiting
        cache.invalidate(key)
        release.set()
        await finished.wait()
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        gc.collect()
        await asyncio.sleep(0)
        assert errors == []
        assert not cache.has_manifest(key)

    asyncio.run(run())


@pytest.mark.parametrize("operation", ["repo_info", "_json_body", "encode_body"])
@pytest.mark.parametrize("reset", ["invalidate", "replace"])
def test_late_route_work_cannot_publish_a_body_after_invalidation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, operation: str, reset: str
) -> None:
    """A request holds its admission before any comparison or serialization can await."""
    store, base, target = _store(tmp_path)
    location = GitLocation.revision(repository_store_target(git_dir=store), target)
    intent = {"left": base, "right": target, "base_policy": "merge_base"}
    key = sidekick.comparison_cache_key(location, intent, store_tag(store))
    assert key is not None
    cache = ComparisonCache()
    monkeypatch.setattr(sidekick, "_COMPARISONS", cache)
    spy = _Spy(monkeypatch)

    async def run() -> None:
        entered, release = asyncio.Event(), threading.Event()
        loop = asyncio.get_running_loop()
        original = getattr(sidekick, operation)

        async def paused_async(*args: Any, **kwargs: Any) -> Any:
            entered.set()
            assert await asyncio.to_thread(release.wait, 10), "request barrier timed out"
            return await original(*args, **kwargs)

        def paused_thread(*args: Any, **kwargs: Any) -> Any:
            loop.call_soon_threadsafe(entered.set)
            assert release.wait(10), "encoding barrier timed out"
            return original(*args, **kwargs)

        monkeypatch.setattr(
            sidekick, operation, paused_async if operation == "repo_info" else paused_thread
        )
        pending = asyncio.create_task(sidekick.comparison_at(_plain_request(**intent), location))
        try:
            await asyncio.wait_for(entered.wait(), 10)
            if reset == "replace":
                monkeypatch.setattr(sidekick, "_COMPARISONS", ComparisonCache())
            else:
                cache.invalidate(key)
            assert sidekick._COMPARISONS.sizes()["body_bytes"] == 0
        finally:
            release.set()
        old = await pending
        assert old.status_code == 200
        assert sidekick._COMPARISONS.sizes()["bodies"] == 0
        monkeypatch.setattr(sidekick, operation, original)
        patches = spy.patches
        fresh = await sidekick.comparison_at(_plain_request(**intent), location)
        assert fresh.body == old.body
        assert spy.patches == patches + 1, "a fresh request must recompute the uncached body"
        assert sidekick._COMPARISONS.sizes()["bodies"] == 1
        repeated = await sidekick.comparison_at(_plain_request(**intent), location)
        assert repeated.body == fresh.body
        assert spy.patches == patches + 1, "a fresh writer can populate the body cache"

    asyncio.run(run())


def test_stale_body_writers_preserve_fresh_entries_and_byte_accounting() -> None:
    cache = ComparisonCache(max_body_bytes=10, max_body_entry_bytes=6)
    key, other = ("comparison",), ("unrelated",)
    body_key = (*key, "file", "8")
    generation = cache.body_generation()
    cache.remember_body(body_key, b"old", generation=generation)
    cache.remember_body(other, b"keep", generation=generation)
    cache.invalidate(key)
    assert cache.sizes()["body_bytes"] == 4
    cache.remember_body(body_key, b"fresh", generation=cache.body_generation())
    cache.remember_body(body_key, b"stale", generation=generation)
    cache.remember_body(("another",), b"stale", generation=generation)
    assert cache.body(body_key) == b"fresh"
    assert cache.body(other) == b"keep"
    assert cache.body(("another",)) is None
    assert cache.sizes() == {"manifests": 0, "bodies": 2, "body_bytes": 9}

    generation = cache.body_generation()
    cache.invalidate(("absent",))
    cache.remember_body(("absent",), b"stale", generation=generation)
    assert cache.body(("absent",)) is None, "even an absent key can have an in-flight writer"
    assert cache.body(body_key) == b"fresh" and cache.body(other) == b"keep"
    assert cache.sizes()["body_bytes"] == 9


def test_body_admission_does_not_revive_after_lru_eviction_or_cache_replacement() -> None:
    cache = ComparisonCache(max_body_bytes=4, max_body_entry_bytes=4)
    key = ("comparison",)
    old = cache.body_generation()
    cache.remember_body(key, b"old", generation=old)
    cache.invalidate(key)
    fresh = cache.body_generation()
    cache.remember_body(key, b"new!", generation=fresh)
    cache.remember_body(("other",), b"last", generation=fresh)
    assert cache.body(key) is None, "the key was evicted after fresh admission"
    cache.invalidate(("absent",))
    cache.remember_body(key, b"old", generation=old)
    cache.remember_body(key, b"new!", generation=fresh)
    assert cache.body(key) is None, "neither earlier generation can return after eviction"
    assert cache.body(("other",)) == b"last"
    assert cache.sizes() == {"manifests": 0, "bodies": 1, "body_bytes": 4}
    current = cache.body_generation()
    cache.remember_body(key, b"ok", generation=current)
    assert cache.body(key) == b"ok" and cache.body(("other",)) is None
    assert cache.sizes()["body_bytes"] == 2
    replacement = ComparisonCache()
    replacement.remember_body(key, b"old", generation=current)
    assert replacement.sizes() == {"manifests": 0, "bodies": 0, "body_bytes": 0}
