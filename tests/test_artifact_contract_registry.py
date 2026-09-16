from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import date
from typing import Any, cast

import pytest
from frontmatter_format import FmFormatError

from metabrowser.plugin_loader.artifact_contracts import (
    ArtifactContractSpec,
    CapabilityRegistryError,
    CapabilitySet,
    build_contract_registry,
    build_resource_profile_registry,
    contract_inventory,
    resolve_resource_profile,
    serialize_artifact,
    validate_artifact,
    validate_record,
)
from metabrowser.plugin_loader.capability_discovery import LoadedCapabilitySet
from metabrowser.plugin_loader.capability_types import (
    ArtifactProfile,
    ArtifactValidationContext,
    BrowserParserSpec,
    ConformanceCorpusSpec,
)
from metabrowser.provider_resources.profiles import (
    CollectionPaginationPolicy,
    ResourceCollectionSpec,
    ResourceProfileSpec,
    ResourceTargetClass,
)

_CONTRACT_ID = "example.test:Item/v1"
_PROFILE_ID = "example.test:item/v1"


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


def _validate_record(
    value: dict[str, Any],
    _context: ArtifactValidationContext,
) -> dict[str, Any]:
    if value["name"] == "semantic-invalid":
        raise ValueError("semantic validation failed")
    return dict(value)


def _validate_identity_record(
    value: dict[str, Any],
    _context: ArtifactValidationContext,
) -> dict[str, Any]:
    return dict(value)


def _dump_record(value: object) -> dict[str, Any]:
    return dict(cast(dict[str, Any], value))


def _contract(contract_id: str = _CONTRACT_ID) -> ArtifactContractSpec:
    schema_bytes = _schema_bytes(contract_id)
    corpus_payload = b'{"cases":[]}'
    return ArtifactContractSpec(
        contract_id=contract_id,
        artifact_profile="frontmatter-md",
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
        browser_parser=None,
    )


def _profile() -> ResourceProfileSpec:
    return ResourceProfileSpec(
        profile_id=_PROFILE_ID,
        target_class=ResourceTargetClass.provider_object,
        target_result_contract_id=None,
        collections=(
            ResourceCollectionSpec(
                name="item",
                artifact_contract_id=_CONTRACT_ID,
                minimum_artifacts=1,
                maximum_artifacts=1,
                pagination=CollectionPaginationPolicy.forbidden,
                required_for_last_complete=True,
            ),
        ),
    )


def _provider(
    provider_id: str,
    *,
    contracts: tuple[ArtifactContractSpec, ...] = (),
    profiles: tuple[ResourceProfileSpec, ...] = (),
) -> LoadedCapabilitySet:
    return LoadedCapabilitySet(
        provider_id=provider_id,
        source_distribution="fixture-dist",
        capabilities=CapabilitySet(
            artifact_contracts=contracts,
            resource_profiles=profiles,
        ),
    )


def test_contract_and_profile_registries_are_immutable_and_cross_checked() -> None:
    provider = _provider("fixture", contracts=(_contract(),), profiles=(_profile(),))

    contracts = build_contract_registry((provider,))
    profiles = build_resource_profile_registry((provider,), contracts=contracts)

    assert contracts[_CONTRACT_ID].spec.contract_id == _CONTRACT_ID
    assert resolve_resource_profile(_PROFILE_ID, profiles=profiles) == _profile()
    with pytest.raises(TypeError):
        cast(dict[str, object], contracts)[_CONTRACT_ID] = object()
    with pytest.raises(TypeError):
        cast(dict[str, object], profiles)[_PROFILE_ID] = object()


def test_duplicate_contract_and_profile_ids_fail_even_when_declarations_match() -> None:
    first = _provider("first", contracts=(_contract(),), profiles=(_profile(),))
    second = _provider("second", contracts=(_contract(),), profiles=(_profile(),))

    with pytest.raises(CapabilityRegistryError, match="duplicate artifact contract"):
        build_contract_registry((first, second))

    contracts = build_contract_registry((first,))
    with pytest.raises(CapabilityRegistryError, match="duplicate resource profile"):
        build_resource_profile_registry((first, second), contracts=contracts)


def test_contract_id_is_validated_before_registry_key_use() -> None:
    malformed = replace(_contract(), contract_id=cast(Any, []))

    with pytest.raises(CapabilityRegistryError, match="contract ID"):
        build_contract_registry((_provider("fixture", contracts=(malformed,)),))


def test_registry_rejects_schema_digest_id_and_remote_reference_mismatches() -> None:
    contract = _contract()
    tampered_schema = contract.schema_bytes.replace(
        b'"type":"object"',
        b'"title":"tampered","type":"object"',
        1,
    )
    with pytest.raises(CapabilityRegistryError, match="schema bytes digest"):
        build_contract_registry(
            (
                _provider(
                    "fixture",
                    contracts=(replace(contract, schema_bytes=tampered_schema),),
                ),
            )
        )
    with pytest.raises(CapabilityRegistryError, match="schema digest"):
        build_contract_registry(
            (_provider("fixture", contracts=(replace(contract, schema_digest="0" * 64),)),)
        )

    mutated_schema = cast(dict[str, Any], json.loads(contract.schema_bytes))
    mutated_schema["description"] = "changed without recompiling the logical identity"
    mutated_schema_bytes = json.dumps(
        mutated_schema,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    with pytest.raises(CapabilityRegistryError, match="schema digest"):
        build_contract_registry(
            (
                _provider(
                    "fixture",
                    contracts=(
                        replace(
                            contract,
                            schema_bytes=mutated_schema_bytes,
                            schema_bytes_sha256=_schema_bytes_digest(mutated_schema_bytes),
                        ),
                    ),
                ),
            )
        )

    wrong_contract = _schema_bytes("example.test:Wrong/v1")
    with pytest.raises(CapabilityRegistryError, match="x-softschema contract"):
        build_contract_registry(
            (
                _provider(
                    "fixture",
                    contracts=(
                        replace(
                            contract,
                            schema_bytes=wrong_contract,
                            schema_bytes_sha256=_schema_bytes_digest(wrong_contract),
                            schema_digest=_schema_digest(wrong_contract),
                        ),
                    ),
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
    with pytest.raises(CapabilityRegistryError, match=r"local \$defs"):
        build_contract_registry(
            (
                _provider(
                    "fixture",
                    contracts=(
                        replace(
                            contract,
                            schema_bytes=remote_ref,
                            schema_bytes_sha256=_schema_bytes_digest(remote_ref),
                            schema_digest=_schema_digest(remote_ref),
                        ),
                    ),
                ),
            )
        )


def test_registry_verifies_resolvable_corpus_and_browser_parser_evidence() -> None:
    contract = _contract()
    with pytest.raises(CapabilityRegistryError, match="corpus payload digest"):
        build_contract_registry(
            (
                _provider(
                    "fixture",
                    contracts=(
                        replace(
                            contract,
                            corpus=replace(contract.corpus, payload=b'{"changed":true}'),
                        ),
                    ),
                ),
            )
        )

    module_bytes = b"export function parseItem(value) { return value; }\n"
    parser = BrowserParserSpec(
        module_id="fixture-model",
        module_bytes=module_bytes,
        module_bytes_sha256=_schema_bytes_digest(module_bytes),
        export_name="parseItem",
    )
    for malformed_parser in (
        replace(parser, module_id=cast(Any, None)),
        replace(parser, export_name=cast(Any, None)),
        replace(parser, export_name=cast(Any, True)),
    ):
        with pytest.raises(CapabilityRegistryError, match="browser parser must name"):
            build_contract_registry(
                (
                    _provider(
                        "fixture",
                        contracts=(replace(contract, browser_parser=malformed_parser),),
                    ),
                )
            )
    with pytest.raises(CapabilityRegistryError, match="browser parser module digest"):
        build_contract_registry(
            (
                _provider(
                    "fixture",
                    contracts=(
                        replace(
                            contract,
                            browser_parser=replace(parser, module_bytes=b"changed"),
                        ),
                    ),
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
        with pytest.raises(CapabilityRegistryError, match="cannot be enforced"):
            build_contract_registry(
                (
                    _provider(
                        "fixture",
                        contracts=(
                            replace(
                                contract,
                                schema_bytes=schema_bytes,
                                schema_bytes_sha256=_schema_bytes_digest(schema_bytes),
                                schema_digest=_schema_digest(schema_bytes),
                            ),
                        ),
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

    with pytest.raises(CapabilityRegistryError, match="must declare Draft 2020-12"):
        build_contract_registry((_provider("fixture", contracts=(contract,)),))


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
        with pytest.raises(CapabilityRegistryError, match="schema is not portable"):
            build_contract_registry(
                (
                    _provider(
                        "fixture",
                        contracts=(
                            replace(
                                contract,
                                schema_bytes=schema_bytes,
                                schema_bytes_sha256=_schema_bytes_digest(schema_bytes),
                                schema_digest="0" * 64,
                            ),
                        ),
                    ),
                )
            )


def test_profile_references_only_installed_artifact_contracts() -> None:
    provider = _provider("fixture", profiles=(_profile(),))

    with pytest.raises(CapabilityRegistryError, match="unregistered artifact contract"):
        build_resource_profile_registry((provider,), contracts={})


def test_profile_cannot_claim_another_capability_providers_contract() -> None:
    contract_provider = _provider("contract-owner", contracts=(_contract(),))
    profile_provider = _provider("profile-owner", profiles=(_profile(),))
    contracts = build_contract_registry((contract_provider,))

    with pytest.raises(CapabilityRegistryError, match="owned by another capability provider"):
        build_resource_profile_registry((profile_provider,), contracts=contracts)


def test_cached_artifact_can_name_but_cannot_supply_its_schema() -> None:
    contract = _contract()
    registry = build_contract_registry((_provider("fixture", contracts=(contract,)),))
    payload = (
        b"---\n"
        b"softschema:\n"
        b"  contract: example.test:Item/v1\n"
        b"  envelope: item\n"
        b"  status: enforced\n"
        b"item:\n"
        b"  name: accepted\n"
        b"---\n"
        b"Reader-facing body.\n"
    )

    artifact = validate_artifact(
        payload,
        expected_contract_id=_CONTRACT_ID,
        contracts=registry,
    )

    assert artifact.contract_id == _CONTRACT_ID
    assert artifact.record == {"name": "accepted"}
    assert artifact.body == "Reader-facing body.\n"

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
    registry_with_other = build_contract_registry(
        (_provider("fixture", contracts=(contract, other_contract)),)
    )
    wrong_slot_payload = payload.replace(_CONTRACT_ID.encode(), other_contract_id.encode())
    with pytest.raises(ValueError, match="does not match its expected contract"):
        validate_artifact(
            wrong_slot_payload,
            expected_contract_id=_CONTRACT_ID,
            contracts=registry_with_other,
        )


def test_record_validation_applies_structural_and_semantic_contracts() -> None:
    registry = build_contract_registry((_provider("fixture", contracts=(_contract(),)),))

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
    registry = build_contract_registry((_provider("fixture", contracts=(open_contract,)),))

    with pytest.raises(ValueError, match="does not satisfy contract"):
        validate_record(
            {"name": "accepted", "undeclared": True},
            contract_id=_CONTRACT_ID,
            contracts=registry,
        )


def test_installed_contract_serialization_round_trips_both_profiles() -> None:
    frontmatter_contract = _contract()
    pure_yaml_contract = replace(frontmatter_contract, artifact_profile="pure-yaml")
    frontmatter_registry = build_contract_registry(
        (_provider("frontmatter", contracts=(frontmatter_contract,)),)
    )
    pure_yaml_registry = build_contract_registry(
        (_provider("pure-yaml", contracts=(pure_yaml_contract,)),)
    )
    record = {"name": "accepted"}

    frontmatter_payload = serialize_artifact(
        record,
        contract_id=_CONTRACT_ID,
        contracts=frontmatter_registry,
        body="Reader-facing body.\n",
    )
    pure_yaml_payload = serialize_artifact(
        record,
        contract_id=_CONTRACT_ID,
        contracts=pure_yaml_registry,
    )

    assert (
        serialize_artifact(
            record,
            contract_id=_CONTRACT_ID,
            contracts=frontmatter_registry,
            body="Reader-facing body.\n",
        )
        == frontmatter_payload
    )
    assert (
        validate_artifact(
            frontmatter_payload,
            expected_contract_id=_CONTRACT_ID,
            contracts=frontmatter_registry,
        ).body
        == "Reader-facing body.\n"
    )
    assert (
        validate_artifact(
            pure_yaml_payload,
            expected_contract_id=_CONTRACT_ID,
            contracts=pure_yaml_registry,
        ).record
        == record
    )
    with pytest.raises(ValueError, match="cannot contain a Markdown body"):
        serialize_artifact(
            record,
            contract_id=_CONTRACT_ID,
            contracts=pure_yaml_registry,
            body="not allowed",
        )


@pytest.mark.parametrize("artifact_profile", ["frontmatter-md", "pure-yaml"])
@pytest.mark.parametrize(
    "nonportable_value",
    [float("nan"), 9_007_199_254_740_992, date(2026, 9, 15), ("tuple",)],
)
def test_artifact_serialization_rejects_nonportable_values(
    artifact_profile: ArtifactProfile,
    nonportable_value: object,
) -> None:
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
        artifact_profile=artifact_profile,
        schema_bytes=schema_bytes,
        schema_bytes_sha256=_schema_bytes_digest(schema_bytes),
        schema_digest=_schema_digest(schema_bytes),
        validate_record=_validate_identity_record,
    )
    registry = build_contract_registry((_provider("fixture", contracts=(contract,)),))

    with pytest.raises(ValueError, match="non-portable YAML values"):
        serialize_artifact(
            {"value": nonportable_value},
            contract_id=_CONTRACT_ID,
            contracts=registry,
        )


def test_artifact_parsing_uses_portable_yaml_and_preserves_body_bytes() -> None:
    contract = _contract()
    frontmatter_registry = build_contract_registry(
        (_provider("frontmatter", contracts=(contract,)),)
    )
    pure_yaml_registry = build_contract_registry(
        (
            _provider(
                "pure-yaml",
                contracts=(replace(contract, artifact_profile="pure-yaml"),),
            ),
        )
    )
    bom_and_spaced_fences = (
        b"\xef\xbb\xbf---   \r\n"
        b"softschema:\r\n"
        b"  contract: example.test:Item/v1\r\n"
        b"  envelope: item\r\n"
        b"  status: enforced\r\n"
        b"item:\r\n"
        b"  name: accepted\r\n"
        b"---   \r\n"
        b"Body bytes stay exact.\r\n"
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
        bom_and_spaced_fences,
        expected_contract_id=_CONTRACT_ID,
        contracts=frontmatter_registry,
    )

    assert artifact.body == "Body bytes stay exact.\r\n"
    with pytest.raises(FmFormatError, match="malformed YAML"):
        validate_artifact(
            alias_payload,
            expected_contract_id=_CONTRACT_ID,
            contracts=pure_yaml_registry,
        )


def test_contract_inventory_identity_does_not_depend_on_declaring_provider() -> None:
    contract = _contract()
    before = build_contract_registry((_provider("hosted-review", contracts=(contract,)),))
    after = build_contract_registry((_provider("provider-resources", contracts=(contract,)),))

    assert contract_inventory(before) == contract_inventory(after)
    assert "declaring_module" not in json.dumps(contract_inventory(before))
    assert "fixture-dist" not in json.dumps(contract_inventory(before))
    assert contract_inventory(before)[0]["schema_bytes_sha256"] == contract.schema_bytes_sha256
    assert contract_inventory(before)[0]["corpus_payload_sha256"] == (
        contract.corpus.payload_sha256
    )
    assert contract_inventory(before)[0]["corpus_record_selectors"] == ("fixture-record",)


def test_contract_registry_rejects_invalid_corpus_record_selectors() -> None:
    contract = _contract()

    with pytest.raises(CapabilityRegistryError, match="corpus_record_selectors"):
        build_contract_registry(
            (
                _provider(
                    "fixture",
                    contracts=(
                        replace(
                            contract,
                            corpus_record_selectors=("fixture-record", "fixture-record"),
                        ),
                    ),
                ),
            )
        )
