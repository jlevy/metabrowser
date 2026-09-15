"""Closed provider-neutral models for hosted change requests."""

from __future__ import annotations

import re
from datetime import datetime
from enum import StrEnum
from math import isfinite
from typing import Annotated, Any

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StrictBool,
    field_validator,
    model_validator,
)

NonEmptyString = Annotated[str, Field(min_length=1)]
GitObjectId = Annotated[str, Field(pattern=r"^[0-9a-f]{40,64}$")]
MAX_SAFE_INTEGER = 9_007_199_254_740_991
MAX_PORT = 65_535
DEFAULT_HTTPS_PORT = 443
_HOST_LABEL = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
_CANONICAL_HTTPS_RE = re.compile(
    rf"^https://(?P<host>{_HOST_LABEL}(?:\.{_HOST_LABEL})*)"
    r"(?::(?P<port>[1-9][0-9]{0,4}))?"
    r"(?P<tail>(?:[/?#][A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]*)?)$"
)
_NONCANONICAL_PERCENT_RE = re.compile(r"%(?![0-9A-F]{2})")
_RFC3339_UTC_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.(?P<milliseconds>\d{3}))?Z$"
)


def _parse_json_integer(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError("value must be an integral JSON number")
    if isinstance(value, float):
        if not isfinite(value) or not value.is_integer():
            raise ValueError("value must be an integral JSON number")
        return int(value)
    return value


SafeNonNegativeInteger = Annotated[
    int,
    BeforeValidator(_parse_json_integer),
    Field(ge=0, le=MAX_SAFE_INTEGER),
]
SafePositiveInteger = Annotated[
    int,
    BeforeValidator(_parse_json_integer),
    Field(ge=1, le=MAX_SAFE_INTEGER),
]


class ChangeRequestState(StrEnum):
    open = "open"
    closed = "closed"
    merged = "merged"
    unknown = "unknown"


class RevisionAvailability(StrEnum):
    present = "present"
    unavailable = "unavailable"
    not_requested = "not_requested"


class ReviewDecision(StrEnum):
    required = "required"
    approved = "approved"
    changes_requested = "changes_requested"
    not_requested = "not_requested"
    unknown = "unknown"


class _HostedReviewModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _require_https_url(value: str) -> str:
    match = _CANONICAL_HTTPS_RE.fullmatch(value)
    if match is None:
        raise ValueError("provider URLs must be credential-free HTTPS URLs")
    port_text = match.group("port")
    if port_text is not None:
        port = int(port_text)
        if port == DEFAULT_HTTPS_PORT or port > MAX_PORT:
            raise ValueError("provider URLs must be credential-free HTTPS URLs")
    if _NONCANONICAL_PERCENT_RE.search(match.group("tail")) is not None:
        raise ValueError("provider URLs must be credential-free HTTPS URLs")
    return value


def _parse_rfc3339(value: str) -> datetime:
    match = _RFC3339_UTC_RE.fullmatch(value)
    if match is None or match.group("milliseconds") == "000":
        raise ValueError("timestamps must use canonical RFC 3339 UTC syntax")
    try:
        return datetime.fromisoformat(value.removesuffix("Z") + "+00:00")
    except ValueError as exc:
        raise ValueError("timestamps must use canonical RFC 3339 UTC syntax") from exc


class ProviderObjectRef(_HostedReviewModel):
    provider: NonEmptyString
    instance: NonEmptyString
    object_kind: NonEmptyString
    opaque_id: NonEmptyString


class RepositoryRef(_HostedReviewModel):
    provider: NonEmptyString
    instance: NonEmptyString
    opaque_id: NonEmptyString


class ActorRef(_HostedReviewModel):
    provider_opaque_id: NonEmptyString
    handle: NonEmptyString
    url: NonEmptyString

    _https_url = field_validator("url")(_require_https_url)


class RevisionRef(_HostedReviewModel):
    repository_id: NonEmptyString
    ref: NonEmptyString
    oid: GitObjectId | None
    availability: RevisionAvailability

    @model_validator(mode="after")
    def _oid_matches_availability(self) -> RevisionRef:
        if (self.oid is not None) != (self.availability is RevisionAvailability.present):
            raise ValueError("oid is present exactly when revision availability is present")
        return self


class ComparisonRef(_HostedReviewModel):
    base: RevisionRef
    head: RevisionRef
    merge_commit_oid: GitObjectId | None
    merge_commit_availability: RevisionAvailability

    @model_validator(mode="after")
    def _merge_oid_matches_availability(self) -> ComparisonRef:
        if (self.merge_commit_oid is not None) != (
            self.merge_commit_availability is RevisionAvailability.present
        ):
            raise ValueError(
                "merge_commit_oid is present exactly when merge commit availability is present"
            )
        return self


class LabelRef(_HostedReviewModel):
    name: NonEmptyString
    color: str | None = Field(default=None, pattern=r"^[0-9a-fA-F]{6}$")


class MilestoneRef(_HostedReviewModel):
    provider_opaque_id: NonEmptyString
    title: NonEmptyString
    url: NonEmptyString

    _https_url = field_validator("url")(_require_https_url)


class ReviewSummary(_HostedReviewModel):
    decision: ReviewDecision
    requested_people: tuple[ActorRef, ...]
    requested_teams: tuple[NonEmptyString, ...]


class ChangeRequestCounts(_HostedReviewModel):
    commits: SafeNonNegativeInteger
    discussion_comments: SafeNonNegativeInteger
    reviews: SafeNonNegativeInteger


class ChangeRequest(_HostedReviewModel):
    id: NonEmptyString
    provider_ref: ProviderObjectRef
    repository: RepositoryRef
    number: SafePositiveInteger
    url: NonEmptyString
    title: NonEmptyString
    author: ActorRef
    state: ChangeRequestState
    draft: StrictBool
    locked: StrictBool
    created_at: NonEmptyString
    updated_at: NonEmptyString
    closed_at: NonEmptyString | None
    merged_at: NonEmptyString | None
    comparison: ComparisonRef
    labels: tuple[LabelRef, ...]
    assignees: tuple[ActorRef, ...]
    milestone: MilestoneRef | None
    review: ReviewSummary
    counts: ChangeRequestCounts

    _https_url = field_validator("url")(_require_https_url)

    @field_validator("created_at", "updated_at", "closed_at", "merged_at")
    @classmethod
    def _rfc3339_timestamp(cls, value: str | None) -> str | None:
        if value is not None:
            _parse_rfc3339(value)
        return value

    @model_validator(mode="after")
    def _relationships_and_lifecycle(self) -> ChangeRequest:
        provider = self.provider_ref
        repository = self.repository
        if (provider.provider, provider.instance) != (repository.provider, repository.instance):
            raise ValueError("provider object and repository must use the same provider instance")
        if self.comparison.base.repository_id != repository.opaque_id:
            raise ValueError("comparison base must belong to the change request repository")

        created_at = _parse_rfc3339(self.created_at)
        updated_at = _parse_rfc3339(self.updated_at)
        if updated_at < created_at:
            raise ValueError("updated_at must not precede created_at")
        for name, value in (("closed_at", self.closed_at), ("merged_at", self.merged_at)):
            if value is None:
                continue
            observed_at = _parse_rfc3339(value)
            if observed_at < created_at:
                raise ValueError(f"{name} must not precede created_at")
            if observed_at > updated_at:
                raise ValueError(f"{name} must not follow updated_at")
        if self.state is ChangeRequestState.open:
            if self.closed_at is not None or self.merged_at is not None:
                raise ValueError("open change requests have no closed or merged timestamp")
        elif self.state is ChangeRequestState.closed:
            if self.closed_at is None or self.merged_at is not None:
                raise ValueError("closed change requests require closed_at and forbid merged_at")
        elif self.state is ChangeRequestState.merged and (
            self.closed_at is None or self.merged_at is None
        ):
            raise ValueError("merged change requests require closed_at and merged_at")
        return self


def validate_change_request(value: dict[str, Any]) -> ChangeRequest:
    """Parse one normalized change request or raise a Pydantic validation error."""
    return ChangeRequest.model_validate(value)


def dump_change_request(value: ChangeRequest) -> dict[str, Any]:
    """Return the deterministic JSON-compatible projection, including explicit nulls."""
    return value.model_dump(mode="json")
