"""SoftSchema contract and compiled-schema evidence for hosted-review records."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import TypeAdapter, ValidationError
from softschema import SchemaProfile, SchemaView

from metabrowser.builtin_plugins.hosted_review.contracts import (
    HOSTED_REVIEW_BROWSER_CONTRACT_IDS,
    HOSTED_REVIEW_CONTRACTS,
    HOSTED_REVIEW_SERVER_ONLY_CONTRACT_IDS,
    build_hosted_review_contract_registry,
    compile_contracts,
    hosted_review_capabilities,
    provider_resource_capabilities,
    validate_contract_values,
)
from metabrowser.builtin_plugins.hosted_review.models import (
    CHANGE_REQUEST_COMMENT_CONTRACT_ID,
    CHANGE_REQUEST_CONTRACT_ID,
    CHANGE_REQUEST_INDEX_CONTRACT_ID,
    CHECK_CONTRACT_ID,
    COMMIT_STATUS_CONTRACT_ID,
    HOSTED_REPOSITORY_CONTRACT_ID,
    PROVIDER_BINDING_CONTRACT_ID,
    PROVIDER_SYNC_MANIFEST_CONTRACT_ID,
    PROVIDER_VIEW_POINTER_CONTRACT_ID,
    REPOSITORY_ACTIVITY_CONTRACT_ID,
    RESOURCE_SET_CONTRACT_ID,
    RETRIEVAL_CONTRACT_ID,
    REVIEW_COMMENT_CONTRACT_ID,
    REVIEW_CONTRACT_ID,
    REVIEW_THREAD_CONTRACT_ID,
    TOMBSTONE_CONTRACT_ID,
    ChangeRequest,
    DefaultBranchAvailability,
    LocalGitObjectAvailability,
    LocalObjectAvailability,
    ResourceSet,
    RevisionObservation,
)
from metabrowser.builtin_plugins.hosted_review.resource_profiles import (
    CHANGE_REQUEST_INDEX_PROFILE_ID,
    REPOSITORY_SUMMARY_PROFILE,
    REPOSITORY_SUMMARY_PROFILE_ID,
)
from metabrowser.plugin_loader.artifact_contracts import (
    build_installed_registries,
    serialize_artifact,
    validate_artifact,
)
from metabrowser.plugin_loader.artifact_contracts import (
    validate_record as validate_installed_record,
)
from metabrowser.plugin_loader.capability_discovery import (
    CapabilityDiscoveryResult,
    LoadedCapabilitySet,
)

FORMAT_ROOT = Path(__file__).resolve().parents[1] / "src/metabrowser/data/hosted-review-format"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

EXPECTED_BROWSER_CONTRACT_IDS = frozenset(
    {
        HOSTED_REPOSITORY_CONTRACT_ID,
        CHANGE_REQUEST_INDEX_CONTRACT_ID,
        CHANGE_REQUEST_CONTRACT_ID,
        CHANGE_REQUEST_COMMENT_CONTRACT_ID,
        REVIEW_CONTRACT_ID,
        REVIEW_THREAD_CONTRACT_ID,
        REVIEW_COMMENT_CONTRACT_ID,
        CHECK_CONTRACT_ID,
        COMMIT_STATUS_CONTRACT_ID,
        REPOSITORY_ACTIVITY_CONTRACT_ID,
    }
)
EXPECTED_SERVER_ONLY_CONTRACT_IDS = frozenset(
    {
        PROVIDER_BINDING_CONTRACT_ID,
        RETRIEVAL_CONTRACT_ID,
        RESOURCE_SET_CONTRACT_ID,
        PROVIDER_SYNC_MANIFEST_CONTRACT_ID,
        PROVIDER_VIEW_POINTER_CONTRACT_ID,
        TOMBSTONE_CONTRACT_ID,
    }
)
FRONTMATTER_CONTRACT_IDS = frozenset(
    {
        CHANGE_REQUEST_CONTRACT_ID,
        CHANGE_REQUEST_COMMENT_CONTRACT_ID,
        REVIEW_CONTRACT_ID,
        REVIEW_COMMENT_CONTRACT_ID,
    }
)
EXPECTED_SCHEMA_NAME_BY_CONTRACT = {
    PROVIDER_BINDING_CONTRACT_ID: "provider-binding-v1.schema.yaml",
    RETRIEVAL_CONTRACT_ID: "retrieval-v1.schema.yaml",
    HOSTED_REPOSITORY_CONTRACT_ID: "hosted-repository-v1.schema.yaml",
    RESOURCE_SET_CONTRACT_ID: "resource-set-v1.schema.yaml",
    PROVIDER_SYNC_MANIFEST_CONTRACT_ID: "provider-sync-manifest-v1.schema.yaml",
    PROVIDER_VIEW_POINTER_CONTRACT_ID: "provider-view-pointer-v1.schema.yaml",
    TOMBSTONE_CONTRACT_ID: "tombstone-v1.schema.yaml",
    CHANGE_REQUEST_INDEX_CONTRACT_ID: "change-request-index-v1.schema.yaml",
    CHANGE_REQUEST_CONTRACT_ID: "change-request-v1.schema.yaml",
    CHANGE_REQUEST_COMMENT_CONTRACT_ID: "change-request-comment-v1.schema.yaml",
    REVIEW_CONTRACT_ID: "review-v1.schema.yaml",
    REVIEW_THREAD_CONTRACT_ID: "review-thread-v1.schema.yaml",
    REVIEW_COMMENT_CONTRACT_ID: "review-comment-v1.schema.yaml",
    CHECK_CONTRACT_ID: "check-v1.schema.yaml",
    COMMIT_STATUS_CONTRACT_ID: "commit-status-v1.schema.yaml",
    REPOSITORY_ACTIVITY_CONTRACT_ID: "repository-activity-v1.schema.yaml",
}
EXPECTED_BROWSER_PARSER_IDS = {
    HOSTED_REPOSITORY_CONTRACT_ID: "hosted-review-model:parseHostedRepository",
    CHANGE_REQUEST_INDEX_CONTRACT_ID: "hosted-review-model:parseChangeRequestIndex",
    CHANGE_REQUEST_CONTRACT_ID: "hosted-review-model:parseChangeRequest",
    CHANGE_REQUEST_COMMENT_CONTRACT_ID: "hosted-review-model:parseChangeRequestComment",
    REVIEW_CONTRACT_ID: "hosted-review-model:parseReview",
    REVIEW_THREAD_CONTRACT_ID: "hosted-review-model:parseReviewThread",
    REVIEW_COMMENT_CONTRACT_ID: "hosted-review-model:parseReviewComment",
    CHECK_CONTRACT_ID: "hosted-review-model:parseCheck",
    COMMIT_STATUS_CONTRACT_ID: "hosted-review-model:parseCommitStatus",
    REPOSITORY_ACTIVITY_CONTRACT_ID: "hosted-review-model:parseRepositoryActivity",
}
EXPECTED_CORPUS_RECORD_SELECTORS = {
    PROVIDER_BINDING_CONTRACT_ID: ("provider_binding",),
    RETRIEVAL_CONTRACT_ID: ("retrieval", "deletion_retrieval"),
    HOSTED_REPOSITORY_CONTRACT_ID: ("hosted_repository",),
    RESOURCE_SET_CONTRACT_ID: ("resource_set",),
    PROVIDER_SYNC_MANIFEST_CONTRACT_ID: ("provider_sync_manifest",),
    PROVIDER_VIEW_POINTER_CONTRACT_ID: ("provider_view_pointer",),
    TOMBSTONE_CONTRACT_ID: ("tombstone",),
    CHANGE_REQUEST_INDEX_CONTRACT_ID: (
        "change_request_index",
        "empty_change_request_index",
    ),
    CHANGE_REQUEST_CONTRACT_ID: (),
    CHANGE_REQUEST_COMMENT_CONTRACT_ID: ("change_request_comment",),
    REVIEW_CONTRACT_ID: ("review",),
    REVIEW_THREAD_CONTRACT_ID: ("review_thread", "review_thread_empty"),
    REVIEW_COMMENT_CONTRACT_ID: ("review_comment", "review_comment_reply"),
    CHECK_CONTRACT_ID: ("check_suite", "check_run"),
    COMMIT_STATUS_CONTRACT_ID: ("commit_status",),
    REPOSITORY_ACTIVITY_CONTRACT_ID: (),
}


def _load(name: str) -> dict[str, Any]:
    return json.loads((FORMAT_ROOT / name).read_text(encoding="utf-8"))


def _valid_records() -> dict[str, dict[str, Any]]:
    change_request = _load("change-request-conformance.json")
    change_request_index = _load("change-request-index-conformance.json")
    hosted_repository = _load("hosted-repository-conformance.json")
    provider_storage = _load("provider-storage-conformance.json")
    repository_activity = _load("repository-activity-conformance.json")
    review_records = _load("review-records-conformance.json")
    return {
        PROVIDER_BINDING_CONTRACT_ID: hosted_repository["base_records"]["provider_binding"],
        RETRIEVAL_CONTRACT_ID: provider_storage["base_records"]["retrieval"],
        RESOURCE_SET_CONTRACT_ID: provider_storage["base_records"]["resource_set"],
        PROVIDER_SYNC_MANIFEST_CONTRACT_ID: provider_storage["base_records"][
            "provider_sync_manifest"
        ],
        PROVIDER_VIEW_POINTER_CONTRACT_ID: provider_storage["base_records"][
            "provider_view_pointer"
        ],
        TOMBSTONE_CONTRACT_ID: provider_storage["base_records"]["tombstone"],
        HOSTED_REPOSITORY_CONTRACT_ID: hosted_repository["base_records"]["hosted_repository"],
        CHANGE_REQUEST_INDEX_CONTRACT_ID: change_request_index["base_records"][
            "change_request_index"
        ],
        CHANGE_REQUEST_CONTRACT_ID: change_request["base_document"],
        CHANGE_REQUEST_COMMENT_CONTRACT_ID: review_records["base_records"][
            "change_request_comment"
        ],
        REVIEW_CONTRACT_ID: review_records["base_records"]["review"],
        REVIEW_THREAD_CONTRACT_ID: review_records["base_records"]["review_thread"],
        REVIEW_COMMENT_CONTRACT_ID: review_records["base_records"]["review_comment"],
        CHECK_CONTRACT_ID: review_records["base_records"]["check_run"],
        COMMIT_STATUS_CONTRACT_ID: review_records["base_records"]["commit_status"],
        REPOSITORY_ACTIVITY_CONTRACT_ID: repository_activity["base_document"],
    }


def _changed_record(base_record: dict[str, Any], changes: list[dict[str, Any]]) -> dict[str, Any]:
    record = copy.deepcopy(base_record)
    for change in changes:
        path = change["path"]
        target: Any = record
        for part in path[:-1]:
            target = target[part]
        target[path[-1]] = change["value"]
    return record


def test_contract_inventory_is_exact_and_partitions_consumers() -> None:
    ids = tuple(contract.contract_id for contract in HOSTED_REVIEW_CONTRACTS)

    assert ids == tuple(sorted(ids))
    assert len(ids) == len(set(ids)) == 16
    assert HOSTED_REVIEW_BROWSER_CONTRACT_IDS == EXPECTED_BROWSER_CONTRACT_IDS
    assert HOSTED_REVIEW_SERVER_ONLY_CONTRACT_IDS == EXPECTED_SERVER_ONLY_CONTRACT_IDS
    assert EXPECTED_BROWSER_CONTRACT_IDS.isdisjoint(EXPECTED_SERVER_ONLY_CONTRACT_IDS)
    assert frozenset(ids) == EXPECTED_BROWSER_CONTRACT_IDS | EXPECTED_SERVER_ONLY_CONTRACT_IDS


def test_contracts_bind_models_enforced_profiles_envelopes_and_packaged_schemas() -> None:
    for contract in HOSTED_REVIEW_CONTRACTS:
        assert contract.envelope
        assert contract.artifact_profile == (
            SchemaProfile.frontmatter_md.value
            if contract.contract_id in FRONTMATTER_CONTRACT_IDS
            else SchemaProfile.pure_yaml.value
        )
        assert contract.schema_bytes
        assert SHA256_RE.fullmatch(contract.schema_bytes_sha256)
        assert contract.schema_bytes_sha256 == hashlib.sha256(contract.schema_bytes).hexdigest()
        assert SHA256_RE.fullmatch(contract.schema_digest)
        assert contract.producer_ids
        assert contract.consumer_ids
        assert contract.corpus.corpus_id
        assert contract.corpus.media_type == "application/json"
        assert contract.corpus.payload
        assert contract.corpus.payload_sha256 == hashlib.sha256(contract.corpus.payload).hexdigest()
        assert (
            contract.corpus_record_selectors
            == EXPECTED_CORPUS_RECORD_SELECTORS[contract.contract_id]
        )
        browser_parser_id = (
            contract.browser_parser.parser_id if contract.browser_parser is not None else None
        )
        assert contract.browser_consumed is (browser_parser_id is not None)
        assert browser_parser_id == EXPECTED_BROWSER_PARSER_IDS.get(contract.contract_id)
        if contract.browser_parser is not None:
            assert contract.browser_parser.module_bytes
            assert (
                contract.browser_parser.module_bytes_sha256
                == hashlib.sha256(contract.browser_parser.module_bytes).hexdigest()
            )
    assert {path.name for path in (FORMAT_ROOT / "schemas").glob("*.schema.yaml")} == (
        frozenset(EXPECTED_SCHEMA_NAME_BY_CONTRACT.values())
    )


def test_every_embedded_corpus_selector_resolves_and_exercises_its_contract() -> None:
    registries = build_installed_registries()
    for contract in HOSTED_REVIEW_CONTRACTS:
        corpus = json.loads(contract.corpus.payload)
        cases = corpus["cases"]
        selectors = set(contract.corpus_record_selectors)
        case_record_names = {
            test_case.get("record") for test_case in cases if test_case.get("record") is not None
        }
        if selectors:
            assert selectors <= set(corpus["base_records"])
            assert selectors <= case_record_names
        selected_cases = [
            test_case
            for test_case in cases
            if not selectors or test_case.get("record") in selectors
        ]
        assert selected_cases

        for test_case in selected_cases:
            record_name = test_case.get("record")
            base_record = (
                corpus["base_document"]
                if record_name is None
                else corpus["base_records"][record_name]
            )
            document = _changed_record(base_record, test_case["changes"])
            if test_case["expect"] == "valid":
                validate_installed_record(
                    document,
                    contract_id=contract.contract_id,
                    contracts=registries.contracts,
                )
            else:
                with pytest.raises(ValueError):
                    validate_installed_record(
                        document,
                        contract_id=contract.contract_id,
                        contracts=registries.contracts,
                    )


def _string_schemas(
    schema: Any, path: tuple[Any, ...] = ()
) -> Iterator[tuple[tuple[Any, ...], Any]]:
    """Yield every ``str`` node of a Pydantic core schema with the path that reached it."""
    if isinstance(schema, dict):
        if schema.get("type") == "str":
            yield path, schema.get("strict")
        for key, value in cast(dict[str, Any], schema).items():
            yield from _string_schemas(value, (*path, key))
    elif isinstance(schema, list | tuple):
        for index, value in enumerate(cast(list[Any], schema)):
            yield from _string_schemas(value, (*path, index))


def _enum_schemas(schema: Any, path: tuple[Any, ...] = ()) -> Iterator[tuple[tuple[Any, ...], Any]]:
    """Yield every enum node of a Pydantic core schema with the path that reached it."""
    if isinstance(schema, dict):
        if schema.get("type") == "enum":
            yield path, schema["cls"]
        for key, value in cast(dict[str, Any], schema).items():
            yield from _enum_schemas(value, (*path, key))
    elif isinstance(schema, list | tuple):
        for index, value in enumerate(cast(list[Any], schema)):
            yield from _enum_schemas(value, (*path, index))


def test_every_contract_model_enum_refuses_bytes() -> None:
    # A string field is strict, but an enum field is not a string schema: lax mode would
    # decode bytes before the member lookup and admit a value the browser validator
    # refuses. Enum members still arrive as strings, so the rule is on the input type.
    registry = build_hosted_review_contract_registry()
    total = 0
    coercing: list[tuple[str, tuple[Any, ...]]] = []
    for contract in registry.all.values():
        model = contract.model
        assert model is not None, contract.id
        for path, enum_cls in _enum_schemas(model.__pydantic_core_schema__):
            total += 1
            adapter: TypeAdapter[Any] = TypeAdapter(enum_cls)
            member = next(iter(enum_cls))
            assert adapter.validate_python(member.value) is member, (contract.id, path)
            try:
                adapter.validate_python(str(member.value).encode("utf-8"))
            except ValidationError:
                continue
            coercing.append((contract.id, path))

    assert not coercing
    assert total > 0


def test_every_contract_model_string_is_strict() -> None:
    # Lax mode would coerce bytes (a YAML ``!!binary`` scalar) into a string the browser
    # validator refuses, so no registered model may carry a nonstrict string.
    registry = build_hosted_review_contract_registry()
    total = 0
    lax: list[tuple[str, tuple[Any, ...]]] = []
    for contract in registry.all.values():
        model = contract.model
        assert model is not None, contract.id
        for path, strict in _string_schemas(model.__pydantic_core_schema__):
            total += 1
            if strict is not True:
                lax.append((contract.id, path))

    assert not lax
    assert total > 0


def test_compiled_schemas_match_models_contract_ids_and_digests() -> None:
    results = compile_contracts(check_only=True)

    assert tuple(result.out_path for result in results) == tuple(
        FORMAT_ROOT / "schemas" / EXPECTED_SCHEMA_NAME_BY_CONTRACT[contract.contract_id]
        for contract in HOSTED_REVIEW_CONTRACTS
    )
    for contract, result in zip(HOSTED_REVIEW_CONTRACTS, results, strict=True):
        assert result.drift is False, result.drift_diff
        assert result.schema_sha256 is not None
        assert SHA256_RE.fullmatch(result.schema_sha256)
        view = SchemaView.load(result.out_path)
        assert view.contract_id == contract.contract_id
        assert view.schema_sha256 == result.schema_sha256
        assert contract.schema_bytes == result.out_path.read_bytes()
        assert contract.schema_digest == result.schema_sha256


def test_safe_integer_constraints_are_structural_schema_keywords() -> None:
    number = ChangeRequest.model_json_schema()["properties"]["number"]
    assert number["minimum"] == 1
    assert number["maximum"] == 9_007_199_254_740_991


def test_nullable_pagination_composition_has_explicit_closure() -> None:
    schema = ResourceSet.model_json_schema()

    collection_page = schema["$defs"]["CollectionPage"]["properties"]
    assert collection_page["next"]["unevaluatedProperties"] is False
    assert collection_page["requested_with"]["unevaluatedProperties"] is False
    pagination = schema["$defs"]["PaginationEvidence"]["properties"]
    assert pagination["remote_consistency"]["unevaluatedProperties"] is False


def test_registry_resolves_every_contract_and_returns_a_copy() -> None:
    registry = build_hosted_review_contract_registry()

    assert tuple(sorted(registry.all)) == tuple(
        contract.contract_id for contract in HOSTED_REVIEW_CONTRACTS
    )
    for contract in HOSTED_REVIEW_CONTRACTS:
        resolved = registry.resolve(contract.contract_id)
        assert resolved is not None
        assert resolved.id == contract.contract_id
    registry.all.clear()
    assert len(registry.all) == 16


def test_capability_factories_split_neutral_storage_from_domain_contracts() -> None:
    provider_capabilities = provider_resource_capabilities()
    hosted_review = hosted_review_capabilities()

    assert {spec.contract_id for spec in provider_capabilities.artifact_contracts} == {
        contract_id
        for contract_id in EXPECTED_BROWSER_CONTRACT_IDS | EXPECTED_SERVER_ONLY_CONTRACT_IDS
        if ".provider:" in contract_id
    }
    assert tuple(profile.profile_id for profile in provider_capabilities.resource_profiles) == (
        REPOSITORY_SUMMARY_PROFILE_ID,
    )
    assert {spec.contract_id for spec in hosted_review.artifact_contracts} == {
        contract_id
        for contract_id in EXPECTED_BROWSER_CONTRACT_IDS | EXPECTED_SERVER_ONLY_CONTRACT_IDS
        if ".provider:" not in contract_id
    }
    assert tuple(profile.profile_id for profile in hosted_review.resource_profiles) == (
        CHANGE_REQUEST_INDEX_PROFILE_ID,
    )


@pytest.mark.parametrize("contract_id", sorted(_valid_records()))
def test_valid_records_pass_structural_and_semantic_validation(contract_id: str) -> None:
    document = _valid_records()[contract_id]
    result = validate_contract_values(contract_id, document)
    registries = build_installed_registries()
    contract = next(
        contract for contract in HOSTED_REVIEW_CONTRACTS if contract.contract_id == contract_id
    )
    record = validate_installed_record(
        document,
        contract_id=contract_id,
        contracts=registries.contracts,
    )

    assert result.structural.ok, result.structural.errors
    assert result.semantic.ok, result.semantic.errors
    assert contract.dump_record(record) == document


def test_resource_set_contract_applies_the_trusted_profile_registry() -> None:
    document = copy.deepcopy(_valid_records()[RESOURCE_SET_CONTRACT_ID])
    document["profile"] = "com.github.jlevy.metabrowser.provider:missing/v1"

    result = validate_contract_values(RESOURCE_SET_CONTRACT_ID, document)
    registries = build_installed_registries()

    assert result.structural.ok, result.structural.errors
    assert not result.semantic.ok
    assert "unregistered profile" in result.semantic.errors[0]["msg"]
    with pytest.raises(ValueError, match="unregistered profile"):
        validate_installed_record(
            document,
            contract_id=RESOURCE_SET_CONTRACT_ID,
            contracts=registries.contracts,
        )


def test_resource_set_uses_the_exact_atomic_registry_snapshot() -> None:
    capabilities = provider_resource_capabilities()
    custom_profile = replace(
        REPOSITORY_SUMMARY_PROFILE,
        profile_id="example.test:repository-summary/v1",
    )
    discovery = CapabilityDiscoveryResult(
        providers=(
            LoadedCapabilitySet(
                provider_id="provider-resources",
                source_distribution="fixture-dist",
                capabilities=replace(
                    capabilities,
                    resource_profiles=(custom_profile,),
                ),
            ),
        )
    )
    registries = build_installed_registries(discovery)
    document = copy.deepcopy(_valid_records()[RESOURCE_SET_CONTRACT_ID])
    document["profile"] = custom_profile.profile_id

    record = validate_installed_record(
        document,
        contract_id=RESOURCE_SET_CONTRACT_ID,
        contracts=registries.contracts,
    )

    assert isinstance(record, ResourceSet)
    assert record.profile == custom_profile.profile_id


def test_installed_serializer_preserves_required_null_fields() -> None:
    registries = build_installed_registries()
    source = _valid_records()[CHANGE_REQUEST_CONTRACT_ID]
    record = validate_installed_record(
        source,
        contract_id=CHANGE_REQUEST_CONTRACT_ID,
        contracts=registries.contracts,
    )

    payload = serialize_artifact(
        record,
        contract_id=CHANGE_REQUEST_CONTRACT_ID,
        contracts=registries.contracts,
        body="Reader-facing description.\n",
    )
    artifact = validate_artifact(
        payload,
        expected_contract_id=CHANGE_REQUEST_CONTRACT_ID,
        contracts=registries.contracts,
    )

    assert b"merge_commit_oid: null" in payload
    assert artifact.record == record
    assert artifact.body == "Reader-facing description.\n"


@pytest.mark.parametrize("contract_id", sorted(_valid_records()))
def test_enforced_contracts_reject_undeclared_root_fields(contract_id: str) -> None:
    document = copy.deepcopy(_valid_records()[contract_id])
    document["unexpected_contract_field"] = True

    result = validate_contract_values(contract_id, document)

    assert not result.structural.ok
    assert any(error.get("code") == "undeclared_property" for error in result.structural.errors)
    assert not result.semantic.ok


def _object_schema_nodes(node: object) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(node, dict):
        mapping = cast(dict[str, Any], node)
        if mapping.get("type") == "object" or "properties" in mapping:
            found.append(mapping)
        for value in mapping.values():
            found.extend(_object_schema_nodes(value))
    elif isinstance(node, list):
        for value in cast(list[object], node):
            found.extend(_object_schema_nodes(value))
    return found


def test_provider_record_schemas_are_closed_and_cannot_carry_local_object_availability() -> None:
    local_names = {LocalGitObjectAvailability.__name__, LocalObjectAvailability.__name__}
    # `present` also spells DefaultBranchAvailability, and the shared unavailable and
    # not_requested states spell RevisionObservation; the remaining values are local-only.
    local_only_states = (
        {state.value for state in LocalObjectAvailability}
        - {state.value for state in RevisionObservation}
        - {state.value for state in DefaultBranchAvailability}
    )
    assert local_only_states == {"missing_fetchable", "fetch_failed", "outside_bound"}

    for contract in HOSTED_REVIEW_CONTRACTS:
        schema_text = contract.schema_bytes.decode("utf-8")
        assert not any(name in schema_text for name in local_names), contract.contract_id
        assert not any(state in schema_text for state in local_only_states), contract.contract_id
        assert "RevisionAvailability" not in schema_text
        view = SchemaView.load(
            FORMAT_ROOT / "schemas" / EXPECTED_SCHEMA_NAME_BY_CONTRACT[contract.contract_id]
        )
        object_nodes = _object_schema_nodes(view.raw)
        assert object_nodes
        for node in object_nodes:
            assert (
                node.get("additionalProperties") is False
                or node.get("unevaluatedProperties") is False
            ), (contract.contract_id, node.get("title"))


@pytest.mark.parametrize(
    ("contract_id", "revision_path"),
    [
        (CHANGE_REQUEST_CONTRACT_ID, ("comparison", "head")),
        (REVIEW_CONTRACT_ID, ("revision",)),
        (CHECK_CONTRACT_ID, ("revision",)),
        (REPOSITORY_ACTIVITY_CONTRACT_ID, ("items", 1, "head_revision")),
    ],
)
def test_provider_revisions_reject_an_embedded_local_availability_report(
    contract_id: str, revision_path: tuple[str | int, ...]
) -> None:
    document = copy.deepcopy(_valid_records()[contract_id])
    revision: Any = document
    for part in revision_path:
        revision = revision[part]
    report = LocalGitObjectAvailability(
        oid=revision["oid"],
        availability=LocalObjectAvailability.present,
    )
    revision["local_availability"] = report.model_dump(mode="json")

    result = validate_contract_values(contract_id, document)

    assert not result.structural.ok
    assert any(error.get("code") == "undeclared_property" for error in result.structural.errors)
    assert not result.semantic.ok

    local_state = copy.deepcopy(_valid_records()[contract_id])
    revision = local_state
    for part in revision_path:
        revision = revision[part]
    revision["observation"] = LocalObjectAvailability.present.value

    assert not validate_contract_values(contract_id, local_state).semantic.ok


def test_local_object_availability_is_not_an_installed_contract() -> None:
    registry = build_hosted_review_contract_registry()

    assert all(
        contract.model is not LocalGitObjectAvailability for contract in registry.all.values()
    )
    assert all(
        LocalGitObjectAvailability.__name__ not in contract.contract_id
        for contract in HOSTED_REVIEW_CONTRACTS
    )


def test_unknown_contract_id_is_rejected() -> None:
    with pytest.raises(KeyError, match="unregistered hosted-review contract"):
        validate_contract_values("example.test:Missing/v1", {})
