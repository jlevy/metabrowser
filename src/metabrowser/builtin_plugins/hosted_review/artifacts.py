"""Deterministic frontmatter codecs for hosted-review artifacts.

The provider store will own filesystem publication and locking. These helpers only
translate validated records and opaque Markdown bodies to and from canonical bytes.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from io import StringIO
from typing import Any

from frontmatter_format import FmFormatError, FmStyle, from_yaml_string, new_yaml
from ruamel.yaml.error import YAMLError

from metabrowser.builtin_plugins.hosted_review.models import (
    CHANGE_REQUEST_COMMENT_CONTRACT_ID,
    CHANGE_REQUEST_CONTRACT_ID,
    REVIEW_COMMENT_CONTRACT_ID,
    REVIEW_CONTRACT_ID,
    ChangeRequest,
    ChangeRequestComment,
    Review,
    ReviewComment,
    dump_change_request,
    dump_change_request_comment,
    dump_review,
    dump_review_comment,
    validate_change_request,
    validate_change_request_comment,
    validate_review,
    validate_review_comment,
)

ENFORCED_STATUS = "enforced"


@dataclass(frozen=True)
class FrontmatterArtifact:
    contract_id: str
    envelope: str
    status: str
    record: dict[str, Any]
    body: str


@dataclass(frozen=True)
class ChangeRequestArtifact:
    record: ChangeRequest
    body: str


@dataclass(frozen=True)
class ChangeRequestCommentArtifact:
    record: ChangeRequestComment
    body: str


@dataclass(frozen=True)
class ReviewArtifact:
    record: Review
    body: str


@dataclass(frozen=True)
class ReviewCommentArtifact:
    record: ReviewComment
    body: str


def _canonical_yaml(value: dict[str, Any]) -> str:
    stream = StringIO()
    yaml = new_yaml(suppress_vals=lambda _value: False, typ="safe")
    yaml.dump(value, stream)
    return stream.getvalue()


def _serialize_frontmatter_artifact(
    *,
    contract_id: str,
    envelope: str,
    record: dict[str, Any],
    body: str,
) -> bytes:
    """Serialize a caller-validated artifact without performing filesystem publication."""
    if not contract_id or not envelope:
        raise ValueError("contract_id and envelope must be nonempty")
    metadata = {
        "softschema": {
            "contract": contract_id,
            "envelope": envelope,
            "status": ENFORCED_STATUS,
        },
        envelope: record,
    }
    yaml_text = _canonical_yaml(metadata)
    text = f"{FmStyle.yaml.start}\n{yaml_text}{FmStyle.yaml.end}\n{body}"
    return text.encode("utf-8")


def serialize_change_request_artifact(*, record: ChangeRequest, body: str) -> bytes:
    """Serialize one validated ChangeRequest and its opaque Markdown description."""
    return _serialize_frontmatter_artifact(
        contract_id=CHANGE_REQUEST_CONTRACT_ID,
        envelope="change_request",
        record=dump_change_request(record),
        body=body,
    )


def serialize_change_request_comment_artifact(*, record: ChangeRequestComment, body: str) -> bytes:
    """Serialize one validated top-level comment and its opaque Markdown body."""
    return _serialize_frontmatter_artifact(
        contract_id=CHANGE_REQUEST_COMMENT_CONTRACT_ID,
        envelope="change_request_comment",
        record=dump_change_request_comment(record),
        body=body,
    )


def serialize_review_artifact(*, record: Review, body: str) -> bytes:
    """Serialize one validated review and its optional opaque Markdown summary."""
    return _serialize_frontmatter_artifact(
        contract_id=REVIEW_CONTRACT_ID,
        envelope="review",
        record=dump_review(record),
        body=body,
    )


def serialize_review_comment_artifact(*, record: ReviewComment, body: str) -> bytes:
    """Serialize one validated review comment and its opaque Markdown body."""
    return _serialize_frontmatter_artifact(
        contract_id=REVIEW_COMMENT_CONTRACT_ID,
        envelope="review_comment",
        record=dump_review_comment(record),
        body=body,
    )


def parse_frontmatter_artifact(payload: bytes) -> FrontmatterArtifact:
    """Parse one canonical frontmatter artifact and validate its format envelope."""
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise FmFormatError("hosted-review artifacts must be UTF-8") from exc

    start = f"{FmStyle.yaml.start}\n"
    end = f"\n{FmStyle.yaml.end}\n"
    if not text.startswith(start):
        raise FmFormatError("hosted-review artifact is missing YAML frontmatter")
    end_index = text.find(end, len(start))
    if end_index < 0:
        raise FmFormatError("hosted-review artifact has no closing frontmatter delimiter")

    try:
        metadata = from_yaml_string(text[len(start) : end_index + 1])
    except YAMLError as exc:
        raise FmFormatError("hosted-review artifact has malformed YAML frontmatter") from exc
    if not isinstance(metadata, dict):
        raise FmFormatError("hosted-review frontmatter must be a mapping")

    softschema = metadata.get("softschema")
    if not isinstance(softschema, dict) or set(softschema) != {
        "contract",
        "envelope",
        "status",
    }:
        raise FmFormatError("softschema metadata must contain contract, envelope, and status")
    contract_id = softschema.get("contract")
    envelope = softschema.get("envelope")
    status = softschema.get("status")
    if not isinstance(contract_id, str) or not contract_id:
        raise FmFormatError("softschema contract must be a nonempty string")
    if not isinstance(envelope, str) or not envelope:
        raise FmFormatError("softschema envelope must be a nonempty string")
    if status != ENFORCED_STATUS:
        raise FmFormatError("hosted-review artifacts must use enforced contracts")
    if set(metadata) != {"softschema", envelope}:
        raise FmFormatError("frontmatter must contain only softschema and its declared envelope")
    record = metadata.get(envelope)
    if not isinstance(record, dict):
        raise FmFormatError("the declared frontmatter envelope must contain a mapping")

    return FrontmatterArtifact(
        contract_id=contract_id,
        envelope=envelope,
        status=status,
        record=record,
        body=text[end_index + len(end) :],
    )


def snapshot_identity(payload: bytes) -> str:
    """Return a self-describing digest of the complete canonical artifact bytes."""
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _validate_frontmatter_artifact_identity(
    payload: bytes,
    *,
    contract_id: str,
    envelope: str,
    artifact_name: str,
) -> FrontmatterArtifact:
    artifact = parse_frontmatter_artifact(payload)
    if artifact.contract_id != contract_id:
        raise FmFormatError(f"unsupported hosted-review contract: {artifact.contract_id}")
    if artifact.envelope != envelope:
        raise FmFormatError(f"{artifact_name} artifacts require the {envelope} envelope")
    return artifact


def _require_canonical_serialization(payload: bytes, canonical: bytes, artifact_name: str) -> None:
    """Refuse any byte spelling of a record other than the one the serializer writes.

    ``snapshot_identity`` hashes bytes, so a record that also validated with a comment,
    alternate quoting, reordered keys, or a YAML tag would have several identities.
    """
    if payload != canonical:
        raise FmFormatError(f"{artifact_name} artifact is not in its canonical serialization")


def validate_change_request_artifact(payload: bytes) -> ChangeRequestArtifact:
    """Validate the installed ChangeRequest artifact identity and its YAML record."""
    artifact = _validate_frontmatter_artifact_identity(
        payload,
        contract_id=CHANGE_REQUEST_CONTRACT_ID,
        envelope="change_request",
        artifact_name="ChangeRequest",
    )
    record = validate_change_request(artifact.record)
    _require_canonical_serialization(
        payload,
        serialize_change_request_artifact(record=record, body=artifact.body),
        "ChangeRequest",
    )
    return ChangeRequestArtifact(record=record, body=artifact.body)


def validate_change_request_comment_artifact(
    payload: bytes,
) -> ChangeRequestCommentArtifact:
    """Validate one ChangeRequestComment artifact and preserve its Markdown body."""
    artifact = _validate_frontmatter_artifact_identity(
        payload,
        contract_id=CHANGE_REQUEST_COMMENT_CONTRACT_ID,
        envelope="change_request_comment",
        artifact_name="ChangeRequestComment",
    )
    record = validate_change_request_comment(artifact.record)
    _require_canonical_serialization(
        payload,
        serialize_change_request_comment_artifact(record=record, body=artifact.body),
        "ChangeRequestComment",
    )
    return ChangeRequestCommentArtifact(record=record, body=artifact.body)


def validate_review_artifact(payload: bytes) -> ReviewArtifact:
    """Validate one Review artifact and preserve its optional Markdown summary."""
    artifact = _validate_frontmatter_artifact_identity(
        payload,
        contract_id=REVIEW_CONTRACT_ID,
        envelope="review",
        artifact_name="Review",
    )
    record = validate_review(artifact.record)
    _require_canonical_serialization(
        payload, serialize_review_artifact(record=record, body=artifact.body), "Review"
    )
    return ReviewArtifact(record=record, body=artifact.body)


def validate_review_comment_artifact(payload: bytes) -> ReviewCommentArtifact:
    """Validate one ReviewComment artifact and preserve its Markdown body."""
    artifact = _validate_frontmatter_artifact_identity(
        payload,
        contract_id=REVIEW_COMMENT_CONTRACT_ID,
        envelope="review_comment",
        artifact_name="ReviewComment",
    )
    record = validate_review_comment(artifact.record)
    _require_canonical_serialization(
        payload,
        serialize_review_comment_artifact(record=record, body=artifact.body),
        "ReviewComment",
    )
    return ReviewCommentArtifact(record=record, body=artifact.body)
