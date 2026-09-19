"""Installed SoftSchema contracts for the application home and repository cache.

Every contract ID binds to one Pydantic model and one deterministic Draft 2020-12 schema
packaged in the wheel under ``metabrowser/data/cache-format/``. A cache file names its
contract, envelope, and status, but never a schema path: the caller chooses the
contract from the file's place in the layout, and validation uses only the packaged
schema, so a cache-controlled ``softschema.schema`` cannot redirect it.

The machine-owned records are ``enforced`` and join the installed artifact-contract
registry through the ``repository-cache`` capability provider, so the generic inventory
gate, the architecture table check, and the isolated-wheel smoke test cover them like
any other installed contract. Reading the cache never depends on that discovery: the
cache builds its own registry from the same declarations.

``config.yml`` is user-owned and ``permissive``. The installed registry admits only
enforced contracts, so the configuration contract is compiled, drift-checked,
corpus-validated, and verified in the installed wheel here instead.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any, Final, cast

from pydantic import BaseModel, ValidationError
from softschema import (
    CompileResult,
    SchemaProfile,
    SchemaStatus,
    SchemaView,
    ValidationResult,
    compile_model,
    validate_values,
)

from metabrowser.cache.records import (
    CACHE_LAYOUT_CONTRACT_ID,
    CONFIG_CONTRACT_ID,
    REPOSITORY_SOURCE_CONTRACT_ID,
    REPOSITORY_SOURCE_STATE_CONTRACT_ID,
    REPOSITORY_STORE_ALIAS_CONTRACT_ID,
    REPOSITORY_STORE_CONTRACT_ID,
    REPOSITORY_STORE_STATE_CONTRACT_ID,
    ApplicationConfig,
    CacheLayout,
    RepositorySource,
    RepositorySourceState,
    RepositoryStore,
    RepositoryStoreAlias,
    RepositoryStoreState,
)
from metabrowser.plugin_loader.artifact_contracts import ContractRegistry, build_contract_registry
from metabrowser.plugin_loader.capability_discovery import LoadedCapabilitySet
from metabrowser.plugin_loader.capability_types import (
    ArtifactContractSpec,
    ArtifactValidationContext,
    CapabilitySet,
    ConformanceCorpusSpec,
)

FORMAT_ROOT: Final = Path(__file__).resolve().parents[1] / "data/cache-format"
SCHEMA_ROOT: Final = FORMAT_ROOT / "schemas"
CAPABILITY_PROVIDER_ID: Final = "repository-cache"
CACHE_RECORDS_CORPUS_ID: Final = "cache-records-conformance"
APPLICATION_CONFIG_CORPUS_ID: Final = "application-config-conformance"
# One invalid configuration can fail once per entry, and its reasons reach an API
# response, so the count and each reason's length are bounded.
MAX_CONFIG_REASONS: Final = 10
_MAX_CONFIG_REASON_LENGTH: Final = 200
_MAX_CONFIG_NAME_LENGTH: Final = 64
_MAX_PATH_PARTS: Final = 8
_PRODUCERS: Final = ("repository-cache",)
_CONSUMERS: Final = ("repository-cache",)


@dataclass(frozen=True, slots=True)
class CacheContract:
    """One cache record family: its contract, model, packaged schema, and status."""

    contract_id: str
    model: type[BaseModel]
    schema_name: str
    envelope: str
    status: SchemaStatus
    corpus_id: str
    corpus_record_selectors: tuple[str, ...]

    @property
    def schema_path(self) -> Path:
        return SCHEMA_ROOT / self.schema_name


CACHE_CONTRACTS: Final = tuple(
    sorted(
        (
            CacheContract(
                CONFIG_CONTRACT_ID,
                ApplicationConfig,
                "application-config-v1.schema.yaml",
                "config",
                SchemaStatus.permissive,
                APPLICATION_CONFIG_CORPUS_ID,
                ("config",),
            ),
            CacheContract(
                CACHE_LAYOUT_CONTRACT_ID,
                CacheLayout,
                "cache-layout-v1.schema.yaml",
                "layout",
                SchemaStatus.enforced,
                CACHE_RECORDS_CORPUS_ID,
                ("layout",),
            ),
            CacheContract(
                REPOSITORY_SOURCE_CONTRACT_ID,
                RepositorySource,
                "repository-source-v1.schema.yaml",
                "source",
                SchemaStatus.enforced,
                CACHE_RECORDS_CORPUS_ID,
                ("source", "scp_source"),
            ),
            CacheContract(
                REPOSITORY_SOURCE_STATE_CONTRACT_ID,
                RepositorySourceState,
                "repository-source-state-v1.schema.yaml",
                "state",
                SchemaStatus.enforced,
                CACHE_RECORDS_CORPUS_ID,
                ("source_state",),
            ),
            CacheContract(
                REPOSITORY_STORE_ALIAS_CONTRACT_ID,
                RepositoryStoreAlias,
                "repository-store-alias-v1.schema.yaml",
                "alias",
                SchemaStatus.enforced,
                CACHE_RECORDS_CORPUS_ID,
                ("store_alias",),
            ),
            CacheContract(
                REPOSITORY_STORE_CONTRACT_ID,
                RepositoryStore,
                "repository-store-v1.schema.yaml",
                "store",
                SchemaStatus.enforced,
                CACHE_RECORDS_CORPUS_ID,
                ("store",),
            ),
            CacheContract(
                REPOSITORY_STORE_STATE_CONTRACT_ID,
                RepositoryStoreState,
                "repository-store-state-v1.schema.yaml",
                "state",
                SchemaStatus.enforced,
                CACHE_RECORDS_CORPUS_ID,
                ("store_state", "empty_store_state"),
            ),
        ),
        key=lambda contract: contract.contract_id,
    )
)
CACHE_CONTRACT_BY_ID: Final[Mapping[str, CacheContract]] = {
    contract.contract_id: contract for contract in CACHE_CONTRACTS
}
if len(CACHE_CONTRACT_BY_ID) != len(CACHE_CONTRACTS):
    raise RuntimeError("cache contract IDs must be unique")
ENFORCED_CACHE_CONTRACTS: Final = tuple(
    contract for contract in CACHE_CONTRACTS if contract.status is SchemaStatus.enforced
)
ARTIFACT_PROFILE: Final = SchemaProfile.pure_yaml


def _validator_for(
    contract: CacheContract,
) -> Callable[[dict[str, Any], ArtifactValidationContext], object]:
    def validate_record(values: dict[str, Any], _context: ArtifactValidationContext) -> object:
        return contract.model.model_validate(values)

    return validate_record


def _dumper_for(contract: CacheContract) -> Callable[[object], dict[str, Any]]:
    def dump_record(value: object) -> dict[str, Any]:
        if not isinstance(value, contract.model):
            raise TypeError(f"expected {contract.model.__name__}, got {type(value).__name__}")
        return value.model_dump(mode="json")

    return dump_record


@cache
def _corpus(corpus_id: str) -> ConformanceCorpusSpec:
    payload = (FORMAT_ROOT / f"{corpus_id}.json").read_bytes()
    return ConformanceCorpusSpec(
        corpus_id=corpus_id,
        media_type="application/json",
        payload=payload,
        payload_sha256=hashlib.sha256(payload).hexdigest(),
    )


def _artifact_contract(contract: CacheContract) -> ArtifactContractSpec:
    schema_bytes = contract.schema_path.read_bytes()
    view = SchemaView.load(contract.schema_path)
    if view.contract_id != contract.contract_id or view.schema_sha256 is None:
        raise RuntimeError(f"packaged schema does not declare {contract.contract_id!r}")
    return ArtifactContractSpec(
        contract_id=contract.contract_id,
        artifact_profile="pure-yaml",
        envelope=contract.envelope,
        schema_bytes=schema_bytes,
        schema_bytes_sha256=hashlib.sha256(schema_bytes).hexdigest(),
        schema_digest=view.schema_sha256,
        validate_record=_validator_for(contract),
        dump_record=_dumper_for(contract),
        producer_ids=_PRODUCERS,
        consumer_ids=_CONSUMERS,
        corpus=_corpus(contract.corpus_id),
        corpus_record_selectors=contract.corpus_record_selectors,
        browser_consumed=False,
        browser_parser=None,
    )


@cache
def _artifact_contracts() -> tuple[ArtifactContractSpec, ...]:
    return tuple(_artifact_contract(contract) for contract in ENFORCED_CACHE_CONTRACTS)


def repository_cache_capabilities() -> CapabilitySet:
    """Return the enforced cache contracts for the installed capability registry."""

    return CapabilitySet(artifact_contracts=_artifact_contracts())


@cache
def cache_contract_registry() -> ContractRegistry:
    """Return the registry cache reads validate against, built without plugin discovery."""

    provider = LoadedCapabilitySet(
        provider_id=CAPABILITY_PROVIDER_ID,
        source_distribution=None,
        capabilities=repository_cache_capabilities(),
    )
    return build_contract_registry((provider,))


def compile_contracts(*, check_only: bool = False) -> tuple[CompileResult, ...]:
    """Compile every cache schema deterministically in contract-ID order."""

    return tuple(
        compile_model(
            contract.model,
            contract.schema_path,
            contract_id=contract.contract_id,
            check_only=check_only,
        )
        for contract in CACHE_CONTRACTS
    )


def check_packaged_schemas() -> tuple[str, ...]:
    """Report every packaged schema that no longer matches its model.

    The isolated-wheel smoke test calls this against the installed package, so a schema
    left out of the wheel or compiled from a different model fails the release gate.
    """

    return tuple(
        f"{result.out_path.name}: {result.drift_diff}"
        for result in compile_contracts(check_only=True)
        if result.drift
    )


def validate_config_values(values: Any) -> ValidationResult:
    """Validate ``config.yml`` values permissively: known fields strictly, unknown kept."""

    contract = CACHE_CONTRACT_BY_ID[CONFIG_CONTRACT_ID]
    return validate_values(
        values,
        model=contract.model,
        schema=contract.schema_path,
        status=SchemaStatus.permissive,
    )


def _config_reason_location(path: object) -> str:
    """Name where a reason applies, without quoting what is there."""

    if not isinstance(path, list) or not path:
        return "config"
    parts = cast(list[object], path)
    named = ".".join(str(part)[:_MAX_CONFIG_NAME_LENGTH] for part in parts[:_MAX_PATH_PARTS])
    return "config." + named + ("..." if len(parts) > _MAX_PATH_PARTS else "")


def config_reasons(result: ValidationResult) -> list[str]:
    """Return one short reason per validation error, naming no value in the config.

    A structural error record carries the offending value in ``value`` and renders it
    into ``message``, and a semantic one carries it in ``input``; a configuration value
    can be anything the user put there, and these reasons reach an API response. So a
    reason is the location, the rule that failed, and — for a semantic error — Pydantic's
    bounded message, which describes the expectation rather than the input.
    """

    reasons: list[str] = []
    for error in result.structural.errors:
        rule = error.get("code") or error.get("validator") or "invalid"
        offending = error.get("property")
        where = _config_reason_location(error.get("path"))
        named = f" ({str(offending)[:_MAX_CONFIG_NAME_LENGTH]})" if offending is not None else ""
        reasons.append(f"{where}: {rule}{named}")
    for error in result.semantic.errors:
        where = _config_reason_location(error.get("loc"))
        message = str(error.get("msg") or error.get("type") or "invalid")
        reasons.append(f"{where}: {message[:_MAX_CONFIG_REASON_LENGTH]}")
    return reasons


def parse_application_config(values: Any) -> ApplicationConfig:
    """Return validated configuration, raising ``ValueError`` with bounded reasons.

    A broken configuration can fail in as many places as it has entries, so at most
    :data:`MAX_CONFIG_REASONS` are reported and the rest are counted. The message is
    bounded and quotes no configuration value.
    """

    result = validate_config_values(values)
    if not result.structural.ok or not result.semantic.ok:
        reasons = config_reasons(result)
        hidden = len(reasons) - MAX_CONFIG_REASONS
        suffix = f", and {hidden} more" if hidden > 0 else ""
        raise ValueError(
            "config.yml does not satisfy its contract: "
            + "; ".join(reasons[:MAX_CONFIG_REASONS])
            + suffix
        )
    try:
        return ApplicationConfig.model_validate(values)
    except ValidationError as error:
        raise ValueError("config.yml does not satisfy its contract") from error


def config_corpus() -> dict[str, Any]:
    """Return the packaged configuration conformance corpus."""

    return cast(dict[str, Any], json.loads(_corpus(APPLICATION_CONFIG_CORPUS_ID).payload))


__all__ = [
    "ARTIFACT_PROFILE",
    "CACHE_CONTRACTS",
    "CACHE_CONTRACT_BY_ID",
    "CAPABILITY_PROVIDER_ID",
    "ENFORCED_CACHE_CONTRACTS",
    "FORMAT_ROOT",
    "MAX_CONFIG_REASONS",
    "SCHEMA_ROOT",
    "CacheContract",
    "cache_contract_registry",
    "check_packaged_schemas",
    "compile_contracts",
    "config_corpus",
    "config_reasons",
    "parse_application_config",
    "repository_cache_capabilities",
    "validate_config_values",
]
