"""H116: a comparison that fits is answered by two Git processes, and answers as four did.

``_Today`` is the adapter as it ran before H116: each revision in a ``rev-parse`` of its
own, the listing in a run of its own, and the patch in another. Every test here asks it and
the comparison route's adapter, ``patch_with_listing``, the same thing, and requires the
same answer, or the same refusal, byte for byte; the process counts are what changed.
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import subprocess
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient

from metabrowser import server, server_timing
from metabrowser.builtin_plugins.diff import sidekick
from metabrowser.diff.adapters import git as adapter
from metabrowser.diff.adapters import textconv
from metabrowser.diff.adapters.base import DiffSourceError
from metabrowser.diff.adapters.git import GitDiffSource
from metabrowser.diff.format import Availability, ChangeKind, ChangeSetManifest
from metabrowser.git import process as git_process
from metabrowser.git.process import (
    GitCommandError,
    GitLocation,
    GitTimeoutError,
    as_location,
    repository_store_target,
    run_git_at,
)
from metabrowser.git.shallow import PARENT_UNAVAILABLE
from tests.diff_fixture_repo import _env, build_diff_fixture, git
from tests.required_tools import needs_git
from tests.test_diff_textconv_cache import _old_git

pytestmark = needs_git

type Ask = Callable[[ChangeSetManifest], Sequence[Sequence[str]]]


@pytest.fixture(autouse=True)
def _no_ambient_git_config(tmp_path: Path) -> Iterator[None]:
    """Folder reads honor the caller's configuration, and a developer's global file can name
    a textconv driver, which changes every count here: an empty global file, no system file,
    and no configuration from the environment. A test that names a system file sets it.
    The fixture's own patch outlives a test's ``monkeypatch.undo()``."""
    textconv.forget()
    empty = tmp_path / "empty-global-gitconfig"
    empty.write_bytes(b"")
    with pytest.MonkeyPatch.context() as isolated:
        for name in ("GIT_CONFIG", "GIT_CONFIG_COUNT", "GIT_CONFIG_PARAMETERS"):
            isolated.delenv(name, raising=False)
        isolated.delenv("GIT_CONFIG_SYSTEM", raising=False)
        isolated.setenv("GIT_CONFIG_GLOBAL", str(empty))
        isolated.setenv("GIT_CONFIG_NOSYSTEM", "1")
        yield
    textconv.forget()


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


def _warm(location: Path | GitLocation) -> None:
    """Ask once whether the configuration names a textconv driver, outside any count, as a
    server's first comparison of a folder does (``test_a_cold_configuration_...``)."""
    asyncio.run(textconv.read_textconv_named(as_location(location)))


def _both(
    location: Path | GitLocation, intent: dict[str, Any], ask: Ask = _first_page
) -> tuple[tuple[int, str], tuple[int, str]]:
    today = _answer(_Today(location), intent, ask)
    _warm(location)
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
    algorithm, and an order file, which a folder's runs honor. A textconv driver is the one
    setting the one run does not honor (``test_a_textconv_driver_...``)."""
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
    ):
        git(root, "config", key, value)
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


def test_a_listing_run_that_times_out_is_not_run_again(
    repo: tuple[Path, str, str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The listing run would only time out again, after as long, rename detection and all
    (#449, M1): the timeout is the answer, which the route says as a 504."""
    root, _base, target = repo
    real = git_process.git_executable()
    assert real is not None
    slow = tmp_path / "slow-git"
    slow.write_text(
        '#!/bin/sh\nfor a in "$@"; do [ "$a" = diff ] && sleep 2 </dev/null >/dev/null 2>&1; '
        f'done\nexec {real} "$@"\n'
    )
    slow.chmod(0o755)
    _warm(root)
    source = GitDiffSource(root, patch_with_listing=True)
    resolved = asyncio.run(source.resolve({"revision": target}))
    monkeypatch.setattr(git_process, "git_executable", lambda: str(slow))
    quick = dataclasses.replace(git_process.READ_POLICY, timeout_s=0.5)
    monkeypatch.setattr(git_process, "READ_POLICY", quick)
    record, token = server_timing.begin()
    try:
        with pytest.raises(GitTimeoutError):
            asyncio.run(source.manifest(resolved))
    finally:
        server_timing.end(record, token)
    assert record.git_processes() == 1, "the listing run alone, not the listing run again"


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


def test_a_cold_configuration_is_asked_beside_the_one_run(
    repo: tuple[Path, str, str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A server's first comparison of a folder asks whether a textconv driver is named,
    beside the one run, and the answer is kept for the next. The very first also asks Git
    which system file it reads (`git var`), which is kept for the server's life."""
    root, _base, target = repo
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    textconv.forget()
    cold, answer = _answer(GitDiffSource(root, patch_with_listing=True), {"revision": target})
    warm, again = _answer(GitDiffSource(root, patch_with_listing=True), {"revision": target})
    assert (cold, warm) == (3, 2)
    assert answer == again == _answer(_Today(root), {"revision": target})[1]
    monkeypatch.delenv("GIT_CONFIG_NOSYSTEM")
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", str(tmp_path / "no-system-file"))
    textconv.forget()
    first, _ = _answer(GitDiffSource(root, patch_with_listing=True), {"revision": target})
    warm, _ = _answer(GitDiffSource(root, patch_with_listing=True), {"revision": target})
    assert (first, warm) == (4, 2)


def test_a_git_before_2_42_keeps_its_answers_after_its_first_comparison(
    repo: tuple[Path, str, str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Such a Git has no `git var GIT_CONFIG_SYSTEM`; asked to list its system file alone,
    it names it, once per server, and later comparisons take two processes. A system file
    that holds nothing names itself nowhere, so then each comparison asks again: three."""
    root, _base, target = repo
    _old_git(tmp_path, monkeypatch)
    monkeypatch.delenv("GIT_CONFIG_NOSYSTEM")
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", str(tmp_path / "no-system-file"))
    textconv.forget()

    def counts() -> list[int]:
        return [
            _answer(GitDiffSource(root, patch_with_listing=True), {"revision": target})[0]
            for _ in range(3)
        ]

    assert counts() == [5, 2, 2], "rev-parse, the one run; git var, the system file, config"
    (tmp_path / "empty-system-file").write_text("")
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", str(tmp_path / "empty-system-file"))
    textconv.forget()
    assert counts() == [5, 3, 3]


# ── A textconv driver ───────────────────────────────────────────────────


def test_a_textconv_driver_is_run_only_as_the_page_ran_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The reviewer's case, without its second a conversion: files a driver converts, some
    binary, which the listing says are binary and the page never hydrates, and some text,
    which it does, with the driver, on both sides. The one run runs no driver; the page's
    files run in a run of their own as before, so the driver runs as often as it did."""
    root = tmp_path / "textconv"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    calls = tmp_path / "calls.log"
    driver = tmp_path / "driver.sh"
    driver.write_text(f'#!/bin/sh\necho "$1" >> {calls}\ncat "$1"\n')
    driver.chmod(0o755)
    for kind in ("pdf", "md"):
        git(root, "config", f"diff.{kind}conv.textconv", str(driver))
    (root / ".git" / "info").mkdir(exist_ok=True)
    (root / ".git" / "info" / "attributes").write_text("*.pdf diff=pdfconv\n*.md diff=mdconv\n")
    for version in ("one", "two"):
        (root / "a.txt").write_text(f"plain {version}\n")
        for n in range(4):
            (root / f"doc{n}.pdf").write_bytes(b"%PDF\x00" + f"doc {n} {version}".encode())
        for n in range(2):
            (root / f"note{n}.md").write_text(f"note {n} {version}\n")
        git(root, "add", "-A")
        git(root, "commit", "-qm", version)
    target = git(root, "rev-parse", "HEAD").decode().strip()

    def driven(source: GitDiffSource) -> tuple[int, int, str]:
        calls.unlink(missing_ok=True)
        processes, answer = _answer(source, {"revision": target})
        return processes, len(calls.read_text().splitlines()) if calls.exists() else 0, answer

    today = driven(_Today(root))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")  # no system file to ask Git the place of
    textconv.forget()
    cold = driven(GitDiffSource(root, patch_with_listing=True))
    warm = driven(GitDiffSource(root, patch_with_listing=True))
    assert today[1] == 4, "two text files on the page, each side converted, no binary one"
    assert (today[0], cold[0], warm[0]) == (4, 4, 3)
    assert cold[1:] == warm[1:] == today[1:]
    manifest = json.loads(today[2])["manifest"]["files"]
    assert {c["availability"] for c in manifest if c["new"]["path"].endswith(".pdf")} == {"binary"}


# ── A page Git pairs otherwise alone (review of #449, L1) ──────────────


def _commit_of(root: Path, files: dict[bytes, bytes]) -> str:
    """A commit whose tree holds *files*, written with `mktree`."""
    env = _env(root, "2026-01-01T00:00:00 +0000")

    def run(*args: str, stdin: bytes) -> str:
        out = subprocess.run(
            ["git", "-C", str(root), *args], input=stdin, check=True, capture_output=True, env=env
        )
        return out.stdout.decode().strip()

    records = b"".join(
        b"100644 blob "
        + run("hash-object", "-w", "--stdin", stdin=body).encode()
        + b"\t"
        + name
        + b"\0"
        for name, body in sorted(files.items())
    )
    return run("commit-tree", run("mktree", "-z", stdin=records), "-m", "tree", stdin=b"")


def test_a_page_paired_otherwise_alone_is_answered_as_the_manifest_lists_it(
    tmp_path: Path,
) -> None:
    """Fifty-eight changed files, so the page is fifty of them. Asked alone, the page's
    paths pair its renames otherwise than the whole comparison did, so today's page left
    out the files the manifest lists as those renames. The one run's patch is the whole
    comparison's, which pairs them as the manifest does: they have their hunks."""

    def body(changed: dict[int, str]) -> bytes:
        return b"".join(
            (f"{changed[i]} {i}\n" if i in changed else f"common line {i} of the source\n").encode()
            for i in range(100)
        )

    root = tmp_path / "pairing"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    base_files = {b"W": body({}), b"X": body(dict.fromkeys(range(10), "bee"))}
    base_files |= {f"m{i:02d}".encode(): f"filler {i}\n".encode() for i in range(55)}
    target_files = {f"m{i:02d}".encode(): f"filler {i} changed\n".encode() for i in range(55)}
    target_files |= {
        b"a-U": body(dict.fromkeys(range(80, 100), "you")),
        b"b-Y": body(dict.fromkeys(range(95, 100), "why")),
        b"zzz-V": body({}),
    }
    base, target = _commit_of(root, base_files), _commit_of(root, target_files)
    intent = {"left": base, "right": target}
    _warm(root)
    _, today = _answer(_Today(root), intent)
    one_run_count, one_run = _answer(GitDiffSource(root, patch_with_listing=True), intent)
    _, everything = _answer(_Today(root), intent, lambda m: [[c.id for c in m.files]])
    page_today = json.loads(today)["hydrations"][0]
    page_now = json.loads(one_run)["hydrations"][0]
    assert page_today["left_out"], "the case: today's page left files out"
    assert page_now["left_out"] == [] and one_run_count == 2
    whole = json.loads(everything)["hydrations"][0]["patches"]
    assert page_now["patches"] == {file_id: whole[file_id] for file_id in page_now["patches"]}
    assert set(page_now["patches"]) == set(page_today["patches"]) | set(page_today["left_out"])


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


def _superproject(tmp_path: Path) -> tuple[Path, str]:
    """A commit that changes a submodule, adds and deletes a gitlink, turns a file into one
    and one into a file, among files on either side of them. ``sub`` is a real submodule,
    so ``diff.submodule=log`` and ``diff`` have commits to read; the other gitlinks name
    the same commits with no repository behind them."""
    inner = tmp_path / "inner"
    inner.mkdir()
    git(inner, "init", "-q", "-b", "main")
    (inner / "inner.txt").write_text("one\n")
    git(inner, "add", "-A")
    git(inner, "commit", "-qm", "inner one")
    first = git(inner, "rev-parse", "HEAD").decode().strip()
    (inner / "inner.txt").write_text("two\n")
    (inner / "more.txt").write_text("more\n")
    git(inner, "add", "-A")
    git(inner, "commit", "-qm", "inner two")
    second = git(inner, "rev-parse", "HEAD").decode().strip()

    root = tmp_path / "super"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    for name, body in (("a.txt", "alpha\n"), ("m.txt", "middle\n"), ("z.txt", "zulu\n")):
        (root / name).write_text(body)
    (root / "becomes").write_text("a file, then a gitlink\n")
    git(root, "-c", "protocol.file.allow=always", "submodule", "add", "-q", str(inner), "sub")
    git(root, "-C", "sub", "checkout", "-q", first)
    for path in ("gone", "was"):
        git(root, "update-index", "--add", "--cacheinfo", f"160000,{first},{path}")
    git(root, "add", "a.txt", "m.txt", "z.txt", "becomes", "sub", ".gitmodules")
    git(root, "commit", "-qm", "base")

    for name in ("a.txt", "m.txt", "z.txt"):
        (root / name).write_text(f"{name} changed\n")
    git(root, "-C", "sub", "checkout", "-q", second)
    git(root, "update-index", "--force-remove", "gone")
    git(root, "update-index", "--add", "--cacheinfo", f"160000,{second},fresh")
    git(root, "rm", "-q", "--cached", "becomes")
    (root / "becomes").unlink()
    git(root, "update-index", "--add", "--cacheinfo", f"160000,{first},becomes")
    git(root, "update-index", "--force-remove", "was")
    (root / "was").write_text("a gitlink, then a file\n")
    git(root, "add", "a.txt", "m.txt", "z.txt", "sub", "was")
    git(root, "commit", "-qm", "target")
    return root, git(root, "rev-parse", "HEAD").decode().strip()


@pytest.mark.parametrize("submodule", ["short", "log", "diff"])
def test_gitlinks_answer_alike_in_every_submodule_format(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, submodule: str
) -> None:
    """Gitlinks are where a patch's sections and the listing's records stop being one for
    one: with ``log`` a changed submodule's section is a ``Submodule`` line and no ``diff
    --git`` header, and with ``diff`` it is the sections of the submodule's own files."""
    root, target = _superproject(tmp_path)
    git(root, "config", "diff.submodule", submodule)
    _assert_one_run_is_the_two(root, {"revision": target}, monkeypatch)
    monkeypatch.undo()
    (_, answer), (_, _) = _both(root, {"revision": target}, _every_ask)
    kinds = {
        (f["kind"], (f["old"] or {}).get("entry_type"), (f["new"] or {}).get("entry_type"))
        for f in json.loads(answer)["manifest"]["files"]
    }
    assert {
        ("modified", "submodule", "submodule"),
        ("added", None, "submodule"),
        ("deleted", "submodule", None),
        ("type_changed", "file", "submodule"),
        ("type_changed", "submodule", "file"),
    } <= kinds


def test_a_submodules_own_drivers_run_only_as_the_page_ran_them(tmp_path: Path) -> None:
    """With `diff.submodule=diff`, Git diffs a changed submodule's files in a child `git
    diff` of the submodule's own, which runs the submodule's textconv drivers whatever the
    parent passes. A page that does not hold the submodule never ran them, and neither does
    the comparison route's listing: such a configuration is taken to name a driver."""
    root, target = _superproject(tmp_path)
    git(root, "config", "diff.submodule", "diff")
    calls = tmp_path / "calls.log"
    driver = tmp_path / "driver.sh"
    driver.write_text(f'#!/bin/sh\necho "$1" >> {calls}\ncat "$1"\n')
    driver.chmod(0o755)
    git(root, "-C", "sub", "config", "diff.logd.textconv", str(driver))
    (root / ".git" / "modules" / "sub" / "info").mkdir(exist_ok=True)
    (root / ".git" / "modules" / "sub" / "info" / "attributes").write_text("*.txt diff=logd\n")

    def a_txt(manifest: ChangeSetManifest) -> list[list[str]]:
        return [[c.id for c in manifest.files if c.new is not None and c.new.path == "a.txt"]]

    def driven(source: GitDiffSource) -> tuple[int, str]:
        calls.unlink(missing_ok=True)
        _, answer = _answer(source, {"revision": target}, a_txt)
        return (len(calls.read_text().splitlines()) if calls.exists() else 0), answer

    today = driven(_Today(root))
    _warm(root)
    assert driven(GitDiffSource(root, patch_with_listing=True)) == today
    assert today[0] == 0, "a page of a.txt alone diffs no submodule"


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
