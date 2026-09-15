from __future__ import annotations

import hashlib

import pytest
from frontmatter_format import FmFormatError
from hosted_review_cases import change_request_case
from pydantic import ValidationError

from metabrowser.builtin_plugins.hosted_review.artifacts import (
    CHANGE_REQUEST_CONTRACT_ID,
    parse_frontmatter_artifact,
    serialize_change_request_artifact,
    snapshot_identity,
    validate_change_request_artifact,
)
from metabrowser.builtin_plugins.hosted_review.models import (
    dump_change_request,
    validate_change_request,
)


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
