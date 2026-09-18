"""Root-argument classification and provider-reducer arbitration."""

from __future__ import annotations

import pytest

from metabrowser.cache.urls import (
    DEFAULT_PORTS,
    GitSource,
    LocalPath,
    ReducerArbitrationError,
    ReducerOutcome,
    RejectedRoot,
    classify_root_argument,
)


def test_file_url_is_a_git_source_and_a_bare_path_is_not() -> None:
    source = classify_root_argument("file:///srv/git/repo.git")
    assert isinstance(source, GitSource)
    assert source.transport == "file"
    assert source.form == "url"
    assert source.normalized == "file:///srv/git/repo.git"
    path = classify_root_argument("/srv/git/repo.git")
    assert isinstance(path, LocalPath)
    assert path.value == "/srv/git/repo.git"


def test_file_localhost_folds_to_the_empty_authority() -> None:
    source = classify_root_argument("FILE://LocalHost/srv/git/repo.git/")
    assert source == GitSource(transport="file", form="url", normalized="file:///srv/git/repo.git")


def test_file_authority_that_is_not_this_machine_is_rejected() -> None:
    rejected = classify_root_argument("file://fileserver/share/repo.git")
    assert rejected == RejectedRoot("file_authority_not_local")


def test_https_and_ssh_remain_git_sources() -> None:
    https = classify_root_argument("HTTPS://Example.COM:443/Owner/Repo.git")
    assert https == GitSource(
        transport="https",
        form="url",
        normalized="https://example.com/Owner/Repo.git",
    )
    scp = classify_root_argument("git@example.com:owner/repo.git")
    assert scp == GitSource(
        transport="ssh",
        form="scp",
        normalized="git@example.com:owner/repo.git",
    )


def test_defaults_match_the_frozen_https_and_ssh_ports() -> None:
    assert DEFAULT_PORTS == {"https": "443", "ssh": "22"}


class _ClaimingReducer:
    def __init__(self, clone_url: str) -> None:
        self.clone_url = clone_url

    def reduce(self, value: str) -> ReducerOutcome | None:
        if "github.com" in value:
            return ReducerOutcome(clone_url=self.clone_url)
        return None


def test_one_reducer_claim_replaces_the_input_before_the_grammar() -> None:
    classified = classify_root_argument(
        "https://github.com/owner/repo/pull/12",
        reducers=(_ClaimingReducer("https://github.com/owner/repo.git"),),
    )
    assert classified == GitSource(
        transport="https",
        form="url",
        normalized="https://github.com/owner/repo.git",
    )


def test_two_reducer_claims_are_a_discovery_error() -> None:
    with pytest.raises(ReducerArbitrationError, match="2 provider URL reducers"):
        classify_root_argument(
            "https://github.com/owner/repo",
            reducers=(
                _ClaimingReducer("https://github.com/owner/repo.git"),
                _ClaimingReducer("https://github.com/owner/other.git"),
            ),
        )
