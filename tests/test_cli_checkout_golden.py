"""Golden CLI transcript: a pull request beside a checkout that lends its objects.

Each command runs the production CLI in-process, as ``tests/test_cli_github_pull_golden.py``
does, with the same substitutions: ``remote_url_for`` fetches
``https://github.com/octo/demo`` from a local origin, a fake ``gh`` answers for the pull
request, and the clock is fixed. The origins and checkouts are the replicas in
``tests/checkout_replica.py``. Acquisition needs a Git the floor admits, so this is a driver
rather than a tryscript. ``<ROOT>`` is the sandbox and ``<HOME>`` the application home.

A pull envelope carries the whole record, so what this prints of one is the part that is the
subject here: the comparison and why there is none. The record itself is pinned by
``tests/golden/cli-github-pull-refresh.txt``, and ``tests/test_checkout_overlay.py`` holds
that it is the same on an overlay.
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from metabrowser.cache import pull_refs
from metabrowser.cache.identity import repository_store_id, source_identity, store_key
from metabrowser.cache.paths import store_directory
from metabrowser.cache.urls import GitSource
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
    Labels,
    check_golden,
    isolate_cli,
    label_home,
    normalize_pull_comparison_scopes,
    pinned_git,
    quoted,
    run_metab,
)
from tests.required_tools import needs_git

pytestmark = [
    needs_git,
    pytest.mark.skipif(os.name != "posix", reason="owner-only cache is POSIX-only"),
]

PULL = f"{CANONICAL}/pull/1"
STATUS = "/api/source/status"
STORES = "/api/cache/stores"
REFS = "/api/source/refs?kind=branch"
PULL_ROUTE = "/api/plugin/github/pull?number=1"


class _Session:
    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self.tmp_path = tmp_path
        self.monkeypatch = monkeypatch
        self.home = isolate_cli(tmp_path, monkeypatch).home
        self.replica: Replica | None = None
        self.blocks: list[str] = []
        monkeypatch.setattr("metabrowser.builtin_plugins.github.pulls.utc_now", lambda: FETCHED_AT)
        monkeypatch.setattr("metabrowser.cache.acquire.remote_url_for", self._remote_url_for)

    def _remote_url_for(self, source: GitSource) -> str:
        if source.normalized == CANONICAL and self.replica is not None:
            return self.replica.url
        return source.normalized

    def serve_replica(self, replica: Replica, *, base: str, head: str, earlier: str) -> None:
        self.replica = replica
        (self.tmp_path / "gh").mkdir(exist_ok=True)
        answers = scenario_for(replica, base=base, head=head, earlier=earlier)
        for name, value in install_fake_gh(self.tmp_path / "gh", answers).items():
            self.monkeypatch.setenv(name, value)

    def fresh_home(self, name: str) -> None:
        self.home = self.tmp_path / name
        self.monkeypatch.setenv("METABROWSER_CACHE_DIR", str(self.home))

    @property
    def store(self) -> Path:
        identity = repository_store_id(source_identity("https", CANONICAL), "sha1")
        return self.home / store_directory(store_key(identity)) / "repository.git"

    def _labelled(self, text: str) -> str:
        text = label_home(text, self.home)
        text = text.replace(str(self.tmp_path.resolve()), "<ROOT>")
        text = text.replace(str(self.tmp_path), "<ROOT>")
        return Labels().apply(text)

    def say(self, text: str) -> None:
        self.blocks.append(f"## {text}\n")

    def _show(self, result: Invocation, args: tuple[str, ...], stdout: str) -> None:
        shown = replace(result, stdout=self._labelled(stdout), stderr=self._labelled(result.stderr))
        command = " ".join(quoted(arg) for arg in args)
        self.blocks.append(shown.block(self._labelled(command)))

    def run(self, *args: str) -> Invocation:
        result = run_metab(args)
        self._show(result, args, result.stdout)
        return result

    def comparison(self, *args: str) -> Invocation:
        """The pull route, printing what the record says about Files changed."""

        all_args = (PULL, *args, "--api", PULL_ROUTE)
        result = run_metab(all_args)
        assert result.exit_code == 0, result.stderr
        envelope = result.payload()
        record = envelope["record"]
        summary = {
            "state": envelope["state"],
            "comparison_route": envelope["comparison_route"],
            "comparison": record["comparison"],
            "unavailable": record["unavailable"],
        }
        self._show(result, all_args, json.dumps(summary, indent=2) + "\n")
        return result

    def files_changed(self, route: str) -> None:
        result = run_metab((PULL, "--api", route))
        assert result.exit_code == 0, result.stderr
        changed = sorted(
            (change.get("new") or change.get("old"))["path"]
            for change in result.payload()["manifest"]["files"]
        )
        self.blocks.append(f"# Files changed: {changed}\n")

    def store_refs(self) -> None:
        listed = pinned_git(self.store, "for-each-ref", "--format=%(refname) %(objectname)")
        self.blocks.append(f"# the store's refs\n{listed}\n")


def _write_checkout_unchanged(session: _Session, checkout: Path, before: Any) -> None:
    assert fingerprint(checkout) == before
    session.blocks.append("# the checkout's .git is unchanged, byte for byte\n")


def test_golden_a_pull_request_beside_a_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = _Session(tmp_path, monkeypatch)
    linear = build_linear(tmp_path / "linear")
    session.serve_replica(linear, base=linear["M5"], head=linear["H1"], earlier=linear["M4"])
    checkout = clone_checkout(linear, tmp_path / "checkout")
    worktree = tmp_path / "feature-x"
    pinned_git(checkout, "worktree", "add", "-q", "-b", "feature-x", str(worktree))
    # A branch and a tag only the checkout has, under the origin's name.
    planted = pinned_git(checkout, "rev-parse", "HEAD~2")
    pinned_git(checkout, "update-ref", "refs/remotes/origin/release-2.0", planted)
    pinned_git(checkout, "tag", "v9.9", planted)
    before = fingerprint(checkout)

    session.say("Name a linked worktree: its common directory lends, and nothing is copied.")
    session.run(PULL, "--checkout", str(worktree), "--no-serve")
    session.store_refs()
    session.say("Remembered: no flag, from any directory.")
    assert session.run(PULL, "--api", STATUS).exit_code == 0
    session.run(CANONICAL, "--api", REFS)
    session.run(CANONICAL, "--api", STORES)
    _write_checkout_unchanged(session, checkout, before)

    session.say("A published store wins: another checkout named changes nothing.")
    other = clone_checkout(linear, tmp_path / "other")
    session.run(CANONICAL, "--checkout", str(other), "--no-serve")

    session.say("Inside a checkout without the flag: a full clone, and the flag once.")
    session.fresh_home("home-inside")
    below = checkout / "deep"
    below.mkdir()
    monkeypatch.chdir(below)
    session.run(CANONICAL, "--no-serve")
    session.run(CANONICAL, "--no-serve")
    session.run(CANONICAL, "--api", STORES)
    monkeypatch.chdir(tmp_path)

    session.say("A full mirror already here is kept.")
    session.run(CANONICAL, "--checkout", str(checkout), "--no-serve")

    session.say("A checkout that cannot lend falls to a full clone and says why.")
    for name, setup in (
        ("partial", lambda path: pinned_git(path, "config", "extensions.partialClone", "origin")),
        ("promisor", lambda path: pinned_git(path, "config", "remote.origin.promisor", "true")),
        (
            "alternates",
            lambda path: (path / ".git/objects/info/alternates").write_text("/elsewhere\n"),
        ),
        ("format", lambda path: pinned_git(path, "config", "extensions.objectFormat", "sha256")),
    ):
        session.fresh_home(f"home-{name}")
        spoiled = clone_checkout(linear, tmp_path / f"spoiled-{name}")
        setup(spoiled)
        session.run(CANONICAL, "--checkout", str(spoiled), "--no-serve")

    session.say("A path that is no checkout of the repository is refused, and says what it found.")
    session.fresh_home("home-refused")
    elsewhere = clone_checkout(linear, tmp_path / "elsewhere")
    pinned_git(elsewhere, "remote", "set-url", "origin", "https://user:secret@github.com/a/b.git")
    pinned_git(elsewhere, "remote", "add", "upstream", "git@github.com:c/d.git")
    session.run(CANONICAL, "--checkout", str(elsewhere), "--no-serve")
    empty = tmp_path / "empty"
    empty.mkdir()
    session.run(CANONICAL, "--checkout", str(empty), "--no-serve")
    session.run(str(empty), "--checkout", str(empty), "--api", STATUS)

    session.say("A checkout whose remote is a fork lends through the remote that is the source.")
    session.fresh_home("home-fork")
    fork = clone_checkout(linear, tmp_path / "fork")
    pinned_git(fork, "remote", "rename", "origin", "upstream")
    pinned_git(fork, "remote", "add", "origin", "https://github.com/forker/demo.git")
    session.run(CANONICAL, "--checkout", str(fork), "--no-serve")
    remote = (session.store.parent / "store.yml").read_text(encoding="utf-8")
    assert "remote: upstream" in remote

    # ── Merge base on a shallow store ───────────────────────────────
    heavy = build_merge_heavy(tmp_path / "heavy")
    session.serve_replica(heavy, base=heavy["M7"], head=heavy["H2"], earlier=heavy["H1"])

    session.say(
        "A depth-3 clone of a merge-heavy history, where Git alone answers A1 and the truth "
        f"is A4 ({heavy['A4']}). With no rounds of deepening allowed: base_uncertain, no diff."
    )
    session.fresh_home("home-depth-3")
    shallow = clone_checkout(heavy, tmp_path / "shallow", "--depth", "3", "--no-single-branch")
    before = fingerprint(shallow)
    with monkeypatch.context() as patched:
        patched.setattr(pull_refs, "DEEPEN_ROUNDS", ())
        session.comparison("--checkout", str(shallow))
    session.run(PULL, "--api", STATUS)
    session.say("The same again, deepening: one round, in the store. Certain at A4.")
    pinned_git(session.store, "update-ref", "-d", "refs/pull/1/head")
    answered = session.run(PULL, "--no-serve")
    assert answered.exit_code == 0
    settled = session.comparison()
    session.files_changed(settled.payload()["comparison_route"])
    _write_checkout_unchanged(session, shallow, before)

    session.say("A depth-1 clone: Git's answer is empty, which is uncertain and not no history.")
    session.fresh_home("home-depth-1")
    shallowest = clone_checkout(
        heavy, tmp_path / "shallowest", "--depth", "1", "--no-single-branch"
    )
    with monkeypatch.context() as patched:
        patched.setattr(pull_refs, "DEEPEN_ROUNDS", ())
        session.comparison("--checkout", str(shallowest))
    pinned_git(session.store, "update-ref", "-d", "refs/pull/1/head")
    assert run_metab((PULL, "--no-serve")).exit_code == 0
    settled = session.comparison()
    session.files_changed(settled.payload()["comparison_route"])

    session.say(
        "Offline: a comparison the record cannot settle stays base_uncertain, and asking the "
        "comparison route for the tips directly does not guess either."
    )
    session.fresh_home("home-offline")
    offline = clone_checkout(heavy, tmp_path / "offline", "--depth", "3", "--no-single-branch")
    with monkeypatch.context() as patched:
        patched.setattr(pull_refs, "DEEPEN_ROUNDS", ())
        session.comparison("--checkout", str(offline))
        session.run(
            PULL,
            "--api",
            f"/api/plugin/diff/comparison?left={heavy['M7']}&right={heavy['H2']}"
            "&base_policy=merge_base",
        )
        session.say(
            f"A commit at the boundary, A5 ({heavy['A5']}), changes one line of f; Git grafts "
            "it into a root. Its own diff is refused as parent_unavailable rather than shown "
            "against the empty tree, and its commit detail reports what it changed as unknown."
        )
        session.run(PULL, "--api", f"/api/plugin/diff/comparison?revision={heavy['A5']}")
        session.run(PULL, "--api", f"/api/git/commit/{heavy['A5']}")

    # ── The sweep ───────────────────────────────────────────────────
    session.say(
        "A branch the origin deleted and the checkout collected leaves a dangling ref that "
        "would wedge every fetch. The refresh sweeps it first."
    )
    session.fresh_home("home-sweep")
    session.serve_replica(linear, base=linear["M5"], head=linear["H1"], earlier=linear["M4"])
    pinned_git(linear.origin, "branch", "-q", "feat", linear["M3"])
    feature = tmp_path / "feat-work"
    pinned_git(linear.origin, "worktree", "add", "-q", str(feature), "feat")
    (feature / "f").write_text("f\n", encoding="utf-8")
    pinned_git(feature, "add", "f")
    pinned_git(feature, "commit", "-qm", "F1")
    pinned_git(linear.origin, "worktree", "remove", "--force", str(feature))
    swept = clone_checkout(linear, tmp_path / "swept")
    session.run(CANONICAL, "--checkout", str(swept), "--no-serve")
    session.store_refs()
    pinned_git(linear.origin, "branch", "-q", "-D", "feat")
    pinned_git(swept, "remote", "set-url", "origin", linear.url)
    pinned_git(swept, "fetch", "-q", "--prune", "origin")
    pinned_git(swept, "remote", "set-url", "origin", REMOTE_SPELLING)
    pinned_git(swept, "reflog", "expire", "--expire-unreachable=now", "--all")
    pinned_git(swept, "gc", "-q", "--prune=now")
    body = tmp_path / "refresh.json"
    body.write_text("{}\n", encoding="utf-8")
    refreshed = run_metab((CANONICAL, "--api", "/api/source/refresh", "--data", str(body)))
    assert refreshed.exit_code == 0, refreshed.stderr
    last = refreshed.stdout.rpartition("after:")[2]
    outcome = json.loads(last[last.index("{") :])["last_outcome"]["outcome"]
    session.blocks.append(f"# the refresh's outcome: {outcome}\n")
    session.store_refs()

    # ── A checkout that has gone ────────────────────────────────────
    session.say("The checkout moved: a typed refusal at open, with the recorded path and repair.")
    moved = tmp_path / "moved"
    shutil.move(swept, moved)
    session.run(PULL, "--api", STATUS)
    session.run(PULL, "--show", "m")
    session.say("The cache routes read records and no object, so they still answer.")
    session.run(CANONICAL, "--api", STORES)
    session.say("Naming where it is now repairs it, and it is remembered.")
    session.run(CANONICAL, "--checkout", str(moved), "--no-serve")
    session.run(CANONICAL, "--no-serve")
    session.run(PULL, "--checkout", str(tmp_path / "absent"), "--no-serve")

    session.say("A store whose alternates file disagrees with its record is refused.")
    (session.store / "objects" / "info" / "alternates").write_text(
        f"{tmp_path}/elsewhere/objects\n", encoding="utf-8"
    )
    session.run(CANONICAL, "--no-serve")
    session.run(str(empty), "--api", STORES)

    # ── A commit the checkout collected ─────────────────────────────
    session.say(
        f"The checkout collected an ancestor, M3 ({linear['M3']}), that the store never held: "
        "the comparison needs it, and the record says commits_unavailable, never "
        "no_merge_base."
    )
    session.fresh_home("home-collected")
    collected = clone_checkout(linear, tmp_path / "collected")
    _unpack_objects(collected, tmp_path / "collected-packs")
    session.comparison("--checkout", str(collected))
    (collected / ".git" / "objects" / linear["M3"][:2] / linear["M3"][2:]).unlink()
    for record in session.home.glob("sources/*/pulls/1*.json"):
        record.unlink()
    session.comparison()

    rendered = normalize_pull_comparison_scopes("\n".join(session.blocks))
    check_golden("cli-checkout-overlay.txt", rendered)


def _unpack_objects(checkout: Path, aside: Path) -> None:
    """The clone's packs unpacked into loose objects, so that one can be deleted."""

    import subprocess

    from tests.golden_harness import pinned_git_env

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
