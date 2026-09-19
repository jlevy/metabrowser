from __future__ import annotations

from typing import Any

import pytest
from hosted_review_cases import apply_case_changes, load_hosted_review_corpus

from metabrowser.builtin_plugins.hosted_review import models as hosted_review


def _corpus() -> dict[str, Any]:
    return load_hosted_review_corpus("repository-activity-conformance.json")


def test_repository_activity_agrees_with_the_portable_corpus() -> None:
    corpus = _corpus()

    for case in corpus["cases"]:
        document = apply_case_changes(corpus["base_document"], case["changes"])
        if case["expect"] == "valid":
            parsed = hosted_review.validate_repository_activity(document)
            assert hosted_review.dump_repository_activity(parsed) == document
        else:
            with pytest.raises(ValueError):
                hosted_review.validate_repository_activity(document)


def test_repository_activity_composes_commit_and_change_request_items() -> None:
    activity = hosted_review.validate_repository_activity(_corpus()["base_document"])

    assert tuple(item.kind for item in activity.items) == (
        hosted_review.ActivityKind.commit,
        hosted_review.ActivityKind.change_request,
    )
    assert activity.items[0].freshness.kind == "immutable"
    assert activity.items[1].freshness.kind == "observed"


def test_index_style_change_request_can_defer_revision_resolution() -> None:
    corpus = _corpus()
    case = next(
        case
        for case in corpus["cases"]
        if case["name"] == "index-style-unresolved-change-request-revisions"
    )

    activity = hosted_review.validate_repository_activity(
        apply_case_changes(corpus["base_document"], case["changes"])
    )
    change_request = activity.items[1]

    assert change_request.comparison_available is False
    assert change_request.primary_revision.repository_id is None
    assert (
        change_request.primary_revision.availability
        is hosted_review.RevisionAvailability.not_requested
    )
    assert change_request.base_revision is not None
    assert (
        change_request.base_revision.availability
        is hosted_review.RevisionAvailability.not_requested
    )
    assert change_request.head_revision is not None
    assert change_request.head_revision.repository_id is None


def test_partial_activity_names_its_bound_and_opaque_continuation() -> None:
    corpus = _corpus()
    case = next(
        case for case in corpus["cases"] if case["name"] == "partial-page-with-continuation"
    )

    activity = hosted_review.validate_repository_activity(
        apply_case_changes(corpus["base_document"], case["changes"])
    )

    assert activity.coverage is hosted_review.ActivityCoverage.partial
    assert activity.continuation is not None
    assert activity.continuation.value == "next_page_2"
    assert activity.truncation is not None
    assert activity.truncation.reason is hosted_review.TruncationReason.item_bound
    assert activity.truncation.limit == activity.max_items == len(activity.items)


def test_activity_actors_preserve_source_identity_without_inventing_provider_data() -> None:
    activity = hosted_review.validate_repository_activity(_corpus()["base_document"])

    commit_actor = activity.items[0].actors[0]
    change_request_actor = activity.items[1].actors[0]
    assert isinstance(commit_actor, hosted_review.GitActivityActor)
    assert (commit_actor.name, commit_actor.email) == ("Commit Author", "author@example.com")
    assert isinstance(change_request_actor, hosted_review.ProviderActivityActor)
    assert change_request_actor.actor.provider_opaque_id == "person-4"


def test_equal_event_times_use_id_ascending_as_the_tie_break() -> None:
    corpus = _corpus()
    case = next(
        case for case in corpus["cases"] if case["name"] == "equal-event-at-orders-id-ascending"
    )

    activity = hosted_review.validate_repository_activity(
        apply_case_changes(corpus["base_document"], case["changes"])
    )

    assert tuple(item.id for item in activity.items) == ("a-commit", "z-change-request")
