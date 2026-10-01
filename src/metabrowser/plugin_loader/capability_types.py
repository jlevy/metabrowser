"""Dependency-light declarations for installed backend capabilities."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

type ArtifactProfile = Literal["frontmatter-md", "pure-yaml"]


def _runtime_descriptor_value(value: object) -> object:
    """Erase static declaration types so installed providers are checked at runtime."""
    return value


@dataclass(frozen=True, slots=True)
class ConformanceCorpusSpec:
    """Immutable packaged corpus evidence for one or more contracts."""

    corpus_id: str
    media_type: Literal["application/json"]
    payload: bytes
    payload_sha256: str


@dataclass(frozen=True, slots=True)
class ArtifactContractSpec:
    """Trusted installed declaration for one versioned artifact contract."""

    contract_id: str
    artifact_profile: ArtifactProfile
    envelope: str
    schema_bytes: bytes
    schema_bytes_sha256: str
    schema_digest: str
    validate_record: Callable[[dict[str, Any]], object]
    dump_record: Callable[[object], dict[str, Any]]
    producer_ids: tuple[str, ...]
    consumer_ids: tuple[str, ...]
    corpus: ConformanceCorpusSpec
    corpus_record_selectors: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CapabilitySet:
    """Declarations returned by one installed capability provider."""

    artifact_contracts: tuple[ArtifactContractSpec, ...] = ()

    def __post_init__(self) -> None:
        artifact_contracts = _runtime_descriptor_value(self.artifact_contracts)
        if not isinstance(artifact_contracts, tuple) or any(
            not isinstance(contract, ArtifactContractSpec) for contract in artifact_contracts
        ):
            raise TypeError("capability artifact_contracts must be a tuple of ArtifactContractSpec")


__all__ = [
    "ArtifactContractSpec",
    "ArtifactProfile",
    "CapabilitySet",
    "ConformanceCorpusSpec",
]
