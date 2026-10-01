from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import date
from typing import Any, cast

import pytest

from metabrowser.plugin_loader.artifact_contracts import (
    ArtifactContractSpec,
    ConformanceCorpusSpec,
    ContractRegistryError,
    build_contract_registry,
    serialize_artifact,
    validate_artifact,
    validate_record,
)

_CONTRACT_ID = "example.test:Item/v1"


def _schema_bytes(
    contract_id: str = _CONTRACT_ID,
    *,
    close_root: bool = True,
) -> bytes:
    schema: dict[str, Any] = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": {"name": {"type": "string", "minLength": 1}},
        "required": ["name"],
        "x-softschema": {"contract": contract_id},
    }
    if close_root:
        schema["additionalProperties"] = False
    return _encoded_schema(schema)


def _encoded_schema(schema: dict[str, Any]) -> bytes:
    canonical = json.dumps(schema, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    schema["x-softschema"]["schema_sha256"] = hashlib.sha256(canonical.encode()).hexdigest()
    return json.dumps(schema, sort_keys=True, separators=(",", ":")).encode()


def _schema_digest(schema_bytes: bytes) -> str:
    schema = cast(dict[str, Any], json.loads(schema_bytes))
    return cast(str, schema["x-softschema"]["schema_sha256"])


def _schema_bytes_digest(schema_bytes: bytes) -> str:
    return hashlib.sha256(schema_bytes).hexdigest()


def _validate_record(value: dict[str, Any]) -> dict[str, Any]:
    if value["name"] == "semantic-invalid":
        raise ValueError("semantic validation failed")
    return dict(value)


def _validate_identity_record(value: dict[str, Any]) -> dict[str, Any]:
    return dict(value)


def _dump_record(value: object) -> dict[str, Any]:
    return dict(cast(dict[str, Any], value))


def _contract(contract_id: str = _CONTRACT_ID) -> ArtifactContractSpec:
    schema_bytes = _schema_bytes(contract_id)
    corpus_payload = b'{"cases":[]}'
    return ArtifactContractSpec(
        contract_id=contract_id,
        artifact_profile="pure-yaml",
        envelope="item",
        schema_bytes=schema_bytes,
        schema_bytes_sha256=_schema_bytes_digest(schema_bytes),
        schema_digest=_schema_digest(schema_bytes),
        validate_record=_validate_record,
        dump_record=_dump_record,
        producer_ids=("fixture-producer",),
        consumer_ids=("fixture-consumer",),
        corpus=ConformanceCorpusSpec(
            corpus_id="fixture-corpus",
            media_type="application/json",
            payload=corpus_payload,
            payload_sha256=_schema_bytes_digest(corpus_payload),
        ),
        corpus_record_selectors=("fixture-record",),
    )


def test_contract_registry_is_immutable() -> None:
    contracts = build_contract_registry((_contract(),))

    assert contracts[_CONTRACT_ID].spec.contract_id == _CONTRACT_ID
    with pytest.raises(TypeError):
        cast(dict[str, object], contracts)[_CONTRACT_ID] = object()


def test_duplicate_contract_ids_fail_even_when_declarations_match() -> None:
    with pytest.raises(ContractRegistryError, match="duplicate artifact contract"):
        build_contract_registry((_contract(), _contract()))


def test_contract_id_is_validated_before_registry_key_use() -> None:
    malformed = replace(_contract(), contract_id=cast(Any, []))

    with pytest.raises(ContractRegistryError, match="contract ID"):
        build_contract_registry((malformed,))


def test_registry_rejects_schema_digest_id_and_remote_reference_mismatches() -> None:
    contract = _contract()
    tampered_schema = contract.schema_bytes.replace(
        b'"type":"object"',
        b'"title":"tampered","type":"object"',
        1,
    )
    with pytest.raises(ContractRegistryError, match="schema bytes digest"):
        build_contract_registry((replace(contract, schema_bytes=tampered_schema),))
    with pytest.raises(ContractRegistryError, match="schema digest"):
        build_contract_registry((replace(contract, schema_digest="0" * 64),))

    mutated_schema = cast(dict[str, Any], json.loads(contract.schema_bytes))
    mutated_schema["description"] = "changed without recompiling the logical identity"
    mutated_schema_bytes = json.dumps(
        mutated_schema,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    with pytest.raises(ContractRegistryError, match="schema digest"):
        build_contract_registry(
            (
                replace(
                    contract,
                    schema_bytes=mutated_schema_bytes,
                    schema_bytes_sha256=_schema_bytes_digest(mutated_schema_bytes),
                ),
            )
        )

    wrong_contract = _schema_bytes("example.test:Wrong/v1")
    with pytest.raises(ContractRegistryError, match="x-softschema contract"):
        build_contract_registry(
            (
                replace(
                    contract,
                    schema_bytes=wrong_contract,
                    schema_bytes_sha256=_schema_bytes_digest(wrong_contract),
                    schema_digest=_schema_digest(wrong_contract),
                ),
            )
        )

    remote_ref_document: dict[str, Any] = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://schemas.example/contracts/item-v1.schema.json",
        "$ref": "https://schemas.example/item.json",
        "x-softschema": {"contract": _CONTRACT_ID},
    }
    canonical = json.dumps(
        remote_ref_document,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    remote_ref_document["x-softschema"]["schema_sha256"] = hashlib.sha256(
        canonical.encode()
    ).hexdigest()
    remote_ref = json.dumps(
        remote_ref_document,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    with pytest.raises(ContractRegistryError, match=r"local \$defs"):
        build_contract_registry(
            (
                replace(
                    contract,
                    schema_bytes=remote_ref,
                    schema_bytes_sha256=_schema_bytes_digest(remote_ref),
                    schema_digest=_schema_digest(remote_ref),
                ),
            )
        )


def test_registry_verifies_resolvable_corpus_evidence() -> None:
    contract = _contract()
    with pytest.raises(ContractRegistryError, match="corpus payload digest"):
        build_contract_registry(
            (
                replace(
                    contract,
                    corpus=replace(contract.corpus, payload=b'{"changed":true}'),
                ),
            )
        )


def test_registry_rejects_unresolved_and_dynamic_schema_references() -> None:
    contract = _contract()
    unresolved = _encoded_schema(
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$ref": "#/$defs/Missing",
            "x-softschema": {"contract": _CONTRACT_ID},
        }
    )
    dynamic = _encoded_schema(
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$dynamicRef": "https://example.invalid/item",
            "x-softschema": {"contract": _CONTRACT_ID},
        }
    )

    for schema_bytes in (unresolved, dynamic):
        with pytest.raises(ContractRegistryError, match="cannot be enforced"):
            build_contract_registry(
                (
                    replace(
                        contract,
                        schema_bytes=schema_bytes,
                        schema_bytes_sha256=_schema_bytes_digest(schema_bytes),
                        schema_digest=_schema_digest(schema_bytes),
                    ),
                )
            )


@pytest.mark.parametrize(
    "declared_dialect",
    [None, "http://json-schema.org/draft-07/schema#"],
)
def test_registry_requires_the_exact_schema_dialect(declared_dialect: str | None) -> None:
    schema: dict[str, Any] = {
        "type": "object",
        "properties": {"credit_card": {"type": "string"}},
        "dependencies": {"credit_card": ["billing_address"]},
        "x-softschema": {"contract": _CONTRACT_ID},
    }
    if declared_dialect is not None:
        schema["$schema"] = declared_dialect
    schema_bytes = _encoded_schema(schema)
    contract = replace(
        _contract(),
        schema_bytes=schema_bytes,
        schema_bytes_sha256=_schema_bytes_digest(schema_bytes),
        schema_digest=_schema_digest(schema_bytes),
    )

    with pytest.raises(ContractRegistryError, match="must declare Draft 2020-12"):
        build_contract_registry((contract,))


def test_registry_rejects_nonportable_schema_yaml() -> None:
    contract = _contract()
    schemas = (
        (
            b"$schema: https://json-schema.org/draft/2020-12/schema\n"
            b"type: object\n"
            b"properties:\n"
            b"  name: &name_schema\n"
            b"    type: string\n"
            b"required: [name]\n"
            b"x-softschema:\n"
            b"  contract: example.test:Item/v1\n"
            b"  schema_sha256: " + b"0" * 64 + b"\n"
        ),
        (
            b"$schema: https://json-schema.org/draft/2020-12/schema\n"
            b"type: object\n"
            b"properties:\n"
            b"  count:\n"
            b"    type: integer\n"
            b"    minimum: 9007199254740993\n"
            b"x-softschema:\n"
            b"  contract: example.test:Item/v1\n"
            b"  schema_sha256: " + b"0" * 64 + b"\n"
        ),
    )

    for schema_bytes in schemas:
        with pytest.raises(ContractRegistryError, match="schema is not portable"):
            build_contract_registry(
                (
                    replace(
                        contract,
                        schema_bytes=schema_bytes,
                        schema_bytes_sha256=_schema_bytes_digest(schema_bytes),
                        schema_digest="0" * 64,
                    ),
                )
            )


def test_cached_artifact_can_name_but_cannot_supply_its_schema() -> None:
    contract = _contract()
    registry = build_contract_registry((contract,))
    payload = (
        b"softschema:\n"
        b"  contract: example.test:Item/v1\n"
        b"  envelope: item\n"
        b"  status: enforced\n"
        b"item:\n"
        b"  name: accepted\n"
    )

    artifact = validate_artifact(
        payload,
        expected_contract_id=_CONTRACT_ID,
        contracts=registry,
    )

    assert artifact.contract_id == _CONTRACT_ID
    assert artifact.record == {"name": "accepted"}

    injected_schema = payload.replace(
        b"  status: enforced\n",
        b"  status: enforced\n  schema: ./attacker.schema.json\n",
    )
    with pytest.raises(ValueError, match="contract, envelope, and status"):
        validate_artifact(
            injected_schema,
            expected_contract_id=_CONTRACT_ID,
            contracts=registry,
        )

    other_contract_id = "example.test:Other/v1"
    other_contract = _contract(other_contract_id)
    registry_with_other = build_contract_registry((contract, other_contract))
    wrong_slot_payload = payload.replace(_CONTRACT_ID.encode(), other_contract_id.encode())
    with pytest.raises(ValueError, match="does not match its expected contract"):
        validate_artifact(
            wrong_slot_payload,
            expected_contract_id=_CONTRACT_ID,
            contracts=registry_with_other,
        )


def test_record_validation_applies_structural_and_semantic_contracts() -> None:
    registry = build_contract_registry((_contract(),))

    assert validate_record({"name": "accepted"}, contract_id=_CONTRACT_ID, contracts=registry) == {
        "name": "accepted"
    }
    with pytest.raises(ValueError, match="does not satisfy contract"):
        validate_record({}, contract_id=_CONTRACT_ID, contracts=registry)
    with pytest.raises(ValueError, match="semantic validation failed"):
        validate_record(
            {"name": "semantic-invalid"},
            contract_id=_CONTRACT_ID,
            contracts=registry,
        )


def test_enforced_record_validation_closes_an_open_source_schema() -> None:
    contract = _contract()
    open_schema = _schema_bytes(close_root=False)
    open_contract = replace(
        contract,
        schema_bytes=open_schema,
        schema_bytes_sha256=_schema_bytes_digest(open_schema),
        schema_digest=_schema_digest(open_schema),
    )
    registry = build_contract_registry((open_contract,))

    with pytest.raises(ValueError, match="does not satisfy contract"):
        validate_record(
            {"name": "accepted", "undeclared": True},
            contract_id=_CONTRACT_ID,
            contracts=registry,
        )


def test_installed_contract_serialization_round_trips() -> None:
    registry = build_contract_registry((_contract(),))
    record = {"name": "accepted"}

    payload = serialize_artifact(record, contract_id=_CONTRACT_ID, contracts=registry)

    assert serialize_artifact(record, contract_id=_CONTRACT_ID, contracts=registry) == payload
    assert (
        validate_artifact(payload, expected_contract_id=_CONTRACT_ID, contracts=registry).record
        == record
    )


def test_registry_rejects_an_unsupported_artifact_profile() -> None:
    contract = replace(_contract(), artifact_profile=cast(Any, "frontmatter-md"))

    with pytest.raises(ContractRegistryError, match="unsupported artifact profile"):
        build_contract_registry((contract,))


@pytest.mark.parametrize(
    "nonportable_value",
    [float("nan"), 9_007_199_254_740_992, date(2026, 9, 15), ("tuple",)],
)
def test_artifact_serialization_rejects_nonportable_values(nonportable_value: object) -> None:
    schema_bytes = _encoded_schema(
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": {"value": {}},
            "required": ["value"],
            "additionalProperties": False,
            "x-softschema": {"contract": _CONTRACT_ID},
        }
    )
    contract = replace(
        _contract(),
        schema_bytes=schema_bytes,
        schema_bytes_sha256=_schema_bytes_digest(schema_bytes),
        schema_digest=_schema_digest(schema_bytes),
        validate_record=_validate_identity_record,
    )
    registry = build_contract_registry((contract,))

    with pytest.raises(ValueError, match="non-portable YAML values"):
        serialize_artifact(
            {"value": nonportable_value},
            contract_id=_CONTRACT_ID,
            contracts=registry,
        )


def test_artifact_parsing_uses_portable_yaml() -> None:
    registry = build_contract_registry((_contract(),))
    with_bom_and_crlf = (
        b"\xef\xbb\xbfsoftschema:\r\n"
        b"  contract: example.test:Item/v1\r\n"
        b"  envelope: item\r\n"
        b"  status: enforced\r\n"
        b"item:\r\n"
        b"  name: accepted\r\n"
    )
    alias_payload = (
        b"softschema:\n"
        b"  contract: example.test:Item/v1\n"
        b"  envelope: item\n"
        b"  status: enforced\n"
        b"item:\n"
        b"  name: &name accepted\n"
    )

    artifact = validate_artifact(
        with_bom_and_crlf, expected_contract_id=_CONTRACT_ID, contracts=registry
    )

    assert artifact.record == {"name": "accepted"}
    with pytest.raises(ValueError, match="malformed YAML"):
        validate_artifact(alias_payload, expected_contract_id=_CONTRACT_ID, contracts=registry)
    with pytest.raises(ValueError, match="must be UTF-8"):
        validate_artifact(b"\xff\xfe", expected_contract_id=_CONTRACT_ID, contracts=registry)


def test_contract_registry_rejects_invalid_corpus_record_selectors() -> None:
    contract = _contract()

    with pytest.raises(ContractRegistryError, match="corpus_record_selectors"):
        build_contract_registry(
            (
                replace(
                    contract,
                    corpus_record_selectors=("fixture-record", "fixture-record"),
                ),
            )
        )
