"""An overlay store: serving a pull request by borrowing a named checkout's objects.

Each test holds one rule of ``plan-2026-11-02-pr-review-mirror-and-checkout.md`` through the
production CLI path, on a replica from ``tests/checkout_replica.py``: never a silently wrong
merge base, refs that are only what the origin sent, a working directory that never lends,
nothing written to the checkout and no Git run in it, the refusals, the sweep, and a checkout
that has gone. Nothing reaches the network: ``remote_url_for`` fetches from a local origin
and a fake ``gh`` answers for the pull request.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import stat
import subprocess
import threading
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient

from metabrowser import server
from metabrowser.builtin_plugins.diff import sidekick
from metabrowser.builtin_plugins.diff.comparison_cache import ComparisonCache
from metabrowser.cache import pull_refs
from metabrowser.cache.acquire import acquire_source
from metabrowser.cache.identity import repository_store_id, source_identity, store_key
from metabrowser.cache.lender import (
    CheckoutRefusedError,
    Lender,
    LenderRefusal,
    check_lender,
    negotiation_tips,
    own_boundary,
    suggested_checkout,
)
from metabrowser.cache.paths import store_directory
from metabrowser.cache.records import StoreLender
from metabrowser.cache.update import RefreshOutcome, update_store
from metabrowser.cache.urls import GitSource
from metabrowser.capabilities import apply_capabilities
from metabrowser.git import process as git_process
from metabrowser.git.tree_source import GitPath
from metabrowser.repository_context import discover_repository_context, read_bounded_text
from tests.checkout_replica import (
    REMOTE_SPELLING,
    Replica,
    build_linear,
    build_merge_heavy,
    clone_checkout,
    fingerprint,
    scenario_for,
)
from tests.github_pull_fixture import CANONICAL, FETCHED_AT, install_fake_gh
from tests.golden_harness import (
    Invocation,
    isolate_cli,
    ok,
    pinned_git,
    pinned_git_env,
    refused,
    run_metab,
    serve_published,
    settle,
)
from tests.required_tools import needs_git

pytestmark = [
    needs_git,
    pytest.mark.skipif(os.name != "posix", reason="borrowing needs POSIX links and FIFOs"),
]

PULL = f"{CANONICAL}/pull/1"
SOURCE = GitSource(transport="https", form="url", normalized=CANONICAL)
STATUS = "/api/source/status"
PULL_ROUTE = "/api/plugin/github/pull?number=1"
FIFO_SECONDS = 20.0


@dataclass
class _Stand:
    tmp_path: Path
    home: Path
    monkeypatch: pytest.MonkeyPatch
    replica: Replica

    @property
    def store(self) -> Path:
        identity = repository_store_id(source_identity("https", CANONICAL), "sha1")
        return self.home / store_directory(store_key(identity)) / "repository.git"

    def store_git(self, *args: str) -> str:
        return pinned_git(self.store, *args)

    def store_refs(self) -> dict[str, str]:
        listed = self.store_git("for-each-ref", "--format=%(refname) %(objectname)")
        return dict(line.split(" ", 1) for line in listed.splitlines())

    def answer(self, answers: dict[str, Any]) -> None:
        for name, value in install_fake_gh(self.tmp_path / "gh", answers).items():
            self.monkeypatch.setenv(name, value)

    def pull(self, *flags: str) -> dict[str, Any]:
        result = ok([PULL, *flags, "--api", PULL_ROUTE])
        return result.payload()


def _stand(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replica: Replica,
    *,
    base: str,
    head: str,
    earlier: str,
) -> _Stand:
    home = isolate_cli(tmp_path, monkeypatch).home

    def remote_url_for(source: GitSource) -> str:
        return replica.url if source.normalized == CANONICAL else source.normalized

    monkeypatch.setattr("metabrowser.cache.acquire.remote_url_for", remote_url_for)
    monkeypatch.setattr("metabrowser.builtin_plugins.github.pulls.utc_now", lambda: FETCHED_AT)
    stand = _Stand(tmp_path, home, monkeypatch, replica)
    (tmp_path / "gh").mkdir()
    stand.answer(scenario_for(replica, base=base, head=head, earlier=earlier))
    return stand


@pytest.fixture
def merge_heavy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> _Stand:
    replica = build_merge_heavy(tmp_path / "replica")
    return _stand(
        tmp_path,
        monkeypatch,
        replica,
        base=replica["M7"],
        head=replica["H2"],
        earlier=replica["H1"],
    )


@pytest.fixture
def linear(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> _Stand:
    replica = build_linear(tmp_path / "replica")
    return _stand(
        tmp_path,
        monkeypatch,
        replica,
        base=replica["M5"],
        head=replica["H1"],
        earlier=replica["M4"],
    )


def _no_deepening(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pull_refs, "DEEPEN_ROUNDS", ())


def _changed_paths(result: Invocation) -> set[str]:
    return {
        (change.get("new") or change.get("old"))["path"]
        for change in result.payload()["manifest"]["files"]
    }


def _names(replica: Replica, oid: str | None) -> str | None:
    return next((name for name, value in replica.commits.items() if value == oid), oid)


# ── No silent wrongness ─────────────────────────────────────────────


def test_without_the_certainty_check_the_replica_answers_the_wrong_merge_base(
    merge_heavy: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The fixture holds the bug the check is for: with the boundary unread, A1 is served."""

    monkeypatch.setattr("metabrowser.git.shallow.read_boundary", lambda _git_dir: frozenset())
    checkout = clone_checkout(
        merge_heavy.replica, merge_heavy.tmp_path / "checkout", "--depth", "3", "--no-single-branch"
    )
    envelope = merge_heavy.pull("--checkout", str(checkout))
    assert _names(merge_heavy.replica, envelope["record"]["comparison"]["base"]) == "A1"


def test_a_merge_heavy_depth_3_checkout_is_never_served_the_wrong_merge_base(
    merge_heavy: _Stand,
) -> None:
    replica = merge_heavy.replica
    checkout = clone_checkout(
        replica, merge_heavy.tmp_path / "checkout", "--depth", "3", "--no-single-branch"
    )
    envelope = merge_heavy.pull("--checkout", str(checkout))

    # Deepened in the store, within the job: certain at A4, and the true Files changed.
    assert _names(replica, envelope["record"]["comparison"]["base"]) == "A4"
    assert envelope["record"]["unavailable"] == {}
    compared = ok([PULL, "--api", envelope["comparison_route"]])
    assert _changed_paths(compared) == {"p"}
    # The link was replaced before Git could write through it.
    assert not (merge_heavy.store / "shallow").is_symlink()


def test_an_uncertain_merge_base_reads_base_uncertain_and_shows_no_files_changed(
    merge_heavy: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    _no_deepening(monkeypatch)
    replica = merge_heavy.replica
    checkout = clone_checkout(
        replica, merge_heavy.tmp_path / "checkout", "--depth", "3", "--no-single-branch"
    )
    envelope = merge_heavy.pull("--checkout", str(checkout))
    record = envelope["record"]
    assert record["comparison"] is None
    assert record["unavailable"] == {"comparison": "base_uncertain"}
    assert envelope["comparison_route"] is None
    # The rest of the record stands.
    assert record["pull"]["title"] == "Add p"
    assert replica["A1"] not in json.dumps(record)
    # The boundary is still the checkout's: nothing owned it, since nothing deepened.
    assert (merge_heavy.store / "shallow").is_symlink()


def test_offline_an_uncertain_merge_base_stays_typed_and_no_guess_is_shown(
    merge_heavy: _Stand,
) -> None:
    replica = merge_heavy.replica
    checkout = clone_checkout(
        replica, merge_heavy.tmp_path / "checkout", "--depth", "3", "--no-single-branch"
    )
    ok([CANONICAL, "--checkout", str(checkout), "--no-serve"])
    # The pull request's head is fetched with the origin there, and then the network goes.
    real_fetch = pull_refs.fetch_into_store

    async def offline_once_deepening(
        published: Any,
        specs: list[str],
        *,
        deepen: int | None = None,
        timeout_s: float | None = None,
    ) -> None:
        if deepen is not None:
            raise git_process.GitCommandError(["fetch"], 128, "unable to access")
        await real_fetch(published, specs, deepen=deepen, timeout_s=timeout_s)

    merge_heavy.monkeypatch.setattr(pull_refs, "fetch_into_store", offline_once_deepening)
    envelope = merge_heavy.pull()
    assert envelope["record"]["comparison"] is None
    assert envelope["record"]["unavailable"] == {"comparison": "base_uncertain"}
    # Read again with nothing to fetch: the same answer, from the record.
    assert merge_heavy.pull()["record"]["unavailable"] == {"comparison": "base_uncertain"}


def test_a_depth_1_checkout_has_an_empty_answer_that_is_uncertain_then_certain(
    merge_heavy: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    replica = merge_heavy.replica
    checkout = clone_checkout(
        replica, merge_heavy.tmp_path / "checkout", "--depth", "1", "--no-single-branch"
    )
    rounds: list[int | None] = []
    real_fetch = pull_refs.fetch_into_store

    async def counted(published: Any, specs: list[str], **kwargs: Any) -> None:
        rounds.append(kwargs.get("deepen"))
        await real_fetch(published, specs, **kwargs)

    monkeypatch.setattr(pull_refs, "fetch_into_store", counted)
    envelope = merge_heavy.pull("--checkout", str(checkout))
    assert _names(replica, envelope["record"]["comparison"]["base"]) == "A4"
    assert [depth for depth in rounds if depth is not None] == list(
        pull_refs.DEEPEN_ROUNDS[: len([depth for depth in rounds if depth is not None])]
    )
    assert any(depth is not None for depth in rounds)
    assert _changed_paths(ok([PULL, "--api", envelope["comparison_route"]])) == {"p"}


def test_a_deepened_lender_settles_the_answer_with_no_fetch(
    merge_heavy: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The live boundary: the checkout's own fetch is seen at once, through the link."""

    _no_deepening(monkeypatch)
    replica = merge_heavy.replica
    checkout = clone_checkout(
        replica, merge_heavy.tmp_path / "checkout", "--depth", "3", "--no-single-branch"
    )
    assert merge_heavy.pull("--checkout", str(checkout))["record"]["comparison"] is None
    pinned_git(checkout, "remote", "set-url", "origin", replica.url)
    pinned_git(checkout, "fetch", "-q", "--deepen=10", "origin")
    pinned_git(checkout, "remote", "set-url", "origin", REMOTE_SPELLING)
    envelope = ok([PULL, "--no-serve"])
    assert envelope.exit_code == 0
    assert merge_heavy.pull()["record"]["comparison"]["base"] == replica["A4"]
    assert (merge_heavy.store / "shallow").is_symlink()


@pytest.mark.parametrize(
    ("boundary", "certain"),
    [("M2", True), ("M5", False)],
    ids=["below-the-merge-base-is-right", "above-it-is-uncertain"],
)
def test_a_crafted_boundary_cannot_make_a_wrong_answer_certain(
    linear: _Stand, monkeypatch: pytest.MonkeyPatch, boundary: str, certain: bool
) -> None:
    _no_deepening(monkeypatch)
    replica = linear.replica
    checkout = clone_checkout(replica, linear.tmp_path / "checkout")
    (checkout / ".git" / "shallow").write_text(replica[boundary] + "\n", encoding="utf-8")
    record = linear.pull("--checkout", str(checkout))["record"]
    if certain:
        assert record["comparison"]["base"] == replica["M4"]
    else:
        assert record["comparison"] is None
        assert record["unavailable"] == {"comparison": "base_uncertain"}


def test_an_answer_that_is_a_tip_is_certain_whatever_the_boundary_says(linear: _Stand) -> None:
    """M4 is an ancestor of the head with a boundary beside it: no ancestor can be lower."""

    replica = linear.replica
    side = linear.tmp_path / "side"
    pinned_git(replica.origin, "worktree", "add", "-q", "--detach", str(side), replica["M4"])
    (side / "s").write_text("s\n", encoding="utf-8")
    pinned_git(side, "add", "s")
    pinned_git(side, "commit", "-qm", "S1")
    s1 = pinned_git(side, "rev-parse", "HEAD")
    pinned_git(side, "merge", "-q", "--no-ff", "-m", "merge", replica["H1"])
    tip = pinned_git(side, "rev-parse", "HEAD")
    pinned_git(replica.origin, "update-ref", "refs/heads/side", tip)
    checkout = clone_checkout(replica, linear.tmp_path / "checkout")
    (checkout / ".git" / "shallow").write_text(s1 + "\n", encoding="utf-8")
    ok([CANONICAL, "--checkout", str(checkout), "--no-serve"])
    answered = ok(
        [
            CANONICAL,
            "--api",
            f"/api/plugin/diff/comparison?left={replica['H1']}&right={tip}&base_policy=merge_base",
        ]
    )
    assert answered.payload()["resolved"]["left"]["id"] == replica["H1"]


def test_the_comparison_route_refuses_an_uncertain_merge_base_too(
    merge_heavy: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Asked for the tips directly, as the page never does, it does not guess either."""

    _no_deepening(monkeypatch)
    replica = merge_heavy.replica
    checkout = clone_checkout(
        replica, merge_heavy.tmp_path / "checkout", "--depth", "3", "--no-single-branch"
    )
    merge_heavy.pull("--checkout", str(checkout))
    answered = run_metab(
        [
            PULL,
            "--api",
            f"/api/plugin/diff/comparison?left={replica['M7']}&right={replica['H2']}"
            "&base_policy=merge_base",
        ]
    )
    assert answered.exit_code != 0 or "base_uncertain" in answered.stdout
    assert "base_uncertain" in answered.stdout + answered.stderr
    assert replica["A1"] not in answered.stdout


# ── The store's refs are only what the origin sent ──────────────────


def _planted(stand: _Stand) -> tuple[Path, str]:
    """A checkout naming the victim's URL with an attacker's commit, branch, and tag."""

    checkout = clone_checkout(stand.replica, stand.tmp_path / "planted")
    (checkout / "x").write_text("x\n", encoding="utf-8")
    pinned_git(checkout, "add", "x")
    pinned_git(checkout, "commit", "-qm", "ATTACKER COMMIT")
    attacker = pinned_git(checkout, "rev-parse", "HEAD")
    pinned_git(checkout, "update-ref", "refs/remotes/origin/release-2.0", attacker)
    pinned_git(checkout, "update-ref", "refs/remotes/origin/trunk", attacker)
    pinned_git(checkout, "tag", "v9.9", attacker)
    return checkout, attacker


def test_a_named_checkouts_planted_refs_are_never_served(linear: _Stand) -> None:
    replica = linear.replica
    checkout, attacker = _planted(linear)
    served = ok([CANONICAL, "--checkout", str(checkout), "--api", "/api/source/refs?kind=branch"])
    names = {row["name"]: row["commit"] for row in served.payload()["refs"]}
    assert names == {"trunk": replica["M5"]}
    tags = ok([CANONICAL, "--api", "/api/source/refs?kind=tag"]).payload()["refs"]
    assert tags == []
    assert linear.store_refs() == {"refs/remotes/origin/trunk": replica["M5"]}
    assert attacker not in linear.store_refs().values()
    # A refresh is the mirror's own fetch, with the same tips, and adds nothing of theirs.
    assert ok([PULL, "--no-serve"]).exit_code == 0
    assert set(linear.store_refs()) == {"refs/remotes/origin/trunk", "refs/pull/1/head"}


def test_tips_are_read_from_files_loose_over_packed_and_only_the_matching_remote(
    tmp_path: Path,
) -> None:
    common = tmp_path / "repo" / ".git"
    (common / "refs" / "remotes" / "upstream" / "feature").mkdir(parents=True)
    (common / "refs" / "remotes" / "origin").mkdir(parents=True)
    a, b, c, d = "a" * 40, "b" * 40, "c" * 40, "d" * 40
    (common / "packed-refs").write_text(
        "# pack-refs with: peeled fully-peeled sorted\n"
        f"{a} refs/remotes/upstream/trunk\n^{d}\n"
        f"{b} refs/remotes/origin/mine\n"
        f"{c} refs/remotes/upstream/old\n",
        encoding="utf-8",
    )
    (common / "refs" / "remotes" / "upstream" / "old").write_text(d + "\n", encoding="utf-8")
    (common / "refs" / "remotes" / "upstream" / "HEAD").write_text(
        "ref: refs/remotes/upstream/trunk\n", encoding="utf-8"
    )
    os.mkfifo(common / "refs" / "remotes" / "upstream" / "feature" / "fifo")
    lender = StoreLender(objects=str(common / "objects"), checkout=str(tmp_path), remote="upstream")
    assert negotiation_tips(lender, preferred="trunk") == (a, d)
    assert negotiation_tips(lender, preferred="old") == (d, a)


def test_a_fork_lends_through_the_remote_that_is_the_repository(linear: _Stand) -> None:
    checkout = clone_checkout(linear.replica, linear.tmp_path / "fork")
    pinned_git(checkout, "remote", "rename", "origin", "upstream")
    pinned_git(checkout, "remote", "add", "origin", "https://github.com/forker/demo.git")
    checked = check_lender(checkout, SOURCE)
    assert isinstance(checked, Lender) and checked.remote == "upstream"


def test_the_remote_match_uses_the_providers_grammar_and_ignores_case(linear: _Stand) -> None:
    checkout = clone_checkout(linear.replica, linear.tmp_path / "spelled")
    for spelling in (
        "git@github.com:OCTO/Demo.git",
        "ssh://git@github.com/octo/demo",
        "https://user:secret@github.com/octo/demo.git",
    ):
        pinned_git(checkout, "remote", "set-url", "origin", spelling)
        assert isinstance(check_lender(checkout, SOURCE), Lender), spelling


def test_a_fetch_negotiates_from_the_matching_remote_and_only_what_the_store_can_read(
    linear: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A fork's own branch is no tip, and one the checkout lost would make Git refuse."""

    replica = linear.replica
    trace = linear.tmp_path / "git-trace"
    real = git_process.git_environment

    def traced(policy: Any = None, **kwargs: Any) -> dict[str, str]:
        return {**real(policy, **kwargs), "GIT_TRACE": str(trace)}

    monkeypatch.setattr(git_process, "git_environment", traced)
    checkout = clone_checkout(replica, linear.tmp_path / "fork")
    pinned_git(checkout, "remote", "rename", "origin", "upstream")
    pinned_git(checkout, "remote", "add", "origin", "https://github.com/forker/demo.git")
    (checkout / "mine").write_text("mine\n", encoding="utf-8")
    pinned_git(checkout, "add", "mine")
    pinned_git(checkout, "commit", "-qm", "the fork's own")
    own = pinned_git(checkout, "rev-parse", "HEAD")
    pinned_git(checkout, "update-ref", "refs/remotes/origin/mine", own)
    lost = "1" * 40
    (checkout / ".git" / "refs" / "remotes" / "upstream" / "lost").write_text(
        lost + "\n", encoding="utf-8"
    )
    # A tip that is no commit, such as a tag of a tree, is no use to Git either.
    blob = pinned_git(checkout, "rev-parse", f"{replica['M1']}:m")
    (checkout / ".git" / "refs" / "remotes" / "upstream" / "blob").write_text(
        blob + "\n", encoding="utf-8"
    )
    ok([CANONICAL, "--checkout", str(checkout), "--no-serve"])
    fetches = [
        line
        for line in trace.read_text(encoding="utf-8").splitlines()
        if "--negotiation-tip" in line
    ]
    assert fetches
    assert f"--negotiation-tip={replica['M5']}" in fetches[0]
    for absent in (own, lost, blob):
        assert absent not in fetches[0]
    # The store itself is the origin's, whatever the fork holds.
    assert linear.store_refs() == {"refs/remotes/origin/trunk": replica["M5"]}


def test_a_long_list_of_tips_is_cut_and_keeps_the_default_branch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    common = tmp_path / "repo" / ".git"
    common.mkdir(parents=True)
    main = "f" * 40
    lines = [f"{index:040x} refs/remotes/origin/b{index:05}" for index in range(1, 8)]
    lines.append(f"{main} refs/remotes/origin/zzz-main")
    (common / "packed-refs").write_text("\n".join(lines) + "\n", encoding="utf-8")
    monkeypatch.setattr("metabrowser.cache.lender.MAX_NEGOTIATION_TIPS", 3)
    lender = StoreLender(objects=str(common / "objects"), checkout=str(tmp_path), remote="origin")
    tips = negotiation_tips(lender, preferred="zzz-main")
    assert len(tips) == 3 and tips[0] == main


def test_a_checkout_of_another_repository_is_refused_and_says_what_it_found(
    linear: _Stand,
) -> None:
    checkout = clone_checkout(linear.replica, linear.tmp_path / "other")
    pinned_git(checkout, "remote", "set-url", "origin", "https://user:secret@github.com/a/b.git")
    result = refused([PULL, "--checkout", str(checkout), "--api", STATUS])
    assert "is not a checkout of https://github.com/octo/demo" in result.error
    assert "origin is https://github.com/a/b" in result.error
    assert "secret" not in result.stderr
    assert not linear.home.exists() or not linear.store.exists()


# ── The working directory never lends ───────────────────────────────


def test_the_working_directory_never_lends_and_says_so_once(
    linear: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    checkout, _attacker = _planted(linear)
    below = checkout / "deep" / "below"
    below.mkdir(parents=True)
    monkeypatch.chdir(below)

    first = ok([PULL, "--api", STATUS])
    assert first.payload()["borrows"] is None
    assert first.stderr.count("--checkout") == 1
    assert f"--checkout {checkout.resolve()}" in first.stderr
    store = linear.store
    assert not (store / "objects" / "info" / "alternates").exists()
    assert "lender" not in (store.parent / "store.yml").read_text(encoding="utf-8")
    # Only the origin's refs, and a full store: its own objects answer with the checkout gone.
    assert "refs/remotes/origin/release-2.0" not in linear.store_refs()
    second = ok([PULL, "--api", STATUS])
    assert "--checkout" not in second.stderr


def test_a_planted_git_file_pointing_elsewhere_lends_nothing(
    linear: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    checkout, _attacker = _planted(linear)
    stand_here = linear.tmp_path / "planted-file"
    stand_here.mkdir()
    (stand_here / ".git").write_text(f"gitdir: {checkout / '.git'}\n", encoding="utf-8")
    monkeypatch.chdir(stand_here)
    assert ok([CANONICAL, "--api", STATUS]).payload()["borrows"] is None
    assert not (linear.store / "objects" / "info" / "alternates").exists()


def test_no_suggestion_outside_a_checkout_of_the_repository(tmp_path: Path) -> None:
    assert suggested_checkout(SOURCE, tmp_path) is None
    repository = tmp_path / "elsewhere"
    repository.mkdir()
    pinned_git(repository, "init", "-q")
    pinned_git(repository, "remote", "add", "origin", "https://github.com/a/b")
    assert suggested_checkout(SOURCE, repository) is None


def test_a_full_mirror_is_kept_when_a_checkout_is_named_afterwards(linear: _Stand) -> None:
    checkout = clone_checkout(linear.replica, linear.tmp_path / "checkout")
    ok([CANONICAL, "--no-serve"])
    named = ok([CANONICAL, "--checkout", str(checkout), "--api", STATUS])
    assert named.payload()["borrows"] is None
    assert "it is kept" in named.stderr
    assert not (linear.store / "objects" / "info" / "alternates").exists()


def test_a_healthy_overlay_keeps_its_checkout_when_another_is_named(linear: _Stand) -> None:
    checkout = clone_checkout(linear.replica, linear.tmp_path / "checkout")
    other = clone_checkout(linear.replica, linear.tmp_path / "other")
    ok([CANONICAL, "--checkout", str(checkout), "--no-serve"])
    named = ok([CANONICAL, "--checkout", str(other), "--api", STATUS])
    assert named.payload()["borrows"] == str(checkout.resolve())
    assert "--checkout changed nothing" in named.stderr


def test_checkout_is_refused_on_a_folder(tmp_path: Path) -> None:
    result = refused([str(tmp_path), "--checkout", str(tmp_path), "--api", STATUS])
    assert "--checkout names a checkout" in result.error


# ── Nothing writes to the checkout ──────────────────────────────────


def _read_only(checkout: Path) -> Callable[[], None]:
    """Take write permission away from the Git directory; the returned call restores it."""

    git_dir = checkout / ".git"
    modes: list[tuple[Path, int]] = []
    for directory, subdirectories, files in os.walk(git_dir):
        for name in (*subdirectories, *files):
            path = Path(directory) / name
            modes.append((path, stat.S_IMODE(os.lstat(path).st_mode)))
    modes.append((git_dir, stat.S_IMODE(os.lstat(git_dir).st_mode)))
    for path, mode in modes:
        path.chmod(mode & ~0o222)

    def restore() -> None:
        for path, mode in reversed(modes):
            path.chmod(mode)

    return restore


def test_nothing_writes_to_the_checkout_from_acquisition_to_deepening(
    merge_heavy: _Stand,
) -> None:
    replica = merge_heavy.replica
    checkout = clone_checkout(
        replica, merge_heavy.tmp_path / "checkout", "--depth", "3", "--no-single-branch"
    )
    before = fingerprint(checkout)
    for name in ("shallow", "config", "packed-refs"):
        assert name in before
    assert any(entry.startswith("objects/") for entry in before)
    restore = _read_only(checkout)
    try:
        before = fingerprint(checkout)
        envelope = merge_heavy.pull("--checkout", str(checkout))
        assert envelope["record"]["comparison"]["base"] == replica["A4"]
        ok([PULL, "--no-serve"])
        ok([PULL, "--api", envelope["comparison_route"]])
        ok([PULL, "--show", "p"])
        outcome = asyncio.run(
            update_store(merge_heavy.home, merge_heavy.store.parent.name, remote_url=replica.url)
        )
        assert outcome.outcome is RefreshOutcome.succeeded
        assert fingerprint(checkout) == before
    finally:
        restore()


def test_deepening_never_writes_through_the_link_to_the_checkouts_boundary(
    merge_heavy: _Stand,
) -> None:
    """With the link in place Git would replace the checkout's file: own_boundary stops that."""

    replica = merge_heavy.replica
    checkout = clone_checkout(
        replica, merge_heavy.tmp_path / "checkout", "--depth", "3", "--no-single-branch"
    )
    boundary = checkout / ".git" / "shallow"
    inode = boundary.stat().st_ino
    text = boundary.read_text(encoding="utf-8")
    merge_heavy.pull("--checkout", str(checkout))
    store_boundary = merge_heavy.store / "shallow"
    assert store_boundary.is_file() and not store_boundary.is_symlink()
    assert store_boundary.read_text(encoding="utf-8") != text
    assert (boundary.stat().st_ino, boundary.read_text(encoding="utf-8")) == (inode, text)
    assert not (checkout / ".git" / "shallow.lock").exists()


def test_own_boundary_removes_a_dangling_link_rather_than_leave_git_to_follow_it(
    tmp_path: Path,
) -> None:
    store = tmp_path / "store"
    store.mkdir()
    (store / "shallow").symlink_to(tmp_path / "gone" / "shallow")
    own_boundary(store)
    assert not os.path.lexists(store / "shallow")


def test_a_boundary_that_cannot_be_copied_stops_the_deepening(tmp_path: Path) -> None:
    store = tmp_path / "store"
    store.mkdir()
    fifo = tmp_path / "fifo"
    os.mkfifo(fifo)
    (store / "shallow").symlink_to(fifo)
    with pytest.raises(OSError, match="could not be copied"):
        own_boundary(store)
    assert (store / "shallow").is_symlink()


def _hostile_configuration(checkout: Path, marker: Path) -> None:
    script = checkout.parent / "marker.sh"
    script.write_text(f'#!/bin/sh\necho "$0 $*" >> "{marker}"\nexit 1\n', encoding="utf-8")
    script.chmod(0o755)
    hooks = checkout.parent / "planted-hooks"
    hooks.mkdir()
    for hook in ("pre-commit", "post-checkout", "post-merge", "reference-transaction", "pre-push"):
        (hooks / hook).symlink_to(script)
        (checkout / ".git" / "hooks").mkdir(exist_ok=True)
        (checkout / ".git" / "hooks" / hook).symlink_to(script)
    for key, value in (
        ("core.hooksPath", str(hooks)),
        ("core.fsmonitor", str(script)),
        ("core.sshCommand", str(script)),
        ("diff.external", str(script)),
        ("diff.textconv", str(script)),
        ("core.pager", str(script)),
        ("uploadpack.packObjectsHook", str(script)),
        ("core.alternateRefsCommand", str(script)),
        ("credential.helper", f"!{script}"),
    ):
        pinned_git(checkout, "config", key, value)
    (checkout / ".gitattributes").write_text("p diff=planted\n", encoding="utf-8")
    pinned_git(checkout, "config", "diff.planted.textconv", str(script))
    pinned_git(checkout, "config", "diff.planted.command", str(script))


def test_a_hostile_checkout_configuration_runs_nothing(merge_heavy: _Stand) -> None:
    replica = merge_heavy.replica
    checkout = clone_checkout(
        replica, merge_heavy.tmp_path / "checkout", "--depth", "3", "--no-single-branch"
    )
    marker = merge_heavy.tmp_path / "marker"
    _hostile_configuration(checkout, marker)
    envelope = merge_heavy.pull("--checkout", str(checkout))
    ok([PULL, "--api", envelope["comparison_route"]])
    ok([PULL, "--show", "p"])
    ok([PULL, "--no-serve"])
    assert not marker.exists(), marker.read_text(encoding="utf-8")


def test_no_git_process_runs_with_the_checkout_as_its_repository(
    merge_heavy: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Git's own trace of every command it runs, children included, never names the checkout."""

    trace = merge_heavy.tmp_path / "git-trace"
    real = git_process.git_environment

    def traced(policy: Any = None, **kwargs: Any) -> dict[str, str]:
        return {**real(policy, **kwargs), "GIT_TRACE": str(trace)}

    monkeypatch.setattr(git_process, "git_environment", traced)
    checkout = clone_checkout(
        merge_heavy.replica, merge_heavy.tmp_path / "checkout", "--depth", "3", "--no-single-branch"
    )
    envelope = merge_heavy.pull("--checkout", str(checkout))
    ok([PULL, "--api", envelope["comparison_route"]])
    ok([PULL, "--no-serve"])
    lines = trace.read_text(encoding="utf-8").splitlines()
    assert any("fetch" in line for line in lines)
    named = [line for line in lines if "built-in: git" in line or "run_command: " in line]
    assert named
    # Git's trace of a child's argv, and the store's own alternate-refs no-op is ``true``.
    assert not [line for line in named if str(checkout.resolve()) in line and "true" not in line]


def _common_git_dir(checkout: Path) -> Path:
    return checkout / ".git"


@pytest.mark.parametrize(
    ("spoil", "code"),
    [
        (
            lambda c: pinned_git(c, "config", "extensions.partialClone", "origin"),
            "partial_clone",
        ),
        (lambda c: pinned_git(c, "config", "remote.origin.promisor", "true"), "partial_clone"),
        (
            lambda c: (_common_git_dir(c) / "objects" / "pack" / "pack-x.promisor").write_text(""),
            "partial_clone",
        ),
        (
            lambda c: (_common_git_dir(c) / "objects" / "info" / "alternates").write_text(
                "/elsewhere\n"
            ),
            "own_alternates",
        ),
    ],
    ids=["extensions-partialclone", "remote-promisor", "promisor-pack", "own-alternates"],
)
def test_a_lender_that_cannot_lend_falls_to_a_full_clone_and_says_why(
    linear: _Stand, spoil: Callable[[Path], object], code: str
) -> None:
    checkout = clone_checkout(linear.replica, linear.tmp_path / "checkout")
    spoil(checkout)
    checked = check_lender(checkout, SOURCE)
    assert isinstance(checked, LenderRefusal) and checked.code == code
    result = ok([PULL, "--checkout", str(checkout), "--api", STATUS])
    assert result.payload()["borrows"] is None
    assert f"{checked.message}; cloning" in result.stderr
    assert not (linear.store / "objects" / "info" / "alternates").exists()


def test_a_lender_of_another_object_format_falls_to_a_full_clone(linear: _Stand) -> None:
    checkout = clone_checkout(linear.replica, linear.tmp_path / "checkout")
    pinned_git(checkout, "config", "extensions.objectFormat", "sha256")
    result = ok([PULL, "--checkout", str(checkout), "--api", STATUS])
    assert result.payload()["borrows"] is None
    assert "the checkout's objects are sha256 and the origin's are sha1; cloning" in result.stderr


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads everything")
def test_objects_that_cannot_be_read_fall_to_a_full_clone(linear: _Stand) -> None:
    checkout = clone_checkout(linear.replica, linear.tmp_path / "checkout")
    objects = _common_git_dir(checkout) / "objects"
    objects.chmod(0o000)
    try:
        checked = check_lender(checkout, SOURCE)
    finally:
        objects.chmod(0o755)
    assert isinstance(checked, LenderRefusal) and checked.code == "objects_unreadable"


def test_a_path_that_is_no_checkout_is_refused(linear: _Stand) -> None:
    empty = linear.tmp_path / "empty"
    empty.mkdir()
    result = refused([PULL, "--checkout", str(empty), "--api", STATUS])
    assert "is not a Git checkout" in result.error
    with pytest.raises(CheckoutRefusedError):
        check_lender(linear.tmp_path / "absent", SOURCE)


def test_a_path_holding_a_newline_cannot_be_borrowed_through(linear: _Stand) -> None:
    checkout = clone_checkout(linear.replica, linear.tmp_path / "line\nbreak")
    checked = check_lender(checkout, SOURCE)
    assert isinstance(checked, LenderRefusal) and checked.code == "path_not_recordable"


def _within(seconds: float, work: Callable[[], object]) -> object:
    """*work*'s answer, or a failure when it blocks: a daemon thread cannot hang the run."""

    answer: list[object] = []
    thread = threading.Thread(target=lambda: answer.append(work()), daemon=True)
    thread.start()
    thread.join(seconds)
    assert not thread.is_alive(), "a read blocked on a FIFO"
    return answer[0] if answer else None


def _fifo_at(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink(missing_ok=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    os.mkfifo(path)


@pytest.mark.parametrize(
    "where",
    ["config", "HEAD", "packed-refs", "shallow", "refs/remotes/origin/trunk", "commondir"],
)
def test_a_fifo_in_the_checkout_blocks_nothing(linear: _Stand, where: str) -> None:
    checkout = clone_checkout(linear.replica, linear.tmp_path / "checkout")
    pinned_git(checkout, "pack-refs", "--all")
    _fifo_at(checkout / ".git" / where)

    def discover() -> object:
        try:
            checked = check_lender(checkout, SOURCE)
        except CheckoutRefusedError:
            return None
        if isinstance(checked, Lender):
            negotiation_tips(checked.record)
        return checked

    _within(FIFO_SECONDS, discover)
    _within(FIFO_SECONDS, lambda: discover_repository_context(checkout))
    _within(FIFO_SECONDS, lambda: suggested_checkout(SOURCE, checkout))


def test_a_fifo_boundary_cannot_lend(linear: _Stand) -> None:
    checkout = clone_checkout(linear.replica, linear.tmp_path / "checkout")
    _fifo_at(checkout / ".git" / "shallow")
    checked = check_lender(checkout, SOURCE)
    assert isinstance(checked, LenderRefusal) and checked.code == "boundary_unreadable"


def test_a_fifo_is_no_text(tmp_path: Path) -> None:
    fifo = tmp_path / "fifo"
    os.mkfifo(fifo)
    assert _within(FIFO_SECONDS, lambda: read_bounded_text(fifo, 100)) is None


def test_a_linked_worktree_lends_the_common_directorys_objects(linear: _Stand) -> None:
    replica = linear.replica
    checkout = clone_checkout(replica, linear.tmp_path / "checkout")
    worktree = linear.tmp_path / "feature-x"
    pinned_git(checkout, "worktree", "add", "-q", "-b", "feature-x", str(worktree))
    assert (worktree / ".git").is_file()
    before = fingerprint(checkout)
    status = ok([PULL, "--checkout", str(worktree), "--api", STATUS]).payload()
    assert status["borrows"] == str(checkout.resolve())
    assert (linear.store / "objects" / "info" / "alternates").read_text(encoding="utf-8") == (
        f"{(checkout / '.git' / 'objects').resolve()}\n"
    )
    assert fingerprint(checkout) == before
    # The linked worktree goes; the common directory and its objects stay.
    pinned_git(checkout, "worktree", "remove", "--force", str(worktree))
    assert ok([PULL, "--api", STATUS]).payload()["borrows"] == str(checkout.resolve())


# ── Overlay storage ─────────────────────────────────────────────────


def test_a_pull_request_reads_the_same_from_an_overlay_as_from_a_full_mirror(
    linear: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    replica = linear.replica
    checkout = clone_checkout(replica, linear.tmp_path / "checkout")
    ok([PULL, "--no-serve"])
    full_record = linear.pull()["record"]
    route = linear.pull()["comparison_route"]
    full = {
        "comparison": ok([PULL, "--api", route]).stdout,
        "file": ok([PULL, "--show", "p"]).stdout,
        "tree": ok([PULL, "--api", "/api/tree?depth=2"]).stdout,
    }
    monkeypatch.setenv("METABROWSER_CACHE_DIR", str(linear.tmp_path / "overlay-home"))
    overlay_record = ok([PULL, "--checkout", str(checkout), "--api", PULL_ROUTE]).payload()[
        "record"
    ]
    overlay = {
        "comparison": ok([PULL, "--api", route]).stdout,
        "file": ok([PULL, "--show", "p"]).stdout,
        "tree": ok([PULL, "--api", "/api/tree?depth=2"]).stdout,
    }
    assert overlay_record == full_record
    assert overlay == full


def test_borrowing_copies_no_object_the_checkout_has(linear: _Stand) -> None:
    replica = linear.replica
    checkout = clone_checkout(replica, linear.tmp_path / "checkout")
    pinned_git(replica.origin, "update-ref", "refs/keep/fetched", replica["H1"])
    pinned_git(checkout, "remote", "set-url", "origin", replica.url)
    pinned_git(checkout, "fetch", "-q", "origin", "+refs/pull/1/head:refs/remotes/origin/seen")
    pinned_git(checkout, "remote", "set-url", "origin", REMOTE_SPELLING)
    envelope = linear.pull("--checkout", str(checkout))
    assert envelope["record"]["comparison"]["base"] == replica["M4"]
    assert linear.store_git("count-objects") == "0 objects, 0 kilobytes"
    assert linear.store_git("cat-file", "-t", replica["H1"]) == "commit"
    status = ok([PULL, "--api", STATUS])
    assert status.payload()["borrows"] == str(checkout.resolve())
    assert status.payload()["shallow"] is False


def test_a_head_the_checkout_lacks_is_fetched_into_the_store_alone(linear: _Stand) -> None:
    replica = linear.replica
    checkout = clone_checkout(replica, linear.tmp_path / "checkout", "--single-branch")
    before = fingerprint(checkout)
    envelope = linear.pull("--checkout", str(checkout))
    assert envelope["record"]["comparison"]["head"] == replica["H1"]
    assert linear.store_git("cat-file", "-t", replica["H1"]) == "commit"
    assert pinned_git(checkout, "cat-file", "-t", replica["M5"]) == "commit"
    assert fingerprint(checkout) == before
    objects = linear.store_git("count-objects")
    assert objects != "0 objects, 0 kilobytes"


def test_the_store_says_what_it_borrows_and_a_full_store_says_nothing(linear: _Stand) -> None:
    checkout = clone_checkout(linear.replica, linear.tmp_path / "checkout")
    first = ok([CANONICAL, "--checkout", str(checkout), "--no-serve"])
    assert f"borrowing objects from {checkout.resolve()}" in first.stderr
    assert f"borrows: {checkout.resolve()}" in first.stdout
    again = ok([CANONICAL, "--no-serve"])
    assert f"borrowing objects from {checkout.resolve()}" in again.stderr
    store = (linear.store.parent / "store.yml").read_text(encoding="utf-8")
    assert "lender:" in store and "remote: origin" in store
    config = linear.store_git("config", "--get", "core.alternateRefsCommand")
    assert config == "true"
    assert linear.store_git("config", "--get", "core.commitGraph") == "false"


def test_a_full_stores_record_has_no_lender_key(linear: _Stand) -> None:
    ok([CANONICAL, "--no-serve"])
    assert "lender" not in (linear.store.parent / "store.yml").read_text(encoding="utf-8")


def test_a_shallow_checkout_says_so(merge_heavy: _Stand) -> None:
    checkout = clone_checkout(
        merge_heavy.replica, merge_heavy.tmp_path / "checkout", "--depth", "3", "--no-single-branch"
    )
    result = ok([CANONICAL, "--checkout", str(checkout), "--api", STATUS])
    assert "history is shallow, as the checkout's is" in result.stderr
    assert result.payload()["shallow"] is True
    assert (merge_heavy.store / "shallow").is_symlink()


def test_the_cache_routes_report_the_mode_and_the_lenders_health(linear: _Stand) -> None:
    checkout = clone_checkout(linear.replica, linear.tmp_path / "checkout")
    ok([CANONICAL, "--checkout", str(checkout), "--no-serve"])
    row = ok([CANONICAL, "--api", "/api/cache/stores"]).payload()["stores"][0]
    assert (row["mode"], row["lender"], row["publication"]) == ("overlay", "present", "published")
    assert str(checkout) not in json.dumps(row)
    shutil.move(checkout, linear.tmp_path / "moved")
    row = ok([CANONICAL, "--api", "/api/cache/stores"]).payload()["stores"][0]
    assert (row["mode"], row["lender"]) == ("overlay", "lender_missing")


# ── A dangling ref cannot wedge a fetch ─────────────────────────────


def _store_with_dangling_ref(stand: _Stand) -> tuple[Path, str]:
    """An overlay holding a branch the origin deleted and the checkout has collected."""

    replica = stand.replica
    pinned_git(replica.origin, "branch", "-q", "feat", replica["M3"])
    feat_work = stand.tmp_path / "feat"
    pinned_git(replica.origin, "worktree", "add", "-q", str(feat_work), "feat")
    (feat_work / "f").write_text("f\n", encoding="utf-8")
    pinned_git(feat_work, "add", "f")
    pinned_git(feat_work, "commit", "-qm", "F1")
    feat = pinned_git(feat_work, "rev-parse", "HEAD")
    pinned_git(replica.origin, "worktree", "remove", "--force", str(feat_work))
    checkout = clone_checkout(replica, stand.tmp_path / "checkout")
    ok([CANONICAL, "--checkout", str(checkout), "--no-serve"])
    assert stand.store_refs()["refs/remotes/origin/feat"] == feat
    pinned_git(replica.origin, "branch", "-q", "-D", "feat")
    pinned_git(checkout, "remote", "set-url", "origin", replica.url)
    pinned_git(checkout, "fetch", "-q", "--prune", "origin")
    pinned_git(checkout, "remote", "set-url", "origin", REMOTE_SPELLING)
    pinned_git(checkout, "reflog", "expire", "--expire-unreachable=now", "--all")
    pinned_git(checkout, "gc", "-q", "--prune=now")
    return checkout, feat


@pytest.mark.parametrize("packed", [False, True], ids=["loose", "packed"])
def test_a_dangling_ref_cannot_wedge_a_refresh(linear: _Stand, packed: bool) -> None:
    _checkout, feat = _store_with_dangling_ref(linear)
    if packed:
        linear.store_git("pack-refs", "--all")
    update = asyncio.run(
        update_store(linear.home, linear.store.parent.name, remote_url=linear.replica.url)
    )
    assert update.outcome is RefreshOutcome.succeeded
    assert "refs/remotes/origin/feat" not in linear.store_refs()
    assert feat not in linear.store_refs().values()


def test_a_pull_requests_dangling_head_cannot_wedge_a_refresh(linear: _Stand) -> None:
    """Pruning cannot heal this one: no refspec of a refresh names ``refs/pull/<n>/head``.

    Git's connectivity check walks every ref, so without the sweep the refresh and its retry
    both die on ``bad object``. The checkout held the pull request's commits, so the store
    holds only the ref, and it dangles once the checkout collects them. Fetching the pull
    request again brings them back.
    """

    replica = linear.replica
    checkout = clone_checkout(replica, linear.tmp_path / "checkout")
    pinned_git(checkout, "remote", "set-url", "origin", replica.url)
    pinned_git(checkout, "fetch", "-q", "origin", "+refs/pull/1/head:refs/remotes/origin/seen")
    pinned_git(checkout, "remote", "set-url", "origin", REMOTE_SPELLING)
    linear.pull("--checkout", str(checkout))
    assert linear.store_git("count-objects") == "0 objects, 0 kilobytes"
    pinned_git(checkout, "update-ref", "-d", "refs/remotes/origin/seen")
    pinned_git(checkout, "reflog", "expire", "--expire-unreachable=now", "--all")
    pinned_git(checkout, "gc", "-q", "--prune=now")
    assert refused_cat_file(linear.store, replica["H1"])

    update = asyncio.run(
        update_store(linear.home, linear.store.parent.name, remote_url=replica.url)
    )
    assert update.outcome is RefreshOutcome.succeeded
    assert "refs/pull/1/head" not in linear.store_refs()

    assert ok([PULL, "--no-serve"]).exit_code == 0
    assert linear.store_refs()["refs/pull/1/head"] == replica["H1"]
    assert linear.store_git("cat-file", "-t", replica["H1"]) == "commit"


def refused_cat_file(store: Path, oid: str) -> bool:
    """Whether the store cannot read *oid*, as a dangling ref's object is."""

    try:
        pinned_git(store, "cat-file", "-e", oid)
    except subprocess.CalledProcessError:
        return True
    return False


def test_a_branch_the_checkout_lost_comes_back_with_the_refresh(linear: _Stand) -> None:
    """The origin has the branch, and only the objects are gone: a refresh brings them back."""

    replica = linear.replica
    pinned_git(replica.origin, "branch", "-q", "feat", replica["M3"])
    feat_work = linear.tmp_path / "feat"
    pinned_git(replica.origin, "worktree", "add", "-q", str(feat_work), "feat")
    (feat_work / "f").write_text("f\n", encoding="utf-8")
    pinned_git(feat_work, "add", "f")
    pinned_git(feat_work, "commit", "-qm", "F1")
    feat = pinned_git(feat_work, "rev-parse", "HEAD")
    pinned_git(replica.origin, "worktree", "remove", "--force", str(feat_work))
    checkout = clone_checkout(replica, linear.tmp_path / "checkout")
    ok([CANONICAL, "--checkout", str(checkout), "--no-serve"])
    assert linear.store_refs()["refs/remotes/origin/feat"] == feat
    pinned_git(checkout, "update-ref", "-d", "refs/remotes/origin/feat")
    pinned_git(checkout, "reflog", "expire", "--expire-unreachable=now", "--all")
    pinned_git(checkout, "gc", "-q", "--prune=now")

    update = asyncio.run(
        update_store(linear.home, linear.store.parent.name, remote_url=replica.url)
    )
    assert update.outcome is RefreshOutcome.succeeded
    assert linear.store_refs()["refs/remotes/origin/feat"] == feat
    assert linear.store_git("cat-file", "-t", feat) == "commit"


def test_a_dangling_ref_cannot_wedge_a_pull_requests_fetch(linear: _Stand) -> None:
    _store_with_dangling_ref(linear)
    envelope = linear.pull()
    assert envelope["record"]["comparison"]["head"] == linear.replica["H1"]
    assert "refs/remotes/origin/feat" not in linear.store_refs()


def test_a_killed_deepens_lock_is_cleaned_up(merge_heavy: _Stand) -> None:
    replica = merge_heavy.replica
    checkout = clone_checkout(
        replica, merge_heavy.tmp_path / "checkout", "--depth", "3", "--no-single-branch"
    )
    merge_heavy.pull("--checkout", str(checkout))
    (merge_heavy.store / "shallow.lock").write_text("", encoding="utf-8")
    ok([PULL, "--no-serve"])
    assert not (merge_heavy.store / "shallow.lock").exists()


# ── A checkout that has gone ────────────────────────────────────────


@pytest.fixture
def moved(linear: _Stand) -> Iterator[tuple[_Stand, Path, Path]]:
    checkout = clone_checkout(linear.replica, linear.tmp_path / "checkout")
    ok([PULL, "--checkout", str(checkout), "--no-serve"])
    target = linear.tmp_path / "moved"
    shutil.move(checkout, target)
    yield linear, checkout, target


@pytest.mark.parametrize(
    "mode",
    [
        ("--api", STATUS),
        ("--api", PULL_ROUTE),
        ("--show", "m"),
        ("--no-serve",),
        ("--check-api",),
    ],
    ids=["status", "pull", "show", "no-serve", "check-api"],
)
def test_a_moved_checkout_is_a_typed_refusal_that_names_the_repair(
    moved: tuple[_Stand, Path, Path], mode: tuple[str, ...]
) -> None:
    _unused, checkout, _target = moved
    result = refused([PULL, *mode])
    assert "(lender_missing)" in result.error
    assert str(checkout.resolve()) in result.error
    assert f"metab {CANONICAL} --checkout <new path>" in result.error
    assert "Traceback" not in result.stderr


def test_serving_refuses_a_moved_checkout_before_anything_is_bound(
    moved: tuple[_Stand, Path, Path],
) -> None:
    result = refused([PULL, "--no-open", "--port", "1"])
    assert "(lender_missing)" in result.error


def test_naming_the_new_place_repairs_a_moved_checkout(
    moved: tuple[_Stand, Path, Path],
) -> None:
    stand, checkout, target = moved
    repaired = ok([PULL, "--checkout", str(target), "--api", STATUS])
    assert repaired.payload()["borrows"] == str(target.resolve())
    assert "borrowing objects from" in repaired.stderr
    # Remembered from then on.
    assert ok([PULL, "--api", STATUS]).payload()["borrows"] == str(target.resolve())
    alternates = (stand.store / "objects" / "info" / "alternates").read_text(encoding="utf-8")
    assert alternates == f"{(target / '.git' / 'objects').resolve()}\n"
    assert os.readlink(stand.store / "shallow") == str((target / ".git" / "shallow").resolve())
    assert not checkout.exists()


def test_a_repair_keeps_a_boundary_the_store_owns_and_gains_the_new_checkouts(
    merge_heavy: _Stand,
) -> None:
    replica = merge_heavy.replica
    checkout = clone_checkout(
        replica, merge_heavy.tmp_path / "checkout", "--depth", "3", "--no-single-branch"
    )
    merge_heavy.pull("--checkout", str(checkout))
    owned = set((merge_heavy.store / "shallow").read_text(encoding="utf-8").split())
    other = clone_checkout(
        replica, merge_heavy.tmp_path / "other", "--depth", "2", "--no-single-branch"
    )
    lent = set((other / ".git" / "shallow").read_text(encoding="utf-8").split())
    shutil.rmtree(checkout)
    ok([PULL, "--checkout", str(other), "--api", STATUS])
    boundary = merge_heavy.store / "shallow"
    assert not boundary.is_symlink()
    assert set(boundary.read_text(encoding="utf-8").split()) == owned | lent


def test_a_repair_is_checked_as_a_new_lender_is(moved: tuple[_Stand, Path, Path]) -> None:
    stand, _checkout, target = moved
    pinned_git(target, "config", "extensions.partialClone", "origin")
    result = refused([PULL, "--checkout", str(target), "--api", STATUS])
    assert "cannot repair this mirror" in result.error
    other = stand.tmp_path / "other"
    other.mkdir()
    pinned_git(other, "init", "-q")
    assert "is not a checkout of" in refused([PULL, "--checkout", str(other)]).error


def test_a_refresh_reports_a_moved_checkout_by_name(moved: tuple[_Stand, Path, Path]) -> None:
    stand, _checkout, _target = moved
    update = asyncio.run(
        update_store(stand.home, stand.store.parent.name, remote_url=stand.replica.url)
    )
    assert update.outcome is RefreshOutcome.lender_missing


def test_a_pull_requests_fetch_reports_a_moved_checkout_by_name(
    moved: tuple[_Stand, Path, Path],
) -> None:
    stand, _checkout, _target = moved
    published = asyncio.run(_inspect(stand))

    async def fetch() -> None:
        await pull_refs.fetch_pull_head(published, 1)

    with pytest.raises(pull_refs.PullRefError) as raised:
        asyncio.run(fetch())
    assert raised.value.state == "lender_missing"


async def _inspect(stand: _Stand) -> Any:
    return await acquire_source(SOURCE, home=stand.home, inspecting=True)


@pytest.mark.parametrize(
    "tamper",
    [
        lambda store, _elsewhere: (store / "objects" / "info" / "alternates").unlink(),
        lambda store, elsewhere: (store / "objects" / "info" / "alternates").write_text(
            f"{elsewhere}\n"
        ),
    ],
    ids=["record-without-alternates", "alternates-naming-elsewhere"],
)
def test_alternates_that_disagree_with_the_record_are_refused_as_damaged(
    linear: _Stand, tamper: Callable[[Path, Path], object]
) -> None:
    checkout = clone_checkout(linear.replica, linear.tmp_path / "checkout")
    ok([CANONICAL, "--checkout", str(checkout), "--no-serve"])
    tamper(linear.store, linear.tmp_path)
    result = refused([CANONICAL, "--api", STATUS])
    assert "(damaged)" in result.error
    for root in (str(linear.tmp_path), CANONICAL):
        row = ok([root, "--api", "/api/cache/stores"]).payload()["stores"][0]
        assert row["publication"] == "damaged"
        assert row["problems"][0]["code"] == "mismatch"


def test_alternates_a_full_store_should_not_have_are_refused(linear: _Stand) -> None:
    ok([CANONICAL, "--no-serve"])
    (linear.store / "objects" / "info" / "alternates").write_text(
        f"{linear.tmp_path}\n", encoding="utf-8"
    )
    assert "(damaged)" in refused([CANONICAL, "--api", STATUS]).error


# ── A pull request stays untrusted ──────────────────────────────────


def test_borrowing_cannot_change_the_untrusted_profile(
    linear: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    checkout = clone_checkout(linear.replica, linear.tmp_path / "checkout")
    monkeypatch.setenv("METAB_ACTIVE_CONTENT", "1")
    monkeypatch.setenv("METAB_ALLOW_EDITS", "1")
    refused_edits = refused([PULL, "--checkout", str(checkout), "--allow-edits", "--api", STATUS])
    assert "always runs under the untrusted profile" in refused_edits.error
    overlay = ok([PULL, "--checkout", str(checkout), "--api", "/api/capabilities"]).payload()
    assert overlay["capabilities"] == {"active_content": False, "mutations": False}
    assert (linear.store / "objects" / "info" / "alternates").exists()
    shutil.rmtree(linear.home)
    full = ok([PULL, "--api", "/api/capabilities"]).payload()
    assert full["capabilities"] == overlay["capabilities"]
    assert not (linear.store / "objects" / "info" / "alternates").exists()


def test_a_served_overlay_names_its_checkout_only_where_it_names_its_location(
    linear: _Stand,
) -> None:
    """The path is on the application page, and a mirror's content cannot read it.

    Every answer about the repository's content is free of it. So is the raw form of a
    file, which is what a page of the repository's own could reach, and the status route
    refuses that origin.
    """

    checkout = clone_checkout(linear.replica, linear.tmp_path / "checkout")
    ok([CANONICAL, "--checkout", str(checkout), "--no-serve"])
    path = str(checkout.resolve())
    apply_capabilities(untrusted=True, no_active_content=False, allow_edits=False)
    serve_published(asyncio.run(acquire_source(SOURCE, home=linear.home)))
    with TestClient(server.app) as client:
        assert client.get(STATUS).json()["borrows"] == path
        shell = client.get("/view/")
        assert f"borrowing objects from {path}:" in shell.text
        assert "content-security-policy" in shell.headers
        assert client.get("/api/capabilities").json()["capabilities"] == {
            "active_content": False,
            "mutations": False,
        }
        for route in ("/api/tree?depth=2", "/api/catalog", "/api/routes"):
            assert path not in client.get(route).text, route
        refused_origin = client.get(STATUS, headers={"origin": "null"})
        assert refused_origin.status_code == 403
        assert path not in refused_origin.text


def test_a_running_server_answers_by_name_when_the_checkout_goes(linear: _Stand) -> None:
    """Never a traceback or a blank page: a read and a refresh each say what happened."""

    checkout = clone_checkout(linear.replica, linear.tmp_path / "checkout")
    ok([CANONICAL, "--checkout", str(checkout), "--no-serve"])
    apply_capabilities(untrusted=True, no_active_content=False, allow_edits=False)
    serve_published(asyncio.run(acquire_source(SOURCE, home=linear.home)))
    wire = GitPath.from_display("m").to_wire()
    commit = linear.replica["M5"]
    with TestClient(server.app, raise_server_exceptions=False) as client:
        shutil.move(checkout, linear.tmp_path / "moved")
        # A reader already running keeps the packs it has open, so a read may still answer;
        # one that cannot says why, in the shape every route's failure has.
        for route, params in (
            ("/api/file", {"path": wire}),
            ("/api/git/commit/" + commit, {}),
            ("/api/plugin/diff/comparison", {"revision": commit}),
        ):
            answered = client.get(route, params=params)
            assert answered.headers["content-type"].startswith("application/json"), route
            assert answered.status_code == 200 or "error" in answered.json(), route
            assert "Traceback" not in answered.text
            assert str(checkout.resolve()) not in answered.text, route
        started = client.post(
            "/api/source/refresh", json={}, headers={"accept": "application/json"}
        )
        assert started.status_code == 202, started.text
        status = settle(client)
        assert status["last_outcome"]["outcome"] == "lender_missing"


def test_the_tooltip_names_the_checkout_beside_the_location(linear: _Stand) -> None:
    from metabrowser.server import (
        _mirror_tip,  # pyright: ignore[reportPrivateUsage]
    )

    checkout = clone_checkout(linear.replica, linear.tmp_path / "checkout")
    status = ok([PULL, "--checkout", str(checkout), "--api", STATUS]).payload()
    tip = _mirror_tip(status)
    assert tip is not None
    assert f"stored in {status['location']}, borrowing objects from {checkout.resolve()}:" in tip


# ── A boundary commit's own diff ────────────────────────────────────


_COMPARISON = "/api/plugin/diff/comparison"


def _shallow_heavy(stand: _Stand) -> Path:
    return clone_checkout(
        stand.replica, stand.tmp_path / "checkout", "--depth", "3", "--no-single-branch"
    )


def test_a_boundary_commits_diff_is_refused_on_a_pin_rather_than_shown_against_nothing(
    merge_heavy: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Git grafts a boundary commit into a root, and a root's diff is the whole tree added.

    A5 changes one line of ``f``; its parent A4 is beyond the depth-3 boundary. The
    comparison answers a typed refusal, as ``base_uncertain`` does, never ``+a5``.
    """

    _no_deepening(monkeypatch)
    replica = merge_heavy.replica
    merge_heavy.pull("--checkout", str(_shallow_heavy(merge_heavy)))
    for name in ("A5", "A1"):
        refusal = refused([PULL, "--api", f"{_COMPARISON}?revision={replica[name]}"])
        assert "parent_unavailable" in refusal.stdout, name
        assert "+a5" not in refusal.stdout
        detail = ok([PULL, "--api", f"/api/git/commit/{replica[name]}"]).payload()
        assert detail["files"] == []
        assert set(detail["stats"].values()) == {None}, name
    # A commit above the boundary compares against its parent as ever.
    above = ok([PULL, "--api", f"{_COMPARISON}?revision={replica['A6']}"]).payload()
    assert above["resolved"]["left"]["id"] == replica["A5"]


def test_a_real_root_commit_still_compares_against_the_empty_tree(linear: _Stand) -> None:
    replica = linear.replica
    checkout = clone_checkout(replica, linear.tmp_path / "checkout")
    linear.pull("--checkout", str(checkout))
    root = ok([PULL, "--api", f"{_COMPARISON}?revision={replica['M1']}"]).payload()
    assert root["resolved"]["left"]["kind"] == "empty"
    assert [change["new"]["path"] for change in root["manifest"]["files"]] == ["m"]
    detail = ok([PULL, "--api", f"/api/git/commit/{replica['M1']}"]).payload()
    assert detail["stats"]["files_added"] == 1


def test_a_shallow_folder_refuses_a_boundary_commits_diff_the_same_way(
    merge_heavy: _Stand,
) -> None:
    """The same defect on a served checkout, fixed in the one adapter both read through."""

    replica = merge_heavy.replica
    checkout = _shallow_heavy(merge_heavy)
    refusal = refused([str(checkout), "--api", f"{_COMPARISON}?revision={replica['A5']}"])
    assert "parent_unavailable" in refusal.stdout
    assert "+a5" not in refusal.stdout
    at_cli = run_metab([str(checkout), "--diff", replica["A5"]])
    assert at_cli.exit_code != 0 and "parent_unavailable" in at_cli.stderr
    assert "+a5" not in at_cli.stdout
    detail = ok([str(checkout), "--api", f"/api/git/commit/{replica['A5']}"]).payload()
    assert detail["files"] == [] and set(detail["stats"].values()) == {None}
    # The log is Git's cut graph, labelled shallow by the status route; the commit above
    # the boundary and its diff read as ever.
    log = ok([str(checkout), "--api", "/api/git/log?limit=10"]).payload()
    assert [c["parent_ids"] for c in log["commits"] if c["id"] == replica["A5"]] == [[]]
    above = ok([str(checkout), "--api", f"{_COMPARISON}?revision={replica['A6']}"]).payload()
    assert above["resolved"]["left"]["id"] == replica["A5"]


# ── What a store's kept comparison may depend on ────────────────────
#
# ``builtin_plugins/diff/comparison_cache.py`` keeps a store's answer for two commit IDs in
# memory, and a browser keeps it as immutable. Each test below is one of the inputs that
# file says a borrowing store adds, read in one process, so the kept answers are in play.


def test_a_refusal_at_the_boundary_is_not_kept_once_the_checkout_deepens(
    merge_heavy: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    _no_deepening(monkeypatch)
    replica = merge_heavy.replica
    checkout = _shallow_heavy(merge_heavy)
    merge_heavy.pull("--checkout", str(checkout))
    own_diff = f"{_COMPARISON}?revision={replica['A5']}"
    from_base = f"{_COMPARISON}?left={replica['M7']}&right={replica['H2']}&base_policy=merge_base"
    assert "parent_unavailable" in refused([PULL, "--api", own_diff]).stdout
    assert "base_uncertain" in refused([PULL, "--api", from_base]).stdout
    pinned_git(checkout, "remote", "set-url", "origin", replica.url)
    pinned_git(checkout, "fetch", "-q", "--unshallow", "origin")
    pinned_git(checkout, "remote", "set-url", "origin", REMOTE_SPELLING)
    for route in (own_diff, from_base):
        assert ok([PULL, "--api", route]).payload()["resolved"]["left"]["id"] == replica["A4"]


def test_a_lenders_own_attributes_change_no_comparison(
    linear: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Git reads the attributes of the repository it runs in, which is the store."""

    replica = linear.replica
    checkout = clone_checkout(replica, linear.tmp_path / "checkout")
    linear.pull("--checkout", str(checkout))
    route = f"{_COMPARISON}?left={replica['M3']}&right={replica['M5']}"
    before = ok([PULL, "--api", route]).stdout
    (checkout / ".git" / "info").mkdir(exist_ok=True)
    (checkout / ".git" / "info" / "attributes").write_text("* binary\n", encoding="utf-8")
    monkeypatch.setattr(sidekick, "_COMPARISONS", ComparisonCache())
    after = ok([PULL, "--api", route])
    assert after.stdout == before
    assert after.payload()["manifest"]["files"][0]["binary"] is False


def test_a_kept_comparison_is_still_its_commits_diff_when_the_lender_loses_them(
    linear: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A kept answer is what any store holding the two commits answers, so it stays.

    One computed after the loss is refused and kept by nobody, and a validator the process
    did not issue is not honored, since the store no longer answers for the commits.
    """

    replica = linear.replica
    checkout = clone_checkout(replica, linear.tmp_path / "checkout")
    ok([CANONICAL, "--checkout", str(checkout), "--no-serve"])
    apply_capabilities(untrusted=True, no_active_content=False, allow_edits=False)
    serve_published(asyncio.run(acquire_source(SOURCE, home=linear.home)))
    params = {"left": replica["M3"], "right": replica["M5"]}
    with TestClient(server.app, raise_server_exceptions=False) as client:
        kept = client.get(_COMPARISON, params=params)
        assert kept.status_code == 200
        packs = checkout / ".git" / "objects" / "pack"
        shutil.move(packs, linear.tmp_path / "collected")
        packs.mkdir()
        again = client.get(_COMPARISON, params=params)
        assert (again.status_code, again.content) == (200, kept.content)
        monkeypatch.setattr(sidekick, "_COMPARISONS", ComparisonCache())
        computed = client.get(_COMPARISON, params=params)
        assert computed.status_code == 404 and "unknown revision" in computed.text
        validated = client.get(
            _COMPARISON, params=params, headers={"if-none-match": kept.headers["etag"]}
        )
        assert validated.status_code == 404


# ── The checks that admit a lender hold for as long as it lends ─────


def _lender_missing(result: Invocation, reason: str) -> None:
    assert "(lender_missing)" in result.error
    assert reason in result.error
    assert f"metab {CANONICAL} --checkout <new path>" in result.error
    assert "Traceback" not in result.stderr


def test_a_lender_that_grew_its_own_alternates_is_refused_on_every_later_open(
    linear: _Stand,
) -> None:
    """Git would follow the chain to a directory nothing recorded, on a remembered open too."""

    checkout = clone_checkout(linear.replica, linear.tmp_path / "checkout")
    linear.pull("--checkout", str(checkout))
    donor = clone_checkout(linear.replica, linear.tmp_path / "donor")
    chain = checkout / ".git" / "objects" / "info" / "alternates"
    chain.write_text(f"{donor / '.git' / 'objects'}\n", encoding="utf-8")
    for mode in (("--api", STATUS), ("--api", PULL_ROUTE), ("--show", "m"), ("--no-serve",)):
        _lender_missing(refused([PULL, *mode]), "now borrows objects itself")
    # A running server's refresh and a pull request's fetch refuse the same way.
    update = asyncio.run(
        update_store(linear.home, linear.store.parent.name, remote_url=linear.replica.url)
    )
    assert update.outcome is RefreshOutcome.lender_missing
    published = asyncio.run(_inspect(linear))
    with pytest.raises(pull_refs.PullRefError) as raised:
        asyncio.run(pull_refs.fetch_pull_head(published, 1))
    assert raised.value.state == "lender_missing"
    stores = ok([CANONICAL, "--api", "/api/cache/stores"]).payload()["stores"]
    assert stores[0]["lender"] == "lender_missing"
    # Naming the same checkout cannot repair it while it borrows; without the chain it lends.
    assert "cannot repair" in refused([PULL, "--checkout", str(checkout), "--api", STATUS]).error
    chain.unlink()
    assert ok([PULL, "--api", STATUS]).payload()["borrows"] == str(checkout.resolve())


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads everything")
def test_an_unreadable_lender_keeps_its_refs_rather_than_being_swept(linear: _Stand) -> None:
    """Every borrowed object reads as missing then; a sweep would delete every ref."""

    replica = linear.replica
    checkout = clone_checkout(replica, linear.tmp_path / "checkout")
    linear.pull("--checkout", str(checkout))
    before = linear.store_refs()
    assert "refs/remotes/origin/trunk" in before and "refs/pull/1/head" in before
    packs = checkout / ".git" / "objects" / "pack"
    pack_files = sorted(packs.iterdir())
    try:
        # The pack files alone: the directories still read, so only the probe of the
        # checkout's own tips through the store can tell.
        for pack in pack_files:
            pack.chmod(0)
        update = asyncio.run(
            update_store(linear.home, linear.store.parent.name, remote_url=replica.url)
        )
        assert update.outcome is RefreshOutcome.lender_missing
        published = asyncio.run(_inspect(linear))
        with pytest.raises(pull_refs.PullRefError) as raised:
            asyncio.run(pull_refs.fetch_pull_head(published, 1))
        assert raised.value.state == "lender_missing"
        assert linear.store_refs() == before
        # The directory itself unreadable: refused at open as a new lender would be.
        packs.chmod(0)
        _lender_missing(refused([PULL, "--api", STATUS]), "could not be read")
        assert linear.store_refs() == before
    finally:
        packs.chmod(0o755)
        for pack in pack_files:
            pack.chmod(0o644)
    assert ok([PULL, "--api", STATUS]).payload()["borrows"] == str(checkout.resolve())
    assert linear.store_refs() == before


def _loose_object(checkout: Path, oid: str) -> Path:
    return checkout / ".git" / "objects" / oid[:2] / oid[2:]


def _one_loose_object_unreadable(stand: _Stand) -> tuple[Path, list[Path]]:
    """The checkout fetched the pull request itself, and that one loose commit is unreadable.

    Its other tips still read, so the probe of them through the store passes, and only the
    pull request's head, whose commit the store borrows, reads as missing.
    """

    replica = stand.replica
    checkout = clone_checkout(replica, stand.tmp_path / "checkout")
    pinned_git(checkout, "remote", "set-url", "origin", replica.url)
    pinned_git(checkout, "fetch", "-q", "origin", "+refs/pull/1/head:refs/remotes/origin/seen")
    pinned_git(checkout, "remote", "set-url", "origin", REMOTE_SPELLING)
    stand.pull("--checkout", str(checkout))
    assert stand.store_git("count-objects") == "0 objects, 0 kilobytes"
    head = _loose_object(checkout, replica["H1"])
    assert head.is_file()
    return checkout, [head]


def _no_file_tips_and_unreadable_packs(stand: _Stand) -> tuple[Path, list[Path]]:
    """A lender whose refs no file holds, as reftable keeps them, and whose packs cannot be read.

    ``negotiation_tips`` then has nothing to probe the lender with.
    """

    checkout = clone_checkout(stand.replica, stand.tmp_path / "checkout")
    stand.pull("--checkout", str(checkout))
    git_dir = checkout / ".git"
    (git_dir / "packed-refs").unlink(missing_ok=True)
    shutil.rmtree(git_dir / "refs" / "remotes", ignore_errors=True)
    lender = StoreLender(objects=str(git_dir / "objects"), checkout=str(checkout), remote="origin")
    assert negotiation_tips(lender) == ()
    return checkout, sorted((git_dir / "objects" / "pack").iterdir())


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads everything")
@pytest.mark.parametrize(
    "unreadable",
    [_one_loose_object_unreadable, _no_file_tips_and_unreadable_packs],
    ids=["one-loose-object", "no-file-tips"],
)
def test_a_ref_is_swept_only_when_its_object_is_shown_to_be_gone(
    linear: _Stand, unreadable: Callable[[_Stand], tuple[Path, list[Path]]]
) -> None:
    """Review D2: an object the lender holds but cannot lend now is no collected object.

    A permission blip on one loose object, or a lender whose tips no file names, passed the
    probe of the lender's tips, and the sweep deleted a live ref: GitHub keeps every
    ``refs/pull/<n>/head``, and nothing but the next fetch of it brought it back. A ref is
    swept only when its object is in no loose file and every pack of the lender reads.
    """

    checkout, files = unreadable(linear)
    before = linear.store_refs()
    assert "refs/pull/1/head" in before and "refs/remotes/origin/trunk" in before
    try:
        for path in files:
            path.chmod(0)
        update = asyncio.run(
            update_store(linear.home, linear.store.parent.name, remote_url=linear.replica.url)
        )
        assert update.outcome is RefreshOutcome.lender_missing, update
        assert update.swept == ()
        assert linear.store_refs() == before
        published = asyncio.run(_inspect(linear))
        with pytest.raises(pull_refs.PullRefError) as raised:
            asyncio.run(pull_refs.fetch_pull_head(published, 1))
        assert raised.value.state == "lender_missing"
        assert "could not be read" in str(raised.value)
        assert linear.store_refs() == before
    finally:
        for path in files:
            path.chmod(0o444)
    update = asyncio.run(
        update_store(linear.home, linear.store.parent.name, remote_url=linear.replica.url)
    )
    assert update.outcome is RefreshOutcome.succeeded, update
    assert linear.store_refs()["refs/pull/1/head"] == before["refs/pull/1/head"]
    assert checkout.is_dir()


def test_another_repository_at_the_lenders_path_is_refused_and_the_flag_replaces_it(
    linear: _Stand, merge_heavy_replica: Replica
) -> None:
    checkout = clone_checkout(linear.replica, linear.tmp_path / "checkout")
    linear.pull("--checkout", str(checkout))
    shutil.rmtree(checkout)
    clone_checkout(merge_heavy_replica, checkout)
    pinned_git(checkout, "remote", "set-url", "origin", "https://github.com/other/repo.git")
    _lender_missing(refused([PULL, "--api", STATUS]), "is not one any more")
    complete = clone_checkout(linear.replica, linear.tmp_path / "complete")
    repaired = ok([PULL, "--checkout", str(complete), "--api", STATUS])
    assert repaired.payload()["borrows"] == str(complete.resolve())
    assert (
        ok([PULL, "--api", PULL_ROUTE]).payload()["record"]["comparison"]["head"]
        == (linear.replica["H1"])
    )


@pytest.fixture
def merge_heavy_replica(tmp_path: Path) -> Replica:
    return build_merge_heavy(tmp_path / "another")


def test_a_repair_that_stopped_before_its_record_is_finished_by_the_same_command(
    moved: tuple[_Stand, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The alternates file written and the record not: ``--checkout`` finishes it."""

    from metabrowser.cache import acquire

    stand, _checkout, target = moved
    real = acquire.write_record_atomic

    def refusing(*args: Any, **kwargs: Any) -> Any:
        # Only the store's own record, which the repair writes last; the hit's
        # last-opened stamp before it is written as ever.
        if not str(args[1]).endswith("store.yml"):
            return real(*args, **kwargs)
        monkeypatch.setattr(acquire, "write_record_atomic", real)
        raise acquire.AcquisitionError("the disk refused the record")

    monkeypatch.setattr(acquire, "write_record_atomic", refusing)
    stopped = refused([PULL, "--checkout", str(target), "--api", STATUS])
    assert "Traceback" not in stopped.stderr
    alternates = stand.store / "objects" / "info" / "alternates"
    assert alternates.read_text(encoding="utf-8") == f"{(target / '.git' / 'objects').resolve()}\n"
    # Half written: refused as damaged without the flag, and never a wrong read.
    assert "(damaged)" in refused([PULL, "--api", STATUS]).error
    repaired = ok([PULL, "--checkout", str(target), "--api", STATUS])
    assert repaired.payload()["borrows"] == str(target.resolve())
    assert ok([PULL, "--api", STATUS]).payload()["borrows"] == str(target.resolve())


@pytest.mark.skipif(os.geteuid() == 0, reason="root writes everything")
@pytest.mark.parametrize(
    ("read_only", "said", "half_written"),
    [
        (
            ("repository.git", "objects", "info"),
            "the mirror could not be repaired: Permission denied",
            False,
        ),
        ((), "cannot be verified as private to the current user", True),
    ],
    ids=["alternates-directory", "record-directory"],
)
def test_a_repair_the_disk_refuses_is_an_error_and_the_same_command_finishes_it(
    moved: tuple[_Stand, Path, Path], read_only: tuple[str, ...], said: str, half_written: bool
) -> None:
    """Review D3: a permission error during a repair printed a traceback.

    Refused at the alternates file, nothing changed and the old refusal stands. Refused at
    the record, after the alternates file and the boundary, the cache's own refusal names
    the storage, and the store is half written and refused as damaged, never read. The
    same command repairs either once the disk allows.
    """

    stand, _checkout, target = moved
    directory = stand.store.parent.joinpath(*read_only)
    alternates = stand.store / "objects" / "info" / "alternates"
    record = stand.store.parent / "store.yml"
    before = (alternates.read_text(encoding="utf-8"), record.read_bytes())
    # Private, as the cache requires of its directories, and not writable.
    directory.chmod(0o500)
    try:
        stopped = refused([PULL, "--checkout", str(target), "--api", STATUS])
        assert said in stopped.error
        assert "Traceback" not in stopped.stderr
        assert str(stand.home) not in stopped.error
        assert record.read_bytes() == before[1]
        if half_written:
            assert alternates.read_text(encoding="utf-8").startswith(str(target.resolve()))
            assert "(damaged)" in refused([PULL, "--api", STATUS]).error
        else:
            assert alternates.read_text(encoding="utf-8") == before[0]
            _lender_missing(refused([PULL, "--api", STATUS]), "is gone")
    finally:
        directory.chmod(0o700)
    repaired = ok([PULL, "--checkout", str(target), "--api", STATUS])
    assert repaired.payload()["borrows"] == str(target.resolve())
    assert ok([PULL, "--api", STATUS]).payload()["borrows"] == str(target.resolve())


def test_a_repair_waits_for_no_fetch_and_is_refused_while_one_holds_the_store(
    moved: tuple[_Stand, Path, Path],
) -> None:
    from metabrowser.cache.locks import store_fetch_lock

    stand, _checkout, target = moved
    with store_fetch_lock(stand.home, stand.store.parent.name):
        result = refused([PULL, "--checkout", str(target), "--api", STATUS])
    assert "Traceback" not in result.stderr
    record = (stand.store.parent / "store.yml").read_text(encoding="utf-8")
    assert str(target.resolve()) not in record
    assert ok([PULL, "--checkout", str(target), "--api", STATUS]).payload()["borrows"] == str(
        target.resolve()
    )


def test_a_cache_route_says_that_checkout_is_not_applied(moved: tuple[_Stand, Path, Path]) -> None:
    _stand, _checkout, target = moved
    answered = ok([PULL, "--checkout", str(target), "--api", "/api/cache/stores"])
    assert "not applied to a cache route" in answered.stderr
    assert answered.payload()["stores"][0]["lender"] == "lender_missing"
    assert "lender_missing" in refused([PULL, "--api", STATUS]).error


@pytest.mark.parametrize("store", ["full", "overlay"], ids=["full-mirror", "healthy-overlay"])
def test_a_path_that_is_no_checkout_is_refused_the_same_way_on_every_hit(
    linear: _Stand, store: str
) -> None:
    checkout = clone_checkout(linear.replica, linear.tmp_path / "checkout")
    ok([CANONICAL, *(("--checkout", str(checkout)) if store == "overlay" else ()), "--no-serve"])
    absent = linear.tmp_path / "absent"
    assert "is not a Git checkout" in refused([PULL, "--checkout", str(absent), "--no-serve"]).error
    empty = linear.tmp_path / "empty"
    empty.mkdir()
    pinned_git(empty, "init", "-q")
    assert "is not a checkout of" in refused([PULL, "--checkout", str(empty), "--no-serve"]).error


# ── What a refusal shows of a remote ────────────────────────────────


@pytest.mark.parametrize(
    "spelling",
    [
        "ssh://git:GHP_SUPERSECRET_TOKEN@github.com/a/b.git",
        "GHP_SUPERSECRET_TOKEN@example.com:a/b.git",
        "https://GHP_SUPERSECRET_TOKEN@github.com/a/b.git",
        "git://GHP_SUPERSECRET_TOKEN:x@example.com/a/b.git",
    ],
    ids=["ssh-password", "scp-user", "https-user", "git-userinfo"],
)
def test_a_refusal_never_prints_a_remotes_credentials(linear: _Stand, spelling: str) -> None:
    checkout = clone_checkout(linear.replica, linear.tmp_path / "other")
    pinned_git(checkout, "remote", "set-url", "origin", spelling)
    result = refused([PULL, "--checkout", str(checkout), "--api", STATUS])
    assert "is not a checkout of https://github.com/octo/demo" in result.error
    assert "GHP_SUPERSECRET_TOKEN" not in result.stderr + result.stdout
    assert "a/b" in result.error


def test_an_ssh_spelling_keeps_its_user_for_the_match(linear: _Stand) -> None:
    checkout = clone_checkout(linear.replica, linear.tmp_path / "spelled")
    pinned_git(checkout, "remote", "set-url", "origin", "ssh://git:token@github.com/octo/demo")
    assert isinstance(check_lender(checkout, SOURCE), Lender)


# ── A remote spelled as a path ──────────────────────────────────────


def _file_source(replica: Replica) -> GitSource:
    from metabrowser.cache.providers import url_reducers
    from metabrowser.cache.urls import classify_root_argument

    source = classify_root_argument(replica.url, reducers=url_reducers())
    assert isinstance(source, GitSource)
    return source


@pytest.mark.parametrize("relative", [False, True], ids=["absolute", "relative"])
def test_a_remote_spelled_as_a_path_is_the_file_source_of_that_path(
    linear: _Stand, relative: bool
) -> None:
    """``git clone /x/origin.git`` records that spelling, and the documented commands work."""

    replica = linear.replica
    source = _file_source(replica)
    checkout = clone_checkout(replica, linear.tmp_path / "checkout")
    spelled = os.path.relpath(replica.origin, checkout) if relative else str(replica.origin)
    pinned_git(checkout, "remote", "set-url", "origin", spelled)
    checked = check_lender(checkout, source)
    assert isinstance(checked, Lender) and checked.remote == "origin"
    (checkout / "sub").mkdir()
    assert suggested_checkout(source, checkout / "sub") == checkout.resolve()
    borrowed = ok([source.normalized, "--checkout", str(checkout), "--api", STATUS])
    assert borrowed.payload()["borrows"] == str(checkout.resolve())
    assert "borrowing objects from" in borrowed.stderr


def test_a_path_remote_matches_only_the_directory_it_names(linear: _Stand) -> None:
    """A lookalike beside the origin, and a path for an https source, lend nothing."""

    replica = linear.replica
    source = _file_source(replica)
    lookalike = replica.origin.parent / "origin.git-not"
    shutil.copytree(replica.origin, lookalike)
    checkout = clone_checkout(replica, linear.tmp_path / "checkout")
    pinned_git(checkout, "remote", "set-url", "origin", str(lookalike))
    with pytest.raises(CheckoutRefusedError) as refusal:
        check_lender(checkout, source)
    assert f"origin is file://{lookalike}" in str(refusal.value)
    assert suggested_checkout(source, checkout) is None
    # A path never names a GitHub repository, whatever it is called.
    pinned_git(checkout, "remote", "set-url", "origin", str(replica.origin))
    with pytest.raises(CheckoutRefusedError):
        check_lender(checkout, SOURCE)
    assert suggested_checkout(SOURCE, checkout) is None


# ── What a fetch tells the origin it has ────────────────────────────


def _store_objects(stand: _Stand) -> int:
    counted = dict(
        line.split(": ", 1) for line in stand.store_git("count-objects", "-v").splitlines()
    )
    return int(counted["count"]) + int(counted["in-pack"])


def test_a_refresh_brings_only_what_the_store_lacks_and_not_the_gap_again(
    linear: _Stand,
) -> None:
    """Review A's measurement: a branch the checkout never fetched, moved by one commit.

    With the lender's tips alone as ``--negotiation-tip``, Git offered none of the store's
    own refs, and the origin sent the branch's whole history again on every refresh. The
    store's refs are tips too now, so a refresh costs the one commit. The store keeps each
    fetch as a pack (``transfer.unpackLimit=1``) so the objects received can be counted.
    """

    replica = linear.replica
    side_work = linear.tmp_path / "side"
    pinned_git(replica.origin, "branch", "-q", "side", replica["M3"])
    pinned_git(replica.origin, "worktree", "add", "-q", str(side_work), "side")
    for number in range(24):
        (side_work / "s").write_text(f"s{number}\n", encoding="utf-8")
        pinned_git(side_work, "add", "s")
        pinned_git(side_work, "commit", "-qm", f"S{number}")
    checkout = clone_checkout(replica, linear.tmp_path / "checkout", "--single-branch")
    ok([CANONICAL, "--checkout", str(checkout), "--no-serve"])
    assert "refs/remotes/origin/side" in linear.store_refs()
    linear.store_git("config", "transfer.unpackLimit", "1")
    received: list[int] = []
    for number in range(2):
        (side_work / "s").write_text(f"pushed {number}\n" * 2000, encoding="utf-8")
        pinned_git(side_work, "add", "s")
        pinned_git(side_work, "commit", "-qm", f"P{number}")
        before = _store_objects(linear)
        update = asyncio.run(
            update_store(linear.home, linear.store.parent.name, remote_url=replica.url)
        )
        assert update.outcome is RefreshOutcome.succeeded
        received.append(_store_objects(linear) - before)
    # One commit, its tree, and its blob; the 24 commits' 72 objects never again.
    assert received == [3, 3], received


# ── A served pull head the sweep removed ────────────────────────────


def test_a_swept_pull_head_is_unobserved_and_never_reported_as_gone_from_the_origin(
    linear: _Stand,
) -> None:
    """GitHub keeps every ``refs/pull/<n>/head``; the store removed it, not the origin."""

    replica = linear.replica
    checkout = clone_checkout(replica, linear.tmp_path / "checkout")
    pinned_git(checkout, "remote", "set-url", "origin", replica.url)
    pinned_git(checkout, "fetch", "-q", "origin", "+refs/pull/1/head:refs/remotes/origin/seen")
    pinned_git(checkout, "remote", "set-url", "origin", REMOTE_SPELLING)
    linear.pull("--checkout", str(checkout))
    published = asyncio.run(_inspect(linear))
    pinned_git(checkout, "update-ref", "-d", "refs/remotes/origin/seen")
    pinned_git(checkout, "reflog", "expire", "--expire-unreachable=now", "--all")
    pinned_git(checkout, "gc", "-q", "--prune=now")
    assert refused_cat_file(linear.store, replica["H1"])

    from metabrowser import mirror_refresh
    from metabrowser.cache.repository_store import open_revision
    from metabrowser.cache.served_mirror import StoreMirror
    from metabrowser.git.tree_source import GitRevisionSubject
    from metabrowser.source import reset_source_session, serve_subject_opener

    async def opener() -> GitRevisionSubject:
        return await open_revision(
            home=published.home,
            store_key=published.store_key,
            commit_oid=replica["M5"],
            store_identity=published.store_id,
            ref="refs/pull/1/head",
        )

    apply_capabilities(untrusted=True, no_active_content=False, allow_edits=False)
    reset_source_session()
    serve_subject_opener(opener)
    mirror_refresh.serve_mirror(StoreMirror.from_published(published), pull_request=1)
    with TestClient(server.app, raise_server_exceptions=False) as client:
        started = client.post(
            "/api/source/refresh", json={}, headers={"accept": "application/json"}
        )
        assert started.status_code == 202, started.text
        status = settle(client)
        assert status["last_outcome"]["outcome"] == "succeeded"
        assert "refs/pull/1/head" not in linear.store_refs()
        assert status["ref_on_origin"] is None and status["latest"] is None


# ── The boundary, read before and after Git ─────────────────────────


def test_a_boundary_that_appears_while_merge_base_runs_is_uncertain(
    linear: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    from metabrowser.git import shallow
    from metabrowser.git.process import repository_store_target

    replica = linear.replica
    checkout = clone_checkout(replica, linear.tmp_path / "checkout")
    linear.pull("--checkout", str(checkout))
    target = repository_store_target(git_dir=linear.store)
    real = shallow.run_git

    async def cutting(args: list[str], **kwargs: Any) -> bytes:
        if args[0] == "merge-base":
            # The checkout becomes shallow under the store's link, between the read
            # and Git: as a ``fetch --depth`` in it, or a re-clone at the same path.
            (checkout / ".git" / "shallow").write_text(replica["M4"] + "\n", encoding="utf-8")
        return await real(args, **kwargs)

    monkeypatch.setattr(shallow, "run_git", cutting)
    answer = asyncio.run(shallow.merge_base_answer(target, replica["M5"], replica["H1"]))
    assert answer.certain is False


def test_a_boundary_the_store_owns_is_dropped_once_the_checkout_is_complete(
    merge_heavy: _Stand,
) -> None:
    replica = merge_heavy.replica
    checkout = _shallow_heavy(merge_heavy)
    merge_heavy.pull("--checkout", str(checkout))
    boundary = merge_heavy.store / "shallow"
    assert boundary.is_file() and not boundary.is_symlink()
    assert ok([PULL, "--api", STATUS]).payload()["shallow"] is True
    pinned_git(checkout, "remote", "set-url", "origin", replica.url)
    pinned_git(checkout, "fetch", "-q", "--unshallow", "origin")
    pinned_git(checkout, "remote", "set-url", "origin", REMOTE_SPELLING)
    assert not (checkout / ".git" / "shallow").exists()
    update = asyncio.run(
        update_store(merge_heavy.home, merge_heavy.store.parent.name, remote_url=replica.url)
    )
    assert update.outcome is RefreshOutcome.succeeded
    assert not boundary.exists()
    assert ok([PULL, "--api", STATUS]).payload()["shallow"] is False
    assert merge_heavy.store_git("rev-list", "--count", replica["M7"]) == "9"


# ── A commit the checkout has collected ─────────────────────────────


def test_a_missing_borrowed_ancestor_is_commits_unavailable_and_not_no_merge_base(
    linear: _Stand,
) -> None:
    replica = linear.replica
    checkout = clone_checkout(replica, linear.tmp_path / "checkout")
    # The clone's one pack, unpacked into loose objects so that one can be deleted.
    aside = linear.tmp_path / "aside"
    aside.mkdir()
    for pack in (checkout / ".git" / "objects" / "pack").iterdir():
        shutil.move(pack, aside / pack.name)
    for pack in aside.glob("*.pack"):
        with pack.open("rb") as stream:
            subprocess.run(
                ["git", "unpack-objects", "-q"],
                cwd=checkout,
                stdin=stream,
                check=True,
                capture_output=True,
                env=pinned_git_env(),
            )
    assert pinned_git(checkout, "cat-file", "-t", replica["M3"]) == "commit"
    envelope = linear.pull("--checkout", str(checkout))
    assert envelope["record"]["comparison"]["base"] == replica["M4"]
    loose = checkout / ".git" / "objects" / replica["M3"][:2] / replica["M3"][2:]
    loose.unlink()
    for record in linear.home.glob("sources/*/pulls/1*.json"):
        record.unlink()
    again = linear.pull()["record"]
    assert again["comparison"] is None
    assert again["unavailable"] == {"comparison": "commits_unavailable"}


def _no_history_as_before_git_2_45(monkeypatch: pytest.MonkeyPatch) -> None:
    """Git before 2.45 answers exit 1, "no common history", for a walk it could not finish."""

    from metabrowser.git import shallow

    real = shallow.run_git

    async def older(args: list[str], **kwargs: Any) -> bytes:
        if args[0] == "merge-base":
            raise git_process.GitCommandError(args, 1, "")
        return await real(args, **kwargs)

    monkeypatch.setattr(shallow, "run_git", older)


def test_no_history_is_believed_only_when_the_walk_reads_every_commit(
    linear: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    from metabrowser.git import shallow
    from metabrowser.git.process import repository_store_target

    replica = linear.replica
    checkout = clone_checkout(replica, linear.tmp_path / "checkout")
    aside = linear.tmp_path / "aside"
    aside.mkdir()
    for pack in (checkout / ".git" / "objects" / "pack").iterdir():
        shutil.move(pack, aside / pack.name)
    for pack in aside.glob("*.pack"):
        with pack.open("rb") as stream:
            subprocess.run(
                ["git", "unpack-objects", "-q"],
                cwd=checkout,
                stdin=stream,
                check=True,
                capture_output=True,
                env=pinned_git_env(),
            )
    linear.pull("--checkout", str(checkout))
    target = repository_store_target(git_dir=linear.store)
    _no_history_as_before_git_2_45(monkeypatch)

    whole = asyncio.run(shallow.merge_base_answer(target, replica["M5"], replica["H1"]))
    assert whole == shallow.MergeBaseAnswer(None, certain=True)

    (checkout / ".git" / "objects" / replica["M3"][:2] / replica["M3"][2:]).unlink()
    with pytest.raises(git_process.GitCommandError):
        asyncio.run(shallow.merge_base_answer(target, replica["M5"], replica["H1"]))


@pytest.mark.parametrize("defect", ["missing", "empty", "invalid", "directory"])
def test_a_pack_without_its_index_does_not_authorize_sweeping_refs(
    linear: _Stand, defect: str
) -> None:
    checkout, files = _no_file_tips_and_unreadable_packs(linear)
    before = linear.store_refs()
    indexes = [path for path in files if path.suffix == ".idx"]
    assert indexes
    saved = {path: path.read_bytes() for path in indexes}
    for path in indexes:
        path.unlink()
        if defect == "empty":
            path.write_bytes(b"")
        elif defect == "invalid":
            path.write_bytes(b"invalid index" * 100)
        elif defect == "directory":
            path.mkdir()
    update = asyncio.run(
        update_store(linear.home, linear.store.parent.name, remote_url=linear.replica.url)
    )
    assert update.outcome is RefreshOutcome.lender_missing, update
    assert update.swept == ()
    assert linear.store_refs() == before
    for path, data in saved.items():
        if path.is_dir():
            path.rmdir()
        path.write_bytes(data)
    update = asyncio.run(
        update_store(linear.home, linear.store.parent.name, remote_url=linear.replica.url)
    )
    assert update.outcome is RefreshOutcome.succeeded, update
    assert linear.store_refs() == before
    assert checkout.is_dir()


@pytest.mark.parametrize(
    ("failure", "state"),
    [
        (git_process.GitTimeoutError, "comparison_timeout"),
        (git_process.GitOutputTooLargeError, "comparison_too_large"),
    ],
)
def test_an_unfinished_merge_base_walk_preserves_the_pull_record(
    linear: _Stand,
    monkeypatch: pytest.MonkeyPatch,
    failure: type[git_process.GitError],
    state: str,
) -> None:
    from metabrowser.git import shallow

    checkout = clone_checkout(linear.replica, linear.tmp_path / "checkout")
    linear.pull("--checkout", str(checkout))
    for record in linear.home.glob("sources/*/pulls/1*.json"):
        record.unlink()
    real = shallow.run_git

    async def bounded(args: list[str], **kwargs: Any) -> bytes:
        if args[0] == "merge-base":
            raise git_process.GitCommandError(args, 1, "")
        if args[0] == "rev-list":
            raise failure("injected walk bound")
        return await real(args, **kwargs)

    monkeypatch.setattr(shallow, "run_git", bounded)
    record = linear.pull()["record"]
    assert record["pull"]["title"] == "Add p"
    assert record["comparison"] is None
    assert record["unavailable"] == {"comparison": state}


def test_old_git_cannot_hide_a_missing_ancestor_below_its_merge_base(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from metabrowser.git import shallow
    from metabrowser.git.process import repository_store_target

    replica = build_linear(tmp_path / "replica")
    target = repository_store_target(git_dir=replica.origin)
    missing = replica["M2"]
    (replica.origin / "objects" / missing[:2] / missing[2:]).unlink()
    real = shallow.run_git

    async def older(args: list[str], **kwargs: Any) -> bytes:
        if args[0] == "merge-base":
            # Pre-2.45 candidate reduction may succeed after an unreadable ancestor.
            # Pruning that candidate's history hides the missing commit from rev-list.
            return (replica["M3"] + "\n").encode("ascii")
        return await real(args, **kwargs)

    monkeypatch.setattr(shallow, "run_git", older)
    monkeypatch.setattr(
        git_process, "detect_git_version", lambda: ((2, 43, 7), "git version 2.43.7")
    )
    with pytest.raises(git_process.GitCommandError):
        asyncio.run(shallow.merge_base_answer(target, replica["M5"], replica["H1"]))


@pytest.mark.parametrize("version", [(2, 43, 7), (2, 50, 1)])
@pytest.mark.parametrize("shallow_boundary", [False, True])
def test_a_complete_criss_cross_graph_keeps_either_best_merge_base(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    version: tuple[int, int, int],
    shallow_boundary: bool,
) -> None:
    from metabrowser.git import shallow
    from metabrowser.git.process import repository_store_target

    replica = build_linear(tmp_path / "replica")
    tree = pinned_git(replica.origin, "rev-parse", f"{replica['M1']}^{{tree}}")

    def commit(name: str, *parents: str) -> str:
        args = ["commit-tree", tree, "-m", name]
        for parent in parents:
            args.extend(("-p", parent))
        return pinned_git(replica.origin, *args)

    a = commit("a", replica["M1"])
    b = commit("b", replica["M1"])
    left = commit("left", a, b)
    right = commit("right", b, a)
    if shallow_boundary:
        (replica.origin / "shallow").write_text(replica["M1"] + "\n", encoding="ascii")
    monkeypatch.setattr(git_process, "detect_git_version", lambda: (version, "git version test"))
    target = repository_store_target(git_dir=replica.origin)
    answer = asyncio.run(shallow.merge_base_answer(target, left, right))
    assert answer.certain
    assert answer.merge_base in {a, b}


def test_a_running_pull_fetch_requires_its_store_record(linear: _Stand) -> None:
    checkout = clone_checkout(linear.replica, linear.tmp_path / "checkout")
    linear.pull("--checkout", str(checkout))
    published = asyncio.run(_inspect(linear))
    before = linear.store_refs()
    (linear.store.parent / "store.yml").unlink()
    with pytest.raises(pull_refs.PullRefError) as raised:
        asyncio.run(pull_refs.fetch_pull_head(published, 1))
    assert raised.value.state == "fetch_failed"
    assert linear.store_refs() == before


def test_a_lender_whose_boundary_became_a_fifo_is_refused_before_git(linear: _Stand) -> None:
    from metabrowser.cache.lender import lender_problem

    checkout = clone_checkout(linear.replica, linear.tmp_path / "checkout")
    linear.pull("--checkout", str(checkout))
    published = asyncio.run(_inspect(linear))
    assert published.lender is not None
    os.mkfifo(checkout / ".git" / "shallow")
    assert lender_problem(published.lender) is not None


def test_a_refused_boundary_replace_leaves_no_temporary_symlink(
    linear: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    from metabrowser.cache.lender import attach_lender

    checkout = clone_checkout(linear.replica, linear.tmp_path / "checkout")
    linear.pull("--checkout", str(checkout))
    published = asyncio.run(_inspect(linear))
    assert published.lender is not None
    replace = os.replace

    def refuse(source: Any, destination: Any) -> None:
        if Path(destination) == linear.store / "shallow":
            raise PermissionError("injected boundary publication refusal")
        replace(source, destination)

    monkeypatch.setattr(os, "replace", refuse)
    with pytest.raises(PermissionError):
        attach_lender(linear.store, published.lender)
    assert not list(linear.store.glob(".shallow.*"))


def test_no_history_is_uncertain_if_the_boundary_moves_during_its_verification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from metabrowser.git import shallow
    from metabrowser.git.process import repository_store_target

    replica = build_linear(tmp_path / "replica")
    target = repository_store_target(git_dir=replica.origin)
    real = shallow.run_git

    async def cutting(args: list[str], **kwargs: Any) -> bytes:
        if args[0] == "merge-base":
            raise git_process.GitCommandError(args, 1, "")
        if args[0] == "rev-list":
            (replica.origin / "shallow").write_text(replica["M4"] + "\n", encoding="ascii")
        return await real(args, **kwargs)

    monkeypatch.setattr(shallow, "run_git", cutting)
    answer = asyncio.run(shallow.merge_base_answer(target, replica["M5"], replica["H1"]))
    assert not answer.certain


@pytest.mark.parametrize("index_version", [1, 2])
def test_a_complete_pack_index_does_not_claim_a_collected_object(
    linear: _Stand, index_version: int
) -> None:
    from metabrowser.cache.lender import collection_doubt

    checkout, files = _no_file_tips_and_unreadable_packs(linear)
    for path in files:
        if path.suffix == ".pack":
            pinned_git(checkout, "index-pack", f"--index-version={index_version}", str(path))
    lender = StoreLender(
        objects=str(checkout / ".git" / "objects"), checkout=str(checkout), remote="origin"
    )
    assert collection_doubt(lender, ["f" * 40]) is None


@pytest.mark.parametrize("damage", ["partial", "alternates", "format", "changed"])
def test_borrowing_only_acquisition_never_falls_back_to_a_clone(
    linear: _Stand, damage: str
) -> None:
    from metabrowser.cache import acquire

    checkout = clone_checkout(linear.replica, linear.tmp_path / "strict-checkout")

    def spoil() -> None:
        if damage in {"partial", "changed"}:
            pinned_git(checkout, "config", "remote.origin.promisor", "true")
        elif damage == "alternates":
            (checkout / ".git/objects/info/alternates").write_text("/unavailable\n")
        else:
            pinned_git(checkout, "config", "extensions.objectFormat", "sha256")

    if damage != "changed":
        spoil()
    else:
        original = acquire.remote_url_for

        def changed(source: GitSource) -> str:
            spoil()
            return original(source)

        linear.monkeypatch.setattr(acquire, "remote_url_for", changed)
    before = fingerprint(checkout)
    phases: list[str] = []
    with pytest.raises(CheckoutRefusedError):
        asyncio.run(
            acquire_source(
                SOURCE,
                home=linear.home,
                checkout=checkout,
                allow_clone_fallback=False,
                on_phase=phases.append,
            )
        )
    assert not any(phase.startswith("fetching") for phase in phases), phases
    assert not linear.store.exists()
    if damage != "changed":
        assert fingerprint(checkout) == before


def test_borrowing_only_acquisition_reuses_an_existing_full_store(linear: _Stand) -> None:
    from metabrowser.cache import acquire

    full = asyncio.run(acquire_source(SOURCE, home=linear.home))
    checkout = clone_checkout(linear.replica, linear.tmp_path / "strict-checkout")
    pinned_git(checkout, "config", "remote.origin.promisor", "true")
    before = fingerprint(checkout)

    async def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("a healthy full store must not acquire again")

    linear.monkeypatch.setattr(acquire, "acquire_into_staging", forbidden)
    reused = asyncio.run(
        acquire_source(SOURCE, home=linear.home, checkout=checkout, allow_clone_fallback=False)
    )
    assert reused.git_dir == full.git_dir and reused.lender is None
    assert fingerprint(checkout) == before


@pytest.mark.parametrize("damage", ["missing", "corrupt", "origin_missing"])
def test_explicit_recovery_restores_observed_blob_ids_without_writing_checkout(
    linear: _Stand, damage: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    import zlib

    from metabrowser.cache.object_recovery import recover_comparison_objects
    from metabrowser.git.object_failures import observed_object_failures
    from metabrowser.git.process import repository_store_target
    from metabrowser.git.tree_source import GitObjectUnavailableError, read_store_blob
    from tests.git_pin_harness import pinned_client

    replica = linear.replica
    work = replica.origin.parent / "source"
    pinned_git(work, "checkout", "-q", "pr")
    (work / "m").write_text("changed in the pull request\n")
    pinned_git(work, "commit", "-qam", "change existing file")
    head = pinned_git(work, "rev-parse", "HEAD")
    pinned_git(work, "push", "-q", str(replica.origin), "HEAD:refs/pull/1/head")
    linear.answer(scenario_for(replica, base=replica["M5"], head=head, earlier=replica["H1"]))
    checkout = clone_checkout(replica, linear.tmp_path / "checkout")
    aside = linear.tmp_path / "aside"
    aside.mkdir()
    for path in (checkout / ".git/objects/pack").iterdir():
        shutil.move(path, aside / path.name)
    for pack in aside.glob("*.pack"):
        with pack.open("rb") as stream:
            subprocess.run(
                ["git", "unpack-objects", "-q"],
                cwd=checkout,
                stdin=stream,
                check=True,
                capture_output=True,
                env=pinned_git_env(),
            )
    envelope = linear.pull("--checkout", str(checkout))
    base = envelope["record"]["comparison"]["base"]
    oid = pinned_git(checkout, "rev-parse", f"{base}:m")
    authentic = pinned_git(checkout, "cat-file", "blob", oid).encode() + b"\n"
    loose = checkout / ".git/objects" / oid[:2] / oid[2:]
    assert loose.exists()
    if damage == "corrupt":
        forged = b"forged lender bytes\n"
        loose.unlink()
        loose.write_bytes(zlib.compress(b"blob " + str(len(forged)).encode() + b"\0" + forged))
    else:
        loose.unlink()
    if damage == "origin_missing":
        (replica.origin / "objects" / oid[:2] / oid[2:]).unlink()
    before = fingerprint(checkout)
    published = asyncio.run(acquire_source(SOURCE, home=linear.home))
    assert published is not None
    target = repository_store_target(git_dir=published.git_dir)
    commits = (base, head)
    route = f"/api/plugin/diff/comparison?left={base}&right={head}&base_policy=merge_base"
    monkeypatch.setattr(sidekick, "_COMPARISONS", ComparisonCache())

    async def run() -> None:
        # Commit negotiation claims success although the descendant is still missing.
        if damage == "missing":
            await pull_refs.fetch_commit(published, head)
            with pytest.raises(GitObjectUnavailableError):
                await read_store_blob(target, oid)
        async with pinned_client(published.git_dir, head) as (client, _subject):
            if damage == "corrupt":
                # Another file's request does not scan/hash this whole manifest.
                untouched = await client.get(route + "&file=p")
                assert untouched.status_code == 200, untouched.text
                assert sidekick._COMPARISONS.sizes()["bodies"] == 1
            response = await client.get(route)
            assert response.status_code == 409, response.text
            expected = "object_corrupt" if damage == "corrupt" else "object_unavailable"
            assert response.json()["error"] == expected
            if damage == "corrupt":
                assert sidekick._COMPARISONS.sizes()["bodies"] == 0
                assert sidekick._COMPARISONS.sizes()["manifests"] == 0
            pending = observed_object_failures.pending(target, commits)
            assert [failure.oid for failure in pending] == [oid]
            # Recovery must keep the displayed endpoints even after the PR ref moves.
            pinned_git(replica.origin, "update-ref", "refs/pull/1/head", replica["M5"])
            if damage == "missing":
                assert await recover_comparison_objects(published, commits) == pending
                assert await read_store_blob(target, oid) == authentic
                assert observed_object_failures.pending(target, commits) == ()
                ready = await client.get(route)
                assert ready.status_code == 200, ready.text
                assert ready.json()["patches"]
            else:
                with pytest.raises(pull_refs.PullRefError) as refused:
                    await recover_comparison_objects(published, commits)
                expected = "object_corrupt" if damage == "corrupt" else "commits_unavailable"
                assert refused.value.state == expected
                assert observed_object_failures.pending(target, commits) == pending
        assert fingerprint(checkout) == before

    asyncio.run(run())
