"""File ages on a Git revision: ``git last-modified`` read against ``git log -1 -- path``.

The meaning pinned here is the one a hosting site's file list has: a file's time is the
committer time of the last commit that changed it, following history simplification. The
histories below are the cases a one-pass ``git log --name-only`` gets wrong:

- a change on a side branch that a merge discarded, which is not the file's last change;
- a file a merge resolves differently from both of its parents, which only the merge changed;
- a rename, which is a delete and an add of two paths;
- a shallow boundary, where Git calls the boundary commit a root that adds everything.

Every test here runs the real ``git last-modified``, so each asks for ``file_ages_git``:
below the minimum it skips, and in the CI job that builds a release at or above it, it fails
instead of skipping (``tests/file_ages_git.py``). The absent path has its own tests, which
run on every Git.
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import subprocess
import time
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest

from metabrowser import event_log
from metabrowser.git.file_ages import (
    FILE_AGES_GIT_MINIMUM,
    UNDATED,
    AgeLimits,
    FileAgesUnavailableError,
    RevisionAges,
    date_revision,
    file_ages_availability,
    file_ages_version_label,
    is_ancestor,
    merges_between,
    nearest_ancestor,
)
from metabrowser.git.file_ages_service import AgesStatus, FileAgesService
from metabrowser.git.process import RepositoryStoreTarget, repository_store_target
from metabrowser.git.shallow import read_boundary
from tests.file_ages_git import kept_answer, pretend_git, pretend_old_git, settled
from tests.git_pin_harness import git_env
from tests.required_tools import needs_git

pytestmark = needs_git

LIMITS = AgeLimits(timeout_s=30.0)
# Committer dates, one day apart from a fixed day, so a time names its commit.
DAY = 86_400
EPOCH = 1_700_000_000


class History:
    """A repository built commit by commit with chosen committer times."""

    def __init__(self, root: Path) -> None:
        root.mkdir(parents=True, exist_ok=True)
        self.root = root
        self.env = {
            **git_env(root),
            "GIT_AUTHOR_NAME": "Ages",
            "GIT_AUTHOR_EMAIL": "ages@example.invalid",
            "GIT_COMMITTER_NAME": "Ages",
            "GIT_COMMITTER_EMAIL": "ages@example.invalid",
        }
        self.git("init", "-q", "-b", "main", ".")
        self.git("config", "commit.gpgsign", "false")
        self.times: dict[str, int] = {}

    def git(self, *args: str, when: int | None = None, check: bool = True) -> str:
        env = dict(self.env)
        if when is not None:
            stamp = f"{when} +0000"
            env["GIT_COMMITTER_DATE"] = stamp
            env["GIT_AUTHOR_DATE"] = stamp
        done = subprocess.run(
            ["git", *args],
            cwd=self.root,
            env=env,
            capture_output=True,
            text=True,
            check=check,
        )
        return done.stdout.strip()

    def write(self, name: str, text: str) -> None:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def commit(self, day: int, message: str, **files: str | None) -> str:
        """Commit *files* (name with ``__`` for ``/``; ``None`` deletes) at day *day*."""

        for key, text in files.items():
            name = key.replace("__", "/")
            if text is None:
                self.git("rm", "-q", "-f", name)
            else:
                self.write(name, text)
                self.git("add", name)
        self.git("commit", "-q", "--allow-empty", "-m", message, when=EPOCH + day * DAY)
        head = self.git("rev-parse", "HEAD")
        assert head
        self.times[head] = EPOCH + day * DAY
        return head

    def merge(self, branch: str, day: int, message: str, *extra: str) -> str:
        self.git("merge", "-q", "--no-ff", *extra, "-m", message, branch, when=EPOCH + day * DAY)
        head = self.git("rev-parse", "HEAD")
        self.times[head] = EPOCH + day * DAY
        return head

    @property
    def target(self) -> RepositoryStoreTarget:
        return repository_store_target(git_dir=self.root / ".git")

    def names(self, commit: str) -> list[bytes]:
        out = subprocess.run(
            ["git", "ls-tree", "-r", "-z", "--full-tree", commit],
            cwd=self.root,
            env=self.env,
            capture_output=True,
            check=True,
        ).stdout
        names: list[bytes] = []
        for record in out.split(b"\0"):
            meta, _, name = record.partition(b"\t")
            if name and meta.split(b" ")[1] == b"blob":
                names.append(name)
        return sorted(names)

    def reference(self, commit: str, name: bytes) -> int:
        """``git log -1 -- path`` as the oracle."""

        out = self.git("log", "-1", "--format=%ct", commit, "--", name.decode())
        return int(out)

    async def date(
        self, commit: str, *, base: RevisionAges | None = None, limits: AgeLimits = LIMITS
    ) -> RevisionAges:
        boundary = read_boundary(self.root / ".git")
        return await date_revision(
            target=self.target,
            commit=commit,
            names=self.names(commit),
            boundary=boundary,
            limits=limits,
            base=base,
        )


@pytest.fixture
def history(tmp_path: Path, file_ages_git: tuple[int, int, int]) -> History:
    return History(tmp_path / "repo")


def build_branchy(history: History) -> str:
    """Linear commits, a side branch whose change a merge discards, a conflict resolved by
    the merge alone, a rename, and a file only the root touched."""

    history.commit(0, "root", root_only="r\n", shared="one\n", doc__guide="g1\n", doc__old="o\n")
    history.commit(1, "main edits guide", doc__guide="g2\n")
    history.git("checkout", "-q", "-b", "side")
    history.commit(2, "side edits shared", shared="side\n")
    history.commit(3, "side edits guide", doc__guide="g-side\n", only_side="s\n")
    history.git("checkout", "-q", "main")
    history.commit(4, "main edits shared", shared="main\n")
    history.commit(5, "main edits guide again", doc__guide="g3\n")
    # `git merge -s ours`-like per file: keep main's guide, resolve shared by hand.
    history.git("merge", "-q", "--no-ff", "--no-commit", "side", when=EPOCH + 6 * DAY, check=False)
    history.write("shared", "resolved\n")
    history.write("doc/guide", "g3\n")
    history.git("add", "shared", "doc/guide")
    history.git("commit", "-q", "-m", "merge side", when=EPOCH + 6 * DAY)
    history.git("mv", "doc/old", "doc/older")
    history.git("commit", "-q", "-m", "rename old", when=EPOCH + 7 * DAY)
    return history.git("rev-parse", "HEAD")


def test_a_discarded_change_and_a_merge_resolution_date_as_git_log_says(
    history: History,
) -> None:
    tip = build_branchy(history)
    ages = asyncio.run(history.date(tip))
    assert ages.complete
    for name in history.names(tip):
        assert ages.time_of(name) == history.reference(tip, name), name
    # The merge dropped the side branch's guide, so the guide's last change is main's.
    assert ages.time_of(b"doc/guide") == EPOCH + 5 * DAY
    # Only the merge made "resolved": it differs from both parents.
    assert ages.time_of(b"shared") == EPOCH + 6 * DAY
    # A rename is an add of the new name.
    assert ages.time_of(b"doc/older") == EPOCH + 7 * DAY
    assert ages.time_of(b"root_only") == EPOCH
    assert ages.time_of(b"only_side") == EPOCH + 3 * DAY


def test_a_directory_is_the_newest_of_its_files(history: History) -> None:
    tip = build_branchy(history)
    ages = asyncio.run(history.date(tip))
    assert ages.newest_under(b"doc") == EPOCH + 7 * DAY
    assert ages.newest_under(b"") == EPOCH + 7 * DAY
    assert ages.newest_under(b"doc/guide") == EPOCH + 5 * DAY
    assert ages.newest_under(b"missing") is None
    # A prefix that is another name's start is not a directory of it.
    assert ages.newest_under(b"sha") is None


def test_an_answer_from_an_ancestor_equals_a_cold_one(history: History) -> None:
    tip = build_branchy(history)
    first = history.git("rev-list", "--max-parents=0", "HEAD")
    cold = asyncio.run(history.date(tip))
    for ancestor in (history.git("rev-parse", "HEAD~1"), history.git("rev-parse", "HEAD~3"), first):
        base = asyncio.run(history.date(ancestor))
        derived = asyncio.run(history.date(tip, base=base))
        assert derived.times == cold.times, ancestor
        assert derived.from_commit == ancestor
        assert derived.older_than is None


def test_an_ancestor_off_the_first_parent_chain_is_still_equal(history: History) -> None:
    """A base on the side branch: some chains reach other excluded commits, so the answer
    is read whole, and is the same."""

    tip = build_branchy(history)
    side = history.git("rev-parse", "side")
    base = asyncio.run(history.date(side))
    derived = asyncio.run(history.date(tip, base=base))
    assert derived.times == asyncio.run(history.date(tip)).times


def test_the_nearest_answered_ancestor_is_the_newest_committed(history: History) -> None:
    tip = build_branchy(history)
    early = asyncio.run(history.date(history.git("rev-parse", "HEAD~4")))
    late = asyncio.run(history.date(history.git("rev-parse", "HEAD~1")))
    unrelated = asyncio.run(history.date(history.git("rev-parse", "side")))
    found = asyncio.run(nearest_ancestor(history.target, tip, [early, unrelated, late]))
    assert found is not None
    assert found.commit == late.commit
    assert asyncio.run(is_ancestor(history.target, early.commit, tip))
    assert not asyncio.run(is_ancestor(history.target, tip, early.commit))


def test_a_shallow_boundary_leaves_files_undated_and_says_older_than(
    history: History, tmp_path: Path
) -> None:
    tip = build_branchy(history)
    shallow = tmp_path / "shallow"
    subprocess.run(
        ["git", "clone", "-q", "--depth", "2", f"file://{history.root}", str(shallow)],
        check=True,
        capture_output=True,
        env=history.env,
    )
    clone = History.__new__(History)
    clone.root = shallow
    clone.env = history.env
    clone.times = {}
    boundary = read_boundary(shallow / ".git")
    assert boundary
    ages = asyncio.run(clone.date(tip))
    assert not ages.complete
    assert ages.stop == "boundary"
    # `root_only` was last changed before the boundary: undated, never the boundary's time.
    assert ages.time_of(b"root_only") is None
    boundary_time = max(
        int(clone.git("log", "-1", "--format=%ct", oid)) for oid in sorted(boundary)
    )
    assert ages.older_than == boundary_time
    # What the two commits changed is dated as in the full history.
    assert ages.time_of(b"doc/older") == EPOCH + 7 * DAY
    assert all(
        value in (UNDATED, history.reference(tip, name))
        for name, value in zip(ages.names, ages.times, strict=True)
    )


def test_a_cut_read_keeps_what_git_printed_and_says_older_than_the_oldest_printed(
    history: History, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A read past its budget keeps the files Git had printed and leaves the rest undated,
    last changed before the oldest commit printed. Git prints a file as soon as it knows
    it, so the read is stood in for by one that prints a single file and then stalls."""

    from metabrowser.git import file_ages

    tip = build_branchy(history)
    root = history.git("rev-list", "--max-parents=0", "HEAD")

    async def prints_one_then_stalls(
        _process: object, wanted: frozenset[bytes], found: dict[bytes, bytes]
    ) -> None:
        assert b"root_only" in wanted
        found[b"root_only"] = root.encode()
        await asyncio.sleep(3600)

    monkeypatch.setattr(file_ages, "_consume", prints_one_then_stalls)
    ages = asyncio.run(history.date(tip, limits=AgeLimits(timeout_s=0.5)))
    assert ages.stop == "budget"
    assert ages.dated == 1
    assert ages.time_of(b"root_only") == EPOCH
    assert ages.older_than == EPOCH


def test_a_cut_read_that_printed_nothing_says_older_than_the_revision(
    history: History, monkeypatch: pytest.MonkeyPatch
) -> None:
    from metabrowser.git import file_ages

    tip = build_branchy(history)

    async def stalls(*_args: object) -> None:
        await asyncio.sleep(3600)

    monkeypatch.setattr(file_ages, "_consume", stalls)
    ages = asyncio.run(history.date(tip, limits=AgeLimits(timeout_s=0.5)))
    assert ages.stop == "budget"
    assert ages.dated == 0
    assert ages.older_than == EPOCH + 7 * DAY


def test_the_boundary_unreadable_is_unavailable_not_a_guess(history: History) -> None:
    tip = build_branchy(history)
    with pytest.raises(FileAgesUnavailableError) as raised:
        asyncio.run(
            date_revision(
                target=history.target,
                commit=tip,
                names=history.names(tip),
                boundary=None,
                limits=LIMITS,
            )
        )
    assert raised.value.reason == "boundary"


# ── The absent path: every Git runs these ──────────────────────────


def test_the_minimum_is_named_in_one_place() -> None:
    assert FILE_AGES_GIT_MINIMUM == (2, 53, 0)
    assert file_ages_version_label() == "2.53"


@pytest.mark.parametrize(
    ("line", "version", "reason", "hint"),
    [
        (
            "git version 2.50.1 (Apple Git-155)",
            (2, 50, 1),
            "too_old",
            "File ages on Git revisions need Git 2.53 or newer (found 2.50.1)",
        ),
        (
            "git version 2.52.0",
            (2, 52, 0),
            "too_old",
            "File ages on Git revisions need Git 2.53 or newer (found 2.52.0)",
        ),
        (
            "a build of git that names no version",
            None,
            "unreadable",
            "File ages on Git revisions need Git 2.53 or newer "
            "(found a build of git that names no version)",
        ),
        ("git version 2.53.0", (2, 53, 0), None, None),
        ("git version 2.56.1", (2, 56, 1), None, None),
    ],
)
def test_availability_names_what_is_found(
    monkeypatch: pytest.MonkeyPatch,
    line: str,
    version: tuple[int, int, int] | None,
    reason: str | None,
    hint: str | None,
) -> None:
    pretend_git(monkeypatch, line, version)
    availability = file_ages_availability()
    assert availability.available is (reason is None)
    assert availability.reason == reason
    assert availability.hint == hint
    assert (availability.remedy is None) is (reason is None)


def test_no_git_on_path_is_its_own_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    from metabrowser.git import file_ages

    monkeypatch.setattr(file_ages, "git_executable", lambda: None)
    availability = file_ages_availability()
    assert availability.reason == "no_git"
    assert availability.hint == (
        "File ages on Git revisions need Git 2.53 or newer; no git was found on PATH"
    )


def test_an_old_git_reads_nothing_and_the_service_says_unavailable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    pretend_old_git(monkeypatch)

    async def names() -> list[bytes]:
        raise AssertionError("an unavailable Git asks for no names")

    async def run() -> None:
        service = FileAgesService()
        status = service.request(
            repository_store_target(git_dir=_empty_git_dir(tmp_path)), "0" * 40, names
        )
        assert status.state == "unavailable"
        assert status.reason == "too_old"
        assert status.hint == "File ages on Git revisions need Git 2.53 or newer (found 2.50.1)"
        assert status.wire() == {
            "state": "unavailable",
            "hint": "File ages on Git revisions need Git 2.53 or newer (found 2.50.1)",
            "reason": "too_old",
        }

    asyncio.run(run())


def _empty_git_dir(tmp_path: Path) -> Path:
    git_dir = tmp_path / "empty.git"
    subprocess.run(["git", "init", "-q", "--bare", str(git_dir)], check=True, capture_output=True)
    return git_dir


# ── The service: per commit, in the background ─────────────────────


def test_the_service_answers_dating_then_ready_and_keeps_the_answer(history: History) -> None:
    tip = build_branchy(history)
    names = history.names(tip)
    calls = 0

    async def source() -> list[bytes]:
        nonlocal calls
        calls += 1
        return names

    async def run() -> None:
        service = FileAgesService()
        first = service.request(history.target, tip, source)
        assert first.state == "dating"
        # A second ask while the read runs starts nothing more.
        assert service.request(history.target, tip, source).state == "dating"
        await settled(service, history.target, tip)
        ready = service.request(history.target, tip, source)
        assert ready.state == "ready"
        assert ready.ages is not None
        assert ready.wire()["dated"] == len(names)
        assert service.request(history.target, tip, source).state == "ready"
        assert calls == 1

    asyncio.run(run())


def test_the_service_derives_a_new_tip_from_a_kept_ancestor(history: History) -> None:
    tip = build_branchy(history)
    earlier = history.git("rev-parse", "HEAD~1")

    async def run() -> None:
        service = FileAgesService()
        for commit in (earlier, tip):
            names = history.names(commit)

            async def source(names: list[bytes] = names) -> list[bytes]:
                return names

            service.request(history.target, commit, source)
            await settled(service, history.target, commit)
        answer = kept_answer(service, history.target, tip)
        assert answer is not None
        assert answer.from_commit == earlier
        assert answer.times == (await history.date(tip)).times

    asyncio.run(run())


def test_a_truncated_index_is_failed_and_asked_again_only_later(history: History) -> None:
    tip = build_branchy(history)
    now = [0.0]

    async def truncated() -> list[bytes] | None:
        return None

    async def run() -> None:
        service = FileAgesService(retry_after_s=30.0, clock=lambda: now[0])
        service.request(history.target, tip, truncated)
        await settled(service, history.target, tip)
        failed = service.request(history.target, tip, truncated)
        assert failed.state == "failed"
        assert failed.reason == "too_many_files"
        now[0] = 31.0
        assert service.request(history.target, tip, truncated).state == "dating"

    asyncio.run(run())


def test_the_real_git_is_at_or_above_the_minimum(file_ages_git: tuple[int, int, int]) -> None:
    assert file_ages_git >= FILE_AGES_GIT_MINIMUM
    assert os.environ.get("GIT_DIR") is None


# ── Review of the first version: derived reads, races, cuts, records, a Git abort ────────


class Plumbing:
    """Commits built from trees and parents directly, so a history has exactly the shape a
    test names (a merge that restores a mode, a child dated before its parent)."""

    def __init__(self, history: History) -> None:
        self.history = history

    def blob(self, text: str) -> str:
        done = subprocess.run(
            ["git", "hash-object", "-w", "--stdin"],
            cwd=self.history.root,
            env=self.history.env,
            input=text + "\n",
            capture_output=True,
            text=True,
            check=True,
        )
        return done.stdout.strip()

    def tree(self, entries: dict[str, tuple[str, str]]) -> str:
        """A tree of ``path -> (mode, blob)``, written through a private index."""

        index = self.history.root / ".git" / "plumbing-index"
        env = {**self.history.env, "GIT_INDEX_FILE": str(index)}
        index.unlink(missing_ok=True)
        for path, (mode, oid) in entries.items():
            subprocess.run(
                ["git", "update-index", "--add", "-z", "--index-info"],
                cwd=self.history.root,
                env=env,
                input=f"{mode} {oid}\t{path}\0".encode(),
                capture_output=True,
                check=True,
            )
        done = subprocess.run(
            ["git", "write-tree"],
            cwd=self.history.root,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        index.unlink(missing_ok=True)
        return done.stdout.strip()

    def commit(self, when: int, tree: str, *parents: str) -> str:
        args = [item for parent in parents for item in ("-p", parent)]
        return self.history.git("commit-tree", tree, *args, "-m", "c", when=when)


def mode_restoring_merge_history(history: History) -> tuple[str, str]:
    """A and C, where ``git last-modified C ^A`` marks ``a`` as last changed at ``A`` though
    its last change is older: the merge M2 puts ``a``'s mode back to its first parent's, and
    Git then blames the excluded commit. (Found by the review of the first version.)"""

    plumbing = Plumbing(history)
    x, side, feature = plumbing.blob("x"), plumbing.blob("side"), plumbing.blob("feature")

    def tree(mode: str, y: str | None = None) -> str:
        entries = {"a": (mode, x)}
        if y is not None:
            entries["d/y"] = ("100644", y)
        return plumbing.tree(entries)

    def day(number: int) -> int:
        return EPOCH + number * DAY

    root = plumbing.commit(day(0), tree("100644"))
    side_commit = plumbing.commit(day(1), tree("100644", side), root)
    plain = plumbing.commit(day(2), tree("100644"), root)
    a = plumbing.commit(day(3), tree("100755", feature), plain)
    m1 = plumbing.commit(day(4), tree("100755", feature), a, side_commit)
    m2 = plumbing.commit(day(7), tree("100644", feature), plain, m1)
    c = plumbing.commit(day(8), tree("100644", feature), m2)
    return a, c


def test_a_range_with_a_merge_is_read_cold_and_the_answer_is_git_logs(history: History) -> None:
    a, c = mode_restoring_merge_history(history)
    base = asyncio.run(history.date(a))
    assert asyncio.run(merges_between(history.target, a, c)) == 2
    assert asyncio.run(nearest_ancestor(history.target, c, [base])) is None
    cold = asyncio.run(history.date(c))
    # The file's last change is the root commit's, as `git log -1 -- a` says.
    assert cold.time_of(b"a") == EPOCH == history.reference(c, b"a")


def test_a_linear_range_is_derived_and_equal_to_a_cold_read(history: History) -> None:
    history.commit(0, "root", one="1\n", two="2\n")
    base_commit = history.commit(1, "edit", one="1b\n")
    tip = history.commit(2, "edit again", two="2b\n", three="3\n")
    base = asyncio.run(history.date(base_commit))
    assert asyncio.run(merges_between(history.target, base_commit, tip)) == 0
    assert asyncio.run(nearest_ancestor(history.target, tip, [base])) is base
    assert asyncio.run(history.date(tip, base=base)).times == asyncio.run(history.date(tip)).times


def random_history(history: History, seed: int, steps: int) -> list[str]:
    """Branches, edits, mode changes, deletes, and merges, deterministic for *seed*, as
    commit IDs. A merge that conflicts is abandoned."""

    rng = random.Random(seed)
    names = ["a", "b", "c", "d/e", "d/f", "g"]
    history.commit(0, "root", **{name.replace("/", "__"): "0\n" for name in names})
    branches = ["main"]
    commits: list[str] = [history.git("rev-parse", "HEAD")]
    for step in range(1, steps + 1):
        when = EPOCH + step * DAY
        choice = rng.choice(["edit", "edit", "edit", "mode", "delete", "branch", "merge"])
        if choice == "branch":
            name = f"b{step}"
            history.git("checkout", "-q", "-b", name, rng.choice(commits))
            branches.append(name)
            continue
        if choice == "merge" and len(branches) > 1:
            other = rng.choice([branch for branch in branches if branch != branches[0]])
            history.git("checkout", "-q", branches[0])
            done = subprocess.run(
                ["git", "merge", "-q", "--no-ff", "-X", "theirs", "-m", "m", other],
                cwd=history.root,
                env={
                    **history.env,
                    "GIT_COMMITTER_DATE": f"{when} +0000",
                    "GIT_AUTHOR_DATE": f"{when} +0000",
                },
                capture_output=True,
                check=False,
            )
            if done.returncode != 0:
                history.git("merge", "--abort", check=False)
            else:
                commits.append(history.git("rev-parse", "HEAD"))
            continue
        history.git("checkout", "-q", rng.choice(branches))
        name = rng.choice(names)
        path = history.root / name
        if choice == "delete" and path.exists():
            history.git("rm", "-q", "-f", name)
        elif choice == "mode" and path.exists():
            path.chmod(0o755 if not os.access(path, os.X_OK) else 0o644)
            history.git("add", name)
        else:
            history.write(name, f"{step}\n")
            history.git("add", name)
        history.git("commit", "-q", "--allow-empty", "-m", "e", when=when)
        commits.append(history.git("rev-parse", "HEAD"))
    history.git("checkout", "-q", "main")
    history.git(
        "merge",
        "-q",
        "--no-ff",
        "-X",
        "theirs",
        "-m",
        "all",
        *branches[1:],
        check=False,
        when=EPOCH + (steps + 1) * DAY,
    )
    return commits


@pytest.mark.parametrize(
    ("seed", "offered", "refused_too"),
    [(3, True, False), (4, True, True), (6, True, True), (23, False, True)],
)
def test_whatever_is_derived_equals_a_cold_read_over_a_merge_heavy_history(
    tmp_path: Path, file_ages_git: tuple[int, int, int], seed: int, offered: bool, refused_too: bool
) -> None:
    """Over random histories with merges, mode changes, and deletes, an answer a service would
    derive (an ancestor `nearest_ancestor` offers) equals the cold one, and the ranges that
    hold a merge are among those it refuses."""

    history = History(tmp_path / "repo")
    random_history(history, seed, 28)
    tip = history.git("rev-parse", "HEAD")
    ancestors = history.git("rev-list", tip).split()[1:]
    sampled = ancestors[:: max(1, len(ancestors) // 8)]

    async def run() -> tuple[int, int]:
        cold = await history.date(tip)
        derived_checked = refused = 0
        for ancestor in sampled:
            base = await history.date(ancestor)
            offered = await nearest_ancestor(history.target, tip, [base])
            merges = await merges_between(history.target, ancestor, tip)
            if merges:
                assert offered is None
                refused += 1
                continue
            assert offered is base
            assert (await history.date(tip, base=base)).times == cold.times, ancestor
            derived_checked += 1
        return derived_checked, refused

    derived_checked, refused = asyncio.run(run())
    assert derived_checked + refused == len(sampled)
    # The seeds are chosen so that the generator reaches both sides of the rule.
    assert (derived_checked > 0, refused > 0) == (offered, refused_too)
    for name in history.names(tip):
        assert asyncio.run(history.date(tip)).time_of(name) == history.reference(tip, name), name


def test_an_answer_cut_by_its_budget_is_never_a_base(
    history: History, monkeypatch: pytest.MonkeyPatch
) -> None:
    from metabrowser.git import file_ages

    tip = build_branchy(history)
    early = history.git("rev-parse", "HEAD~1")

    async def stalls(*_args: object) -> None:
        await asyncio.sleep(3600)

    with monkeypatch.context() as patch:
        patch.setattr(file_ages, "_consume", stalls)
        cut = asyncio.run(history.date(early, limits=AgeLimits(timeout_s=0.3)))
    assert cut.stop == "budget"
    whole = asyncio.run(history.date(early))
    assert asyncio.run(nearest_ancestor(history.target, tip, [cut])) is None
    assert asyncio.run(nearest_ancestor(history.target, tip, [cut, whole])) is whole


def test_the_derived_read_and_the_cold_read_after_it_each_have_a_budget(
    history: History, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A derived read that must be read again cold does not spend the cold read's time: each
    ``git last-modified`` is given the whole budget."""

    from metabrowser.git import file_ages

    tip = build_branchy(history)
    seen: list[float] = []
    original = file_ages._read_last_modified  # pyright: ignore[reportPrivateUsage]
    base = asyncio.run(history.date(history.git("rev-parse", "HEAD~1")))

    async def recorded(*args: Any, **kwargs: Any) -> Any:
        seen.append(kwargs["deadline"] - time.monotonic())
        await asyncio.sleep(0.2)
        if len(seen) == 1:
            # The derived read reaches a commit other than its base: it is read again cold.
            return file_ages._Read(found={b"shared": b"^" + b"0" * 40}, cut=False)  # pyright: ignore[reportPrivateUsage]
        return await original(*args, **kwargs)

    monkeypatch.setattr(file_ages, "_read_last_modified", recorded)
    asyncio.run(history.date(tip, base=base, limits=AgeLimits(timeout_s=5.0)))
    assert len(seen) == 2
    assert all(remaining > 4.5 for remaining in seen), seen


# ── The service: the race, the retry of a cut answer, and what it records ────────────


def test_a_read_cancelled_and_asked_for_again_is_not_removed_by_the_first_ones_end(
    history: History,
) -> None:
    """The finished first task must not pop the second read's entry (and let a third start)."""

    tip = build_branchy(history)
    started: list[int] = []

    async def run() -> None:
        release = asyncio.Event()

        async def names() -> list[bytes]:
            started.append(1)
            try:
                await release.wait()
            except asyncio.CancelledError:
                for _ in range(3):
                    await asyncio.sleep(0)
                raise
            return history.names(tip)

        service = FileAgesService()
        service.request(history.target, tip, names)
        await asyncio.sleep(0)
        service.cancel(history.target, tip)
        service.request(history.target, tip, names)
        for _ in range(10):
            await asyncio.sleep(0)
        # The first read has ended; the second still runs, and a poll starts no third.
        assert service.request(history.target, tip, names).state == "dating"
        assert len(started) == 2
        release.set()
        await settled(service, history.target, tip)
        assert service.request(history.target, tip, names).state == "ready"

    asyncio.run(run())


def test_a_cut_answer_is_served_then_read_again_after_its_window(
    history: History, monkeypatch: pytest.MonkeyPatch
) -> None:
    from metabrowser.git import file_ages

    tip = build_branchy(history)
    now = [0.0]
    reads = []

    async def names() -> list[bytes]:
        return history.names(tip)

    async def run() -> None:
        service = FileAgesService(
            limits=AgeLimits(timeout_s=0.3), cut_retry_after_s=300.0, clock=lambda: now[0]
        )

        async def stalls(*_args: object) -> None:
            reads.append(1)
            await asyncio.sleep(3600)

        with monkeypatch.context() as patch:
            patch.setattr(file_ages, "_consume", stalls)
            service.request(history.target, tip, names)
            await settled(service, history.target, tip)
            cut = service.request(history.target, tip, names)
            assert (cut.state, cut.ages is not None and cut.ages.stop) == ("partial", "budget")
            now[0] = 299.0
            assert service.request(history.target, tip, names).state == "partial"
            assert len(reads) == 1
            now[0] = 301.0
            assert service.request(history.target, tip, names).state == "dating"
            await settled(service, history.target, tip)
            assert len(reads) == 2
        # With the Git as it is, the next read replaces the cut answer.
        now[0] = 1000.0
        service.request(history.target, tip, names)
        await settled(service, history.target, tip)
        assert service.request(history.target, tip, names).state == "ready"

    asyncio.run(run())


@pytest.fixture
def log(tmp_path: Path) -> Generator[event_log.EventLog]:
    from metabrowser import home

    state = tmp_path / "state"
    home.ensure_storage_root(state)
    home.ensure_private_directory(state, event_log.EVENTS_DIRECTORY)
    sink = event_log.EventLog(state / event_log.EVENTS_DIRECTORY, state)
    with event_log.installed(sink):
        yield sink
    sink.close()


def read_records(sink: event_log.EventLog) -> list[dict[str, Any]]:
    assert sink.path is not None
    return [
        json.loads(line)
        for line in sink.path.read_text(encoding="utf-8").splitlines()
        if '"file_ages.read"' in line
    ]


def test_every_step_of_a_read_is_inside_its_span_and_any_failure_is_recorded(
    history: History, log: event_log.EventLog
) -> None:
    tip = build_branchy(history)

    async def breaks() -> list[bytes]:
        raise RuntimeError("the names could not be listed")

    async def run() -> None:
        service = FileAgesService()
        assert service.request(history.target, tip, breaks).state == "dating"
        await settled(service, history.target, tip)
        failed = service.request(history.target, tip, breaks)
        assert (failed.state, failed.reason) == ("failed", "git_failed")

    asyncio.run(run())
    end = [record for record in read_records(log) if record["event"] == "end"]
    assert len(end) == 1
    assert end[0]["outcome"] == "failed"
    assert end[0]["attrs"]["reason"] == "git_failed"
    assert "the names could not be listed" in end[0]["attrs"]["error"]


def test_an_answer_records_what_it_measured(history: History, log: event_log.EventLog) -> None:
    tip = build_branchy(history)

    async def names() -> list[bytes]:
        return history.names(tip)

    async def run() -> None:
        service = FileAgesService()
        service.request(history.target, tip, names)
        await settled(service, history.target, tip)

    asyncio.run(run())
    end = [record for record in read_records(log) if record["event"] == "end"]
    assert [record["outcome"] for record in end] == ["ok"]
    attrs = end[0]["attrs"]
    assert attrs["stop"] == "complete" and attrs["dated"] == len(history.names(tip))
    assert attrs["files"] == len(history.names(tip)) and "commits" not in attrs


def git_aborting_history(history: History) -> str:
    """Three commits on which Git 2.56.1 aborts (``BUG: builtin/last-modified.c:468``): a
    child dated before its parent, and a merge of the child with that parent."""

    plumbing = Plumbing(history)
    blob = plumbing.blob("x")

    def tree(*paths: str) -> str:
        return plumbing.tree(dict.fromkeys(paths, ("100644", blob)))

    x = plumbing.commit(1_700_090_000, tree("p1", "p2"))
    y = plumbing.commit(1_700_043_600, tree("p2"), x)
    return plumbing.commit(1_700_043_600, tree("p1", "p2"), y, x)


def test_a_git_that_aborts_is_a_failed_read_with_its_stderr_recorded(
    history: History, log: event_log.EventLog
) -> None:
    """Git's own abort is never an answer: the read fails as ``git_failed``, the record has
    Git's stderr, and a page keeps no ages. A Git that reads the history gives the answer of
    ``git log -1`` instead, which this accepts too."""

    tip = git_aborting_history(history)
    names = history.names(tip)

    async def source() -> list[bytes]:
        return names

    async def run() -> AgesStatus:
        service = FileAgesService()
        service.request(history.target, tip, source)
        await settled(service, history.target, tip)
        return service.request(history.target, tip, source)

    status = asyncio.run(run())
    if status.state == "failed":
        assert status.reason == "git_failed"
        end = [record for record in read_records(log) if record["event"] == "end"]
        assert end[0]["outcome"] == "failed"
        assert end[0]["attrs"]["returncode"] not in (0, None)
        assert end[0]["attrs"]["stderr"]
    else:
        assert status.ages is not None
        for name in names:
            assert status.ages.time_of(name) == history.reference(tip, name)
