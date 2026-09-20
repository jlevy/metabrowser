from __future__ import annotations

import copy
from typing import Any, cast

import pytest
from hosted_review_cases import apply_case_changes, load_hosted_review_corpus

from metabrowser.builtin_plugins.hosted_review import models as hosted_review

_RETRIEVAL_SNAPSHOT_ID = "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
_RESOURCE_SET_SNAPSHOT_ID = (
    "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
)
_MANIFEST_SNAPSHOT_ID = "sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
_DELETION_RETRIEVAL_SNAPSHOT_ID = (
    "sha256:9999999999999999999999999999999999999999999999999999999999999999"
)


def _corpus() -> dict[str, Any]:
    return load_hosted_review_corpus("provider-storage-conformance.json")


def _storage_api(record_name: str) -> tuple[Any, Any]:
    names = {
        "authorization_context": ("validate_authorization_context", None),
        "retrieval": ("validate_retrieval", "dump_retrieval"),
        "deletion_retrieval": ("validate_retrieval", "dump_retrieval"),
        "resource_set": ("validate_resource_set", "dump_resource_set"),
        "provider_sync_manifest": (
            "validate_provider_sync_manifest",
            "dump_provider_sync_manifest",
        ),
        "provider_view_pointer": (
            "validate_provider_view_pointer",
            "dump_provider_view_pointer",
        ),
        "tombstone": ("validate_tombstone", "dump_tombstone"),
    }
    validator_name, dumper_name = names[record_name]
    dumper = (
        (lambda value: value.model_dump(mode="json"))
        if dumper_name is None
        else getattr(hosted_review, dumper_name)
    )
    return getattr(hosted_review, validator_name), dumper


def _retrievals(
    records: dict[str, Any],
    *,
    deletion_document: dict[str, Any] | None = None,
    repository_document: dict[str, Any] | None = None,
) -> dict[str, hosted_review.Retrieval]:
    return {
        _RETRIEVAL_SNAPSHOT_ID: hosted_review.validate_retrieval(
            records["retrieval"] if repository_document is None else repository_document
        ),
        _DELETION_RETRIEVAL_SNAPSHOT_ID: hosted_review.validate_retrieval(
            records["deletion_retrieval"] if deletion_document is None else deletion_document
        ),
    }


def _live_snapshots(
    tombstone: hosted_review.Tombstone,
) -> dict[str, hosted_review.LiveSnapshotContext]:
    return {
        tombstone.previous_live_snapshot_id: hosted_review.LiveSnapshotContext(
            target=tombstone.target,
            repository=tombstone.repository,
            authorization_context=tombstone.authorization_context,
            observed_at="2026-09-15T11:59:59Z",
        )
    }


def test_provider_storage_models_agree_with_the_portable_corpus() -> None:
    corpus = _corpus()

    for case in corpus["cases"]:
        document = apply_case_changes(corpus["base_records"][case["record"]], case["changes"])
        validator, dumper = _storage_api(case["record"])
        if case["expect"] == "valid":
            assert dumper(validator(document)) == document
        else:
            with pytest.raises(ValueError):
                validator(document)


@pytest.mark.parametrize(
    ("record", "path"),
    [
        ("retrieval", ("normalization_version",)),
        ("retrieval", ("validators", "etag")),
        ("retrieval", ("request_key",)),
        ("resource_set", ("profile",)),
        ("provider_sync_manifest", ("transaction_id",)),
        ("provider_view_pointer", ("resource_set_snapshot_id",)),
        ("tombstone", ("previous_live_snapshot_id",)),
        ("tombstone", ("proof", "retrieval_snapshot_id")),
        ("deletion_retrieval", ("outcome", "provider_event_opaque_id")),
    ],
)
def test_provider_storage_strings_are_never_coerced_from_bytes(
    record: str, path: tuple[str, ...]
) -> None:
    document = copy.deepcopy(_corpus()["base_records"][record])
    validator, _ = _storage_api(record)
    target: Any = document
    for part in path[:-1]:
        target = target[part]
    assert isinstance(target[path[-1]], str)
    target[path[-1]] = cast(str, target[path[-1]]).encode("utf-8")

    with pytest.raises(ValueError):
        validator(document)


def test_new_provider_collection_needs_only_a_trusted_profile_declaration() -> None:
    records = _corpus()["base_records"]
    release_contract_id = "example.test:ReleaseIndex/v1"
    profile = hosted_review.ResourceProfileSpec(
        profile_id="example.test:release-index/v1",
        target_class=hosted_review.ResourceTargetClass.provider_collection,
        target_result_contract_id=release_contract_id,
        collections=(
            hosted_review.ResourceCollectionSpec(
                name="release_index",
                artifact_contract_id=release_contract_id,
                minimum_artifacts=1,
                maximum_artifacts=1,
                pagination=hosted_review.CollectionPaginationPolicy.required,
                required_for_last_complete=True,
            ),
        ),
    )
    profiles = {profile.profile_id: profile}
    query_key = "sha256:1212121212121212121212121212121212121212121212121212121212121212"

    retrieval_document = copy.deepcopy(records["retrieval"])
    retrieval_document["target"] = {
        "kind": "provider_collection",
        "repository": copy.deepcopy(records["resource_set"]["repository"]),
        "result_contract_id": release_contract_id,
        "query_key": query_key,
    }
    retrieval = hosted_review.validate_retrieval(retrieval_document)

    resource_set_document = copy.deepcopy(records["resource_set"])
    resource_set_document["profile"] = profile.profile_id
    resource_set_document["target"] = {
        "kind": "provider_collection",
        "result_contract_id": release_contract_id,
        "query_key": query_key,
    }
    resource_set_document["collections"] = [
        {
            "name": "release_index",
            "coverage": "complete",
            "artifacts": [
                {
                    "contract_id": release_contract_id,
                    "snapshot_id": "sha256:3434343434343434343434343434343434343434343434343434343434343434",
                }
            ],
            "retrieval_snapshot_ids": [_RETRIEVAL_SNAPSHOT_ID],
            "pagination": {
                "pages": [
                    {
                        "ordinal": 1,
                        "requested_with": None,
                        "next": None,
                        "retrieval_snapshot_id": _RETRIEVAL_SNAPSHOT_ID,
                        "observed_provider_ids": [],
                        "provider_exhausted": True,
                        "provider_snapshot_token": None,
                    }
                ],
                "first_observed_at": retrieval.finished_at,
                "last_observed_at": retrieval.finished_at,
                "remote_consistency": {"kind": "best_effort_window"},
            },
            "truncation": None,
            "failure_retrieval_snapshot_id": None,
        }
    ]
    resource_set = hosted_review.validate_resource_set(resource_set_document, profiles)

    manifest_document = copy.deepcopy(records["provider_sync_manifest"])
    manifest_document["retrievals"] = manifest_document["retrievals"][:1]
    manifest = hosted_review.validate_provider_sync_manifest(manifest_document)

    hosted_review.validate_manifest_closure(
        manifest,
        {_RESOURCE_SET_SNAPSHOT_ID: resource_set},
        {_RETRIEVAL_SNAPSHOT_ID: retrieval},
        profiles,
    )


def test_resource_profile_descriptors_reject_invalid_trusted_declarations() -> None:
    with pytest.raises(ValueError):
        hosted_review.ResourceCollectionSpec(
            name="items",
            artifact_contract_id="example.test:Item/v1",
            minimum_artifacts=-1,
            maximum_artifacts=1,
            pagination=hosted_review.CollectionPaginationPolicy.forbidden,
            required_for_last_complete=True,
        )

    with pytest.raises(ValueError):
        hosted_review.ResourceCollectionSpec(
            name="items",
            artifact_contract_id="example.test:Item/v1",
            minimum_artifacts=0,
            maximum_artifacts=cast(int, None),
            pagination=hosted_review.CollectionPaginationPolicy.forbidden,
            required_for_last_complete=True,
        )

    with pytest.raises(ValueError):
        hosted_review.ResourceCollectionSpec(
            name="items",
            artifact_contract_id="example.test:Item/v1",
            minimum_artifacts=0,
            maximum_artifacts=1,
            pagination=cast(hosted_review.CollectionPaginationPolicy, "unbounded"),
            required_for_last_complete=True,
        )

    with pytest.raises(ValueError):
        hosted_review.ResourceCollectionSpec(
            name="items",
            artifact_contract_id="example.test:Item/v1",
            minimum_artifacts=2,
            maximum_artifacts=1,
            pagination=hosted_review.CollectionPaginationPolicy.forbidden,
            required_for_last_complete=True,
        )

    item_collection = hosted_review.ResourceCollectionSpec(
        name="items",
        artifact_contract_id="example.test:Item/v1",
        minimum_artifacts=1,
        maximum_artifacts=1,
        pagination=hosted_review.CollectionPaginationPolicy.forbidden,
        required_for_last_complete=True,
    )
    with pytest.raises(ValueError):
        hosted_review.ResourceProfileSpec(
            profile_id="example.test:item/v1",
            target_class=hosted_review.ResourceTargetClass.provider_object,
            target_result_contract_id="example.test:Item/v1",
            collections=(item_collection,),
        )

    with pytest.raises(ValueError):
        hosted_review.ResourceProfileSpec(
            profile_id="example.test:item/v1",
            target_class=cast(hosted_review.ResourceTargetClass, "unknown"),
            target_result_contract_id=None,
            collections=(item_collection,),
        )

    with pytest.raises(ValueError):
        hosted_review.ResourceProfileSpec(
            profile_id="example.test:item/v1",
            target_class=hosted_review.ResourceTargetClass.provider_collection,
            target_result_contract_id=None,
            collections=(item_collection,),
        )

    with pytest.raises(ValueError):
        hosted_review.ResourceProfileSpec(
            profile_id="example.test:item/v1",
            target_class=hosted_review.ResourceTargetClass.provider_object,
            target_result_contract_id=None,
            collections=(),
        )

    with pytest.raises(ValueError):
        hosted_review.ResourceProfileSpec(
            profile_id="example.test:item/v1",
            target_class=hosted_review.ResourceTargetClass.provider_collection,
            target_result_contract_id="example.test:Other/v1",
            collections=(item_collection,),
        )

    with pytest.raises(ValueError):
        hosted_review.ResourceProfileSpec(
            profile_id="example.test:item/v1",
            target_class=hosted_review.ResourceTargetClass.provider_collection,
            target_result_contract_id="example.test:Item/v1",
            collections=(item_collection, item_collection),
        )

    optional_collection = hosted_review.ResourceCollectionSpec(
        name="optional-items",
        artifact_contract_id="example.test:Item/v1",
        minimum_artifacts=0,
        maximum_artifacts=1,
        pagination=hosted_review.CollectionPaginationPolicy.forbidden,
        required_for_last_complete=False,
    )
    with pytest.raises(ValueError):
        hosted_review.ResourceProfileSpec(
            profile_id="example.test:item/v1",
            target_class=hosted_review.ResourceTargetClass.provider_collection,
            target_result_contract_id="example.test:Item/v1",
            collections=(optional_collection,),
        )


def test_authorization_key_uses_only_the_stable_context() -> None:
    corpus = _corpus()
    first_document = copy.deepcopy(corpus["base_records"]["retrieval"])
    second_document = copy.deepcopy(first_document)
    second_document["display_login"] = "renamed-reviewer"
    second_document["capabilities"]["values"] = ["read:issues", "read:repository"]
    second_document["rate_limit"]["remaining"] = 12
    second_document["finished_at"] = "2026-09-15T12:00:00.250Z"

    first = hosted_review.validate_retrieval(first_document)
    second = hosted_review.validate_retrieval(second_document)

    assert hosted_review.authorization_context_key(first.authorization_context) == (
        "sha256:18cdd1541d4367b81f15c9a4be6c813924996b584b86fb608449df2556d90d5a"
    )
    assert hosted_review.authorization_context_key(
        first.authorization_context
    ) == hosted_review.authorization_context_key(second.authorization_context)

    another_principal = copy.deepcopy(first_document["authorization_context"])
    another_principal["principal_opaque_id"] = "person-5"
    parsed_principal = hosted_review.validate_authorization_context(another_principal)
    assert hosted_review.authorization_context_key(parsed_principal) != (
        hosted_review.authorization_context_key(first.authorization_context)
    )


def test_pointer_role_is_checked_against_resolved_immutable_records() -> None:
    corpus = _corpus()["base_records"]
    resource_set_document = copy.deepcopy(corpus["resource_set"])
    manifest = hosted_review.validate_provider_sync_manifest(corpus["provider_sync_manifest"])
    current = hosted_review.validate_provider_view_pointer(corpus["provider_view_pointer"])
    complete = hosted_review.validate_resource_set(resource_set_document)

    hosted_review.validate_provider_view_pointer_target(
        current,
        {_MANIFEST_SNAPSHOT_ID: manifest},
        {_RESOURCE_SET_SNAPSHOT_ID: complete},
        _retrievals(corpus),
    )

    resource_set_document["collections"][0]["coverage"] = "partial"
    resource_set_document["collections"][0]["truncation"] = {
        "reason": "item_bound",
        "limit": 1,
    }
    partial = hosted_review.validate_resource_set(resource_set_document)
    hosted_review.validate_provider_view_pointer_target(
        current,
        {_MANIFEST_SNAPSHOT_ID: manifest},
        {_RESOURCE_SET_SNAPSHOT_ID: partial},
        _retrievals(corpus),
    )

    last_complete_document = copy.deepcopy(corpus["provider_view_pointer"])
    last_complete_document["role"] = "last_complete"
    last_complete = hosted_review.validate_provider_view_pointer(last_complete_document)
    with pytest.raises(ValueError):
        hosted_review.validate_provider_view_pointer_target(
            last_complete,
            {_MANIFEST_SNAPSHOT_ID: manifest},
            {_RESOURCE_SET_SNAPSHOT_ID: partial},
            _retrievals(corpus),
        )


def test_pointer_requires_its_recorded_snapshot_ids_to_resolve() -> None:
    records = _corpus()["base_records"]
    pointer = hosted_review.validate_provider_view_pointer(records["provider_view_pointer"])
    resource_set = hosted_review.validate_resource_set(records["resource_set"])

    with pytest.raises(ValueError):
        hosted_review.validate_provider_view_pointer_target(
            pointer,
            {},
            {_RESOURCE_SET_SNAPSHOT_ID: resource_set},
            _retrievals(records),
        )


def test_pointer_requires_the_selected_resource_set_manifest_closure() -> None:
    records = _corpus()["base_records"]
    pointer = hosted_review.validate_provider_view_pointer(records["provider_view_pointer"])
    manifest = hosted_review.validate_provider_sync_manifest(records["provider_sync_manifest"])
    resource_set_document = copy.deepcopy(records["resource_set"])
    resource_set_document["collections"][0]["retrieval_snapshot_ids"] = [
        "sha256:4545454545454545454545454545454545454545454545454545454545454545"
    ]
    resource_set = hosted_review.validate_resource_set(resource_set_document)

    with pytest.raises(ValueError):
        hosted_review.validate_provider_view_pointer_target(
            pointer,
            {_MANIFEST_SNAPSHOT_ID: manifest},
            {_RESOURCE_SET_SNAPSHOT_ID: resource_set},
            _retrievals(records),
        )
    with pytest.raises(ValueError):
        hosted_review.validate_provider_view_pointer_target(
            pointer,
            {_MANIFEST_SNAPSHOT_ID: manifest},
            {},
            _retrievals(records),
        )


def test_current_pointer_requires_an_attempted_required_collection() -> None:
    records = _corpus()["base_records"]
    pointer = hosted_review.validate_provider_view_pointer(records["provider_view_pointer"])
    resource_set_document = copy.deepcopy(records["resource_set"])
    resource_set_document["collections"][0].update(
        {
            "coverage": "not_requested",
            "artifacts": [],
            "retrieval_snapshot_ids": [],
        }
    )
    resource_set = hosted_review.validate_resource_set(resource_set_document)
    manifest_document = copy.deepcopy(records["provider_sync_manifest"])
    manifest_document["retrievals"] = []
    manifest = hosted_review.validate_provider_sync_manifest(manifest_document)

    with pytest.raises(ValueError, match="attempted required collection"):
        hosted_review.validate_provider_view_pointer_target(
            pointer,
            {_MANIFEST_SNAPSHOT_ID: manifest},
            {_RESOURCE_SET_SNAPSHOT_ID: resource_set},
            {},
        )


def test_manifest_closure_rejects_a_resource_set_retrieval_outside_the_transaction() -> None:
    corpus = _corpus()["base_records"]
    manifest = hosted_review.validate_provider_sync_manifest(corpus["provider_sync_manifest"])
    resource_set_document = copy.deepcopy(corpus["resource_set"])
    resource_set_document["collections"][0]["retrieval_snapshot_ids"] = [
        "sha256:1212121212121212121212121212121212121212121212121212121212121212"
    ]
    resource_set = hosted_review.validate_resource_set(resource_set_document)

    with pytest.raises(ValueError):
        hosted_review.validate_manifest_closure(
            manifest,
            {_RESOURCE_SET_SNAPSHOT_ID: resource_set},
            _retrievals(corpus),
        )


def test_manifest_closure_rejects_retrieval_for_another_repository() -> None:
    records = _corpus()["base_records"]
    other_repository_document = copy.deepcopy(records["retrieval"])
    other_repository_document["target"]["repository"]["opaque_id"] = "repo-other"
    manifest = hosted_review.validate_provider_sync_manifest(records["provider_sync_manifest"])
    resource_set = hosted_review.validate_resource_set(records["resource_set"])

    with pytest.raises(ValueError):
        hosted_review.validate_manifest_closure(
            manifest,
            {_RESOURCE_SET_SNAPSHOT_ID: resource_set},
            _retrievals(records, repository_document=other_repository_document),
        )


def test_complete_collection_rejects_failed_retrieval_evidence() -> None:
    records = _corpus()["base_records"]
    failed_document = copy.deepcopy(records["retrieval"])
    failed_document["outcome"] = {"kind": "failed", "reason": "provider_error"}
    manifest = hosted_review.validate_provider_sync_manifest(records["provider_sync_manifest"])
    resource_set = hosted_review.validate_resource_set(records["resource_set"])

    with pytest.raises(ValueError):
        hosted_review.validate_manifest_closure(
            manifest,
            {_RESOURCE_SET_SNAPSHOT_ID: resource_set},
            _retrievals(records, repository_document=failed_document),
        )


def test_unavailable_collection_accepts_same_context_not_found_evidence() -> None:
    records = _corpus()["base_records"]
    unavailable_document = copy.deepcopy(records["resource_set"])
    unavailable_document["collections"][0].update(
        {
            "coverage": "unavailable",
            "artifacts": [],
            "failure_retrieval_snapshot_id": _RETRIEVAL_SNAPSHOT_ID,
        }
    )
    not_found_document = copy.deepcopy(records["retrieval"])
    not_found_document["outcome"] = {"kind": "not_found_under_context"}
    resource_set = hosted_review.validate_resource_set(unavailable_document)
    manifest = hosted_review.validate_provider_sync_manifest(records["provider_sync_manifest"])

    hosted_review.validate_manifest_closure(
        manifest,
        {_RESOURCE_SET_SNAPSHOT_ID: resource_set},
        _retrievals(records, repository_document=not_found_document),
    )


def test_unavailable_collection_forbids_successful_paginated_evidence() -> None:
    records = _corpus()["base_records"]
    unavailable_document = copy.deepcopy(records["resource_set"])
    unavailable_document["collections"][0].update(
        {
            "coverage": "unavailable",
            "artifacts": [],
            "failure_retrieval_snapshot_id": _RETRIEVAL_SNAPSHOT_ID,
            "pagination": {
                "pages": [
                    {
                        "ordinal": 1,
                        "requested_with": None,
                        "next": None,
                        "retrieval_snapshot_id": _RETRIEVAL_SNAPSHOT_ID,
                        "observed_provider_ids": [],
                        "provider_exhausted": True,
                        "provider_snapshot_token": None,
                    }
                ],
                "first_observed_at": "2026-09-15T12:00:00.125Z",
                "last_observed_at": "2026-09-15T12:00:00.125Z",
                "remote_consistency": {"kind": "best_effort_window"},
            },
        }
    )

    with pytest.raises(ValueError):
        hosted_review.validate_resource_set(unavailable_document)


def test_pagination_observation_bounds_and_page_order_match_retrievals() -> None:
    records = _corpus()["base_records"]
    resource_set_document = copy.deepcopy(records["resource_set"])
    profile = hosted_review.ResourceProfileSpec(
        profile_id="example.test:paginated-object/v1",
        target_class=hosted_review.ResourceTargetClass.provider_object,
        target_result_contract_id=None,
        collections=(
            hosted_review.ResourceCollectionSpec(
                name="repository",
                artifact_contract_id=hosted_review.HOSTED_REPOSITORY_CONTRACT_ID,
                minimum_artifacts=1,
                maximum_artifacts=1,
                pagination=hosted_review.CollectionPaginationPolicy.required,
                required_for_last_complete=True,
            ),
        ),
    )
    profiles = {profile.profile_id: profile}
    resource_set_document["profile"] = profile.profile_id
    collection = resource_set_document["collections"][0]
    collection["retrieval_snapshot_ids"] = [
        _RETRIEVAL_SNAPSHOT_ID,
        _DELETION_RETRIEVAL_SNAPSHOT_ID,
    ]
    collection["pagination"] = {
        "pages": [
            {
                "ordinal": 1,
                "requested_with": None,
                "next": {"kind": "opaque_cursor", "value": "cursor-2"},
                "retrieval_snapshot_id": _RETRIEVAL_SNAPSHOT_ID,
                "observed_provider_ids": ["repo-1"],
                "provider_exhausted": False,
                "provider_snapshot_token": None,
            },
            {
                "ordinal": 2,
                "requested_with": {"kind": "opaque_cursor", "value": "cursor-2"},
                "next": None,
                "retrieval_snapshot_id": _DELETION_RETRIEVAL_SNAPSHOT_ID,
                "observed_provider_ids": ["repo-1"],
                "provider_exhausted": True,
                "provider_snapshot_token": None,
            },
        ],
        "first_observed_at": "2026-09-15T12:00:00.125Z",
        "last_observed_at": "2026-09-15T12:00:00.375Z",
        "remote_consistency": {"kind": "best_effort_window"},
    }
    resource_set = hosted_review.validate_resource_set(resource_set_document, profiles)
    hidden_retrieval_document = copy.deepcopy(resource_set_document)
    hidden_retrieval_document["collections"][0]["retrieval_snapshot_ids"].append(
        "sha256:5656565656565656565656565656565656565656565656565656565656565656"
    )
    with pytest.raises(ValueError):
        hosted_review.validate_resource_set(hidden_retrieval_document, profiles)

    second_retrieval_document = copy.deepcopy(records["deletion_retrieval"])
    second_retrieval_document["target"] = copy.deepcopy(records["retrieval"]["target"])
    second_retrieval_document["outcome"] = {"kind": "succeeded"}
    manifest = hosted_review.validate_provider_sync_manifest(records["provider_sync_manifest"])

    hosted_review.validate_manifest_closure(
        manifest,
        {_RESOURCE_SET_SNAPSHOT_ID: resource_set},
        _retrievals(records, deletion_document=second_retrieval_document),
        profiles,
    )

    wrong_bounds_document = copy.deepcopy(resource_set_document)
    wrong_bounds_document["collections"][0]["pagination"]["first_observed_at"] = (
        "2026-09-15T12:00:00Z"
    )
    wrong_bounds = hosted_review.validate_resource_set(wrong_bounds_document, profiles)
    with pytest.raises(ValueError):
        hosted_review.validate_manifest_closure(
            manifest,
            {_RESOURCE_SET_SNAPSHOT_ID: wrong_bounds},
            _retrievals(records, deletion_document=second_retrieval_document),
            profiles,
        )

    reversed_time_document = copy.deepcopy(second_retrieval_document)
    reversed_time_document["started_at"] = "2026-09-15T12:00:00.050Z"
    reversed_time_document["finished_at"] = "2026-09-15T12:00:00.100Z"
    reversed_time_document["rate_limit"] = None
    reversed_window_document = copy.deepcopy(resource_set_document)
    reversed_window_document["collections"][0]["pagination"]["first_observed_at"] = (
        "2026-09-15T12:00:00.100Z"
    )
    reversed_window_document["collections"][0]["pagination"]["last_observed_at"] = (
        "2026-09-15T12:00:00.125Z"
    )
    reversed_window = hosted_review.validate_resource_set(reversed_window_document, profiles)
    with pytest.raises(ValueError):
        hosted_review.validate_manifest_closure(
            manifest,
            {_RESOURCE_SET_SNAPSHOT_ID: reversed_window},
            _retrievals(records, deletion_document=reversed_time_document),
            profiles,
        )


def test_partial_failure_truncation_matches_its_failed_retrieval_reason() -> None:
    records = _corpus()["base_records"]
    partial_document = copy.deepcopy(records["resource_set"])
    partial_document["collections"][0].update(
        {
            "coverage": "partial",
            "truncation": {"reason": "provider_failure", "limit": None},
            "failure_retrieval_snapshot_id": _RETRIEVAL_SNAPSHOT_ID,
        }
    )
    failed_document = copy.deepcopy(records["retrieval"])
    failed_document["outcome"] = {"kind": "failed", "reason": "provider_error"}
    resource_set = hosted_review.validate_resource_set(partial_document)
    manifest = hosted_review.validate_provider_sync_manifest(records["provider_sync_manifest"])

    hosted_review.validate_manifest_closure(
        manifest,
        {_RESOURCE_SET_SNAPSHOT_ID: resource_set},
        _retrievals(records, repository_document=failed_document),
    )

    partial_document["collections"][0]["truncation"]["reason"] = "malformed_response"
    mismatched = hosted_review.validate_resource_set(partial_document)
    with pytest.raises(ValueError):
        hosted_review.validate_manifest_closure(
            manifest,
            {_RESOURCE_SET_SNAPSHOT_ID: mismatched},
            _retrievals(records, repository_document=failed_document),
        )


def test_not_modified_retrieval_reuses_a_published_collection_artifact() -> None:
    records = _corpus()["base_records"]
    not_modified_document = copy.deepcopy(records["retrieval"])
    not_modified_document["outcome"] = {
        "kind": "not_modified",
        "reused_snapshot_id": (
            "sha256:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
        ),
    }
    manifest = hosted_review.validate_provider_sync_manifest(records["provider_sync_manifest"])
    resource_set = hosted_review.validate_resource_set(records["resource_set"])

    with pytest.raises(ValueError):
        hosted_review.validate_manifest_closure(
            manifest,
            {_RESOURCE_SET_SNAPSHOT_ID: resource_set},
            _retrievals(records, repository_document=not_modified_document),
        )


def test_not_found_retrieval_cannot_substantiate_explicit_deletion() -> None:
    corpus = _corpus()["base_records"]
    tombstone = hosted_review.validate_tombstone(corpus["tombstone"])
    retrieval_document = copy.deepcopy(corpus["deletion_retrieval"])
    retrieval_document["outcome"] = {"kind": "not_found_under_context"}

    manifest = hosted_review.validate_provider_sync_manifest(corpus["provider_sync_manifest"])
    resource_set = hosted_review.validate_resource_set(corpus["resource_set"])
    with pytest.raises(ValueError):
        hosted_review.validate_tombstone_evidence(
            tombstone,
            manifest,
            {_RESOURCE_SET_SNAPSHOT_ID: resource_set},
            _retrievals(corpus, deletion_document=retrieval_document),
            _live_snapshots(tombstone),
        )


def test_explicit_deletion_evidence_must_use_the_same_authorization_context() -> None:
    corpus = _corpus()["base_records"]
    tombstone = hosted_review.validate_tombstone(corpus["tombstone"])
    retrieval_document = copy.deepcopy(corpus["deletion_retrieval"])
    retrieval_document["authorization_context"]["principal_opaque_id"] = "person-elsewhere"
    manifest = hosted_review.validate_provider_sync_manifest(corpus["provider_sync_manifest"])
    resource_set = hosted_review.validate_resource_set(corpus["resource_set"])
    with pytest.raises(ValueError):
        hosted_review.validate_tombstone_evidence(
            tombstone,
            manifest,
            {_RESOURCE_SET_SNAPSHOT_ID: resource_set},
            _retrievals(corpus, deletion_document=retrieval_document),
            _live_snapshots(tombstone),
        )


def test_explicit_deletion_accepts_typed_same_target_evidence() -> None:
    corpus = _corpus()["base_records"]
    tombstone = hosted_review.validate_tombstone(corpus["tombstone"])
    resource_set = hosted_review.validate_resource_set(corpus["resource_set"])
    manifest = hosted_review.validate_provider_sync_manifest(corpus["provider_sync_manifest"])

    hosted_review.validate_tombstone_evidence(
        tombstone,
        manifest,
        {_RESOURCE_SET_SNAPSHOT_ID: resource_set},
        _retrievals(corpus),
        _live_snapshots(tombstone),
    )


def test_successful_retrieval_without_deletion_result_cannot_tombstone() -> None:
    records = _corpus()["base_records"]
    tombstone = hosted_review.validate_tombstone(records["tombstone"])
    generic_success = copy.deepcopy(records["deletion_retrieval"])
    generic_success["outcome"] = {"kind": "succeeded"}
    manifest = hosted_review.validate_provider_sync_manifest(records["provider_sync_manifest"])
    resource_set = hosted_review.validate_resource_set(records["resource_set"])

    with pytest.raises(ValueError):
        hosted_review.validate_tombstone_evidence(
            tombstone,
            manifest,
            {_RESOURCE_SET_SNAPSHOT_ID: resource_set},
            _retrievals(records, deletion_document=generic_success),
            _live_snapshots(tombstone),
        )


def test_explicit_deletion_rejects_another_provider_object() -> None:
    records = _corpus()["base_records"]
    tombstone = hosted_review.validate_tombstone(records["tombstone"])
    deletion_document = copy.deepcopy(records["deletion_retrieval"])
    deletion_document["outcome"]["target"]["opaque_id"] = "change-other"
    manifest = hosted_review.validate_provider_sync_manifest(records["provider_sync_manifest"])
    resource_set = hosted_review.validate_resource_set(records["resource_set"])

    with pytest.raises(ValueError):
        hosted_review.validate_tombstone_evidence(
            tombstone,
            manifest,
            {_RESOURCE_SET_SNAPSHOT_ID: resource_set},
            _retrievals(records, deletion_document=deletion_document),
            _live_snapshots(tombstone),
        )


def test_explicit_deletion_rejects_another_repository() -> None:
    records = _corpus()["base_records"]
    tombstone = hosted_review.validate_tombstone(records["tombstone"])
    deletion_document = copy.deepcopy(records["deletion_retrieval"])
    deletion_document["outcome"]["repository"]["opaque_id"] = "repo-other"
    manifest = hosted_review.validate_provider_sync_manifest(records["provider_sync_manifest"])
    resource_set = hosted_review.validate_resource_set(records["resource_set"])

    with pytest.raises(ValueError):
        hosted_review.validate_tombstone_evidence(
            tombstone,
            manifest,
            {_RESOURCE_SET_SNAPSHOT_ID: resource_set},
            _retrievals(records, deletion_document=deletion_document),
            _live_snapshots(tombstone),
        )


def test_tombstone_previous_live_snapshot_must_identify_the_same_object() -> None:
    records = _corpus()["base_records"]
    tombstone = hosted_review.validate_tombstone(records["tombstone"])
    manifest = hosted_review.validate_provider_sync_manifest(records["provider_sync_manifest"])
    resource_set = hosted_review.validate_resource_set(records["resource_set"])
    other_target = tombstone.target.model_copy(update={"opaque_id": "change-other"})
    wrong_live = hosted_review.LiveSnapshotContext(
        target=other_target,
        repository=tombstone.repository,
        authorization_context=tombstone.authorization_context,
        observed_at="2026-09-15T11:59:59Z",
    )

    with pytest.raises(ValueError):
        hosted_review.validate_tombstone_evidence(
            tombstone,
            manifest,
            {_RESOURCE_SET_SNAPSHOT_ID: resource_set},
            _retrievals(records),
            {tombstone.previous_live_snapshot_id: wrong_live},
        )


def test_deletion_evidence_must_not_predate_the_previous_live_snapshot() -> None:
    records = _corpus()["base_records"]
    tombstone = hosted_review.validate_tombstone(records["tombstone"])
    manifest = hosted_review.validate_provider_sync_manifest(records["provider_sync_manifest"])
    resource_set = hosted_review.validate_resource_set(records["resource_set"])
    later_live = hosted_review.LiveSnapshotContext(
        target=tombstone.target,
        repository=tombstone.repository,
        authorization_context=tombstone.authorization_context,
        observed_at="2026-09-15T12:00:00.225Z",
    )

    with pytest.raises(ValueError):
        hosted_review.validate_tombstone_evidence(
            tombstone,
            manifest,
            {_RESOURCE_SET_SNAPSHOT_ID: resource_set},
            _retrievals(records),
            {tombstone.previous_live_snapshot_id: later_live},
        )


def test_tombstone_observation_must_stay_inside_its_committed_transaction() -> None:
    records = _corpus()["base_records"]
    tombstone_document = copy.deepcopy(records["tombstone"])
    tombstone_document["observed_at"] = "2026-09-15T12:00:01.125Z"
    tombstone = hosted_review.validate_tombstone(tombstone_document)
    manifest = hosted_review.validate_provider_sync_manifest(records["provider_sync_manifest"])
    resource_set = hosted_review.validate_resource_set(records["resource_set"])

    with pytest.raises(ValueError):
        hosted_review.validate_tombstone_evidence(
            tombstone,
            manifest,
            {_RESOURCE_SET_SNAPSHOT_ID: resource_set},
            _retrievals(records),
            _live_snapshots(tombstone),
        )


@pytest.mark.parametrize("state", ["staged", "failed"])
def test_tombstone_rejects_uncommitted_manifest_states(state: str) -> None:
    records = _corpus()["base_records"]
    tombstone = hosted_review.validate_tombstone(records["tombstone"])
    manifest_document = copy.deepcopy(records["provider_sync_manifest"])
    manifest_document["state"] = state
    if state == "staged":
        manifest_document["finished_at"] = None
    else:
        manifest_document["failure"] = {"reason": "publication_failed"}
    manifest = hosted_review.validate_provider_sync_manifest(manifest_document)
    resource_set = hosted_review.validate_resource_set(records["resource_set"])

    with pytest.raises(ValueError):
        hosted_review.validate_tombstone_evidence(
            tombstone,
            manifest,
            {_RESOURCE_SET_SNAPSHOT_ID: resource_set},
            _retrievals(records),
            _live_snapshots(tombstone),
        )
