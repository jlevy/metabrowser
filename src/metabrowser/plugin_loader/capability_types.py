"""Dependency-light declarations for installed backend capabilities."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Literal

from metabrowser.provider_resources.profiles import ResourceProfileSpec

type ArtifactProfile = Literal["frontmatter-md", "pure-yaml"]


def _runtime_descriptor_value(value: object) -> object:
    """Erase static declaration types so installed providers are checked at runtime."""
    return value


@dataclass(frozen=True, slots=True)
class ArtifactValidationContext:
    """Installed declarations available to one semantic record validator."""

    resource_profiles: Mapping[str, ResourceProfileSpec]


@dataclass(frozen=True, slots=True)
class ConformanceCorpusSpec:
    """Immutable packaged corpus evidence for one or more contracts."""

    corpus_id: str
    media_type: Literal["application/json"]
    payload: bytes
    payload_sha256: str


@dataclass(frozen=True, slots=True)
class BrowserParserSpec:
    """Immutable self-contained browser-parser module evidence."""

    module_id: str
    module_bytes: bytes
    module_bytes_sha256: str
    export_name: str

    @property
    def parser_id(self) -> str:
        """Return the stable module/export identity used in inventories."""
        return f"{self.module_id}:{self.export_name}"


@dataclass(frozen=True, slots=True)
class ArtifactContractSpec:
    """Trusted installed declaration for one versioned artifact contract."""

    contract_id: str
    artifact_profile: ArtifactProfile
    envelope: str
    schema_bytes: bytes
    schema_bytes_sha256: str
    schema_digest: str
    validate_record: Callable[[dict[str, Any], ArtifactValidationContext], object]
    dump_record: Callable[[object], dict[str, Any]]
    producer_ids: tuple[str, ...]
    consumer_ids: tuple[str, ...]
    corpus: ConformanceCorpusSpec
    corpus_record_selectors: tuple[str, ...]
    browser_parser: BrowserParserSpec | None


@dataclass(frozen=True, slots=True)
class CapabilitySet:
    """Declarations returned by one installed capability provider."""

    artifact_contracts: tuple[ArtifactContractSpec, ...] = ()
    resource_profiles: tuple[ResourceProfileSpec, ...] = ()

    def __post_init__(self) -> None:
        artifact_contracts = _runtime_descriptor_value(self.artifact_contracts)
        resource_profiles = _runtime_descriptor_value(self.resource_profiles)
        if not isinstance(artifact_contracts, tuple) or any(
            not isinstance(contract, ArtifactContractSpec) for contract in artifact_contracts
        ):
            raise TypeError("capability artifact_contracts must be a tuple of ArtifactContractSpec")
        if not isinstance(resource_profiles, tuple) or any(
            not isinstance(profile, ResourceProfileSpec) for profile in resource_profiles
        ):
            raise TypeError("capability resource_profiles must be a tuple of ResourceProfileSpec")


__all__ = [
    "ArtifactContractSpec",
    "ArtifactProfile",
    "ArtifactValidationContext",
    "BrowserParserSpec",
    "CapabilitySet",
    "ConformanceCorpusSpec",
]
