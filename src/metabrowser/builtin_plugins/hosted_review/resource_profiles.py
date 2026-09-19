"""Trusted built-in resource profiles for hosted provider artifacts."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from .models import (
    CHANGE_REQUEST_INDEX_CONTRACT_ID,
    CHANGE_REQUEST_INDEX_PROFILE_ID,
    HOSTED_REPOSITORY_CONTRACT_ID,
    REPOSITORY_SUMMARY_PROFILE_ID,
    CollectionPaginationPolicy,
    ResourceCollectionSpec,
    ResourceProfileSpec,
    ResourceTargetClass,
)

REPOSITORY_SUMMARY_PROFILE = ResourceProfileSpec(
    profile_id=REPOSITORY_SUMMARY_PROFILE_ID,
    target_class=ResourceTargetClass.provider_object,
    target_result_contract_id=None,
    collections=(
        ResourceCollectionSpec(
            name="repository",
            artifact_contract_id=HOSTED_REPOSITORY_CONTRACT_ID,
            minimum_artifacts=1,
            maximum_artifacts=1,
            pagination=CollectionPaginationPolicy.forbidden,
            required_for_last_complete=True,
        ),
    ),
)

CHANGE_REQUEST_INDEX_PROFILE = ResourceProfileSpec(
    profile_id=CHANGE_REQUEST_INDEX_PROFILE_ID,
    target_class=ResourceTargetClass.provider_collection,
    target_result_contract_id=CHANGE_REQUEST_INDEX_CONTRACT_ID,
    collections=(
        ResourceCollectionSpec(
            name="change_request_index",
            artifact_contract_id=CHANGE_REQUEST_INDEX_CONTRACT_ID,
            minimum_artifacts=1,
            maximum_artifacts=1,
            pagination=CollectionPaginationPolicy.required,
            required_for_last_complete=True,
        ),
    ),
)

HOSTED_REVIEW_RESOURCE_PROFILES: Mapping[str, ResourceProfileSpec] = MappingProxyType(
    {
        REPOSITORY_SUMMARY_PROFILE.profile_id: REPOSITORY_SUMMARY_PROFILE,
        CHANGE_REQUEST_INDEX_PROFILE.profile_id: CHANGE_REQUEST_INDEX_PROFILE,
    }
)


def resolve_resource_profile(
    profile_id: str,
    profiles: Mapping[str, ResourceProfileSpec] = HOSTED_REVIEW_RESOURCE_PROFILES,
) -> ResourceProfileSpec:
    """Resolve one profile only from the trusted installed-profile catalog."""
    profile = profiles.get(profile_id)
    if profile is None:
        raise ValueError("resource set names an unregistered profile")
    return profile
