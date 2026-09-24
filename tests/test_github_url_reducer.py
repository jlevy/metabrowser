"""The GitHub URL reducer: every accepted shape, every refusal, canonical identity."""

from __future__ import annotations

import pytest

from metabrowser.builtin_plugins.github.urls import GithubUrlReducer, parse_repository_url
from metabrowser.cache.urls import (
    GitSource,
    LineSelection,
    RejectedRoot,
    RepositorySelection,
    classify_root_argument,
)

CANONICAL = "https://github.com/octo/demo"
_REDUCERS = (GithubUrlReducer(),)


def _source(value: str) -> GitSource:
    classified = classify_root_argument(value, reducers=_REDUCERS)
    assert isinstance(classified, GitSource), classified
    assert classified.transport == "https"
    return classified


def _refused(value: str) -> RejectedRoot:
    classified = classify_root_argument(value, reducers=_REDUCERS)
    assert isinstance(classified, RejectedRoot), classified
    return classified


@pytest.mark.parametrize(
    "value",
    [
        "https://github.com/octo/demo",
        "https://github.com/Octo/Demo",
        "https://github.com/octo/demo/",
        "https://github.com/octo/demo.git",
        "https://github.com/octo/demo.GIT/",
        "https://www.github.com/octo/demo",
        "HTTPS://GitHub.COM/octo/demo",
        "https://github.com:443/octo/demo",
        "https://github.com/octo/demo?tab=readme-ov-file",
        "https://github.com/octo/demo#readme",
        "git@github.com:octo/demo.git",
        "git@github.com:Octo/Demo",
        "ssh://git@github.com/octo/demo.git",
        "ssh://git@github.com:22/octo/demo",
        "ssh://git@www.github.com/octo/demo.git",
        "git@www.github.com:octo/demo.git",
    ],
)
def test_repository_spellings_share_one_canonical_source(value: str) -> None:
    source = _source(value)
    assert source.normalized == CANONICAL
    assert source.selection == RepositorySelection()
    # The selection is not part of identity: every spelling is one mirror.
    assert source == GitSource(transport="https", form="url", normalized=CANONICAL)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (
            "https://github.com/octo/demo/tree/main",
            RepositorySelection(kind="tree", ref_and_path=(b"main",)),
        ),
        (
            "https://github.com/octo/demo/tree/release/v1/docs/",
            RepositorySelection(kind="tree", ref_and_path=(b"release", b"v1", b"docs")),
        ),
        (
            "https://github.com/octo/demo/blob/main/README.md",
            RepositorySelection(kind="blob", ref_and_path=(b"main", b"README.md")),
        ),
        (
            "https://github.com/octo/demo/blob/main/README.md#L10",
            RepositorySelection(
                kind="blob",
                ref_and_path=(b"main", b"README.md"),
                lines=LineSelection(start=10, end=10),
            ),
        ),
        (
            "https://github.com/octo/demo/blob/main/README.md#L10-L20",
            RepositorySelection(
                kind="blob",
                ref_and_path=(b"main", b"README.md"),
                lines=LineSelection(start=10, end=20),
            ),
        ),
        (
            "https://github.com/octo/demo/blob/main/README.md#L10C5-L20C8",
            RepositorySelection(
                kind="blob",
                ref_and_path=(b"main", b"README.md"),
                lines=LineSelection(start=10, end=20, start_column=5, end_column=8),
            ),
        ),
        (
            "https://github.com/octo/demo/blob/main/README.md#L10C8-L10C5",
            RepositorySelection(
                kind="blob",
                ref_and_path=(b"main", b"README.md"),
                lines=LineSelection(start=10, end=10, start_column=5, end_column=8),
            ),
        ),
        (
            "https://github.com/octo/demo/blob/main/README.md#L20-L10",
            RepositorySelection(
                kind="blob",
                ref_and_path=(b"main", b"README.md"),
                lines=LineSelection(start=10, end=20),
            ),
        ),
        (
            "https://github.com/octo/demo/blob/main/README.md?plain=1&utm_source=x#L3",
            RepositorySelection(
                kind="blob",
                ref_and_path=(b"main", b"README.md"),
                lines=LineSelection(start=3, end=3),
                plain=True,
            ),
        ),
        (
            "https://github.com/octo/demo/blob/main/README.md#readme-section",
            RepositorySelection(kind="blob", ref_and_path=(b"main", b"README.md")),
        ),
        (
            "https://github.com/octo/demo/blob/main/My%20Notes/%E6%97%A5%E6%9C%AC.md",
            RepositorySelection(
                kind="blob", ref_and_path=(b"main", b"My Notes", "日本.md".encode())
            ),
        ),
        (
            "https://github.com/octo/demo/commit/ABCDEF0123",
            RepositorySelection(kind="commit", commit="abcdef0123"),
        ),
        (
            "https://github.com/octo/demo/pull/12",
            RepositorySelection(kind="pull_request", pull_request=12),
        ),
        (
            "https://github.com/octo/demo/pull/12/files",
            RepositorySelection(kind="pull_request", pull_request=12),
        ),
        (
            "https://github.com/octo/demo/pull/12/commits",
            RepositorySelection(kind="pull_request", pull_request=12),
        ),
        (
            "https://github.com/octo/demo/pull/12/commits/abcdef0",
            RepositorySelection(kind="commit", commit="abcdef0", pull_request=12),
        ),
        (
            "https://raw.githubusercontent.com/octo/demo/main/docs/a.md",
            RepositorySelection(kind="blob", ref_and_path=(b"main", b"docs", b"a.md")),
        ),
        (
            "https://raw.githubusercontent.com/Octo/Demo/refs/heads/main/a.md",
            RepositorySelection(kind="blob", ref_and_path=(b"refs", b"heads", b"main", b"a.md")),
        ),
    ],
)
def test_web_url_shapes_carry_their_selection(value: str, expected: RepositorySelection) -> None:
    source = _source(value)
    assert source.normalized == CANONICAL
    assert source.selection == expected


@pytest.mark.parametrize(
    ("value", "reason", "detail"),
    [
        ("http://github.com/octo/demo", "insecure_http", f"use {CANONICAL}"),
        ("http://github.com/", "insecure_http", "https://github.com/<owner>/<repository>"),
        ("https://github.com/", "unsupported_github_url", "github.com itself"),
        ("https://github.com/octo", "unsupported_github_url", "github.com/octo is an account"),
        ("https://github.com/settings/profile", "reserved_owner", "github.com/settings"),
        ("https://github.com/orgs/octo/repositories", "reserved_owner", "github.com/orgs"),
        ("https://github.com/octo/demo/issues/5", "unsupported_github_url", "issues pages"),
        ("https://github.com/octo/demo/actions", "unsupported_github_url", "actions pages"),
        ("https://github.com/octo/demo/zzz-token", "unsupported_github_url", "this GitHub page"),
        ("https://github.com/octo/demo/tree", "unsupported_github_url", "names a ref"),
        ("https://github.com/octo/demo/blob/main", "unsupported_github_url", "a ref and a file"),
        ("https://github.com/octo/demo/commit/xyz", "invalid_commit_id", CANONICAL),
        ("https://github.com/octo/demo/commit/abc", "invalid_commit_id", CANONICAL),
        ("https://github.com/octo/demo/commit/abcdef", "invalid_commit_id", "7 to 64"),
        ("https://github.com/octo/demo/commit/abcdef0/x", "unsupported_github_url", CANONICAL),
        ("https://github.com/octo/demo/pull/0", "invalid_pull_request", CANONICAL),
        ("https://github.com/octo/demo/pull/x", "invalid_pull_request", CANONICAL),
        ("https://github.com/octo/demo/pull/12/checks", "unsupported_github_url", CANONICAL),
        ("https://raw.githubusercontent.com/octo/demo/main", "unsupported_github_url", "raw URL"),
        ("https://github.com/o_o/demo", "invalid_owner", "owner"),
        ("https://github.com/octo/de$mo", "invalid_repository", "repository name"),
        ("https://github.com/octo/..", "invalid_repository", "repository name"),
        ("https://github.com:8443/octo/demo", "unsupported_port", CANONICAL),
        ("git@github.com:octo/demo/extra", "unsupported_github_url", CANONICAL),
        ("deploy@github.com:octo/demo.git", "invalid_user", "user git"),
        ("https://github.com/octo//demo", "empty_path_segment", "empty segment"),
        ("https://github.com/octo/demo/tree/main/%2e%2e/x", "dot_segment", "'..'"),
        ("https://github.com/octo/demo/tree/main%2Fx", "encoded_delimiter", "separator"),
        ("https://github.com/octo/demo/tree/main/%0A", "control_or_whitespace", "control"),
        ("https://github.com/octo/demo/tree/main/%zz", "invalid_percent_encoding", "escape"),
    ],
)
def test_other_shapes_are_refused_with_a_typed_reason(value: str, reason: str, detail: str) -> None:
    refused = _refused(value)
    assert refused.reason == reason
    assert refused.detail is not None and detail in refused.detail


@pytest.mark.parametrize(
    ("value", "reason"),
    [
        ("https://ghp_secret@github.com/octo/demo", "credentials_in_url"),
        ("https://user:ghp_secret@github.com/octo/demo", "credentials_in_url"),
        (
            "https://raw.githubusercontent.com/octo/demo/main/a?token=ghp_secret#L1 x",
            "control_or_whitespace",
        ),
        ("ssh://git:ghp_secret@github.com/octo/demo.git", "credentials_in_url"),
        ("https://github.com/octo/demo/blob/main/a b.md", "control_or_whitespace"),
        ("https://github.com/octo/demo\n", "control_or_whitespace"),
        ("https://github.com/octo/démo", "non_ascii"),
        ("https://github.com/octo\\demo", "backslash"),
    ],
)
def test_the_generic_checks_run_before_the_reducer_parses(value: str, reason: str) -> None:
    refused = _refused(value)
    assert refused.reason == reason
    # A refusal never repeats the argument, so a token in it stays out of the terminal.
    assert "ghp_secret" not in (refused.detail or "")
    assert "token" not in (refused.detail or "")


def test_query_parameters_are_dropped_and_never_echoed() -> None:
    source = _source("https://github.com/octo/demo/blob/main/a.md?token=ghp_secret&plain=1")
    assert source.normalized == CANONICAL
    assert "ghp_secret" not in repr(source)


@pytest.mark.parametrize(
    "value",
    [
        "https://gist.github.com/octo/abc",
        "https://github.com.example.com/octo/demo",
        "https://example.com/octo/demo",
        "git://github.com/octo/demo",
        "file:///github.com/octo/demo",
        "/srv/github.com/octo/demo",
    ],
)
def test_other_hosts_and_transports_are_not_claimed(value: str) -> None:
    assert GithubUrlReducer().reduce(value) is None


def test_exactly_one_trailing_git_is_removed() -> None:
    assert _source("https://github.com/octo/demo.git.git").normalized == f"{CANONICAL}.git"
    assert _source("git@github.com:octo/demo.GIT").normalized == CANONICAL
    assert _refused("https://github.com/octo/.git").reason == "invalid_repository"


def test_raw_url_refusals_do_not_name_github_com() -> None:
    for value in (
        "https://raw.githubusercontent.com/settings/x/main/a.md",
        "https://raw.githubusercontent.com/settings",
        "https://raw.githubusercontent.com/octo",
    ):
        refused = _refused(value)
        assert "github.com/" not in (refused.detail or ""), value
    assert _refused("https://raw.githubusercontent.com/settings/x/main/a.md").reason == (
        "reserved_owner"
    )


def test_the_fragment_spelling_round_trips() -> None:
    assert LineSelection(start=10, end=10).fragment() == "L10"
    assert LineSelection(start=10, end=20).fragment() == "L10-L20"
    assert LineSelection(10, 20, start_column=5, end_column=8).fragment() == "L10C5-L20C8"


def test_parse_repository_url_reads_only_canonical_urls() -> None:
    assert parse_repository_url(CANONICAL) == ("octo", "demo")
    assert parse_repository_url(f"{CANONICAL}/tree/main") is None
    assert parse_repository_url("https://example.com/octo/demo") is None
