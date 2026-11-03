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
PULL_ROUTE = "/api/plugin/github/pull"
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

    def traced(policy: Any = None) -> dict[str, str]:
        return {**real(policy), "GIT_TRACE": str(trace)}

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

    def traced(policy: Any = None) -> dict[str, str]:
        return {**real(policy), "GIT_TRACE": str(trace)}

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
