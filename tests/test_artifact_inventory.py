from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import replace
from typing import Any, cast

import pytest

from metabrowser.plugin_loader.artifact_contracts import build_installed_registries
from metabrowser.plugin_loader.artifact_inventory import (
    CapabilityInventoryError,
    check_installed_evidence,
    installed_artifact_inventory,
    validate_installed_evidence,
)
from metabrowser.plugin_loader.capability_discovery import (
    CapabilityDiscoveryResult,
    LoadedCapabilitySet,
)
from metabrowser.plugin_loader.capability_types import (
    ArtifactContractSpec,
    ArtifactProfile,
    ArtifactValidationContext,
    BrowserParserSpec,
    CapabilitySet,
    ConformanceCorpusSpec,
)
from metabrowser.provider_resources.profiles import (
    CollectionPaginationPolicy,
    ResourceCollectionSpec,
    ResourceProfileSpec,
    ResourceTargetClass,
)

_CONTRACT_ID = "org.example.widgets:Widget/v1"
_PROFILE_ID = "org.example.widgets:widget-detail/v1"


def _encoded_schema() -> bytes:
    schema: dict[str, Any] = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": {"name": {"type": "string", "minLength": 1}},
        "required": ["name"],
        "additionalProperties": False,
        "x-softschema": {"contract": _CONTRACT_ID},
    }
    canonical = json.dumps(schema, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    schema["x-softschema"]["schema_sha256"] = hashlib.sha256(canonical.encode()).hexdigest()
    return json.dumps(schema, sort_keys=True, separators=(",", ":")).encode()


def _encoded_typed_value_schema() -> bytes:
    scalar_schema = {"type": ["integer", "boolean"]}
    schema: dict[str, Any] = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": {
            "value": scalar_schema,
            "nested": {
                "type": "object",
                "properties": {"value": scalar_schema},
                "required": ["value"],
                "additionalProperties": False,
            },
        },
        "required": ["nested", "value"],
        "additionalProperties": False,
        "x-softschema": {"contract": _CONTRACT_ID},
    }
    canonical = json.dumps(schema, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    schema["x-softschema"]["schema_sha256"] = hashlib.sha256(canonical.encode()).hexdigest()
    return json.dumps(schema, sort_keys=True, separators=(",", ":")).encode()


def _validate_widget(
    value: dict[str, Any],
    _context: ArtifactValidationContext,
) -> dict[str, Any]:
    if value["name"] == "reserved":
        raise ValueError("reserved widget name")
    return dict(value)


def _dump_widget(value: object) -> dict[str, Any]:
    return dict(cast(dict[str, Any], value))


def _validate_typed_value(
    value: dict[str, Any],
    _context: ArtifactValidationContext,
) -> dict[str, Any]:
    return dict(value)


def _corpus_payload() -> bytes:
    return json.dumps(
        {
            "base_records": {"widget": {"name": "accepted"}},
            "cases": [
                {
                    "name": "valid-widget",
                    "record": "widget",
                    "changes": [],
                    "expect": "valid",
                },
                {
                    "name": "structurally-invalid-widget",
                    "record": "widget",
                    "changes": [{"path": ["name"], "value": ""}],
                    "expect": "invalid",
                },
                {
                    "name": "semantically-invalid-widget",
                    "record": "widget",
                    "changes": [{"path": ["name"], "value": "reserved"}],
                    "expect": "invalid",
                },
            ],
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def _contract(*, corpus_payload: bytes | None = None) -> ArtifactContractSpec:
    schema_bytes = _encoded_schema()
    payload = corpus_payload if corpus_payload is not None else _corpus_payload()
    module_bytes = (
        b"export function parseWidget(value) {\n"
        b"  const ok = typeof value.name === 'string' && "
        b"value.name.length > 0 && value.name !== 'reserved';\n"
        b"  return ok ? { ok: true, value } : { ok: false, error: 'invalid widget' };\n"
        b"}\n"
    )
    schema = cast(dict[str, Any], json.loads(schema_bytes))
    return ArtifactContractSpec(
        contract_id=_CONTRACT_ID,
        artifact_profile="pure-yaml",
        envelope="widget",
        schema_bytes=schema_bytes,
        schema_bytes_sha256=hashlib.sha256(schema_bytes).hexdigest(),
        schema_digest=cast(str, schema["x-softschema"]["schema_sha256"]),
        validate_record=_validate_widget,
        dump_record=_dump_widget,
        producer_ids=("example-provider",),
        consumer_ids=("example-browser", "example-store"),
        corpus=ConformanceCorpusSpec(
            corpus_id="widget-conformance",
            media_type="application/json",
            payload=payload,
            payload_sha256=hashlib.sha256(payload).hexdigest(),
        ),
        corpus_record_selectors=("widget",),
        browser_consumed=True,
        browser_parser=BrowserParserSpec(
            module_id="widget-model",
            module_bytes=module_bytes,
            module_bytes_sha256=hashlib.sha256(module_bytes).hexdigest(),
            export_name="parseWidget",
        ),
    )


def _typed_value_contract(
    dump_record: Callable[[object], dict[str, Any]],
) -> ArtifactContractSpec:
    schema_bytes = _encoded_typed_value_schema()
    schema = cast(dict[str, Any], json.loads(schema_bytes))
    corpus_payload = json.dumps(
        {
            "base_records": {"widget": {"value": 1, "nested": {"value": 1}}},
            "cases": [
                {
                    "name": "valid-typed-value",
                    "record": "widget",
                    "changes": [],
                    "expect": "valid",
                },
                {
                    "name": "invalid-extra-field",
                    "record": "widget",
                    "changes": [{"path": ["extra"], "value": True}],
                    "expect": "invalid",
                },
            ],
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return replace(
        _contract(corpus_payload=corpus_payload),
        schema_bytes=schema_bytes,
        schema_bytes_sha256=hashlib.sha256(schema_bytes).hexdigest(),
        schema_digest=cast(str, schema["x-softschema"]["schema_sha256"]),
        validate_record=_validate_typed_value,
        dump_record=dump_record,
        browser_consumed=False,
        browser_parser=None,
    )


def _profile() -> ResourceProfileSpec:
    return ResourceProfileSpec(
        profile_id=_PROFILE_ID,
        target_class=ResourceTargetClass.provider_object,
        target_result_contract_id=None,
        collections=(
            ResourceCollectionSpec(
                name="widget",
                artifact_contract_id=_CONTRACT_ID,
                minimum_artifacts=1,
                maximum_artifacts=1,
                pagination=CollectionPaginationPolicy.forbidden,
                required_for_last_complete=True,
            ),
        ),
    )


def _registries(contract: ArtifactContractSpec | None = None):
    provider = LoadedCapabilitySet(
        provider_id="org-example-widgets",
        source_distribution="example-widgets",
        capabilities=CapabilitySet(
            artifact_contracts=(contract or _contract(),),
            resource_profiles=(_profile(),),
        ),
    )
    return build_installed_registries(CapabilityDiscoveryResult(providers=(provider,)))


def test_installed_inventory_executes_structural_and_semantic_corpus_evidence() -> None:
    registries = _registries()

    assert check_installed_evidence(registries) == ()
    assert validate_installed_evidence(registries) is registries

    inventory = installed_artifact_inventory(registries)
    assert inventory.contracts[0].contract_id == _CONTRACT_ID
    assert inventory.contracts[0].producer_ids == ("example-provider",)
    assert inventory.contracts[0].consumer_ids == ("example-browser", "example-store")
    assert inventory.contracts[0].corpus_record_selectors == ("widget",)
    assert inventory.contracts[0].browser_consumed is True
    assert inventory.contracts[0].browser_parser_id == "widget-model:parseWidget"
    assert inventory.resource_profiles[0].profile_id == _PROFILE_ID
    assert inventory.resource_profiles[0].collections[0].pagination == "forbidden"
    assert inventory.resource_profiles[0].collections[0].required_for_last_complete is True


def test_installed_inventory_rejects_missing_and_zero_case_selectors() -> None:
    contract = replace(_contract(), corpus_record_selectors=("missing",))
    registries = _registries(contract)

    problems = check_installed_evidence(registries)

    assert any("missing" in problem and "base_records" in problem for problem in problems)
    assert any("missing" in problem and "no cases" in problem for problem in problems)


def test_installed_inventory_rejects_orphan_cases_and_wrong_expectations() -> None:
    corpus = cast(dict[str, Any], json.loads(_corpus_payload()))
    corpus["cases"].append(
        {
            "name": "orphan-case",
            "record": "absent",
            "changes": [],
            "expect": "valid",
        }
    )
    corpus["cases"][2]["expect"] = "valid"
    payload = json.dumps(corpus, sort_keys=True, separators=(",", ":")).encode()
    registries = _registries(_contract(corpus_payload=payload))

    problems = check_installed_evidence(registries)

    assert any(
        "orphan-case" in problem and "unknown base record" in problem for problem in problems
    )
    assert any(
        "semantically-invalid-widget" in problem and "expected valid" in problem
        for problem in problems
    )
    with pytest.raises(CapabilityInventoryError, match="semantically-invalid-widget"):
        validate_installed_evidence(registries)


def test_installed_inventory_rejects_malformed_mutation_paths() -> None:
    corpus = cast(dict[str, Any], json.loads(_corpus_payload()))
    corpus["cases"][0]["changes"] = [{"path": ["missing", "nested"], "value": True}]
    payload = json.dumps(corpus, sort_keys=True, separators=(",", ":")).encode()
    registries = _registries(_contract(corpus_payload=payload))

    problems = check_installed_evidence(registries)

    assert any("valid-widget" in problem and "mutation path" in problem for problem in problems)


@pytest.mark.parametrize(
    ("retained_expectation", "missing_evidence"),
    [("valid", "invalid"), ("invalid", "valid")],
)
def test_installed_inventory_requires_contract_wide_evidence_polarity(
    retained_expectation: str,
    missing_evidence: str,
) -> None:
    corpus = cast(dict[str, Any], json.loads(_corpus_payload()))
    corpus["cases"] = [case for case in corpus["cases"] if case["expect"] == retained_expectation]
    payload = json.dumps(corpus, sort_keys=True, separators=(",", ":")).encode()

    problems = check_installed_evidence(_registries(_contract(corpus_payload=payload)))

    assert any(f"no {missing_evidence} evidence" in problem for problem in problems)


@pytest.mark.parametrize("artifact_profile", ["frontmatter-md", "pure-yaml"])
def test_installed_inventory_round_trips_both_artifact_profiles(
    artifact_profile: ArtifactProfile,
) -> None:
    contract = replace(_contract(), artifact_profile=artifact_profile)

    assert check_installed_evidence(_registries(contract)) == ()


def test_installed_inventory_rejects_lossy_dumpers() -> None:
    def dump_lossy_widget(_value: object) -> dict[str, Any]:
        return {"name": "changed-by-dumper"}

    contract = replace(_contract(), dump_record=dump_lossy_widget)

    problems = check_installed_evidence(_registries(contract))

    assert any(
        "valid-widget" in problem and "did not preserve the validated corpus record" in problem
        for problem in problems
    )


def test_installed_inventory_reports_raising_dumpers() -> None:
    def dump_raising_widget(_value: object) -> dict[str, Any]:
        raise RuntimeError("synthetic dumper failure")

    contract = replace(_contract(), dump_record=dump_raising_widget)

    problems = check_installed_evidence(_registries(contract))

    assert any(
        "valid-widget" in problem
        and "dumper raised RuntimeError: synthetic dumper failure" in problem
        for problem in problems
    )


@pytest.mark.parametrize(
    "lossy_path",
    [None, ("value",), ("nested", "value")],
    ids=["exact", "top-level-int-to-bool", "nested-int-to-bool"],
)
def test_installed_inventory_uses_type_sensitive_record_preservation(
    lossy_path: tuple[str, ...] | None,
) -> None:
    def dump_typed_value(value: object) -> dict[str, Any]:
        dumped = cast(dict[str, Any], json.loads(json.dumps(value)))
        if lossy_path == ("value",):
            dumped["value"] = True
        elif lossy_path == ("nested", "value"):
            nested = cast(dict[str, Any], dumped["nested"])
            nested["value"] = True
        return dumped

    problems = check_installed_evidence(_registries(_typed_value_contract(dump_typed_value)))

    if lossy_path is None:
        assert problems == ()
    else:
        assert any(
            "valid-typed-value" in problem
            and "did not preserve the validated corpus record" in problem
            for problem in problems
        )


@pytest.mark.parametrize(
    "lossy_path",
    [("value",), ("nested", "value")],
    ids=["top-level-int-to-bool", "nested-int-to-bool"],
)
def test_installed_inventory_uses_type_sensitive_round_trip_preservation(
    lossy_path: tuple[str, ...],
) -> None:
    original_value: object | None = None

    def dump_typed_value(value: object) -> dict[str, Any]:
        nonlocal original_value
        if original_value is None:
            original_value = value
        dumped = cast(dict[str, Any], json.loads(json.dumps(value)))
        if value is not original_value:
            if lossy_path == ("value",):
                dumped["value"] = True
            else:
                nested = cast(dict[str, Any], dumped["nested"])
                nested["value"] = True
        return dumped

    problems = check_installed_evidence(_registries(_typed_value_contract(dump_typed_value)))

    assert any(
        "valid-typed-value" in problem and "round trip did not preserve semantics" in problem
        for problem in problems
    )


def test_installed_inventory_allows_integral_float_normalization() -> None:
    def dump_normalized_value(value: object) -> dict[str, Any]:
        dumped = cast(dict[str, Any], json.loads(json.dumps(value)))
        dumped["value"] = 1
        nested = cast(dict[str, Any], dumped["nested"])
        nested["value"] = 1
        return dumped

    contract = _typed_value_contract(dump_normalized_value)
    corpus = cast(dict[str, Any], json.loads(contract.corpus.payload))
    corpus["base_records"]["widget"] = {
        "value": 1.0,
        "nested": {"value": 1.0},
    }
    payload = json.dumps(corpus, sort_keys=True, separators=(",", ":")).encode()
    contract = replace(
        contract,
        corpus=replace(
            contract.corpus,
            payload=payload,
            payload_sha256=hashlib.sha256(payload).hexdigest(),
        ),
    )

    assert check_installed_evidence(_registries(contract)) == ()


@pytest.mark.parametrize("record", [None, 1])
def test_document_scope_requires_an_absent_record_key(record: object) -> None:
    corpus = {
        "base_document": {"name": "accepted"},
        "cases": [
            {
                "name": "malformed-document-case",
                "record": record,
                "changes": [],
                "expect": "valid",
            }
        ],
    }
    payload = json.dumps(corpus, sort_keys=True, separators=(",", ":")).encode()
    contract = replace(
        _contract(corpus_payload=payload),
        corpus_record_selectors=(),
    )

    problems = check_installed_evidence(_registries(contract))

    assert any(
        "malformed-document-case" in problem and "record must be a nonempty string" in problem
        for problem in problems
    )
