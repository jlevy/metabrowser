"""Provider-reducer arbitration ahead of the root-argument grammar.

The grammar itself is ``tests/fixtures/repository-cache/url-grammar.json``, replayed
case by case in ``tests/test_repository_cache_contract_fixtures.py``.
"""

from __future__ import annotations

import pytest

from metabrowser.cache.urls import (
    GitSource,
    ReducerArbitrationError,
    ReducerOutcome,
    classify_root_argument,
)


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
