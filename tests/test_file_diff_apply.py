"""Apply-oracle side of the conformance corpus, plus refusal behavior."""

from __future__ import annotations

from typing import Any

import pytest

from metabrowser.diff.apply import (
    ApplyError,
    NotFullyHydrated,
    TreeSnapshot,
    apply_change_set,
)
from metabrowser.diff.format import load_conformance_corpus, validate_document


def _apply_cases() -> list[dict[str, Any]]:
    return list(load_conformance_corpus()["apply_cases"])


@pytest.mark.parametrize("case", _apply_cases(), ids=lambda case: str(case["name"]))
def test_apply_reproduces_the_target_tree(case: dict[str, Any]) -> None:
    document = validate_document(case["document"])
    base = TreeSnapshot.from_corpus(case["base"])
    target = TreeSnapshot.from_corpus(case["target"])
    produced = apply_change_set(document, base)
    assert produced.as_corpus() == target.as_corpus()
    assert produced.tree_hash() == target.tree_hash()


def test_apply_refuses_a_non_ready_file_as_not_hydrated() -> None:
    case = next(c for c in _apply_cases() if c["name"] == "apply-add")
    raw = case["document"]
    downgraded = {
        **raw,
        "manifest": {
            **raw["manifest"],
            "files": [{**raw["manifest"]["files"][0], "availability": "deferred"}],
        },
        "patches": {},
    }
    document = validate_document(downgraded)
    with pytest.raises(NotFullyHydrated):
        apply_change_set(document, TreeSnapshot.from_corpus(case["base"]))


def test_apply_refuses_a_hunk_that_contradicts_the_base() -> None:
    case = next(c for c in _apply_cases() if c["name"] == "apply-delete")
    document = validate_document(case["document"])
    wrong_base = TreeSnapshot.from_corpus(
        {"entries": {"b.txt": {"entry_type": "file", "mode": "100644", "content_b64": "Wg=="}}}
    )
    with pytest.raises(ApplyError):
        apply_change_set(document, wrong_base)


def test_tree_hash_distinguishes_mode_and_content() -> None:
    a = TreeSnapshot.from_corpus(
        {"entries": {"x": {"entry_type": "file", "mode": "100644", "content_b64": "aGk="}}}
    )
    b = TreeSnapshot.from_corpus(
        {"entries": {"x": {"entry_type": "file", "mode": "100755", "content_b64": "aGk="}}}
    )
    c = TreeSnapshot.from_corpus(
        {"entries": {"x": {"entry_type": "file", "mode": "100644", "content_b64": "aG8="}}}
    )
    assert len({a.tree_hash(), b.tree_hash(), c.tree_hash()}) == 3
