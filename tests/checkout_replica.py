"""Small replicas for an overlay store: an origin, a checkout of it, and a planted one.

A replica is a bare ``file://`` origin with GitHub's ``refs/pull/<n>/head``, built with
pinned dates so its commit IDs are the same on every machine, and clones of it. It stands
in for ``https://github.com/octo/demo``: a clone's ``origin`` is set to that URL, as a real
checkout's is, while ``remote_url_for`` fetches from the local origin. ``build_merge_heavy``
is the graph that made a copied shallow boundary answer the wrong merge base:

    R0 - A1 - A2 - A3 - A4 - A5 - A6 - M7   trunk; M7 merges A6 and L1
           \\___ L1 _____________________/
                        A4 - H1 - H2        refs/pull/1/head

A clone of ``trunk`` at ``--depth 3`` holds M7, A6, L1, A5, and A1, with the boundary
{A5, A1}. A1 is in the graph through L1 and is an ancestor of A4, which is cut, so
``merge-base`` on it answers A1. The truth is A4.

``fingerprint`` is what "nothing wrote to the checkout" is measured with, and
``scenario_for`` answers ``gh`` for pull request 1 of a replica.

Run as a script, it builds homes for a tryscript golden, through the production CLI path
with the seams ``tests/github_pull_fixture.py`` uses, since the machine's Git may be below
the acquisition floor and reading a cached store needs no floor::

    checkout_replica.py <directory>

``<directory>/home`` borrows from ``checkout``, a checkout with a linked worktree, which
it was named through, and holds pull request 1. ``<directory>/home-moved`` borrowed from a
checkout that has since moved to ``moved``, ``<directory>/home-damaged`` has an alternates
file that disagrees with its record, and ``<directory>/home-shallow`` borrows from a
``--depth 3`` clone of the merge-heavy graph, with no deepening allowed, so its record says
``base_uncertain``.
"""

from __future__ import annotations

import contextlib
import copy
import hashlib
import os
import shutil
import stat
import subprocess
import sys
from collections.abc import Generator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from tests.github_pull_fixture import (
    CANONICAL,
    FETCHED_AT,
    _substitute,  # pyright: ignore[reportPrivateUsage]
    account,
    install_fake_gh,
    ok,
    page,
    recorded_responses,
)
from tests.golden_harness import pinned_git, pinned_git_env

REMOTE_SPELLING: Final = CANONICAL + ".git"
_RECORDED_GIT: Final = (2, 50, 1)


@dataclass(frozen=True, slots=True)
class Replica:
    """A bare origin and the commits a test names."""

    origin: Path
    commits: Mapping[str, str]

    @property
    def url(self) -> str:
        return f"file://{self.origin.resolve()}"

    def __getitem__(self, name: str) -> str:
        return self.commits[name]


def _commit(work: Path, name: str, path: str | None = None, text: str = "") -> str:
    if path is not None:
        (work / path).write_text(text, encoding="utf-8")
        pinned_git(work, "add", path)
    pinned_git(work, "commit", "-q", "--allow-empty", "-m", name)
    return pinned_git(work, "rev-parse", "HEAD")


def _publish(work: Path, directory: Path, *branches_to_drop: str, head: str) -> Path:
    origin = directory / "origin.git"
    pinned_git(directory, "clone", "-q", "--bare", str(work), str(origin))
    pinned_git(origin, "symbolic-ref", "HEAD", "refs/heads/trunk")
    pinned_git(origin, "update-ref", "refs/pull/1/head", head)
    for branch in branches_to_drop:
        pinned_git(origin, "branch", "-q", "-D", branch)
    return origin


def build_merge_heavy(directory: Path) -> Replica:
    """The graph above, whose ``--depth 3`` clone answers the wrong merge base."""

    work = directory / "source"
    work.mkdir(parents=True)
    pinned_git(work, "init", "-q", "-b", "trunk")
    commits: dict[str, str] = {"R0": _commit(work, "R0")}
    commits["A1"] = _commit(work, "A1", "f", "a1\n")
    pinned_git(work, "branch", "-q", "L")
    for number in (2, 3, 4):
        commits[f"A{number}"] = _commit(work, f"A{number}", "f", f"a{number}\n")
    pinned_git(work, "branch", "-q", "pr")
    for number in (5, 6):
        commits[f"A{number}"] = _commit(work, f"A{number}", "f", f"a{number}\n")
    pinned_git(work, "checkout", "-q", "L")
    commits["L1"] = _commit(work, "L1", "g", "l1\n")
    pinned_git(work, "checkout", "-q", "trunk")
    pinned_git(work, "merge", "-q", "--no-ff", "-m", "M7", "L")
    commits["M7"] = pinned_git(work, "rev-parse", "HEAD")
    pinned_git(work, "checkout", "-q", "pr")
    commits["H1"] = _commit(work, "H1", "p", "p1\n")
    commits["H2"] = _commit(work, "H2", "p", "p1\np2\n")
    pinned_git(work, "checkout", "-q", "trunk")
    origin = _publish(work, directory, "pr", "L", head=commits["H2"])
    return Replica(origin, commits)


def build_linear(directory: Path) -> Replica:
    """M1 to M5 on ``trunk`` and a pull request off M4, as the reviewer's hostile replica."""

    work = directory / "source"
    work.mkdir(parents=True)
    pinned_git(work, "init", "-q", "-b", "trunk")
    commits: dict[str, str] = {}
    for number in range(1, 6):
        commits[f"M{number}"] = _commit(work, f"M{number}", "m", f"m{number}\n")
    pinned_git(work, "checkout", "-q", "-b", "pr", commits["M4"])
    commits["H1"] = _commit(work, "H1", "p", "p\n")
    pinned_git(work, "checkout", "-q", "trunk")
    origin = _publish(work, directory, "pr", head=commits["H1"])
    return Replica(origin, commits)


def clone_checkout(replica: Replica, path: Path, *flags: str) -> Path:
    """A checkout of *replica* whose ``origin`` names the canonical URL, as a real one does."""

    subprocess.run(
        ["git", "clone", "-q", *flags, replica.url, str(path)],
        check=True,
        capture_output=True,
        env=pinned_git_env(),
    )
    pinned_git(path, "remote", "set-url", "origin", REMOTE_SPELLING)
    return path


def fingerprint(checkout: Path) -> dict[str, tuple[int, int, str]]:
    """Every entry under the checkout's Git directory: inode, modification time, and bytes.

    A file replaced by rename has a new inode, so this sees a rewrite to the same bytes. A
    symbolic link is compared by what it names.
    """

    git_dir = checkout / ".git"
    entries: dict[str, tuple[int, int, str]] = {}
    for directory, subdirectories, files in os.walk(git_dir):
        for name in (*subdirectories, *files):
            path = Path(directory) / name
            status = os.lstat(path)
            relative = path.relative_to(git_dir).as_posix()
            if stat.S_ISREG(status.st_mode):
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
            elif stat.S_ISLNK(status.st_mode):
                digest = os.readlink(path)
            else:
                digest = f"mode:{stat.S_IFMT(status.st_mode)}"
            entries[relative] = (status.st_ino, status.st_mtime_ns, digest)
    return entries


def scenario_for(replica: Replica, *, base: str, head: str, earlier: str) -> dict[str, Any]:
    """``gh`` answers for pull request 1 of *replica*: open, based on ``trunk``."""

    parts = _substitute(
        recorded_responses(), {"@HEAD@": head, "@BASE@": base, "@EARLIER@": earlier}
    )
    parts = copy.deepcopy(parts)
    parts["pull"].update(
        number=1,
        title="Add p",
        html_url=f"{CANONICAL}/pull/1",
        base={"ref": "trunk", "sha": base, "repo": {"full_name": "octo/demo"}},
        head={"ref": "pr", "sha": head, "repo": {"full_name": "octo/demo"}},
    )
    root = "repos/octo/demo"
    paths = {
        f"{root}/pulls/1": parts["pull"],
        page(f"{root}/issues/1/comments"): parts["issue_comments"],
        page(f"{root}/pulls/1/reviews"): parts["reviews"],
        page(f"{root}/pulls/1/comments"): parts["review_comments"],
        page(f"{root}/commits/{head}/check-runs"): parts["check_runs"],
        page(f"{root}/commits/{head}/status"): parts["status"],
    }
    return {
        "auth": account(),
        "api": {path: ok(path, body) for path, body in paths.items()},
        "api_failure": None,
    }


@contextlib.contextmanager
def _seams(replica: Replica) -> Generator[None]:
    """The in-process goldens' own: the origin URL, the Git floor, and both clocks."""

    from metabrowser.builtin_plugins.github import pulls
    from metabrowser.cache import acquire
    from metabrowser.cache.urls import GitSource

    def remote_url_for(source: GitSource) -> str:
        return replica.url if source.normalized == CANONICAL else source.normalized

    saved = (
        acquire.remote_url_for,
        acquire.require_acquisition_git,
        acquire.canonical_now,
        pulls.utc_now,
    )
    acquire.remote_url_for = remote_url_for
    # A store records the Git that acquired it, and a transcript prints the record.
    acquire.require_acquisition_git = lambda: _RECORDED_GIT  # pyright: ignore[reportAttributeAccessIssue]
    acquire.canonical_now = lambda: FETCHED_AT.strftime("%Y-%m-%dT%H:%M:%SZ")
    pulls.utc_now = lambda: FETCHED_AT
    try:
        yield
    finally:
        (
            acquire.remote_url_for,
            acquire.require_acquisition_git,
            acquire.canonical_now,
            pulls.utc_now,
        ) = saved


def _cli(arguments: list[str]) -> None:
    from metabrowser.cli.main import _run_cli  # pyright: ignore[reportPrivateUsage]

    try:
        _run_cli(arguments)
    except SystemExit as exc:
        if exc.code not in (0, None):
            raise


def build_homes(directory: Path) -> None:
    """The homes a transcript reads; see the module."""

    replica = build_linear(directory / "linear")
    gh = directory / "gh"
    gh.mkdir()
    answers = scenario_for(replica, base=replica["M5"], head=replica["H1"], earlier=replica["M4"])
    os.environ.update(install_fake_gh(gh, answers))
    os.environ["METABROWSER_LOG_LEVEL"] = "ERROR"
    pull = f"{CANONICAL}/pull/1"
    checkout = clone_checkout(replica, directory / "checkout")
    worktree = directory / "feature-x"
    pinned_git(checkout, "worktree", "add", "-q", "-b", "feature-x", str(worktree))
    pinned_git(checkout, "pack-refs", "--all")
    other = clone_checkout(replica, directory / "other")
    with _seams(replica):
        os.environ["METABROWSER_CACHE_DIR"] = str(directory / "home")
        _cli([pull, "--checkout", str(worktree), "--no-serve"])
        os.environ["METABROWSER_CACHE_DIR"] = str(directory / "home-moved")
        _cli([pull, "--checkout", str(other), "--no-serve"])
        shutil.move(other, directory / "moved")
        os.environ["METABROWSER_CACHE_DIR"] = str(directory / "home-damaged")
        _cli([pull, "--checkout", str(checkout), "--no-serve"])
    for store in (directory / "home-damaged" / "repository-stores").iterdir():
        (store / "repository.git" / "objects" / "info" / "alternates").write_text(
            f"{directory}/elsewhere/objects\n", encoding="utf-8"
        )
    heavy = build_merge_heavy(directory / "heavy")
    shallow = clone_checkout(heavy, directory / "shallow", "--depth", "3", "--no-single-branch")
    answers = scenario_for(heavy, base=heavy["M7"], head=heavy["H2"], earlier=heavy["H1"])
    os.environ.update(install_fake_gh(gh, answers))
    from metabrowser.cache import pull_refs

    rounds = pull_refs.DEEPEN_ROUNDS
    pull_refs.DEEPEN_ROUNDS = ()  # pyright: ignore[reportAttributeAccessIssue]
    try:
        with _seams(heavy):
            os.environ["METABROWSER_CACHE_DIR"] = str(directory / "home-shallow")
            _cli([pull, "--checkout", str(shallow), "--no-serve"])
    finally:
        pull_refs.DEEPEN_ROUNDS = rounds  # pyright: ignore[reportAttributeAccessIssue]
    (directory / "root").mkdir(exist_ok=True)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: checkout_replica.py <directory>")
    build_homes(Path(sys.argv[1]).resolve())
