from __future__ import annotations

import pytest
from hosted_review_cases import change_request_case
from pydantic import ValidationError

from metabrowser.builtin_plugins.hosted_review.models import (
    ChangeRequestState,
    dump_change_request,
    validate_change_request,
)


def test_change_request_accepts_a_provider_neutral_merge_request() -> None:
    parsed = validate_change_request(change_request_case())

    assert parsed.state is ChangeRequestState.open
    assert parsed.provider_ref.provider == "forge"
    assert parsed.provider_ref.object_kind == "merge_request"
    assert dump_change_request(parsed) == change_request_case()


def test_change_request_rejects_lifecycle_timestamps_before_creation() -> None:
    document = change_request_case()
    document["state"] = "merged"
    document["closed_at"] = "2026-09-09T12:00:00Z"
    document["merged_at"] = "2026-09-09T11:59:00Z"

    with pytest.raises(ValidationError, match="closed_at must not precede created_at"):
        validate_change_request(document)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("url", "http://code.example/changes/17", "credential-free HTTPS"),
        ("updated_at", "yesterday", "RFC 3339"),
        ("state", "awaiting_review", "Input should be"),
    ],
)
def test_change_request_rejects_nonportable_top_level_values(
    field: str, value: str, message: str
) -> None:
    document = change_request_case()
    document[field] = value

    with pytest.raises(ValidationError, match=message):
        validate_change_request(document)


def test_change_request_rejects_unknown_fields() -> None:
    document = change_request_case()
    document["provider_payload"] = {"mergeable_state": "mystery"}

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        validate_change_request(document)


def test_change_request_rejects_inconsistent_provider_and_repository_identity() -> None:
    document = change_request_case()
    document["repository"]["instance"] = "other.example"

    with pytest.raises(ValidationError, match="same provider instance"):
        validate_change_request(document)


def test_change_request_rejects_base_from_another_repository() -> None:
    document = change_request_case()
    document["comparison"]["base"]["repository_id"] = "repo-elsewhere"

    with pytest.raises(ValidationError, match="comparison base"):
        validate_change_request(document)


def test_revision_availability_requires_an_object_id_exactly_when_present() -> None:
    missing_oid = change_request_case()
    missing_oid["comparison"]["head"]["oid"] = None
    with pytest.raises(ValidationError, match="oid is present exactly"):
        validate_change_request(missing_oid)

    unfetched_oid = change_request_case()
    unfetched_oid["comparison"]["head"]["availability"] = "not_requested"
    with pytest.raises(ValidationError, match="oid is present exactly"):
        validate_change_request(unfetched_oid)


def test_change_request_rejects_negative_aggregate_counts() -> None:
    document = change_request_case()
    document["counts"]["reviews"] = -1

    with pytest.raises(ValidationError, match="greater than or equal to 0"):
        validate_change_request(document)


def test_merge_commit_availability_matches_its_object_id() -> None:
    document = change_request_case()
    document["comparison"]["merge_commit_availability"] = "present"

    with pytest.raises(ValidationError, match="merge_commit_oid is present exactly"):
        validate_change_request(document)


def test_change_request_preserves_hostile_display_text_as_data() -> None:
    document = change_request_case()
    document["title"] = '<img src=x onerror="alert(1)"> \u202e title'

    parsed = validate_change_request(document)

    assert parsed.title == document["title"]
