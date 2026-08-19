"""The Python side of the File Diff Format conformance corpus.

Every validation case must parse or fail exactly as the corpus says.
The browser model runs the same corpus from ``tests/dom``, which is what
keeps the two implementations in agreement (the file-rollup pattern).
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from metabrowser.diff.format import (
    ChangeSetDocument,
    dump_document,
    load_conformance_corpus,
    load_schema,
    validate_document,
)


def _cases() -> list[dict[str, Any]]:
    return list(load_conformance_corpus()["cases"])


@pytest.mark.parametrize("case", _cases(), ids=lambda case: str(case["name"]))
def test_corpus_case_matches_expectation(case: dict[str, Any]) -> None:
    if case["expect"] == "valid":
        document = validate_document(case["document"])
        assert isinstance(document, ChangeSetDocument)
    else:
        with pytest.raises((ValidationError, ValueError)):
            validate_document(case["document"])


@pytest.mark.parametrize(
    "case",
    [case for case in _cases() if case["expect"] == "valid"],
    ids=lambda case: str(case["name"]),
)
def test_valid_documents_round_trip(case: dict[str, Any]) -> None:
    """dump(validate(x)) must itself validate and preserve the manifest."""
    document = validate_document(case["document"])
    dumped = dump_document(document)
    again = validate_document(dumped)
    assert dump_document(again) == dumped
    assert len(again.manifest.files) == len(document.manifest.files)


def test_schema_names_every_change_kind_the_model_accepts() -> None:
    """The checked-in schema and the model must agree on the taxonomy."""
    schema = load_schema()
    schema_kinds = set(schema["$defs"]["fileChange"]["properties"]["kind"]["enum"])
    from metabrowser.diff.format import ChangeKind

    assert schema_kinds == {kind.value for kind in ChangeKind}


def test_schema_names_every_availability_state_the_model_accepts() -> None:
    schema = load_schema()
    schema_states = set(schema["$defs"]["fileChange"]["properties"]["availability"]["enum"])
    from metabrowser.diff.format import Availability

    assert schema_states == {state.value for state in Availability}


def test_corpus_covers_every_change_kind_and_availability_state() -> None:
    """The corpus is the compatibility gate, so it must exercise the taxonomy."""
    from metabrowser.diff.format import Availability, ChangeKind

    seen_kinds: set[str] = set()
    seen_states: set[str] = set()
    for case in _cases():
        if case["expect"] != "valid":
            continue
        for change in case["document"]["manifest"]["files"]:
            seen_kinds.add(change["kind"])
            seen_states.add(change["availability"])
    assert seen_kinds == {kind.value for kind in ChangeKind}
    missing = {state.value for state in Availability} - seen_states
    # Volatile and failure states are exercised by service tests rather than
    # by static documents; the corpus must still cover the content states.
    assert not missing - {"too_large", "timed_out", "failed", "stale"}, missing
