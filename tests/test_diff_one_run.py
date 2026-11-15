"""H116: a comparison that fits is answered by two Git processes, and answers as four did.

``_Today`` is the adapter as it ran before H116: each revision in a ``rev-parse`` of its
own, the listing in a run of its own, and the patch in another. Every test here asks it and
the comparison route's adapter, ``patch_with_listing``, the same thing, and requires the
same answer, or the same refusal, byte for byte; the process counts are what changed.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient

from metabrowser import server, server_timing
from metabrowser.builtin_plugins.diff import sidekick
from metabrowser.diff.adapters import git as adapter
from metabrowser.diff.adapters.base import DiffSourceError
from metabrowser.diff.adapters.git import GitDiffSource
from metabrowser.diff.format import Availability, ChangeKind, ChangeSetManifest
from metabrowser.git import process as git_process
from metabrowser.git.process import (
    GitCommandError,
    GitLocation,
    repository_store_target,
    run_git_at,
)
from metabrowser.git.shallow import PARENT_UNAVAILABLE
from tests.diff_fixture_repo import _env, build_diff_fixture, git
from tests.required_tools import needs_git

pytestmark = needs_git

type Ask = Callable[[ChangeSetManifest], Sequence[Sequence[str]]]


class _Today(GitDiffSource):
    """The adapter before H116: one ``rev-parse`` a name, and no patch with the listing."""

    async def _rev_parse_together(self, revisions: Sequence[str]) -> list[str] | None:
        return None


def _ready(manifest: ChangeSetManifest) -> list[str]:
    return [c.id for c in manifest.files if c.availability is Availability.ready]


def _first_page(manifest: ChangeSetManifest) -> list[list[str]]:
    """What the route asks first: the ready files, up to its bound."""
    return [_ready(manifest)[: sidekick.MAX_HYDRATED_FILES]]


def _every_ask(manifest: ChangeSetManifest) -> list[list[str]]:
    """The first page, each ready file alone (the deferred loader), pages of three, and
    every file the manifest lists, binary ones included."""
    ready = _ready(manifest)
    return [
        *_first_page(manifest),
        *([file_id] for file_id in ready),
        *(ready[start : start + 3] for start in range(len(ready))),
        [c.id for c in manifest.files],
    ]


def _answer(
    source: GitDiffSource, intent: dict[str, Any], ask: Ask = _first_page
) -> tuple[int, str]:
    """Every answer *source* gives for *intent*, as one string, and the processes it took."""

    async def run() -> dict[str, Any]:
        try:
            resolved = await source.resolve(intent)
            manifest = await source.manifest(resolved)
            hydrations = [
                await source.hydrate(resolved, ids, manifest=manifest)
                for ids in ask(manifest)
                if ids
            ]
        except DiffSourceError as exc:
            return {"refused": str(exc)}
        return {
            "resolved": resolved.model_dump(mode="json"),
            "manifest": manifest.model_dump(mode="json"),
            "hydrations": [
                {
                    "patches": {k: v.model_dump(mode="json") for k, v in h.patches.items()},
                    "left_out": h.left_out,
                    "too_large": h.too_large,
                    "deferred": h.deferred,
                }
                for h in hydrations
            ],
        }

    record, token = server_timing.begin()
    try:
        answer = asyncio.run(run())
    finally:
        server_timing.end(record, token)
    return record.git_processes(), json.dumps(answer, sort_keys=True)


def _both(
    location: Path | GitLocation, intent: dict[str, Any], ask: Ask = _first_page
) -> tuple[tuple[int, str], tuple[int, str]]:
    today = _answer(_Today(location), intent, ask)
    one_run = _answer(GitDiffSource(location, patch_with_listing=True), intent, ask)
    assert one_run[1] == today[1]
    return today, one_run


@pytest.fixture(scope="module")
def repo(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, str, str]:
    root = tmp_path_factory.mktemp("one-run")
    base, target = build_diff_fixture(root)
    return root, base, target


def _store(root: Path, tmp_path: Path) -> Path:
    store = tmp_path / "store.git"
    git(root.parent, "clone", "-q", "--bare", "--template=", str(root), str(store))
    return store


# ── One run prints what the two runs print ───────────────────────────────


class _Printed:
    """What each Git run of the adapter printed, in order."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.runs: list[tuple[list[str], bytes]] = []
        real = run_git_at  # the function the adapter calls

        async def spy(args: Sequence[str], location: GitLocation, **kwargs: Any) -> bytes:
            out = await real(args, location, **kwargs)
            self.runs.append((list(args), out))
            return out

        monkeypatch.setattr(adapter, "run_git_at", spy)


def _assert_one_run_is_the_two(
    location: Path | GitLocation, intent: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    printed = _Printed(monkeypatch)
    today = _Today(location)
    resolved = asyncio.run(today.resolve(intent))
    printed.runs.clear()
    asyncio.run(today.manifest(resolved))
    asyncio.run(today._patch(resolved, None))
    asyncio.run(today._patch(resolved, None, listing=True))
    (_, listing), (_, patch), (_, both) = printed.runs
    assert both == listing + b"\0" + patch
    assert adapter._listing_and_patch(both, cut=False) == (listing, patch)


def test_one_run_prints_what_the_two_runs_print(
    repo: tuple[Path, str, str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Renames, a copy, a type change, a symlink, a mode change, and a binary file; a root
    commit against the empty tree; and the same on a store, under its isolated policy."""
    root, base, target = repo
    _assert_one_run_is_the_two(root, {"left": base, "right": target}, monkeypatch)
    _assert_one_run_is_the_two(root, {"revision": base}, monkeypatch)
    store = GitLocation.revision(repository_store_target(git_dir=_store(root, tmp_path)), target)
    _assert_one_run_is_the_two(store, {"left": base, "right": target}, monkeypatch)


def test_a_folders_diff_settings_reach_the_one_run_as_they_reached_the_two(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Prefixes and an external driver, which the patch runs pin away, and the context, the
    algorithm, an order file, and a textconv driver, which a folder's runs honor."""
    root = tmp_path / "configured"
    root.mkdir()
    base, target = build_diff_fixture(root)
    driver = tmp_path / "driver.sh"
    driver.write_text("#!/bin/sh\necho 'not a diff'\n")
    driver.chmod(0o755)
    order = tmp_path / "order"
    order.write_text("logo.bin\n*.md\n")
    for key, value in (
        ("diff.noprefix", "true"),
        ("diff.mnemonicPrefix", "true"),
        ("diff.external", str(driver)),
        ("diff.context", "1"),
        ("diff.algorithm", "patience"),
        ("diff.orderFile", str(order)),
        ("diff.upper.textconv", "tr a-z A-Z <"),
    ):
        git(root, "config", key, value)
    (root / ".git" / "info").mkdir(exist_ok=True)
    (root / ".git" / "info" / "attributes").write_text("*.md diff=upper\n*.py diff=upper\n")
    shown = git(root, "diff", "--no-ext-diff", base, target, "--", "new.md")
    assert b"+BODY" in shown, "the textconv driver runs"
    _assert_one_run_is_the_two(root, {"left": base, "right": target}, monkeypatch)
    monkeypatch.undo()
    _both(root, {"left": base, "right": target}, _every_ask)


# ── A comparison that fits ─────────────────────────────────────────────


def test_a_commit_that_fits_costs_two_processes_where_it_cost_four(
    repo: tuple[Path, str, str],
) -> None:
    root, _base, target = repo
    (today, _), (one_run, _) = _both(root, {"revision": target})
    assert (today, one_run) == (4, 2)


def test_every_page_a_reader_can_ask_for_is_what_four_processes_said(
    repo: tuple[Path, str, str],
) -> None:
    """Each file alone, every page of three, and all of them, answered from the one run's
    patch, renames, the copy, and the type change's two sections among them."""
    root, base, target = repo
    source = GitDiffSource(root, patch_with_listing=True)
    resolved = asyncio.run(source.resolve({"left": base, "right": target}))
    manifest = asyncio.run(source.manifest(resolved))
    kinds = {c.kind for c in manifest.files if c.availability is Availability.ready}
    assert {ChangeKind.renamed, ChangeKind.copied, ChangeKind.type_changed} <= kinds
    assert any(c.availability is Availability.binary for c in manifest.files)
    _both(root, {"left": base, "right": target}, _every_ask)


def test_two_endpoints_resolve_in_one_rev_parse_and_a_merge_base_in_its_own(
    repo: tuple[Path, str, str],
) -> None:
    root, base, target = repo
    (today, _), (one_run, _) = _both(root, {"left": base, "right": target})
    assert (today, one_run) == (4, 2)
    merge_base = {"left": base, "right": target, "base_policy": "merge_base"}
    (today, _), (one_run, _) = _both(root, merge_base)
    assert (today, one_run) == (5, 3)


def test_a_store_pin_answers_as_it_did(repo: tuple[Path, str, str], tmp_path: Path) -> None:
    """`HEAD` on a pin is the pin, which needs no process; full IDs resolve together."""
    root, base, target = repo
    location = GitLocation.revision(repository_store_target(git_dir=_store(root, tmp_path)), target)
    _both(location, {"revision": "HEAD"}, _every_ask)
    (today, _), (one_run, _) = _both(location, {"revision": "HEAD"})
    assert (today, one_run) == (3, 2)
    (today, _), (one_run, _) = _both(
        location, {"left": base, "right": target, "base_policy": "merge_base"}
    )
    assert one_run < today


# ── Revisions: one rev-parse names what one at a time named ─────────────


def test_every_revision_resolves_or_is_refused_as_one_at_a_time(
    repo: tuple[Path, str, str],
) -> None:
    """A name `_NOT_LISTED` admits resolves in the one run; any other, and any that does
    not resolve, is asked one at a time, so its refusal names it as before."""
    root, base, target = repo
    git(root, "tag", "-a", "-m", "annotated", "annotated", target)
    git(root, "tag", "light", base)
    names = [
        target,
        target[:10],
        "HEAD",
        "main",
        "annotated",
        "light",
        "HEAD@{0}",
        "HEAD^{/target}",
        "no-such-revision",
        "",
        f"{base}..{target}",
        f"^{target}",
        "HEAD:a.py",
        ":/target",
        "HEAD^@",
        "HEAD^!",
        "--all",
        "HEAD extra",
    ]
    for name in names:
        _both(root, {"revision": name}, lambda _manifest: [])
        _both(root, {"left": base, "right": name}, lambda _manifest: [])
        _both(root, {"left": name, "right": target}, lambda _manifest: [])


def test_a_root_commit_compares_with_the_empty_tree_as_before(
    repo: tuple[Path, str, str],
) -> None:
    """Its parent does not resolve, which ends the one run; one at a time then tells a
    root from a boundary, and the listing run takes the empty tree's side."""
    root, base, _target = repo
    (_, answer), (_, _) = _both(root, {"revision": base}, _every_ask)
    assert json.loads(answer)["resolved"]["left"]["kind"] == "empty"
    (today, _), (one_run, _) = _both(root, {"revision": base})
    assert one_run == today == 6, "the one run that failed is the one the listing saved"


def test_a_shallow_boundary_is_refused_as_before(
    repo: tuple[Path, str, str], tmp_path: Path
) -> None:
    root, _base, target = repo
    shallow = tmp_path / "shallow"
    git(tmp_path, "clone", "-q", "--depth", "1", f"file://{root}", str(shallow))
    assert (shallow / ".git" / "shallow").read_text().strip() == target
    (today, answer), (one_run, _) = _both(shallow, {"revision": target})
    assert json.loads(answer) == {"refused": PARENT_UNAVAILABLE}
    assert one_run == today + 1, "the one run that failed costs one process on a refusal"


# ── Past the bound: today's runs, and never more than its cap read ──────


def test_a_run_past_the_bound_is_stopped_after_its_listing_and_the_patch_runs_alone(
    repo: tuple[Path, str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The bound counts the patch after the listing; the read that passes it is kept."""
    root, _base, target = repo
    monkeypatch.setattr(adapter, "MAX_LISTED_PATCH_BYTES", 200)
    _both(root, {"revision": target}, _every_ask)
    (today, _), (one_run, _) = _both(root, {"revision": target})
    assert (today, one_run) == (4, 3)


def test_a_listing_longer_than_the_bound_is_still_read_whole(
    repo: tuple[Path, str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Read in pieces smaller than the listing's two final NULs are apart, and a bound far
    smaller than the listing: the listing is never cut, so it is never listed again (#449,
    L2)."""
    root, _base, target = repo
    monkeypatch.setattr(git_process, "_READ_CHUNK_BYTES", 7)
    monkeypatch.setattr(adapter, "MAX_LISTED_PATCH_BYTES", 10)
    (today, _), (one_run, _) = _both(root, {"revision": target}, _every_ask)
    (today, _), (one_run, _) = _both(root, {"revision": target})
    assert (today, one_run) == (4, 3)


def test_the_patch_bound_counts_only_what_follows_the_listing() -> None:
    bound = adapter._PatchBound(5)
    assert not bound(b":listing\0path\0")
    assert not bound(b"1\t1\tpath\0")
    assert not bound(b"\0diff")  # the NULs straddle two reads: four bytes of patch
    assert not bound(b" ")
    assert bound(b"--git")
    whole = adapter._PatchBound(5)
    assert whole(b"listing\0\0" + b"x" * 6)


def test_the_bound_of_a_page_is_spent_alike_from_the_one_runs_patch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`MAX_FILE_PATCH_BYTES` still decides what is too large and what is deferred."""
    root = tmp_path / "sized"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    (root / "keep.txt").write_text("keep\n")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "base")
    base = git(root, "rev-parse", "HEAD").decode().strip()
    for name, body in (("a", "a\n" * 30), ("b", "b\n" * 30), ("big", "big\n" * 1000)):
        (root / f"{name}.txt").write_text(body)
    (root / "c.txt").write_text("c\n" * 30)
    git(root, "add", "-A")
    git(root, "commit", "-qm", "target")
    target = git(root, "rev-parse", "HEAD").decode().strip()
    for bound in (400, 500, 10_000):
        monkeypatch.setattr(adapter, "MAX_FILE_PATCH_BYTES", bound)
        (_, answer), (one_run, _) = _both(root, {"left": base, "right": target}, _every_ask)
        assert one_run == 2, "every page, too large or deferred, from the one run's patch"
        if bound == 400:
            first = json.loads(answer)["hydrations"][0]
            assert first["too_large"] and first["deferred"]


def test_a_listing_run_that_fails_leaves_the_comparison_to_todays_runs(
    repo: tuple[Path, str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _base, target = repo
    real = GitDiffSource._patch

    async def listing_fails(source: GitDiffSource, *args: Any, **kwargs: Any) -> bytes:
        if kwargs.get("listing"):
            raise GitCommandError(["diff"], 128, "fatal: listing")
        return await real(source, *args, **kwargs)

    monkeypatch.setattr(GitDiffSource, "_patch", listing_fails)
    (today, _), (one_run, _) = _both(root, {"revision": target})
    # The failure is injected without a process; a real one would bring the two level.
    assert one_run == today - 1, "the listing and patch runs of before, and one rev-parse"


# ── Names with unusual bytes, and binary files ──────────────────────────


def _tree_of_names(root: Path, names: list[bytes], content: bytes) -> str:
    """A commit whose tree holds *names*, past the file system and the index."""
    env = _env(root, "2026-01-01T00:00:00 +0000")

    def run(*args: str, stdin: bytes) -> str:
        return (
            subprocess.run(
                ["git", "-C", str(root), *args],
                input=stdin,
                check=True,
                capture_output=True,
                env=env,
            )
            .stdout.decode()
            .strip()
        )

    blob = run("hash-object", "-w", "--stdin", stdin=content)
    records = b"".join(b"100644 blob " + blob.encode() + b"\t" + name + b"\0" for name in names)
    tree = run("mktree", "-z", stdin=records)
    return run("commit-tree", tree, "-m", "names", stdin=b"")


def test_every_byte_a_name_can_hold_answers_alike(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One name per byte but NUL and `/`, quoted by Git in the patch and NUL-framed in the
    listing, and `..`, which Git refuses as a pathspec."""
    root = tmp_path / "bytes"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    names = [b"n%02x-" % byte + bytes([byte]) + b"x" for byte in range(1, 256) if byte != 0x2F]
    names += [b"..", b" lead", b"trail ", b"calf\xe9.txt"]
    base = _tree_of_names(root, names, b"old\n")
    target = _tree_of_names(root, names, b"new\n")
    _assert_one_run_is_the_two(root, {"left": base, "right": target}, monkeypatch)
    monkeypatch.undo()

    def asks(manifest: ChangeSetManifest) -> list[list[str]]:
        ids = [c.id for c in manifest.files]
        return [ids[:50], *([file_id] for file_id in ids[::17]), ids]

    (_, _), (one_run, _) = _both(root, {"left": base, "right": target}, asks)
    assert one_run == 2


def test_binary_files_and_a_nul_past_gits_binary_check_answer_alike(tmp_path: Path) -> None:
    """Git reads the first 8000 bytes for a NUL, so a later one is in the patch, as text."""
    root = tmp_path / "binary"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    (root / "logo.bin").write_bytes(b"\x00\x01binary one\x00")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "base")
    (root / "logo.bin").write_bytes(b"\x00\x01binary two, longer\x00")
    (root / "late.txt").write_bytes(b"text\n" * 2000 + b"\x00 past the first 8000 bytes\n")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "target")
    target = git(root, "rev-parse", "HEAD").decode().strip()
    _both(root, {"revision": target}, _every_ask)
    (today, answer), (one_run, _) = _both(root, {"revision": target})
    assert (today, one_run) == (4, 2)
    assert b"\\u0000" in answer.encode(), "the NUL came through as text"


def test_a_listing_the_one_run_cannot_split_is_left_to_its_own_run() -> None:
    """The NUL between listing and patch is found by structure, never by a guess."""
    raw = b":100644 100644 " + b"1" * 40 + b" " + b"2" * 40 + b" M\0a.txt\0"
    numstat = b"1\t1\ta.txt\0"
    patch = b"diff --git a/a.txt b/a.txt\n"
    assert adapter._listing_and_patch(raw + numstat + b"\0" + patch, cut=False) == (
        raw + numstat,
        patch,
    )
    assert adapter._listing_and_patch(b"", cut=False) == (b"", b"")
    assert adapter._listing_and_patch(b"", cut=True) is None
    # Cut inside its listing, or before its patch has begun: no listing to use.
    assert adapter._listing_and_patch(raw, cut=True) is None
    assert adapter._listing_and_patch(raw + numstat + b"\0diff --g", cut=True) is None
    # A name with no byte, which only a source that runs no fsck holds.
    empty = b":100644 100644 " + b"1" * 40 + b" " + b"2" * 40 + b" M\0\0"
    assert adapter._listing_and_patch(empty + numstat + b"\0" + patch, cut=False) is None
    # Anything after the listing that is not a patch.
    assert adapter._listing_and_patch(raw + numstat + b"\0junk", cut=False) is None


# ── The route ─────────────────────────────────────────────────────────


def test_the_route_answers_a_commit_alike_in_two_processes(
    repo: tuple[Path, str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _base, target = repo
    server._set_root_dir(root)
    client = TestClient(server.app)
    route = f"/api/plugin/diff/comparison?revision={target}"
    assert client.get(route).status_code == 200  # the repository's identity, discovered once

    def counted() -> tuple[bytes, str]:
        answer = client.get(route)
        assert answer.status_code == 200
        return answer.content, answer.headers["server-timing"]

    one_run, one_run_timing = counted()
    monkeypatch.setattr(sidekick, "GitDiffSource", lambda location, **_kwargs: _Today(location))
    today, today_timing = counted()
    assert one_run == today
    assert 'desc="2 processes"' in one_run_timing
    assert 'desc="4 processes"' in today_timing
