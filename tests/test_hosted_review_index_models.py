from __future__ import annotations

import copy
from typing import Any

import pytest
from hosted_review_cases import (
    apply_case_changes,
    change_request_case,
    load_hosted_review_corpus,
)

from metabrowser.builtin_plugins.hosted_review import models as hosted_review


def _corpus() -> dict[str, Any]:
    return load_hosted_review_corpus("change-request-index-conformance.json")


def _index_api(record_name: str) -> tuple[Any, Any]:
    names = {
        "change_request_index": (
            "validate_change_request_index",
            "dump_change_request_index",
        ),
        "empty_change_request_index": (
            "validate_change_request_index",
            "dump_change_request_index",
        ),
        "index_resource_set": ("validate_resource_set", "dump_resource_set"),
    }
    validator_name, dumper_name = names[record_name]
    return getattr(hosted_review, validator_name), getattr(hosted_review, dumper_name)


def test_index_models_agree_with_the_portable_corpus() -> None:
    corpus = _corpus()

    for case in corpus["cases"]:
        document = apply_case_changes(corpus["base_records"][case["record"]], case["changes"])
        validator, dumper = _index_api(case["record"])
        if case["expect"] == "valid":
            assert dumper(validator(document)) == document
        else:
            with pytest.raises(ValueError):
                validator(document)


def test_query_key_hashes_only_the_normalized_query() -> None:
    document = _corpus()["base_records"]["change_request_index"]
    parsed = hosted_review.validate_change_request_index(document)

    assert hosted_review.change_request_index_query_key(parsed.query) == (
        "sha256:f2b2ced437bdfdd0e2da3672083550c597bd00b094477ecb53e2eb46e54bb793"
    )

    changed_query = copy.deepcopy(document["query"])
    changed_query["bounds"]["max_items"] = 51
    parsed_query = hosted_review.ChangeRequestIndexQuery.model_validate(changed_query)
    assert hosted_review.change_request_index_query_key(parsed_query) != document["query_key"]


def test_equal_primary_sort_values_use_provider_id_as_the_tie_breaker() -> None:
    document = copy.deepcopy(_corpus()["base_records"]["change_request_index"])
    document["rows"][1]["updated_at"] = document["rows"][0]["updated_at"]
    hosted_review.validate_change_request_index(document)

    document["rows"].reverse()
    with pytest.raises(ValueError):
        hosted_review.validate_change_request_index(document)


def test_index_order_compares_timestamp_values_not_their_spelling() -> None:
    document = copy.deepcopy(_corpus()["base_records"]["change_request_index"])
    document["rows"][0]["updated_at"] = "2026-09-11T09:30:00.125Z"
    document["rows"][1]["updated_at"] = "2026-09-11T09:30:00Z"

    hosted_review.validate_change_request_index(document)

    document["rows"].reverse()
    with pytest.raises(ValueError):
        hosted_review.validate_change_request_index(document)


def test_index_rejects_a_lone_surrogate_provider_id_even_without_a_tie() -> None:
    document = copy.deepcopy(_corpus()["base_records"]["change_request_index"])
    document["rows"] = [document["rows"][0]]
    document["rows"][0]["provider_ref"]["opaque_id"] = "\ud800"

    with pytest.raises(ValueError):
        hosted_review.validate_change_request_index(document)


def test_index_row_and_direct_change_request_share_identity() -> None:
    index = hosted_review.validate_change_request_index(
        _corpus()["base_records"]["change_request_index"]
    )
    change_request = hosted_review.validate_change_request(change_request_case())

    hosted_review.validate_change_request_index_row_identity(change_request, index.rows[0])

    other_document = change_request_case()
    other_document["provider_ref"]["opaque_id"] = "change-other"
    other = hosted_review.validate_change_request(other_document)
    with pytest.raises(ValueError):
        hosted_review.validate_change_request_index_row_identity(other, index.rows[0])


def test_acquisition_evidence_stays_out_of_the_reusable_index_snapshot() -> None:
    parsed = hosted_review.validate_change_request_index(
        _corpus()["base_records"]["change_request_index"]
    )
    document = hosted_review.dump_change_request_index(parsed)

    assert set(document) == {"query_key", "query", "rows"}
    assert "pagination" not in document
    assert "retrieval" not in document
    assert "remote_consistency" not in document


def test_index_resource_set_resolves_rows_and_pagination_together() -> None:
    records = _corpus()["base_records"]
    index = hosted_review.validate_change_request_index(records["change_request_index"])
    resource_set = hosted_review.validate_resource_set(records["index_resource_set"])
    snapshot_id = resource_set.collections[0].artifacts[0].snapshot_id

    hosted_review.validate_change_request_index_resource_set(resource_set, index, snapshot_id)

    mismatched_document = copy.deepcopy(records["index_resource_set"])
    mismatched_document["collections"][0]["pagination"]["pages"][1]["observed_provider_ids"] = [
        "change-other"
    ]
    mismatched = hosted_review.validate_resource_set(mismatched_document)
    with pytest.raises(ValueError):
        hosted_review.validate_change_request_index_resource_set(mismatched, index, snapshot_id)


def test_index_item_bound_counts_raw_page_observations_before_deduplication() -> None:
    records = _corpus()["base_records"]
    index_document = copy.deepcopy(records["change_request_index"])
    index_document["query"]["bounds"]["max_items"] = 1
    index_document["rows"] = [index_document["rows"][0]]
    parsed_query = hosted_review.ChangeRequestIndexQuery.model_validate(index_document["query"])
    index_document["query_key"] = hosted_review.change_request_index_query_key(parsed_query)
    index = hosted_review.validate_change_request_index(index_document)

    resource_set_document = copy.deepcopy(records["index_resource_set"])
    resource_set_document["target"]["query_key"] = index.query_key
    resource_set_document["collections"][0]["pagination"]["pages"][1]["observed_provider_ids"] = [
        "change-17"
    ]
    resource_set = hosted_review.validate_resource_set(resource_set_document)
    snapshot_id = resource_set.collections[0].artifacts[0].snapshot_id

    with pytest.raises(ValueError, match="item bound"):
        hosted_review.validate_change_request_index_resource_set(
            resource_set,
            index,
            snapshot_id,
        )


@pytest.mark.parametrize(
    ("reason", "query_bound", "wrong_limit"),
    [
        ("byte_bound", 200_000, 200_001),
        ("time_bound", 5_000, 5_001),
    ],
)
def test_index_resource_set_matches_byte_and_time_truncation_to_query_bounds(
    reason: str,
    query_bound: int,
    wrong_limit: int,
) -> None:
    records = _corpus()["base_records"]
    index = hosted_review.validate_change_request_index(records["change_request_index"])
    resource_set_document = copy.deepcopy(records["index_resource_set"])
    collection = resource_set_document["collections"][0]
    collection["coverage"] = "partial"
    collection["pagination"]["pages"][-1]["next"] = {
        "kind": "opaque_cursor",
        "value": "cursor-3",
    }
    collection["pagination"]["pages"][-1]["provider_exhausted"] = False
    collection["truncation"] = {"reason": reason, "limit": query_bound}
    snapshot_id = collection["artifacts"][0]["snapshot_id"]

    matching = hosted_review.validate_resource_set(resource_set_document)
    hosted_review.validate_change_request_index_resource_set(matching, index, snapshot_id)

    collection["truncation"]["limit"] = wrong_limit
    mismatched = hosted_review.validate_resource_set(resource_set_document)
    with pytest.raises(ValueError):
        hosted_review.validate_change_request_index_resource_set(mismatched, index, snapshot_id)
