from __future__ import annotations

import pytest
from hosted_review_cases import change_request_case
from pydantic import ValidationError

from metabrowser.builtin_plugins.hosted_review.models import (
    ChangeRequestState,
    ComparisonRef,
    GitObjectRef,
    LocalGitObjectAvailability,
    LocalObjectAvailability,
    RevisionObservation,
    RevisionRef,
    dump_change_request,
    local_git_object_availability,
    local_merge_commit_availability,
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


def test_revision_observation_requires_an_object_id_exactly_when_observed() -> None:
    missing_oid = change_request_case()
    missing_oid["comparison"]["head"]["oid"] = None
    with pytest.raises(ValidationError, match="oid is present exactly when the provider observed"):
        validate_change_request(missing_oid)

    unrequested_oid = change_request_case()
    unrequested_oid["comparison"]["head"]["observation"] = "not_requested"
    with pytest.raises(ValidationError, match="oid is present exactly when the provider observed"):
        validate_change_request(unrequested_oid)


def test_revision_observation_names_provider_evidence_not_local_git_state() -> None:
    assert {member.value for member in RevisionObservation} == {
        "observed",
        "unavailable",
        "not_requested",
    }
    assert set(RevisionRef.model_fields) == {"repository_id", "ref", "oid", "observation"}
    assert set(GitObjectRef.model_fields) == {"repository_id", "oid", "observation"}
    assert "merge_commit_observation" in ComparisonRef.model_fields

    local_state = change_request_case()
    local_state["comparison"]["head"]["observation"] = "present"
    with pytest.raises(ValidationError, match="observation"):
        validate_change_request(local_state)

    superseded = change_request_case()
    superseded["comparison"]["head"]["availability"] = superseded["comparison"]["head"].pop(
        "observation"
    )
    with pytest.raises(ValidationError, match="observation"):
        validate_change_request(superseded)

    superseded_merge = change_request_case()
    superseded_merge["comparison"]["merge_commit_availability"] = superseded_merge[
        "comparison"
    ].pop("merge_commit_observation")
    with pytest.raises(ValidationError, match="merge_commit_observation"):
        validate_change_request(superseded_merge)


def test_local_object_availability_is_a_separate_closed_vocabulary() -> None:
    assert tuple(member.value for member in LocalObjectAvailability) == (
        "not_requested",
        "present",
        "missing_fetchable",
        "fetch_failed",
        "unavailable",
        "outside_bound",
    )
    assert set(LocalGitObjectAvailability.model_fields) == {"oid", "availability"}

    comparison = validate_change_request(change_request_case()).comparison
    head_oid = comparison.head.oid
    assert head_oid is not None
    for state in LocalObjectAvailability:
        report = local_git_object_availability(comparison.head, state)
        assert report.oid == head_oid
        assert report.availability is state
    # Reporting local state never rewrites the provider observation it describes.
    assert comparison.head.observation is RevisionObservation.observed

    object_ref = GitObjectRef(
        repository_id="repo-2",
        oid=head_oid,
        observation=RevisionObservation.observed,
    )
    assert local_git_object_availability(
        object_ref, LocalObjectAvailability.missing_fetchable
    ) == LocalGitObjectAvailability(
        oid=head_oid,
        availability=LocalObjectAvailability.missing_fetchable,
    )

    with pytest.raises(ValidationError):
        LocalGitObjectAvailability.model_validate({"oid": None, "availability": "present"})
    with pytest.raises(ValidationError):
        LocalGitObjectAvailability.model_validate({"oid": head_oid, "availability": "observed"})
    with pytest.raises(ValidationError):
        LocalGitObjectAvailability.model_validate(
            {"oid": head_oid, "availability": "present", "observation": "observed"}
        )


@pytest.mark.parametrize(
    "oid",
    [
        "0123456789abcdef0123456789abcdef0123456",
        "0123456789abcdef0123456789abcdef012345678",
        "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcde",
        "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef0",
    ],
)
def test_local_object_availability_requires_a_full_git_object_name(oid: str) -> None:
    # The local availability projection has no conformance corpus, so its object ID bound
    # is pinned here alongside the corpus cases for the provider-record families.
    with pytest.raises(ValidationError):
        LocalGitObjectAvailability.model_validate({"oid": oid, "availability": "present"})

    for accepted in ("0" * 40, "0" * 64):
        assert (
            LocalGitObjectAvailability.model_validate(
                {"oid": accepted, "availability": "present"}
            ).oid
            == accepted
        )


@pytest.mark.parametrize("observation", ["unavailable", "not_requested"])
def test_local_object_availability_requires_a_provider_observed_object_id(
    observation: str,
) -> None:
    document = change_request_case()
    document["comparison"]["head"]["observation"] = observation
    document["comparison"]["head"]["oid"] = None
    head = validate_change_request(document).comparison.head

    for state in LocalObjectAvailability:
        with pytest.raises(ValueError, match="provider-observed object ID"):
            local_git_object_availability(head, state)


def test_local_merge_commit_availability_uses_the_observed_merge_commit() -> None:
    document = change_request_case()
    merge_oid = "abcdef0123456789abcdef0123456789abcdef01"
    document["comparison"]["merge_commit_observation"] = "observed"
    document["comparison"]["merge_commit_oid"] = merge_oid
    comparison = validate_change_request(document).comparison

    for state in LocalObjectAvailability:
        report = local_merge_commit_availability(comparison, state)
        assert report == LocalGitObjectAvailability(oid=merge_oid, availability=state)
    # The merge report never substitutes the head revision's object ID.
    assert comparison.head.oid != merge_oid
    assert comparison.merge_commit_observation is RevisionObservation.observed


@pytest.mark.parametrize("observation", ["unavailable", "not_requested"])
def test_local_merge_commit_availability_requires_a_provider_observed_merge_commit(
    observation: str,
) -> None:
    document = change_request_case()
    document["comparison"]["merge_commit_observation"] = observation
    document["comparison"]["merge_commit_oid"] = None
    comparison = validate_change_request(document).comparison
    assert comparison.head.observation is RevisionObservation.observed

    for state in LocalObjectAvailability:
        with pytest.raises(ValueError, match="provider-observed merge commit object ID"):
            local_merge_commit_availability(comparison, state)


def test_change_request_rejects_negative_aggregate_counts() -> None:
    document = change_request_case()
    document["counts"]["reviews"] = -1

    with pytest.raises(ValidationError, match="greater than or equal to 0"):
        validate_change_request(document)


def test_merge_commit_observation_matches_its_object_id() -> None:
    document = change_request_case()
    document["comparison"]["merge_commit_observation"] = "observed"

    with pytest.raises(ValidationError, match="merge_commit_oid is present exactly"):
        validate_change_request(document)


def test_change_request_preserves_hostile_display_text_as_data() -> None:
    document = change_request_case()
    document["title"] = '<img src=x onerror="alert(1)"> \u202e title'

    parsed = validate_change_request(document)

    assert parsed.title == document["title"]


def test_change_request_preserves_unavailable_provider_identity() -> None:
    document = change_request_case()
    document["author"] = None
    document["comparison"]["head"]["repository_id"] = None

    parsed = validate_change_request(document)

    assert parsed.author is None
    assert parsed.comparison.head.repository_id is None
    assert parsed.comparison.head.oid == document["comparison"]["head"]["oid"]


def test_change_request_id_is_verified_against_the_structured_identity() -> None:
    # The recorded GitHub recipe output: a base64 repository node ID and the "pull" kind.
    document = change_request_case()
    repository_id = "MDEwOlJlcG9zaXRvcnkyMTI2MTMwNDk="
    for ref in (document["provider_ref"], document["repository"]):
        ref["provider"] = "github"
        ref["instance"] = "github.com"
    document["repository"]["opaque_id"] = repository_id
    document["comparison"]["base"]["repository_id"] = repository_id
    document["number"] = 14430
    document["url"] = "https://github.com/cli/cli/pull/14430"
    document["id"] = f"github:github.com:{repository_id}:pull:14430"

    assert validate_change_request(document).id == document["id"]

    document["id"] = f"github:github.com:{repository_id}:pull:14431"
    with pytest.raises(ValidationError, match="provider:instance:repository_opaque_id"):
        validate_change_request(document)
