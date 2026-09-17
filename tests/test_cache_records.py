"""SoftSchema contracts and compiled-schema evidence for application-home records."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, cast

import pytest
from softschema import SchemaStatus, SchemaView, compile_model

from metabrowser.cache.contracts import (
    CACHE_CONTRACT_BY_ID,
    CACHE_CONTRACTS,
    CAPABILITY_PROVIDER_ID,
    ENFORCED_CACHE_CONTRACTS,
    FORMAT_ROOT,
    MAX_CONFIG_REASONS,
    cache_contract_registry,
    check_packaged_schemas,
    compile_contracts,
    config_corpus,
    config_reasons,
    parse_application_config,
    repository_cache_capabilities,
    validate_config_values,
)
from metabrowser.cache.records import (
    CACHE_LAYOUT_CONTRACT_ID,
    CONFIG_CONTRACT_ID,
    REPOSITORY_SOURCE_CONTRACT_ID,
    REPOSITORY_SOURCE_STATE_CONTRACT_ID,
    REPOSITORY_STORE_ALIAS_CONTRACT_ID,
    REPOSITORY_STORE_CONTRACT_ID,
    REPOSITORY_STORE_STATE_CONTRACT_ID,
    RepositorySource,
)
from metabrowser.plugin_loader.artifact_contracts import (
    InstalledRegistries,
    serialize_artifact,
    validate_artifact,
    validate_record,
)
from metabrowser.plugin_loader.artifact_inventory import check_installed_evidence
from metabrowser.plugin_loader.capability_discovery import discover_capability_sets

EXPECTED_CONTRACTS = {
    CONFIG_CONTRACT_ID: ("application-config-v1.schema.yaml", "config", SchemaStatus.permissive),
    CACHE_LAYOUT_CONTRACT_ID: ("cache-layout-v1.schema.yaml", "layout", SchemaStatus.enforced),
    REPOSITORY_SOURCE_CONTRACT_ID: (
        "repository-source-v1.schema.yaml",
        "source",
        SchemaStatus.enforced,
    ),
    REPOSITORY_SOURCE_STATE_CONTRACT_ID: (
        "repository-source-state-v1.schema.yaml",
        "state",
        SchemaStatus.enforced,
    ),
    REPOSITORY_STORE_ALIAS_CONTRACT_ID: (
        "repository-store-alias-v1.schema.yaml",
        "alias",
        SchemaStatus.enforced,
    ),
    REPOSITORY_STORE_CONTRACT_ID: (
        "repository-store-v1.schema.yaml",
        "store",
        SchemaStatus.enforced,
    ),
    REPOSITORY_STORE_STATE_CONTRACT_ID: (
        "repository-store-state-v1.schema.yaml",
        "state",
        SchemaStatus.enforced,
    ),
}


def _registries() -> InstalledRegistries:
    return InstalledRegistries(contracts=cache_contract_registry(), resource_profiles={})


def _base_records() -> dict[str, dict[str, Any]]:
    corpus = json.loads((FORMAT_ROOT / "cache-records-conformance.json").read_text())
    return cast(dict[str, dict[str, Any]], corpus["base_records"])


def _valid_record(contract_id: str) -> dict[str, Any]:
    selector = CACHE_CONTRACT_BY_ID[contract_id].corpus_record_selectors[0]
    return copy.deepcopy(_base_records()[selector])


def _artifact(contract_id: str, record: dict[str, Any], **softschema: str) -> bytes:
    contract = CACHE_CONTRACT_BY_ID[contract_id]
    metadata = {
        "contract": contract_id,
        "envelope": contract.envelope,
        "status": "enforced",
        **softschema,
    }
    return json.dumps({"softschema": metadata, contract.envelope: record}).encode()


def test_contract_inventory_is_exact() -> None:
    assert {
        contract.contract_id: (contract.schema_name, contract.envelope, contract.status)
        for contract in CACHE_CONTRACTS
    } == EXPECTED_CONTRACTS
    assert {path.name for path in (FORMAT_ROOT / "schemas").glob("*.schema.yaml")} == {
        schema_name for schema_name, _, _ in EXPECTED_CONTRACTS.values()
    }
    assert [contract.contract_id for contract in CACHE_CONTRACTS] == sorted(EXPECTED_CONTRACTS)


def test_compiled_schemas_match_their_models_and_contract_ids() -> None:
    results = compile_contracts(check_only=True)

    assert check_packaged_schemas() == ()
    for contract, result in zip(CACHE_CONTRACTS, results, strict=True):
        assert result.out_path == contract.schema_path
        assert result.drift is False, result.drift_diff
        view = SchemaView.load(result.out_path)
        assert view.contract_id == contract.contract_id
        assert view.schema_sha256 == result.schema_sha256


def test_a_model_change_without_recompiling_is_reported_as_drift(tmp_path: Path) -> None:
    contract = CACHE_CONTRACT_BY_ID[CACHE_LAYOUT_CONTRACT_ID]
    stale = tmp_path / contract.schema_name
    text = contract.schema_path.read_text(encoding="utf-8")
    stale.write_text(text.replace("created_by", "created_with"), encoding="utf-8")

    result = compile_model(contract.model, stale, contract_id=contract.contract_id, check_only=True)

    assert result.drift is True


def test_installed_specs_carry_the_packaged_schema_bytes_and_digests() -> None:
    specs = {spec.contract_id: spec for spec in repository_cache_capabilities().artifact_contracts}

    assert set(specs) == {contract.contract_id for contract in ENFORCED_CACHE_CONTRACTS}
    assert CONFIG_CONTRACT_ID not in specs
    for contract in ENFORCED_CACHE_CONTRACTS:
        spec = specs[contract.contract_id]
        schema_bytes = contract.schema_path.read_bytes()
        assert spec.schema_bytes == schema_bytes
        assert spec.schema_bytes_sha256 == hashlib.sha256(schema_bytes).hexdigest()
        assert spec.schema_digest == SchemaView.load(contract.schema_path).schema_sha256
        assert spec.artifact_profile == "pure-yaml"
        assert spec.browser_consumed is False
        assert spec.corpus_record_selectors == contract.corpus_record_selectors


def test_the_enforced_corpus_passes_the_generic_evidence_gate() -> None:
    assert check_installed_evidence(_registries()) == ()


def test_the_repository_cache_provider_is_installed_through_its_entry_point() -> None:
    discovery = discover_capability_sets()

    assert discovery.errors == ()
    (provider,) = [p for p in discovery.providers if p.provider_id == CAPABILITY_PROVIDER_ID]
    assert {spec.contract_id for spec in provider.capabilities.artifact_contracts} == {
        contract.contract_id for contract in ENFORCED_CACHE_CONTRACTS
    }


def test_config_corpus_cases_have_their_expected_outcomes() -> None:
    corpus = config_corpus()
    outcomes: dict[str, bool] = {}
    for case in corpus["cases"]:
        record = copy.deepcopy(corpus["base_records"][case["record"]])
        for change in case["changes"]:
            target = record
            for part in change["path"][:-1]:
                target = target[part]
            target[change["path"][-1]] = change["value"]
        result = validate_config_values(record)
        outcomes[case["name"]] = result.structural.ok and result.semantic.ok
        assert outcomes[case["name"]] is (case["expect"] == "valid"), case["name"]
    assert any(outcomes.values())
    assert not all(outcomes.values())


def test_config_keeps_unknown_settings_at_every_level() -> None:
    values = {
        "format": "f01",
        "written_by": "0.11.0",
        "upgrades": [{"version": "0.11.0", "at": "2026-09-17T00:00:00Z", "note": "kept"}],
        "cache": {"root": "~/.metabrowser/cache", "refresh": "manual"},
        "future_setting": [1, 2, 3],
    }

    config = parse_application_config(values)

    assert config.model_dump(mode="json") == values


def test_config_refuses_credentials_under_any_known_or_unknown_key() -> None:
    values = {
        "format": "f01",
        "written_by": "0.11.0",
        "upgrades": [],
        "providers": [{"github": {"api_key": "example"}}],
    }

    with pytest.raises(ValueError, match="credentials"):
        parse_application_config(values)


@pytest.mark.parametrize(
    "contract_id", sorted(contract.contract_id for contract in ENFORCED_CACHE_CONTRACTS)
)
def test_machine_records_reject_undeclared_fields(contract_id: str) -> None:
    record = _valid_record(contract_id)
    registry = cache_contract_registry()
    validate_record(record, contract_id=contract_id, contracts=registry)

    record["undeclared"] = True

    with pytest.raises(ValueError, match="does not satisfy contract"):
        validate_record(record, contract_id=contract_id, contracts=registry)
    with pytest.raises(ValueError, match="Extra inputs"):
        CACHE_CONTRACT_BY_ID[contract_id].model.model_validate(record)


@pytest.mark.parametrize(
    "contract_id", sorted(contract.contract_id for contract in ENFORCED_CACHE_CONTRACTS)
)
def test_machine_records_round_trip_through_their_installed_serializer(contract_id: str) -> None:
    registry = cache_contract_registry()
    record = validate_record(
        _valid_record(contract_id), contract_id=contract_id, contracts=registry
    )

    payload = serialize_artifact(record, contract_id=contract_id, contracts=registry)
    artifact = validate_artifact(payload, expected_contract_id=contract_id, contracts=registry)

    assert artifact.record == record
    assert b"\n  schema:" not in payload


def test_a_cache_file_cannot_redirect_validation_to_its_own_schema(tmp_path: Path) -> None:
    permissive_schema = tmp_path / "anything.schema.yaml"
    permissive_schema.write_text(
        "$schema: https://json-schema.org/draft/2020-12/schema\ntype: object\n",
        encoding="utf-8",
    )
    record = _valid_record(REPOSITORY_SOURCE_CONTRACT_ID)
    registry = cache_contract_registry()

    with pytest.raises(ValueError, match="softschema metadata must contain"):
        validate_artifact(
            _artifact(REPOSITORY_SOURCE_CONTRACT_ID, record, schema=str(permissive_schema)),
            expected_contract_id=REPOSITORY_SOURCE_CONTRACT_ID,
            contracts=registry,
        )

    record["undeclared"] = True
    with pytest.raises(ValueError, match="does not satisfy contract"):
        validate_artifact(
            _artifact(REPOSITORY_SOURCE_CONTRACT_ID, record),
            expected_contract_id=REPOSITORY_SOURCE_CONTRACT_ID,
            contracts=registry,
        )


def test_a_cache_file_cannot_choose_a_different_contract_or_status() -> None:
    registry = cache_contract_registry()
    layout = _valid_record(CACHE_LAYOUT_CONTRACT_ID)

    with pytest.raises(ValueError, match="does not match its expected contract"):
        validate_artifact(
            _artifact(CACHE_LAYOUT_CONTRACT_ID, layout),
            expected_contract_id=REPOSITORY_STORE_STATE_CONTRACT_ID,
            contracts=registry,
        )
    with pytest.raises(ValueError, match="enforced"):
        validate_artifact(
            _artifact(CACHE_LAYOUT_CONTRACT_ID, layout, status="permissive"),
            expected_contract_id=CACHE_LAYOUT_CONTRACT_ID,
            contracts=registry,
        )


def test_a_source_record_is_bound_to_its_identity_material() -> None:
    record = _valid_record(REPOSITORY_SOURCE_CONTRACT_ID)
    source = RepositorySource.model_validate(record)

    assert source.slug.endswith(source.id.removeprefix("sha256:")[:12])
    with pytest.raises(ValueError, match="does not match its transport"):
        RepositorySource.model_validate({**record, "clone_url": "https://github.com/pallets/Flask"})


def test_a_large_invalid_config_reports_bounded_value_free_reasons() -> None:
    """A broken config can fail once per entry, and its reasons reach an API response."""

    secret = "ghp-examplesecrettokenvalue"
    values = {
        "format": secret,
        "written_by": secret,
        "upgrades": [{"version": secret, "at": secret} for _ in range(2000)],
    }

    with pytest.raises(ValueError) as refused:
        parse_application_config(values)

    message = str(refused.value)
    assert len(message) <= 4096
    assert secret not in message
    assert "errors.pydantic.dev" not in message
    assert message.count(";") < MAX_CONFIG_REASONS
    assert message.endswith(" more")
    assert "config.upgrades" in message


def test_config_reasons_name_the_rule_and_location_of_every_error() -> None:
    result = validate_config_values(
        {"format": "f01", "written_by": "0.11.0", "upgrades": [{"version": "0.11.0"}]}
    )

    reasons = config_reasons(result)

    assert reasons
    assert all(reason.startswith("config") for reason in reasons)
    assert any("upgrades.0" in reason for reason in reasons)
