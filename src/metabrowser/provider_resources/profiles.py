"""Trusted provider-neutral resource-profile declarations."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

MAX_SAFE_INTEGER = 9_007_199_254_740_991
_STABLE_TOKEN_RE = re.compile(r"^[a-z][a-z0-9._:-]*$")
_CONTRACT_ID_RE = re.compile(r"^[a-z][a-z0-9.-]*:[A-Za-z][A-Za-z0-9._-]*/v[1-9][0-9]*$")
_RESOURCE_PROFILE_ID_RE = re.compile(r"^[a-z][a-z0-9.-]*:[a-z][a-z0-9-]*/v[1-9][0-9]*$")


def _runtime_descriptor_value(value: object) -> object:
    """Erase static descriptor types so installed declarations are checked at runtime."""
    return value


class ResourceTargetClass(StrEnum):
    """Closed target shapes understood by the provider-resource storage model."""

    provider_object = "provider_object"
    provider_collection = "provider_collection"


class CollectionPaginationPolicy(StrEnum):
    """Closed pagination policies for one profile collection."""

    forbidden = "forbidden"
    optional = "optional"
    required = "required"


@dataclass(frozen=True, slots=True)
class ResourceCollectionSpec:
    """Trusted declaration for one ordered collection in a resource profile."""

    name: str
    artifact_contract_id: str
    minimum_artifacts: int
    maximum_artifacts: int
    pagination: CollectionPaginationPolicy
    required_for_last_complete: bool

    def __post_init__(self) -> None:
        name = _runtime_descriptor_value(self.name)
        artifact_contract_id = _runtime_descriptor_value(self.artifact_contract_id)
        minimum_artifacts = _runtime_descriptor_value(self.minimum_artifacts)
        maximum_artifacts = _runtime_descriptor_value(self.maximum_artifacts)
        pagination = _runtime_descriptor_value(self.pagination)
        required_for_last_complete = _runtime_descriptor_value(self.required_for_last_complete)
        if not isinstance(name, str) or _STABLE_TOKEN_RE.fullmatch(name) is None:
            raise ValueError("resource collection profile name must be a stable token")
        if (
            not isinstance(artifact_contract_id, str)
            or _CONTRACT_ID_RE.fullmatch(artifact_contract_id) is None
        ):
            raise ValueError("resource collection profile requires a versioned contract ID")
        if (
            isinstance(minimum_artifacts, bool)
            or not isinstance(minimum_artifacts, int)
            or minimum_artifacts < 0
            or minimum_artifacts > MAX_SAFE_INTEGER
        ):
            raise ValueError("resource collection minimum cardinality must be nonnegative")
        if (
            isinstance(maximum_artifacts, bool)
            or not isinstance(maximum_artifacts, int)
            or maximum_artifacts < minimum_artifacts
            or maximum_artifacts > MAX_SAFE_INTEGER
        ):
            raise ValueError("resource collection maximum must not precede its minimum")
        if not isinstance(pagination, CollectionPaginationPolicy):
            raise ValueError("resource collection pagination policy must be closed")
        if not isinstance(required_for_last_complete, bool):
            raise ValueError("resource collection completeness requirement must be boolean")


@dataclass(frozen=True, slots=True)
class ResourceProfileSpec:
    """Trusted declaration that gives one stored resource profile its meaning."""

    profile_id: str
    target_class: ResourceTargetClass
    target_result_contract_id: str | None
    collections: tuple[ResourceCollectionSpec, ...]

    def __post_init__(self) -> None:
        profile_id = _runtime_descriptor_value(self.profile_id)
        target_class = _runtime_descriptor_value(self.target_class)
        target_result_contract_id = _runtime_descriptor_value(self.target_result_contract_id)
        collections = _runtime_descriptor_value(self.collections)
        if not isinstance(profile_id, str) or _RESOURCE_PROFILE_ID_RE.fullmatch(profile_id) is None:
            raise ValueError("resource profile ID must be namespaced and versioned")
        if not isinstance(target_class, ResourceTargetClass):
            raise ValueError("resource profile target class must be closed")
        if target_class is ResourceTargetClass.provider_object:
            if target_result_contract_id is not None:
                raise ValueError("provider-object profiles forbid a result contract")
        elif (
            not isinstance(target_result_contract_id, str)
            or _CONTRACT_ID_RE.fullmatch(target_result_contract_id) is None
        ):
            raise ValueError("provider-collection profiles require a versioned result contract")
        if (
            not isinstance(collections, tuple)
            or not collections
            or any(not isinstance(collection, ResourceCollectionSpec) for collection in collections)
        ):
            raise ValueError("resource profiles require at least one collection")
        collection_specs = tuple(
            collection
            for collection in collections
            if isinstance(collection, ResourceCollectionSpec)
        )
        names = tuple(collection.name for collection in collection_specs)
        if len(set(names)) != len(names):
            raise ValueError("resource profile collection names must be unique")
        if not any(collection.required_for_last_complete for collection in collection_specs):
            raise ValueError("resource profiles require a last-complete collection")
        if target_result_contract_id is not None and target_result_contract_id not in {
            collection.artifact_contract_id for collection in collection_specs
        }:
            raise ValueError("collection result contract must belong to its resource profile")


__all__ = [
    "CollectionPaginationPolicy",
    "ResourceCollectionSpec",
    "ResourceProfileSpec",
    "ResourceTargetClass",
]
