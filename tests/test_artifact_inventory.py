"""The corpus evidence engine: what a contract's packaged corpus has to prove.

``devtools/check_artifact_contracts.py`` and the installed-wheel smoke test run this
engine over the cache's contracts. Here it runs over the synthetic contract in
``tests/artifact_contract_fixture.py`` with one thing wrong at a time, and each case
states every problem the engine reports, in order.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, cast

import pytest

from metabrowser.plugin_loader.artifact_contracts import (
    ArtifactContractSpec,
    build_contract_registry,
)
from metabrowser.plugin_loader.artifact_inventory import (
    ContractInventoryError,
    check_installed_evidence,
    installed_artifact_inventory,
    validate_installed_evidence,
)
from tests.artifact_contract_fixture import (
    CONTRACT_ID,
    EMPTY_NAME_CASE,
    RESERVED_NAME_CASE,
    VALID_CASE,
    contract,
    corpus,
    schema,
)

Dumper = Callable[[object], dict[str, Any]]

_NO_VALID = "selected corpus cases have no valid evidence"
_NO_INVALID = "selected corpus cases have no invalid evidence"
_NOT_PRESERVED = "case 'valid' dumper did not preserve the validated corpus record"


def _problems(spec: ArtifactContractSpec) -> list[str]:
    """What the engine reports for *spec*, without the prefix that names the contract."""

    prefix = f"artifact contract {CONTRACT_ID!r} "
    problems = check_installed_evidence(build_contract_registry((spec,)))
    assert all(problem.startswith(prefix) for problem in problems)
    return [problem.removeprefix(prefix) for problem in problems]


def _raising_dumper(_record: object) -> dict[str, Any]:
    raise RuntimeError("synthetic dumper failure")


def _document_case(record: object) -> ArtifactContractSpec:
    """A contract with no selectors, whose one case carries a ``record`` key anyway."""

    evidence = corpus(VALID_CASE | {"record": record}, base_document={"name": "accepted"})
    return contract(corpus=evidence, corpus_record_selectors=())


_NO_DOCUMENT_CASES = [
    "case 'valid' record must be a nonempty string",
    "contract with no record selectors has no document cases",
    _NO_VALID,
    _NO_INVALID,
]
_INCOMPLETE: dict[str, tuple[ArtifactContractSpec, list[str]]] = {
    "selector-the-corpus-does-not-hold": (
        contract(corpus_record_selectors=("missing",)),
        [
            "selector 'missing' is absent from corpus base_records",
            "selector 'missing' has no cases",
            _NO_VALID,
            _NO_INVALID,
        ],
    ),
    "case-on-an-unknown-base-record": (
        contract(
            corpus=corpus(
                VALID_CASE, EMPTY_NAME_CASE, VALID_CASE | {"name": "orphan", "record": "absent"}
            )
        ),
        ["case 'orphan' names unknown base record 'absent'"],
    ),
    "case-expected-valid-and-rejected": (
        contract(
            corpus=corpus(VALID_CASE, EMPTY_NAME_CASE, RESERVED_NAME_CASE | {"expect": "valid"})
        ),
        ["case 'reserved-name' expected valid but was rejected: reserved item name"],
    ),
    "case-expected-invalid-and-accepted": (
        contract(
            corpus=corpus(
                VALID_CASE, EMPTY_NAME_CASE, VALID_CASE | {"name": "passes", "expect": "invalid"}
            )
        ),
        ["case 'passes' expected invalid but was accepted"],
    ),
    "change-at-a-path-that-does-not-resolve": (
        contract(
            corpus=corpus(
                VALID_CASE | {"changes": [{"path": ["missing", "nested"], "value": 1}]},
                EMPTY_NAME_CASE,
            )
        ),
        [
            "case 'valid' has an invalid mutation path: "
            "mutation path ['missing', 'nested'] does not resolve"
        ],
    ),
    "no-invalid-case": (contract(corpus=corpus(VALID_CASE)), [_NO_INVALID]),
    "no-valid-case": (contract(corpus=corpus(EMPTY_NAME_CASE, RESERVED_NAME_CASE)), [_NO_VALID]),
    "dumper-that-changes-the-record": (
        contract(dump_record=lambda _record: {"name": "changed-by-dumper"}),
        [_NOT_PRESERVED],
    ),
    "dumper-that-raises": (
        contract(dump_record=_raising_dumper),
        ["case 'valid' dumper raised RuntimeError: synthetic dumper failure"],
    ),
    "document-case-with-a-null-record": (_document_case(None), _NO_DOCUMENT_CASES),
    "document-case-with-a-numeric-record": (_document_case(1), _NO_DOCUMENT_CASES),
}


def test_a_complete_corpus_passes_and_the_inventory_carries_its_digests() -> None:
    spec = contract()
    contracts = build_contract_registry((spec,))

    assert check_installed_evidence(contracts) == ()
    assert validate_installed_evidence(contracts) is contracts
    # The fields the architecture table shows are compared in
    # tests/test_check_artifact_contracts.py; these two are in no table.
    (entry,) = installed_artifact_inventory(contracts)
    assert entry.schema_bytes_sha256 == spec.schema_bytes_sha256
    assert entry.corpus_payload_sha256 == spec.corpus.payload_sha256


@pytest.mark.parametrize(("spec", "problems"), _INCOMPLETE.values(), ids=_INCOMPLETE)
def test_incomplete_or_contradicted_evidence_is_reported(
    spec: ArtifactContractSpec, problems: list[str]
) -> None:
    assert _problems(spec) == problems


def test_reported_problems_refuse_the_installed_registry() -> None:
    contracts = build_contract_registry((contract(corpus=corpus(VALID_CASE)),))

    with pytest.raises(ContractInventoryError, match=_NO_INVALID):
        validate_installed_evidence(contracts)


# ── Values a dumper may and may not change ─────────────────────────────────────


def _typed_values(dump_record: Dumper, value: object = 1) -> ArtifactContractSpec:
    """A contract whose ``value`` and ``nested.value`` are each an integer or a boolean."""

    scalar = {"type": ["integer", "boolean"]}
    nested = {
        "type": "object",
        "properties": {"value": scalar},
        "required": ["value"],
        "additionalProperties": False,
    }
    extra = VALID_CASE | {
        "name": "extra-field",
        "changes": [{"path": ["extra"], "value": 1}],
        "expect": "invalid",
    }
    evidence = corpus(
        VALID_CASE, extra, base_records={"item": {"value": value, "nested": {"value": value}}}
    )
    typed = schema(properties={"value": scalar, "nested": nested}, required=["nested", "value"])
    return contract(corpus=evidence, dump_record=dump_record, **typed)


def _dumper(change: Callable[[dict[str, Any]], None], *, after_round_trip: bool = False) -> Dumper:
    """A dumper that applies *change* to its copy: always, or only to a re-read record."""

    seen: list[object] = []

    def dump(record: object) -> dict[str, Any]:
        seen.append(record)
        dumped = cast(dict[str, Any], json.loads(json.dumps(record)))
        if not after_round_trip or record is not seen[0]:
            change(dumped)
        return dumped

    return dump


def _top_level(value: object) -> Callable[[dict[str, Any]], None]:
    return lambda dumped: dumped.update(value=value)


def _nested(value: object) -> Callable[[dict[str, Any]], None]:
    return lambda dumped: dumped["nested"].update(value=value)


@pytest.mark.parametrize("change", [_top_level(True), _nested(True)], ids=["top-level", "nested"])
def test_a_dumper_that_turns_an_integer_into_a_boolean_has_changed_the_record(
    change: Callable[[dict[str, Any]], None],
) -> None:
    assert _problems(_typed_values(_dumper(change))) == [_NOT_PRESERVED]
    assert _problems(_typed_values(_dumper(change, after_round_trip=True))) == [
        "case 'valid' pure-yaml round trip did not preserve semantics"
    ]


def test_a_dumper_may_write_an_integral_float_as_an_integer() -> None:
    def to_integers(dumped: dict[str, Any]) -> None:
        _top_level(1)(dumped)
        _nested(1)(dumped)

    # The control: a dumper that changes nothing leaves nothing to report.
    assert _problems(_typed_values(_dumper(lambda _dumped: None))) == []
    assert _problems(_typed_values(_dumper(to_integers), value=1.0)) == []
