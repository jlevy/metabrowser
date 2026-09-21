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
    return load_hosted_review_corpus("review-records-conformance.json")


def _record_api(record_name: str) -> tuple[Any, Any]:
    family = record_name.removesuffix("_empty").removesuffix("_reply")
    names = {
        "change_request_comment": (
            "validate_change_request_comment",
            "dump_change_request_comment",
        ),
        "review": ("validate_review", "dump_review"),
        "review_thread": ("validate_review_thread", "dump_review_thread"),
        "review_comment": ("validate_review_comment", "dump_review_comment"),
        "check_suite": ("validate_check", "dump_check"),
        "check_run": ("validate_check", "dump_check"),
        "commit_status": ("validate_commit_status", "dump_commit_status"),
    }
    validator_name, dumper_name = names[family]
    return getattr(hosted_review, validator_name), getattr(hosted_review, dumper_name)


def _materialize_bundle() -> dict[str, Any]:
    corpus = _corpus()
    records = corpus["base_records"]
    bundle = corpus["bundle"]
    return {
        name: copy.deepcopy([records[record_name] for record_name in record_names])
        for name, record_names in bundle.items()
        if name != "review_comments_complete"
    } | {"review_comments_complete": bundle["review_comments_complete"]}


def _validate_bundle(document: dict[str, Any]) -> None:
    hosted_review.validate_hosted_review_bundle(
        change_request=hosted_review.validate_change_request(change_request_case()),
        change_request_comments=tuple(
            hosted_review.validate_change_request_comment(value)
            for value in document["change_request_comments"]
        ),
        reviews=tuple(hosted_review.validate_review(value) for value in document["reviews"]),
        review_threads=tuple(
            hosted_review.validate_review_thread(value) for value in document["review_threads"]
        ),
        review_comments=tuple(
            hosted_review.validate_review_comment(value) for value in document["review_comments"]
        ),
        checks=tuple(hosted_review.validate_check(value) for value in document["checks"]),
        commit_statuses=tuple(
            hosted_review.validate_commit_status(value) for value in document["commit_statuses"]
        ),
        review_comments_complete=document["review_comments_complete"],
    )


def test_review_record_models_agree_with_the_portable_corpus() -> None:
    corpus = _corpus()

    for case in corpus["cases"]:
        document = apply_case_changes(corpus["base_records"][case["record"]], case["changes"])
        validator, dumper = _record_api(case["record"])
        if case["expect"] == "valid":
            assert dumper(validator(document)) == document
        else:
            with pytest.raises(ValueError):
                validator(document)


def test_hosted_review_bundle_agrees_with_the_portable_corpus() -> None:
    for case in _corpus()["bundle_cases"]:
        document = apply_case_changes(_materialize_bundle(), case["changes"])
        if case["expect"] == "valid":
            _validate_bundle(document)
        else:
            with pytest.raises(ValueError):
                _validate_bundle(document)


def test_deleted_comments_preserve_missing_actor_and_url_explicitly() -> None:
    records = _corpus()["base_records"]

    discussion = hosted_review.validate_change_request_comment(records["change_request_comment"])
    review_comment = hosted_review.validate_review_comment(records["review_comment_reply"])

    assert discussion.author is None and discussion.url is None
    assert review_comment.author is None and review_comment.url is None


def test_anchor_variants_preserve_file_identity_and_revision_context() -> None:
    records = _corpus()["base_records"]
    line = hosted_review.validate_review_thread(records["review_thread"]).anchor
    file = hosted_review.validate_review_thread(records["review_thread_empty"]).anchor
    range_document = next(case for case in _corpus()["cases"] if case["name"] == "range-anchor")
    ranged = hosted_review.validate_review_thread(
        apply_case_changes(records["review_thread"], range_document["changes"])
    ).anchor
    byte_path_document = next(
        case for case in _corpus()["cases"] if case["name"] == "non-utf8-path-bytes"
    )
    byte_path = hosted_review.validate_review_thread(
        apply_case_changes(records["review_thread_empty"], byte_path_document["changes"])
    ).anchor

    assert (line.kind, file.kind, ranged.kind) == ("line", "file", "range")
    assert isinstance(ranged, hosted_review.RangeReviewAnchor)
    assert line.comparison.head.oid == line.current_revision.oid
    assert (ranged.start.side, ranged.end.side) == (
        hosted_review.ReviewSide.base,
        hosted_review.ReviewSide.head,
    )
    assert byte_path.path_b64 == "c3JjL/8ucHk="


def test_range_anchor_preserves_independently_sided_endpoints() -> None:
    corpus = _corpus()
    range_case = next(case for case in corpus["cases"] if case["name"] == "range-anchor")
    document = apply_case_changes(corpus["base_records"]["review_thread"], range_case["changes"])
    thread = hosted_review.validate_review_thread(document)

    assert isinstance(thread.anchor, hosted_review.RangeReviewAnchor)
    assert thread.anchor.start.side is hosted_review.ReviewSide.base
    assert thread.anchor.end.side is hosted_review.ReviewSide.head


def test_current_anchor_can_preserve_an_older_original_revision() -> None:
    corpus = _corpus()
    case = next(
        case
        for case in corpus["cases"]
        if case["name"] == "current-anchor-preserves-older-original-revision"
    )

    thread = hosted_review.validate_review_thread(
        apply_case_changes(corpus["base_records"]["review_thread"], case["changes"])
    )

    assert thread.anchor.original_revision.oid != thread.anchor.current_revision.oid


def test_anchor_records_an_observed_but_unavailable_original_revision() -> None:
    corpus = _corpus()
    case = next(
        case
        for case in corpus["cases"]
        if case["name"] == "original-anchor-revision-may-be-unavailable"
    )

    thread = hosted_review.validate_review_thread(
        apply_case_changes(corpus["base_records"]["review_thread"], case["changes"])
    )

    assert thread.anchor.original_revision.oid is None
    assert (
        thread.anchor.original_revision.availability
        is hosted_review.RevisionAvailability.unavailable
    )


def test_completed_suite_may_lack_run_only_provider_fields() -> None:
    corpus = _corpus()
    case = next(
        case
        for case in corpus["cases"]
        if case["name"] == "check-suite-provider-fields-may-be-unavailable"
    )

    check = hosted_review.validate_check(
        apply_case_changes(corpus["base_records"]["check_suite"], case["changes"])
    )

    assert check.status is hosted_review.CheckStatus.completed
    assert check.conclusion is hosted_review.CheckConclusion.success
    assert check.name is check.started_at is check.completed_at is None


def test_bundle_rejects_a_reply_that_crosses_threads() -> None:
    document = _materialize_bundle()
    document["review_comments"][1]["thread_id"] = "thread-2"
    document["review_comments"][1]["anchor"] = copy.deepcopy(
        document["review_threads"][1]["anchor"]
    )

    with pytest.raises(ValueError, match="only within their thread"):
        _validate_bundle(document)


def test_bundle_rejects_reply_cycles() -> None:
    document = _materialize_bundle()
    document["review_comments"][0]["in_reply_to_id"] = "review-comment-2"

    with pytest.raises(ValueError, match="reply graph cannot contain cycles"):
        _validate_bundle(document)


def test_bundle_distinguishes_complete_and_partial_comment_counts() -> None:
    document = _materialize_bundle()
    document["review_threads"][0]["comment_count"] = 3

    with pytest.raises(ValueError, match="must equal"):
        _validate_bundle(document)

    document["review_comments_complete"] = False
    _validate_bundle(document)
