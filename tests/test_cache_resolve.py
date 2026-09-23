"""Ref-and-path splitting and resolution against a real mirror of a ``file://`` origin."""

from __future__ import annotations

import asyncio
import os
import shutil
from pathlib import Path

import pytest

from metabrowser.cache.acquire import PublishedSource, acquire_source
from metabrowser.cache.resolve import (
    MAX_REF_CANDIDATES,
    RefCandidate,
    ResolvedSelection,
    UnresolvedSelection,
    is_valid_ref_name,
    ref_candidates,
    resolve_commit_id,
    resolve_ref_and_path,
    resolve_selection,
)
from metabrowser.cache.urls import GitSource, RepositorySelection, classify_root_argument
from metabrowser.git.process import repository_store_target
from tests.github_origin import FIRST_COMMIT, SECOND_COMMIT, github_origin
from tests.test_cache_acquire import _allow_installed_git

pytestmark = [
    pytest.mark.skipif(shutil.which("git") is None, reason="git executable is required"),
    pytest.mark.skipif(os.name != "posix", reason="owner-only cache is POSIX-only"),
]


@pytest.mark.parametrize(
    "name",
    ["main", "release/v1", "v1.0", "feature/x-y_z", "a.b", "@x", "x@y", "café", "v1./x"],
)
def test_valid_ref_names(name: str) -> None:
    assert is_valid_ref_name(name)


@pytest.mark.parametrize(
    "name",
    [
        "",
        "@",
        "a..b",
        "a@{1}",
        ".hidden",
        "a/.hidden",
        "a.lock",
        "a/b.lock/c",
        "a/",
        "/a",
        "a//b",
        "a.",
        "a b",
        "a~1",
        "a^",
        "a:b",
        "a?",
        "a*",
        "a[",
        "a\\b",
        "a\x7f",
        "a\tb",
        ":/text",
        "HEAD@{upstream}",
        "x^{/msg}",
    ],
)
def test_invalid_ref_names_never_become_candidates(name: str) -> None:
    assert not is_valid_ref_name(name)


def test_one_candidate_per_leading_segment() -> None:
    segments = (b"release", b"v1", b"docs", b"guide.md")
    assert ref_candidates(segments) == (
        RefCandidate("release", (b"v1", b"docs", b"guide.md")),
        RefCandidate("release/v1", (b"docs", b"guide.md")),
        RefCandidate("release/v1/docs", (b"guide.md",)),
        RefCandidate("release/v1/docs/guide.md", ()),
    )


def test_candidates_stop_at_the_cap_and_skip_invalid_names() -> None:
    many = tuple(f"s{index}".encode() for index in range(MAX_REF_CANDIDATES + 5))
    assert len(ref_candidates(many)) == MAX_REF_CANDIDATES
    assert [c.name for c in ref_candidates((b"a", b".b", b"c"))] == ["a"]
    assert [c.name for c in ref_candidates((b"v1.", b"x"))] == ["v1./x"]


def test_an_undecodable_segment_ends_the_candidates() -> None:
    assert [c.name for c in ref_candidates((b"ok", b"\xff", b"c"))] == ["ok"]


@pytest.fixture
def mirror(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> PublishedSource:
    _allow_installed_git(monkeypatch)
    origin = github_origin(tmp_path)
    source = classify_root_argument(f"file://{origin.resolve()}")
    assert isinstance(source, GitSource)
    return asyncio.run(acquire_source(source, home=tmp_path / "home"))


def _resolve(
    published: PublishedSource, *segments: bytes
) -> ResolvedSelection | UnresolvedSelection:
    target = repository_store_target(git_dir=published.git_dir)
    return asyncio.run(resolve_ref_and_path(target, segments))


def test_a_branch_whose_name_contains_a_slash(mirror: PublishedSource) -> None:
    assert _resolve(mirror, b"release", b"v1", b"docs", b"v1.md") == ResolvedSelection(
        via="branch",
        name="release/v1",
        ref="refs/remotes/origin/release/v1",
        commit=SECOND_COMMIT,
        path=(b"docs", b"v1.md"),
    )


def test_a_branch_wins_over_a_tag_of_the_same_name(mirror: PublishedSource) -> None:
    resolved = _resolve(mirror, b"same", b"README.md")
    assert isinstance(resolved, ResolvedSelection)
    assert (resolved.via, resolved.commit) == ("branch", FIRST_COMMIT)


def test_explicit_namespaces_pick_the_tag_or_the_branch(mirror: PublishedSource) -> None:
    tag = _resolve(mirror, b"refs", b"tags", b"same", b"README.md")
    branch = _resolve(mirror, b"refs", b"heads", b"same", b"README.md")
    assert isinstance(tag, ResolvedSelection) and isinstance(branch, ResolvedSelection)
    assert (tag.via, tag.commit, tag.path) == ("tag", SECOND_COMMIT, (b"README.md",))
    assert (branch.via, branch.commit) == ("branch", FIRST_COMMIT)


def test_an_annotated_tag_is_peeled_to_its_commit(mirror: PublishedSource) -> None:
    resolved = _resolve(mirror, b"v1.0", b"docs")
    assert isinstance(resolved, ResolvedSelection)
    assert (resolved.via, resolved.name, resolved.commit) == ("tag", "v1.0", SECOND_COMMIT)
    light = _resolve(mirror, b"light")
    assert isinstance(light, ResolvedSelection)
    assert (light.via, light.commit, light.path) == ("tag", FIRST_COMMIT, ())


def test_a_tag_that_names_a_tree_is_not_a_commit(mirror: PublishedSource) -> None:
    assert _resolve(mirror, b"tree-tag", b"README.md") == UnresolvedSelection("not_a_commit")


def test_a_branch_named_like_a_commit_id_wins_over_the_commit(mirror: PublishedSource) -> None:
    resolved = _resolve(mirror, FIRST_COMMIT[:4].encode(), b"docs")
    assert isinstance(resolved, ResolvedSelection)
    assert (resolved.via, resolved.commit) == ("branch", SECOND_COMMIT)


def test_full_and_abbreviated_commit_ids(mirror: PublishedSource) -> None:
    full = _resolve(mirror, SECOND_COMMIT.encode(), b"docs", b"v1.md")
    short = _resolve(mirror, FIRST_COMMIT[:7].upper().encode(), b"README.md")
    assert full == ResolvedSelection(
        via="commit", name=None, ref=None, commit=SECOND_COMMIT, path=(b"docs", b"v1.md")
    )
    assert isinstance(short, ResolvedSelection)
    assert (short.via, short.commit, short.path) == ("commit", FIRST_COMMIT, (b"README.md",))


def test_missing_refs_and_commits_ask_for_one_fetch(mirror: PublishedSource) -> None:
    missing = _resolve(mirror, b"nope", b"README.md")
    assert isinstance(missing, UnresolvedSelection)
    assert missing.reason == "ref_not_found" and missing.needs_fetch
    target = repository_store_target(git_dir=mirror.git_dir)
    absent = asyncio.run(resolve_commit_id(target, "0" * 40))
    assert isinstance(absent, UnresolvedSelection)
    assert absent.reason == "commit_not_found" and absent.needs_fetch
    tree = asyncio.run(resolve_commit_id(target, "5a2a414f"))
    assert isinstance(tree, UnresolvedSelection)
    assert tree.reason == "not_a_commit" and not tree.needs_fetch


@pytest.mark.parametrize(
    "segments",
    [
        (b":", b"README.md"),
        (b"HEAD@{1}", b"README.md"),
        (b"topic^{", b"README.md"),
        (b"topic~1",),
        (b"..", b"topic"),
    ],
)
def test_revision_syntax_in_a_url_resolves_nothing(
    mirror: PublishedSource, segments: tuple[bytes, ...]
) -> None:
    assert _resolve(mirror, *segments) == UnresolvedSelection("ref_not_found")


def test_repository_and_pull_request_selections_pin_the_default_branch(
    mirror: PublishedSource,
) -> None:
    target = repository_store_target(git_dir=mirror.git_dir)
    for selection in (
        RepositorySelection(),
        RepositorySelection(kind="pull_request", pull_request=7),
    ):
        resolved = asyncio.run(
            resolve_selection(
                target,
                selection,
                default_ref=mirror.default_remote_ref,
                default_revision=mirror.default_revision,
            )
        )
        assert resolved == ResolvedSelection(
            via="default",
            name="topic",
            ref="refs/remotes/origin/topic",
            commit=FIRST_COMMIT,
        )
    commit = asyncio.run(
        resolve_selection(
            target,
            RepositorySelection(kind="commit", commit=SECOND_COMMIT[:10]),
            default_ref=mirror.default_remote_ref,
            default_revision=mirror.default_revision,
        )
    )
    assert isinstance(commit, ResolvedSelection) and commit.commit == SECOND_COMMIT
