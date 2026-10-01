"""Inventory and corpus evidence for a registry of artifact contracts."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from typing import Any, Literal, cast

from metabrowser.plugin_loader.artifact_contracts import (
    ContractRegistry,
    portable_serialization_values_equal,
    serialize_artifact,
    validate_artifact,
    validate_record,
)


class ContractInventoryError(RuntimeError):
    """Packaged corpus evidence is incomplete or contradicts its contracts."""


@dataclass(frozen=True, slots=True)
class ContractInventoryEntry:
    """Inventory metadata for one installed artifact contract."""

    contract_id: str
    artifact_profile: str
    envelope: str
    schema_bytes_sha256: str
    schema_digest: str
    producer_ids: tuple[str, ...]
    consumer_ids: tuple[str, ...]
    corpus_id: str
    corpus_payload_sha256: str
    corpus_record_selectors: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _CorpusCase:
    name: str
    record: str | None
    changes: tuple[tuple[tuple[str | int, ...], object], ...]
    expectation: Literal["valid", "invalid"]


def _evidence_semantic_json_values_equal(original: object, dumped: object) -> bool:
    """Compare evidence semantically while allowing integral-number normalization.

    Corpus readers may accept a finite integral JSON float such as ``1.0`` while a
    canonical artifact serializer emits the integer ``1``. Booleans remain a
    distinct JSON type even though Python considers ``True == 1``.
    """
    if portable_serialization_values_equal(original, dumped):
        return True
    if type(original) in {int, float} and type(dumped) in {int, float}:
        return original == dumped
    if type(original) is dict and type(dumped) is dict:
        original_mapping = cast(dict[object, object], original)
        dumped_mapping = cast(dict[object, object], dumped)
        return (
            len(original_mapping) == len(dumped_mapping)
            and all(type(key) is str for key in original_mapping)
            and all(
                key in dumped_mapping
                and _evidence_semantic_json_values_equal(value, dumped_mapping[key])
                for key, value in original_mapping.items()
            )
        )
    if type(original) is list and type(dumped) is list:
        original_list = cast(list[object], original)
        dumped_list = cast(list[object], dumped)
        return len(original_list) == len(dumped_list) and all(
            _evidence_semantic_json_values_equal(left, right)
            for left, right in zip(original_list, dumped_list, strict=True)
        )
    return False


def installed_artifact_inventory(contracts: ContractRegistry) -> tuple[ContractInventoryEntry, ...]:
    """Return deterministic metadata, in contract-ID order, without source paths."""
    return tuple(
        ContractInventoryEntry(
            contract_id=installed.spec.contract_id,
            artifact_profile=installed.spec.artifact_profile,
            envelope=installed.spec.envelope,
            schema_bytes_sha256=installed.spec.schema_bytes_sha256,
            schema_digest=installed.spec.schema_digest,
            producer_ids=installed.spec.producer_ids,
            consumer_ids=installed.spec.consumer_ids,
            corpus_id=installed.spec.corpus.corpus_id,
            corpus_payload_sha256=installed.spec.corpus.payload_sha256,
            corpus_record_selectors=installed.spec.corpus_record_selectors,
        )
        for _, installed in sorted(contracts.items())
    )


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key {key!r}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> object:
    raise ValueError(f"non-finite JSON number {value}")


def _decode_corpus(payload: bytes) -> dict[str, object]:
    decoded = json.loads(
        payload,
        object_pairs_hook=_unique_json_object,
        parse_constant=_reject_json_constant,
    )
    if not isinstance(decoded, dict):
        raise ValueError("corpus root must be an object")
    return cast(dict[str, object], decoded)


def _case_name(value: object, *, index: int) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"case {index} requires a nonempty name")
    return value


def _case_record(value: object, *, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"case {name!r} record must be a nonempty string")
    return value


def _case_changes(value: object, *, name: str) -> tuple[tuple[tuple[str | int, ...], object], ...]:
    if not isinstance(value, list):
        raise ValueError(f"case {name!r} changes must be an array")
    changes: list[tuple[tuple[str | int, ...], object]] = []
    for change_index, change in enumerate(value):
        if not isinstance(change, dict) or set(change) != {"path", "value"}:
            raise ValueError(
                f"case {name!r} change {change_index} must contain only path and value"
            )
        path = change["path"]
        if (
            not isinstance(path, list)
            or not path
            or any(
                not isinstance(part, str)
                and (isinstance(part, bool) or not isinstance(part, int) or part < 0)
                for part in path
            )
        ):
            raise ValueError(
                f"case {name!r} change {change_index} path must contain strings or nonnegative integers"
            )
        changes.append((tuple(cast(list[str | int], path)), change["value"]))
    return tuple(changes)


def _case_expectation(value: object, *, name: str) -> Literal["valid", "invalid"]:
    if value not in {"valid", "invalid"}:
        raise ValueError(f"case {name!r} expect must be valid or invalid")
    return cast(Literal["valid", "invalid"], value)


def _parse_cases(corpus: dict[str, object]) -> tuple[tuple[_CorpusCase, ...], list[str]]:
    cases_value = corpus.get("cases")
    if not isinstance(cases_value, list) or not cases_value:
        return (), ["corpus cases must be a nonempty array"]
    cases: list[_CorpusCase] = []
    problems: list[str] = []
    names: set[str] = set()
    for index, value in enumerate(cases_value):
        try:
            if not isinstance(value, dict):
                raise ValueError(f"case {index} must be an object")
            unknown_fields = set(value).difference({"name", "record", "changes", "expect"})
            if unknown_fields:
                raise ValueError(f"case {index} has unknown field {sorted(unknown_fields)[0]!r}")
            name = _case_name(value.get("name"), index=index)
            if name in names:
                raise ValueError(f"duplicate case name {name!r}")
            names.add(name)
            cases.append(
                _CorpusCase(
                    name=name,
                    record=(
                        _case_record(value["record"], name=name) if "record" in value else None
                    ),
                    changes=_case_changes(value.get("changes"), name=name),
                    expectation=_case_expectation(value.get("expect"), name=name),
                )
            )
        except ValueError as exc:
            problems.append(str(exc))
    return tuple(cases), problems


def _record_bases(corpus: dict[str, object]) -> tuple[dict[str, dict[str, Any]], list[str]]:
    value = corpus.get("base_records")
    if value is None:
        return {}, []
    if not isinstance(value, dict):
        return {}, ["corpus base_records must be an object"]
    bases: dict[str, dict[str, Any]] = {}
    problems: list[str] = []
    for name, record in value.items():
        if not isinstance(name, str) or not name:
            problems.append("corpus base_records keys must be nonempty strings")
        elif not isinstance(record, dict):
            problems.append(f"corpus base record {name!r} must be an object")
        else:
            bases[name] = cast(dict[str, Any], record)
    return bases, problems


def _document_base(corpus: dict[str, object]) -> tuple[dict[str, Any] | None, list[str]]:
    value = corpus.get("base_document")
    if value is None:
        return None, []
    if not isinstance(value, dict):
        return None, ["corpus base_document must be an object"]
    return cast(dict[str, Any], value), []


def _apply_changes(
    base: dict[str, Any],
    changes: tuple[tuple[tuple[str | int, ...], object], ...],
) -> dict[str, Any]:
    record = copy.deepcopy(base)
    for path, value in changes:
        target: object = record
        for part in path[:-1]:
            if isinstance(target, dict):
                if not isinstance(part, str) or part not in target:
                    raise ValueError(f"mutation path {list(path)!r} does not resolve")
                target = target[part]
            elif isinstance(target, list):
                if not isinstance(part, int) or isinstance(part, bool) or part >= len(target):
                    raise ValueError(f"mutation path {list(path)!r} does not resolve")
                target = target[part]
            else:
                raise ValueError(f"mutation path {list(path)!r} does not resolve")
        final = path[-1]
        if isinstance(target, dict):
            if not isinstance(final, str):
                raise ValueError(f"mutation path {list(path)!r} does not resolve")
            target[final] = copy.deepcopy(value)
        elif isinstance(target, list):
            if not isinstance(final, int) or isinstance(final, bool) or final >= len(target):
                raise ValueError(f"mutation path {list(path)!r} does not resolve")
            target[final] = copy.deepcopy(value)
        else:
            raise ValueError(f"mutation path {list(path)!r} does not resolve")
    return record


def _round_trip_problems(
    *,
    contract_id: str,
    case_name: str,
    record: dict[str, Any],
    validated: object,
    contracts: ContractRegistry,
) -> list[str]:
    spec = contracts[contract_id].spec
    problems: list[str] = []
    try:
        dumped_object = cast(object, spec.dump_record(validated))
    except Exception as exc:
        return [f"case {case_name!r} dumper raised {type(exc).__name__}: {exc}"]
    if not isinstance(dumped_object, dict):
        return [f"case {case_name!r} dumper returned a non-mapping record"]
    dumped = cast(dict[str, Any], dumped_object)
    if not _evidence_semantic_json_values_equal(record, dumped):
        problems.append(f"case {case_name!r} dumper did not preserve the validated corpus record")
        return problems

    try:
        payload = serialize_artifact(
            validated,
            contract_id=contract_id,
            contracts=contracts,
        )
        repeated_payload = serialize_artifact(
            validated,
            contract_id=contract_id,
            contracts=contracts,
        )
    except Exception as exc:
        return [
            f"case {case_name!r} {spec.artifact_profile} serialization raised "
            f"{type(exc).__name__}: {exc}"
        ]
    if repeated_payload != payload:
        problems.append(
            f"case {case_name!r} {spec.artifact_profile} serialization is not deterministic"
        )
        return problems

    try:
        artifact = validate_artifact(
            payload,
            expected_contract_id=contract_id,
            contracts=contracts,
        )
    except Exception as exc:
        return [
            f"case {case_name!r} {spec.artifact_profile} round-trip parse raised "
            f"{type(exc).__name__}: {exc}"
        ]
    try:
        round_trip_dump = spec.dump_record(artifact.record)
    except Exception as exc:
        return [f"case {case_name!r} round-trip dumper raised {type(exc).__name__}: {exc}"]
    if not _evidence_semantic_json_values_equal(dumped, round_trip_dump):
        problems.append(
            f"case {case_name!r} {spec.artifact_profile} round trip did not preserve semantics"
        )
        return problems
    try:
        round_trip_payload = serialize_artifact(
            artifact.record,
            contract_id=contract_id,
            contracts=contracts,
        )
    except Exception as exc:
        return [f"case {case_name!r} round-trip serialization raised {type(exc).__name__}: {exc}"]
    if round_trip_payload != payload:
        problems.append(
            f"case {case_name!r} {spec.artifact_profile} round-trip bytes are not deterministic"
        )
    return problems


def _corpus_problems(
    contract_id: str,
    contracts: ContractRegistry,
) -> list[str]:
    spec = contracts[contract_id].spec
    prefix = f"artifact contract {contract_id!r}"
    try:
        corpus = _decode_corpus(spec.corpus.payload)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        return [f"{prefix} corpus is not portable JSON: {exc}"]
    cases, problems = _parse_cases(corpus)
    bases, base_problems = _record_bases(corpus)
    document, document_problems = _document_base(corpus)
    problems.extend(base_problems)
    problems.extend(document_problems)

    for case in cases:
        if case.record is not None and case.record not in bases:
            problems.append(f"case {case.name!r} names unknown base record {case.record!r}")
        elif case.record is None and document is None:
            problems.append(f"case {case.name!r} requires corpus base_document")

    selectors = spec.corpus_record_selectors
    if selectors:
        for selector in selectors:
            if selector not in bases:
                problems.append(f"selector {selector!r} is absent from corpus base_records")
            if not any(case.record == selector for case in cases):
                problems.append(f"selector {selector!r} has no cases")
        selected_cases = tuple(case for case in cases if case.record in selectors)
    else:
        if document is None:
            problems.append("contract with no record selectors requires corpus base_document")
        selected_cases = tuple(case for case in cases if case.record is None)
        if not selected_cases:
            problems.append("contract with no record selectors has no document cases")

    if not any(case.expectation == "valid" for case in selected_cases):
        problems.append("selected corpus cases have no valid evidence")
    if not any(case.expectation == "invalid" for case in selected_cases):
        problems.append("selected corpus cases have no invalid evidence")

    for case in selected_cases:
        base = document if case.record is None else bases.get(case.record)
        if base is None:
            continue
        try:
            record = _apply_changes(base, case.changes)
        except ValueError as exc:
            problems.append(f"case {case.name!r} has an invalid mutation path: {exc}")
            continue
        try:
            validated = validate_record(
                record,
                contract_id=contract_id,
                contracts=contracts,
            )
        except ValueError as exc:
            if case.expectation == "valid":
                problems.append(f"case {case.name!r} expected valid but was rejected: {exc}")
        except Exception as exc:
            problems.append(f"case {case.name!r} validator raised {type(exc).__name__}: {exc}")
        else:
            if case.expectation == "invalid":
                problems.append(f"case {case.name!r} expected invalid but was accepted")
            else:
                problems.extend(
                    _round_trip_problems(
                        contract_id=contract_id,
                        case_name=case.name,
                        record=record,
                        validated=validated,
                        contracts=contracts,
                    )
                )
    return [f"{prefix} {problem}" for problem in problems]


def check_installed_evidence(contracts: ContractRegistry) -> tuple[str, ...]:
    """Check every contract's corpus selectors through structural and semantic validation."""
    problems: list[str] = []
    for contract_id in sorted(contracts):
        problems.extend(_corpus_problems(contract_id, contracts))
    return tuple(problems)


def validate_installed_evidence(contracts: ContractRegistry) -> ContractRegistry:
    """Require complete corpus evidence and return the validated registry."""
    problems = check_installed_evidence(contracts)
    if problems:
        raise ContractInventoryError("installed contract inventory failed: " + "; ".join(problems))
    return contracts


__all__ = [
    "ContractInventoryEntry",
    "ContractInventoryError",
    "check_installed_evidence",
    "installed_artifact_inventory",
    "validate_installed_evidence",
]
