"""Installed SoftSchema contracts for provider resources and hosted reviews."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel
from softschema import (
    CompileResult,
    Contract,
    Contracts,
    SchemaProfile,
    SchemaStatus,
    SchemaView,
    SemanticResult,
    ValidationResult,
    compile_model,
    validate_values,
)

from metabrowser.plugin_loader.capability_types import (
    ArtifactContractSpec,
    ArtifactValidationContext,
    BrowserParserSpec,
    CapabilitySet,
    ConformanceCorpusSpec,
)

from .models import (
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
    ChangeRequestComment,
    ChangeRequestIndex,
    Check,
    CommitStatus,
    HostedRepository,
    ProviderBinding,
    ProviderSyncManifest,
    ProviderViewPointer,
    RepositoryActivity,
    ResourceSet,
    Retrieval,
    Review,
    ReviewComment,
    ReviewThread,
    Tombstone,
    dump_change_request,
    dump_change_request_comment,
    dump_change_request_index,
    dump_check,
    dump_commit_status,
    dump_hosted_repository,
    dump_provider_binding,
    dump_provider_sync_manifest,
    dump_provider_view_pointer,
    dump_repository_activity,
    dump_resource_set,
    dump_retrieval,
    dump_review,
    dump_review_comment,
    dump_review_thread,
    dump_tombstone,
    validate_change_request,
    validate_change_request_comment,
    validate_change_request_index,
    validate_check,
    validate_commit_status,
    validate_hosted_repository,
    validate_provider_binding,
    validate_provider_sync_manifest,
    validate_provider_view_pointer,
    validate_repository_activity,
    validate_resource_set,
    validate_retrieval,
    validate_review,
    validate_review_comment,
    validate_review_thread,
    validate_tombstone,
)
from .resource_profiles import CHANGE_REQUEST_INDEX_PROFILE, REPOSITORY_SUMMARY_PROFILE

_FORMAT_ROOT = Path(__file__).resolve().parents[2] / "data/hosted-review-format"
_SCHEMA_ROOT = _FORMAT_ROOT / "schemas"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_PROVIDER_CONTRACT_NAMESPACE = "com.github.jlevy.metabrowser.provider:"


@dataclass(frozen=True, slots=True)
class _ContractDefinition:
    contract_id: str
    model: type[BaseModel]
    schema_name: str
    envelope: str
    profile: SchemaProfile
    producer_ids: tuple[str, ...]
    consumer_ids: tuple[str, ...]
    corpus_id: str
    corpus_record_selectors: tuple[str, ...]
    browser_parser_id: str | None

    @property
    def schema_path(self) -> Path:
        return _SCHEMA_ROOT / self.schema_name


_PROVIDER_PRODUCERS = ("provider-adapter",)
_PROVIDER_CONSUMERS = ("provider-resource-store",)
_HOSTED_REVIEW_PRODUCERS = ("hosted-review-provider",)
_HOSTED_REVIEW_CONSUMERS = ("hosted-review-service",)

_CONTRACT_DEFINITIONS = tuple(
    sorted(
        (
            _ContractDefinition(
                REPOSITORY_ACTIVITY_CONTRACT_ID,
                RepositoryActivity,
                "repository-activity-v1.schema.yaml",
                "repository_activity",
                SchemaProfile.pure_yaml,
                _HOSTED_REVIEW_PRODUCERS,
                _HOSTED_REVIEW_CONSUMERS,
                "repository-activity-conformance",
                (),
                "hosted-review-model:parseRepositoryActivity",
            ),
            _ContractDefinition(
                PROVIDER_BINDING_CONTRACT_ID,
                ProviderBinding,
                "provider-binding-v1.schema.yaml",
                "provider_binding",
                SchemaProfile.pure_yaml,
                _PROVIDER_PRODUCERS,
                _PROVIDER_CONSUMERS,
                "hosted-repository-conformance",
                ("provider_binding",),
                None,
            ),
            _ContractDefinition(
                HOSTED_REPOSITORY_CONTRACT_ID,
                HostedRepository,
                "hosted-repository-v1.schema.yaml",
                "hosted_repository",
                SchemaProfile.pure_yaml,
                _PROVIDER_PRODUCERS,
                ("hosted-review-service", "provider-resource-store"),
                "hosted-repository-conformance",
                ("hosted_repository",),
                "hosted-review-model:parseHostedRepository",
            ),
            _ContractDefinition(
                PROVIDER_SYNC_MANIFEST_CONTRACT_ID,
                ProviderSyncManifest,
                "provider-sync-manifest-v1.schema.yaml",
                "provider_sync_manifest",
                SchemaProfile.pure_yaml,
                _PROVIDER_PRODUCERS,
                _PROVIDER_CONSUMERS,
                "provider-storage-conformance",
                ("provider_sync_manifest",),
                None,
            ),
            _ContractDefinition(
                PROVIDER_VIEW_POINTER_CONTRACT_ID,
                ProviderViewPointer,
                "provider-view-pointer-v1.schema.yaml",
                "provider_view_pointer",
                SchemaProfile.pure_yaml,
                _PROVIDER_PRODUCERS,
                _PROVIDER_CONSUMERS,
                "provider-storage-conformance",
                ("provider_view_pointer",),
                None,
            ),
            _ContractDefinition(
                RESOURCE_SET_CONTRACT_ID,
                ResourceSet,
                "resource-set-v1.schema.yaml",
                "resource_set",
                SchemaProfile.pure_yaml,
                _PROVIDER_PRODUCERS,
                _PROVIDER_CONSUMERS,
                "provider-storage-conformance",
                ("resource_set",),
                None,
            ),
            _ContractDefinition(
                RETRIEVAL_CONTRACT_ID,
                Retrieval,
                "retrieval-v1.schema.yaml",
                "retrieval",
                SchemaProfile.pure_yaml,
                _PROVIDER_PRODUCERS,
                _PROVIDER_CONSUMERS,
                "provider-storage-conformance",
                ("retrieval", "deletion_retrieval"),
                None,
            ),
            _ContractDefinition(
                TOMBSTONE_CONTRACT_ID,
                Tombstone,
                "tombstone-v1.schema.yaml",
                "tombstone",
                SchemaProfile.pure_yaml,
                _PROVIDER_PRODUCERS,
                _PROVIDER_CONSUMERS,
                "provider-storage-conformance",
                ("tombstone",),
                None,
            ),
            _ContractDefinition(
                CHANGE_REQUEST_CONTRACT_ID,
                ChangeRequest,
                "change-request-v1.schema.yaml",
                "change_request",
                SchemaProfile.frontmatter_md,
                _HOSTED_REVIEW_PRODUCERS,
                _HOSTED_REVIEW_CONSUMERS,
                "change-request-conformance",
                (),
                "hosted-review-model:parseChangeRequest",
            ),
            _ContractDefinition(
                CHANGE_REQUEST_COMMENT_CONTRACT_ID,
                ChangeRequestComment,
                "change-request-comment-v1.schema.yaml",
                "change_request_comment",
                SchemaProfile.frontmatter_md,
                _HOSTED_REVIEW_PRODUCERS,
                _HOSTED_REVIEW_CONSUMERS,
                "review-records-conformance",
                ("change_request_comment",),
                "hosted-review-model:parseChangeRequestComment",
            ),
            _ContractDefinition(
                CHANGE_REQUEST_INDEX_CONTRACT_ID,
                ChangeRequestIndex,
                "change-request-index-v1.schema.yaml",
                "change_request_index",
                SchemaProfile.pure_yaml,
                _HOSTED_REVIEW_PRODUCERS,
                _HOSTED_REVIEW_CONSUMERS,
                "change-request-index-conformance",
                ("change_request_index", "empty_change_request_index"),
                "hosted-review-model:parseChangeRequestIndex",
            ),
            _ContractDefinition(
                CHECK_CONTRACT_ID,
                Check,
                "check-v1.schema.yaml",
                "check",
                SchemaProfile.pure_yaml,
                _HOSTED_REVIEW_PRODUCERS,
                _HOSTED_REVIEW_CONSUMERS,
                "review-records-conformance",
                ("check_suite", "check_run"),
                "hosted-review-model:parseCheck",
            ),
            _ContractDefinition(
                COMMIT_STATUS_CONTRACT_ID,
                CommitStatus,
                "commit-status-v1.schema.yaml",
                "commit_status",
                SchemaProfile.pure_yaml,
                _HOSTED_REVIEW_PRODUCERS,
                _HOSTED_REVIEW_CONSUMERS,
                "review-records-conformance",
                ("commit_status",),
                "hosted-review-model:parseCommitStatus",
            ),
            _ContractDefinition(
                REVIEW_CONTRACT_ID,
                Review,
                "review-v1.schema.yaml",
                "review",
                SchemaProfile.frontmatter_md,
                _HOSTED_REVIEW_PRODUCERS,
                _HOSTED_REVIEW_CONSUMERS,
                "review-records-conformance",
                ("review",),
                "hosted-review-model:parseReview",
            ),
            _ContractDefinition(
                REVIEW_COMMENT_CONTRACT_ID,
                ReviewComment,
                "review-comment-v1.schema.yaml",
                "review_comment",
                SchemaProfile.frontmatter_md,
                _HOSTED_REVIEW_PRODUCERS,
                _HOSTED_REVIEW_CONSUMERS,
                "review-records-conformance",
                ("review_comment", "review_comment_reply"),
                "hosted-review-model:parseReviewComment",
            ),
            _ContractDefinition(
                REVIEW_THREAD_CONTRACT_ID,
                ReviewThread,
                "review-thread-v1.schema.yaml",
                "review_thread",
                SchemaProfile.pure_yaml,
                _HOSTED_REVIEW_PRODUCERS,
                _HOSTED_REVIEW_CONSUMERS,
                "review-records-conformance",
                ("review_thread", "review_thread_empty"),
                "hosted-review-model:parseReviewThread",
            ),
        ),
        key=lambda definition: definition.contract_id,
    )
)

_DEFINITION_BY_ID = {definition.contract_id: definition for definition in _CONTRACT_DEFINITIONS}
if len(_DEFINITION_BY_ID) != len(_CONTRACT_DEFINITIONS):
    raise RuntimeError("hosted-review contract IDs must be unique")

_VALIDATOR_BY_ID: dict[str, Callable[[dict[str, Any]], BaseModel]] = {
    PROVIDER_BINDING_CONTRACT_ID: validate_provider_binding,
    RETRIEVAL_CONTRACT_ID: validate_retrieval,
    HOSTED_REPOSITORY_CONTRACT_ID: validate_hosted_repository,
    RESOURCE_SET_CONTRACT_ID: validate_resource_set,
    PROVIDER_SYNC_MANIFEST_CONTRACT_ID: validate_provider_sync_manifest,
    PROVIDER_VIEW_POINTER_CONTRACT_ID: validate_provider_view_pointer,
    TOMBSTONE_CONTRACT_ID: validate_tombstone,
    CHANGE_REQUEST_INDEX_CONTRACT_ID: validate_change_request_index,
    CHANGE_REQUEST_CONTRACT_ID: validate_change_request,
    CHANGE_REQUEST_COMMENT_CONTRACT_ID: validate_change_request_comment,
    REVIEW_CONTRACT_ID: validate_review,
    REVIEW_THREAD_CONTRACT_ID: validate_review_thread,
    REVIEW_COMMENT_CONTRACT_ID: validate_review_comment,
    CHECK_CONTRACT_ID: validate_check,
    COMMIT_STATUS_CONTRACT_ID: validate_commit_status,
    REPOSITORY_ACTIVITY_CONTRACT_ID: validate_repository_activity,
}
_DUMPER_BY_ID: dict[str, Callable[[Any], dict[str, Any]]] = {
    PROVIDER_BINDING_CONTRACT_ID: dump_provider_binding,
    RETRIEVAL_CONTRACT_ID: dump_retrieval,
    HOSTED_REPOSITORY_CONTRACT_ID: dump_hosted_repository,
    RESOURCE_SET_CONTRACT_ID: dump_resource_set,
    PROVIDER_SYNC_MANIFEST_CONTRACT_ID: dump_provider_sync_manifest,
    PROVIDER_VIEW_POINTER_CONTRACT_ID: dump_provider_view_pointer,
    TOMBSTONE_CONTRACT_ID: dump_tombstone,
    CHANGE_REQUEST_INDEX_CONTRACT_ID: dump_change_request_index,
    CHANGE_REQUEST_CONTRACT_ID: dump_change_request,
    CHANGE_REQUEST_COMMENT_CONTRACT_ID: dump_change_request_comment,
    REVIEW_CONTRACT_ID: dump_review,
    REVIEW_THREAD_CONTRACT_ID: dump_review_thread,
    REVIEW_COMMENT_CONTRACT_ID: dump_review_comment,
    CHECK_CONTRACT_ID: dump_check,
    COMMIT_STATUS_CONTRACT_ID: dump_commit_status,
    REPOSITORY_ACTIVITY_CONTRACT_ID: dump_repository_activity,
}
if _VALIDATOR_BY_ID.keys() != _DEFINITION_BY_ID.keys():
    raise RuntimeError("hosted-review contract validators must match the contract inventory")
if _DUMPER_BY_ID.keys() != _DEFINITION_BY_ID.keys():
    raise RuntimeError("hosted-review contract dumpers must match the contract inventory")


def _validator_for(
    definition: _ContractDefinition,
) -> Callable[[dict[str, Any], ArtifactValidationContext], object]:
    validator = _VALIDATOR_BY_ID[definition.contract_id]

    def validate_record(
        values: dict[str, Any],
        context: ArtifactValidationContext,
    ) -> object:
        if definition.contract_id == RESOURCE_SET_CONTRACT_ID:
            return validate_resource_set(values, profiles=context.resource_profiles)
        return validator(values)

    return validate_record


def _dumper_for(definition: _ContractDefinition) -> Callable[[object], dict[str, Any]]:
    def dump_record(value: object) -> dict[str, Any]:
        if not isinstance(value, definition.model):
            raise TypeError(f"expected {definition.model.__name__}, got {type(value).__name__}")
        return _DUMPER_BY_ID[definition.contract_id](value)

    return dump_record


def _schema_metadata(definition: _ContractDefinition) -> tuple[bytes, str]:
    schema_bytes = definition.schema_path.read_bytes()
    view = SchemaView.load(definition.schema_path)
    if view.contract_id != definition.contract_id:
        raise RuntimeError(f"compiled schema contract does not match {definition.contract_id!r}")
    digest = view.schema_sha256
    if digest is None or _SHA256_RE.fullmatch(digest) is None:
        raise RuntimeError(f"compiled schema for {definition.contract_id!r} has no valid digest")
    return schema_bytes, digest


@cache
def _corpus_spec(corpus_id: str) -> ConformanceCorpusSpec:
    payload = (_FORMAT_ROOT / f"{corpus_id}.json").read_bytes()
    return ConformanceCorpusSpec(
        corpus_id=corpus_id,
        media_type="application/json",
        payload=payload,
        payload_sha256=hashlib.sha256(payload).hexdigest(),
    )


def _browser_parser_spec(parser_id: str | None) -> BrowserParserSpec | None:
    if parser_id is None:
        return None
    module_id, export_name = parser_id.split(":", 1)
    module_bytes = Path(__file__).with_name(f"{module_id}.js").read_bytes()
    return BrowserParserSpec(
        module_id=module_id,
        module_bytes=module_bytes,
        module_bytes_sha256=hashlib.sha256(module_bytes).hexdigest(),
        export_name=export_name,
    )


def _artifact_contract(definition: _ContractDefinition) -> ArtifactContractSpec:
    schema_bytes, schema_digest = _schema_metadata(definition)
    return ArtifactContractSpec(
        contract_id=definition.contract_id,
        artifact_profile=definition.profile.value,
        envelope=definition.envelope,
        schema_bytes=schema_bytes,
        schema_bytes_sha256=hashlib.sha256(schema_bytes).hexdigest(),
        schema_digest=schema_digest,
        validate_record=_validator_for(definition),
        dump_record=_dumper_for(definition),
        producer_ids=definition.producer_ids,
        consumer_ids=definition.consumer_ids,
        corpus=_corpus_spec(definition.corpus_id),
        corpus_record_selectors=definition.corpus_record_selectors,
        browser_parser=_browser_parser_spec(definition.browser_parser_id),
    )


HOSTED_REVIEW_CONTRACTS = tuple(
    _artifact_contract(definition) for definition in _CONTRACT_DEFINITIONS
)
HOSTED_REVIEW_BROWSER_CONTRACT_IDS = frozenset(
    definition.contract_id
    for definition in _CONTRACT_DEFINITIONS
    if definition.browser_parser_id is not None
)
HOSTED_REVIEW_SERVER_ONLY_CONTRACT_IDS = frozenset(
    definition.contract_id
    for definition in _CONTRACT_DEFINITIONS
    if definition.browser_parser_id is None
)


def compile_contracts(*, check_only: bool = False) -> tuple[CompileResult, ...]:
    """Compile every schema deterministically in contract-ID order."""
    return tuple(
        compile_model(
            definition.model,
            definition.schema_path,
            contract_id=definition.contract_id,
            check_only=check_only,
        )
        for definition in _CONTRACT_DEFINITIONS
    )


def build_hosted_review_contract_registry() -> Contracts:
    """Return the complete plugin-local SoftSchema registry."""
    contracts = Contracts()
    for definition in _CONTRACT_DEFINITIONS:
        contracts.register(
            Contract(
                id=definition.contract_id,
                model=definition.model,
                envelope_key=definition.envelope,
                status=SchemaStatus.enforced,
                profile=definition.profile,
                schema_path=definition.schema_path,
            )
        )
    return contracts


def validate_contract_values(contract_id: str, values: Any) -> ValidationResult:
    """Apply the compiled structural schema and Pydantic semantic model."""
    definition = _DEFINITION_BY_ID.get(contract_id)
    if definition is None:
        raise KeyError(f"unregistered hosted-review contract {contract_id!r}")
    result = validate_values(
        values,
        model=definition.model,
        schema=definition.schema_path,
        status=SchemaStatus.enforced,
    )
    if not result.semantic.ok:
        return result
    try:
        _VALIDATOR_BY_ID[contract_id](values)
    except ValueError as exc:
        return ValidationResult(
            structural=result.structural,
            semantic=SemanticResult(
                ok=False,
                errors=[
                    {
                        "type": "value_error",
                        "loc": [],
                        "msg": str(exc),
                        "input": values,
                    }
                ],
            ),
        )
    return result


def provider_resource_capabilities() -> CapabilitySet:
    """Return neutral provider-storage contracts and repository profile."""
    return CapabilitySet(
        artifact_contracts=tuple(
            contract
            for contract in HOSTED_REVIEW_CONTRACTS
            if contract.contract_id.startswith(_PROVIDER_CONTRACT_NAMESPACE)
        ),
        resource_profiles=(REPOSITORY_SUMMARY_PROFILE,),
    )


def hosted_review_capabilities() -> CapabilitySet:
    """Return hosted-review domain contracts and index profile."""
    return CapabilitySet(
        artifact_contracts=tuple(
            contract
            for contract in HOSTED_REVIEW_CONTRACTS
            if not contract.contract_id.startswith(_PROVIDER_CONTRACT_NAMESPACE)
        ),
        resource_profiles=(CHANGE_REQUEST_INDEX_PROFILE,),
    )
