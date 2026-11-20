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
import os
import subprocess
from pathlib import Path

import pytest

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
    nearest_ancestor,
)
from metabrowser.git.file_ages_service import FileAgesService
from metabrowser.git.process import RepositoryStoreTarget, repository_store_target
from metabrowser.git.shallow import read_boundary
from tests.file_ages_git import pretend_git, pretend_old_git
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
        await service.settled(history.target, tip)
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
            await service.settled(history.target, commit)
        answer = service.peek(history.target, tip)
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
        await service.settled(history.target, tip)
        failed = service.request(history.target, tip, truncated)
        assert failed.state == "failed"
        assert failed.reason == "too_many_files"
        now[0] = 31.0
        assert service.request(history.target, tip, truncated).state == "dating"

    asyncio.run(run())


def test_the_real_git_is_at_or_above_the_minimum(file_ages_git: tuple[int, int, int]) -> None:
    assert file_ages_git >= FILE_AGES_GIT_MINIMUM
    assert os.environ.get("GIT_DIR") is None
