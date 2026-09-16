from __future__ import annotations

import hashlib

import pytest
from frontmatter_format import FmFormatError
from hosted_review_cases import change_request_case
from pydantic import ValidationError

from metabrowser.builtin_plugins.hosted_review.artifacts import (
    CHANGE_REQUEST_COMMENT_CONTRACT_ID,
    CHANGE_REQUEST_CONTRACT_ID,
    REVIEW_COMMENT_CONTRACT_ID,
    REVIEW_CONTRACT_ID,
    parse_frontmatter_artifact,
    serialize_change_request_artifact,
    serialize_change_request_comment_artifact,
    serialize_review_artifact,
    serialize_review_comment_artifact,
    snapshot_identity,
    validate_change_request_artifact,
    validate_change_request_comment_artifact,
    validate_review_artifact,
    validate_review_comment_artifact,
)
from metabrowser.builtin_plugins.hosted_review.models import (
    dump_change_request,
    dump_change_request_comment,
    dump_review,
    dump_review_comment,
    validate_change_request,
    validate_change_request_comment,
    validate_review,
    validate_review_comment,
)


def _provider_ref(object_kind: str, opaque_id: str) -> dict[str, str]:
    return {
        "provider": "forge",
        "instance": "code.example",
        "object_kind": object_kind,
        "opaque_id": opaque_id,
    }


def _repository_ref() -> dict[str, str]:
    return {
        "provider": "forge",
        "instance": "code.example",
        "opaque_id": "repo-1",
    }


def _actor_ref() -> dict[str, str]:
    return {
        "provider_opaque_id": "person-4",
        "handle": "reviewer",
        "url": "https://code.example/reviewer",
    }


def _change_request_comment_case() -> dict[str, object]:
    return {
        "id": "forge:code.example:comment-8",
        "provider_ref": _provider_ref("change_request_comment", "comment-8"),
        "repository": _repository_ref(),
        "change_request_id": "forge:code.example:repo-1:merge-request:17",
        "url": "https://code.example/teams/project/changes/17#comment-8",
        "author": _actor_ref(),
        "state": "visible",
        "created_at": "2026-09-10T14:00:00Z",
        "updated_at": "2026-09-10T14:30:00Z",
    }


def _review_case() -> dict[str, object]:
    return {
        "id": "forge:code.example:review-3",
        "provider_ref": _provider_ref("review", "review-3"),
        "repository": _repository_ref(),
        "change_request_id": "forge:code.example:repo-1:merge-request:17",
        "url": "https://code.example/teams/project/changes/17#review-3",
        "author": _actor_ref(),
        "disposition": "approved",
        "revision": {
            "repository_id": "repo-2",
            "oid": "89abcdef0123456789abcdef0123456789abcdef",
            "availability": "present",
        },
        "created_at": "2026-09-10T15:00:00Z",
        "updated_at": "2026-09-10T15:30:00Z",
        "submitted_at": "2026-09-10T15:30:00Z",
    }


def _review_comment_case() -> dict[str, object]:
    return {
        "id": "forge:code.example:review-comment-5",
        "provider_ref": _provider_ref("review_comment", "review-comment-5"),
        "repository": _repository_ref(),
        "change_request_id": "forge:code.example:repo-1:merge-request:17",
        "review_id": "forge:code.example:review-3",
        "thread_id": "forge:code.example:review-thread-2",
        "in_reply_to_id": None,
        "url": "https://code.example/teams/project/changes/17#review-comment-5",
        "author": _actor_ref(),
        "state": "visible",
        "created_at": "2026-09-10T15:10:00Z",
        "updated_at": "2026-09-10T15:20:00Z",
        "anchor": {
            "kind": "file",
            "path": "src/example.py",
            "path_b64": None,
            "comparison": {
                "base": {
                    "repository_id": "repo-1",
                    "ref": "main",
                    "oid": "0123456789abcdef0123456789abcdef01234567",
                    "availability": "present",
                },
                "head": {
                    "repository_id": "repo-2",
                    "ref": "topic/provider-neutral",
                    "oid": "89abcdef0123456789abcdef0123456789abcdef",
                    "availability": "present",
                },
                "merge_commit_oid": None,
                "merge_commit_availability": "not_requested",
            },
            "original_revision": {
                "repository_id": "repo-2",
                "oid": "89abcdef0123456789abcdef0123456789abcdef",
                "availability": "present",
            },
            "current_revision": {
                "repository_id": "repo-2",
                "oid": "89abcdef0123456789abcdef0123456789abcdef",
                "availability": "present",
            },
            "state": "current",
        },
    }


def test_frontmatter_artifact_round_trip_preserves_nulls_collections_and_body() -> None:
    model = validate_change_request(change_request_case())
    record = dump_change_request(model)
    body = "A provider-authored description.\n\n- Kept as Markdown\n"

    payload = serialize_change_request_artifact(record=model, body=body)
    parsed = parse_frontmatter_artifact(payload)

    assert parsed.contract_id == CHANGE_REQUEST_CONTRACT_ID
    assert parsed.envelope == "change_request"
    assert parsed.status == "enforced"
    assert parsed.record == record
    assert parsed.body == body
    assert b"closed_at: null\n" in payload
    assert b"labels: []\n" in payload
    assert (
        serialize_change_request_artifact(
            record=validate_change_request(parsed.record), body=parsed.body
        )
        == payload
    )
    assert snapshot_identity(payload) != snapshot_identity(payload + b"more\n")
    assert snapshot_identity(payload) == f"sha256:{hashlib.sha256(payload).hexdigest()}"


def test_change_request_validation_never_recovers_fields_from_markdown() -> None:
    payload = serialize_change_request_artifact(
        record=validate_change_request(change_request_case()),
        body="# title: This heading is not machine data\n",
    )
    payload = payload.replace(b"  title: Keep hosted changes provider neutral\n", b"")

    with pytest.raises(ValidationError, match="title"):
        validate_change_request_artifact(payload)


def test_change_request_artifact_preserves_an_empty_provider_description() -> None:
    model = validate_change_request(change_request_case())
    record = dump_change_request(model)
    payload = serialize_change_request_artifact(record=model, body="")

    parsed = validate_change_request_artifact(payload)

    assert parsed.body == ""
    assert dump_change_request(parsed.record) == record


def test_change_request_comment_artifact_round_trip_preserves_opaque_markdown() -> None:
    model = validate_change_request_comment(_change_request_comment_case())
    body = "Keep this as prose.\n\n---\nsoftschema: not metadata here\n"

    payload = serialize_change_request_comment_artifact(record=model, body=body)
    parsed = validate_change_request_comment_artifact(payload)

    assert parse_frontmatter_artifact(payload).contract_id == CHANGE_REQUEST_COMMENT_CONTRACT_ID
    assert dump_change_request_comment(parsed.record) == dump_change_request_comment(model)
    assert parsed.body == body
    assert (
        serialize_change_request_comment_artifact(record=parsed.record, body=parsed.body) == payload
    )


def test_review_artifact_round_trip_preserves_an_empty_summary() -> None:
    model = validate_review(_review_case())

    payload = serialize_review_artifact(record=model, body="")
    parsed = validate_review_artifact(payload)

    assert parse_frontmatter_artifact(payload).contract_id == REVIEW_CONTRACT_ID
    assert dump_review(parsed.record) == dump_review(model)
    assert parsed.body == ""
    assert serialize_review_artifact(record=parsed.record, body=parsed.body) == payload


def test_review_comment_artifact_round_trip_preserves_anchor_and_markdown() -> None:
    model = validate_review_comment(_review_comment_case())
    body = "The null check should happen before dereferencing `result`.\n"

    payload = serialize_review_comment_artifact(record=model, body=body)
    parsed = validate_review_comment_artifact(payload)

    assert parse_frontmatter_artifact(payload).contract_id == REVIEW_COMMENT_CONTRACT_ID
    assert dump_review_comment(parsed.record) == dump_review_comment(model)
    assert parsed.body == body
    assert serialize_review_comment_artifact(record=parsed.record, body=parsed.body) == payload


def test_typed_artifact_validation_rejects_another_artifact_kind() -> None:
    payload = serialize_review_artifact(record=validate_review(_review_case()), body="")

    with pytest.raises(FmFormatError, match="unsupported hosted-review contract"):
        validate_change_request_comment_artifact(payload)

    wrong_envelope = payload.replace(
        REVIEW_CONTRACT_ID.encode(), CHANGE_REQUEST_COMMENT_CONTRACT_ID.encode(), 1
    )
    with pytest.raises(FmFormatError, match="require the change_request_comment envelope"):
        validate_change_request_comment_artifact(wrong_envelope)


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (b"plain Markdown\n", "missing YAML frontmatter"),
        (b"---\nsoftschema: {}\n", "no closing frontmatter delimiter"),
        (
            b"---\nsoftschema:\n  contract: example\n  envelope: item\n  status: permissive\nitem: {}\n---\n",
            "must use enforced contracts",
        ),
        (
            b"---\nsoftschema:\n  contract: example\n  envelope: item\n  status: enforced\nitem: {}\nother: {}\n---\n",
            "only softschema",
        ),
        (b"\xff", "must be UTF-8"),
    ],
)
def test_frontmatter_artifact_rejects_invalid_envelopes(payload: bytes, message: str) -> None:
    with pytest.raises(FmFormatError, match=message):
        parse_frontmatter_artifact(payload)


def test_change_request_artifact_rejects_an_unknown_contract() -> None:
    payload = serialize_change_request_artifact(
        record=validate_change_request(change_request_case()), body=""
    )
    payload = payload.replace(
        CHANGE_REQUEST_CONTRACT_ID.encode(), b"example.invalid:ChangeRequest/v1"
    )

    with pytest.raises(FmFormatError, match="unsupported hosted-review contract"):
        validate_change_request_artifact(payload)


def test_frontmatter_serialization_is_independent_of_input_mapping_order() -> None:
    record = change_request_case()
    reverse_order = dict(reversed(record.items()))

    expected = serialize_change_request_artifact(
        record=validate_change_request(record), body="body\n"
    )
    actual = serialize_change_request_artifact(
        record=validate_change_request(reverse_order), body="body\n"
    )

    assert actual == expected
