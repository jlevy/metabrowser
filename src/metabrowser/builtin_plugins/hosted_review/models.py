"""Closed provider-neutral models for hosted resources."""

from __future__ import annotations

import hashlib
import json
import re
from base64 import b64decode, b64encode
from binascii import Error as BinasciiError
from collections.abc import Mapping
from datetime import datetime
from enum import StrEnum
from math import isfinite
from typing import Annotated, Any, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StrictBool,
    field_validator,
    model_validator,
)

from metabrowser.provider_resources.profiles import (
    CollectionPaginationPolicy,
    ResourceProfileSpec,
    ResourceTargetClass,
)
from metabrowser.provider_resources.profiles import (
    ResourceCollectionSpec as ResourceCollectionSpec,
)

NonEmptyString = Annotated[str, Field(min_length=1)]
GitObjectId = Annotated[str, Field(pattern=r"^[0-9a-f]{40,64}$")]
StableToken = Annotated[str, Field(pattern=r"^[a-z][a-z0-9._:-]*$")]
MAX_SAFE_INTEGER = 9_007_199_254_740_991
MAX_PORT = 65_535
DEFAULT_HTTPS_PORT = 443
MAX_PROVIDER_KIND_LENGTH = 63
MAX_DNS_HOST_LENGTH = 253
MAX_OPAQUE_CURSOR_LENGTH = 4096
_HOST_LABEL = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
_PROVIDER_KIND_RE = re.compile(r"^[a-z][a-z0-9-]*$")
_STABLE_TOKEN_RE = re.compile(r"^[a-z][a-z0-9._:-]*$")
_CONTRACT_ID_RE = re.compile(r"^[a-z][a-z0-9.-]*:[A-Za-z][A-Za-z0-9._-]*/v[1-9][0-9]*$")
_RESOURCE_PROFILE_ID_RE = re.compile(r"^[a-z][a-z0-9.-]*:[a-z][a-z0-9-]*/v[1-9][0-9]*$")
_OPAQUE_CURSOR_RE = re.compile(r"^[A-Za-z0-9._~+=:-]+$")
_URI_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
_PROVIDER_INSTANCE_RE = re.compile(
    rf"^(?P<host>{_HOST_LABEL}(?:\.{_HOST_LABEL})*)"
    r"(?::(?P<port>[1-9][0-9]{0,4}))?$"
)
_CANONICAL_HTTPS_RE = re.compile(
    rf"^https://(?P<host>{_HOST_LABEL}(?:\.{_HOST_LABEL})*)"
    r"(?::(?P<port>[1-9][0-9]{0,4}))?"
    r"(?P<tail>(?:[/?#][A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]*)?)$"
)
_NONCANONICAL_PERCENT_RE = re.compile(r"%(?![0-9A-F]{2})")
_RFC3339_UTC_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.(?P<milliseconds>\d{3}))?Z$"
)


def _runtime_descriptor_value(value: object) -> object:
    """Erase static descriptor types so trusted registry declarations are checked at runtime."""
    return value


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
    Field(ge=0, le=MAX_SAFE_INTEGER),
    BeforeValidator(_parse_json_integer),
]
SafePositiveInteger = Annotated[
    int,
    Field(ge=1, le=MAX_SAFE_INTEGER),
    BeforeValidator(_parse_json_integer),
]


class ChangeRequestState(StrEnum):
    open = "open"
    closed = "closed"
    merged = "merged"
    unknown = "unknown"


# What the provider reported about one Git object ID. Local repository-store state is the
# separate LocalObjectAvailability vocabulary and never enters a provider record.
class RevisionObservation(StrEnum):
    observed = "observed"
    unavailable = "unavailable"
    not_requested = "not_requested"


class ReviewDecision(StrEnum):
    required = "required"
    approved = "approved"
    changes_requested = "changes_requested"
    not_requested = "not_requested"
    unknown = "unknown"


class CommentState(StrEnum):
    visible = "visible"
    minimized = "minimized"
    deleted = "deleted"
    unknown = "unknown"


class ReviewDisposition(StrEnum):
    pending = "pending"
    commented = "commented"
    approved = "approved"
    changes_requested = "changes_requested"
    dismissed = "dismissed"
    unknown = "unknown"


class ReviewThreadState(StrEnum):
    unresolved = "unresolved"
    resolved = "resolved"
    unknown = "unknown"


class ReviewAnchorState(StrEnum):
    current = "current"
    outdated = "outdated"
    unresolved = "unresolved"
    unmappable = "unmappable"


class ReviewSide(StrEnum):
    base = "base"
    head = "head"


class CheckKind(StrEnum):
    suite = "suite"
    run = "run"
    unknown = "unknown"


class CheckStatus(StrEnum):
    queued = "queued"
    in_progress = "in_progress"
    completed = "completed"
    waiting = "waiting"
    requested = "requested"
    pending = "pending"
    unknown = "unknown"


class CheckConclusion(StrEnum):
    action_required = "action_required"
    cancelled = "cancelled"
    failure = "failure"
    neutral = "neutral"
    skipped = "skipped"
    stale = "stale"
    startup_failure = "startup_failure"
    success = "success"
    timed_out = "timed_out"
    unknown = "unknown"


class CommitStatusState(StrEnum):
    error = "error"
    failure = "failure"
    pending = "pending"
    success = "success"
    unknown = "unknown"


class ActivityKind(StrEnum):
    commit = "commit"
    change_request = "change_request"


class ActivityState(StrEnum):
    open = "open"
    draft = "draft"
    closed = "closed"
    merged = "merged"
    unknown = "unknown"


class ActivityCoverage(StrEnum):
    complete = "complete"
    partial = "partial"


class _HostedReviewModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _require_https_url(value: str) -> str:
    match = _CANONICAL_HTTPS_RE.fullmatch(value)
    if match is None or len(match.group("host")) > MAX_DNS_HOST_LENGTH:
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


def _require_provider_kind(value: str) -> str:
    if len(value) > MAX_PROVIDER_KIND_LENGTH or _PROVIDER_KIND_RE.fullmatch(value) is None:
        raise ValueError("provider kind must be a bounded lowercase ASCII token")
    return value


def _require_provider_instance(value: str) -> str:
    match = _PROVIDER_INSTANCE_RE.fullmatch(value)
    if match is None or len(match.group("host")) > MAX_DNS_HOST_LENGTH:
        raise ValueError("provider instance must be a canonical lowercase DNS host[:port]")
    port_text = match.group("port")
    if port_text is not None:
        port = int(port_text)
        if port == DEFAULT_HTTPS_PORT or port > MAX_PORT:
            raise ValueError("provider instance must use a valid nondefault port")
    return value


def _require_sha256_digest(value: str) -> str:
    if re.fullmatch(r"sha256:[0-9a-f]{64}", value) is None:
        raise ValueError("value must be a lowercase sha256 digest")
    return value


def _require_timestamp(value: str) -> str:
    _parse_rfc3339(value)
    return value


def _require_https(value: str) -> str:
    return _require_https_url(value)


def _require_resource_profile_id(value: str) -> str:
    if _RESOURCE_PROFILE_ID_RE.fullmatch(value) is None:
        raise ValueError("resource profile ID must be namespaced and versioned")
    return value


def _require_contract_id(value: str) -> str:
    if _CONTRACT_ID_RE.fullmatch(value) is None:
        raise ValueError("contract ID must be namespaced and versioned")
    return value


def _canonical_json_bytes(value: object) -> bytes:
    try:
        serialized = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        )
        return serialized.encode("utf-8", errors="strict")
    except (UnicodeEncodeError, ValueError) as exc:
        raise ValueError(
            "hash inputs must be canonical UTF-8 JSON without lone surrogates"
        ) from exc


def _sha256_json_key(value: object) -> str:
    return f"sha256:{hashlib.sha256(_canonical_json_bytes(value)).hexdigest()}"


def _utf8_sort_key(value: str) -> bytes:
    try:
        return value.encode("utf-8", errors="strict")
    except UnicodeEncodeError as exc:
        raise ValueError("ordered identifiers must be valid UTF-8") from exc


type ProviderKind = Annotated[str, AfterValidator(_require_provider_kind)]
type ProviderInstance = Annotated[str, AfterValidator(_require_provider_instance)]
type Sha256Digest = Annotated[str, AfterValidator(_require_sha256_digest)]
type CanonicalTimestamp = Annotated[str, AfterValidator(_require_timestamp)]
type CanonicalHttpsUrl = Annotated[str, AfterValidator(_require_https)]
type ResourceProfileId = Annotated[str, AfterValidator(_require_resource_profile_id)]
type ContractId = Annotated[str, AfterValidator(_require_contract_id)]

PROVIDER_BINDING_CONTRACT_ID = "com.github.jlevy.metabrowser.provider:ProviderBinding/v1"
RETRIEVAL_CONTRACT_ID = "com.github.jlevy.metabrowser.provider:Retrieval/v1"
RESOURCE_SET_CONTRACT_ID = "com.github.jlevy.metabrowser.provider:ResourceSet/v1"
PROVIDER_SYNC_MANIFEST_CONTRACT_ID = "com.github.jlevy.metabrowser.provider:ProviderSyncManifest/v1"
PROVIDER_VIEW_POINTER_CONTRACT_ID = "com.github.jlevy.metabrowser.provider:ProviderViewPointer/v1"
TOMBSTONE_CONTRACT_ID = "com.github.jlevy.metabrowser.provider:Tombstone/v1"
HOSTED_REPOSITORY_CONTRACT_ID = "com.github.jlevy.metabrowser.provider:HostedRepository/v1"
CHANGE_REQUEST_INDEX_CONTRACT_ID = "com.github.jlevy.metabrowser.review:ChangeRequestIndex/v1"
CHANGE_REQUEST_CONTRACT_ID = "com.github.jlevy.metabrowser.review:ChangeRequest/v1"
CHANGE_REQUEST_COMMENT_CONTRACT_ID = "com.github.jlevy.metabrowser.review:ChangeRequestComment/v1"
REVIEW_CONTRACT_ID = "com.github.jlevy.metabrowser.review:Review/v1"
REVIEW_THREAD_CONTRACT_ID = "com.github.jlevy.metabrowser.review:ReviewThread/v1"
REVIEW_COMMENT_CONTRACT_ID = "com.github.jlevy.metabrowser.review:ReviewComment/v1"
CHECK_CONTRACT_ID = "com.github.jlevy.metabrowser.review:Check/v1"
COMMIT_STATUS_CONTRACT_ID = "com.github.jlevy.metabrowser.review:CommitStatus/v1"
REPOSITORY_ACTIVITY_CONTRACT_ID = "com.github.jlevy.metabrowser.activity:RepositoryActivity/v1"
REPOSITORY_SUMMARY_PROFILE_ID = "com.github.jlevy.metabrowser.provider:repository-summary/v1"
CHANGE_REQUEST_INDEX_PROFILE_ID = "com.github.jlevy.metabrowser.review:change-request-index/v1"


class ProviderObjectRef(_HostedReviewModel):
    provider: ProviderKind
    instance: ProviderInstance
    object_kind: NonEmptyString
    opaque_id: NonEmptyString


class RepositoryRef(_HostedReviewModel):
    provider: ProviderKind
    instance: ProviderInstance
    opaque_id: NonEmptyString


class ActorRef(_HostedReviewModel):
    provider_opaque_id: NonEmptyString
    handle: NonEmptyString
    url: NonEmptyString

    _https_url = field_validator("url")(_require_https_url)


class RevisionRef(_HostedReviewModel):
    repository_id: NonEmptyString | None
    ref: NonEmptyString
    oid: GitObjectId | None
    observation: RevisionObservation

    @model_validator(mode="after")
    def _oid_matches_observation(self) -> RevisionRef:
        if (self.oid is not None) != (self.observation is RevisionObservation.observed):
            raise ValueError("oid is present exactly when the provider observed the revision")
        return self


class ComparisonRef(_HostedReviewModel):
    base: RevisionRef
    head: RevisionRef
    merge_commit_oid: GitObjectId | None
    merge_commit_observation: RevisionObservation

    @model_validator(mode="after")
    def _merge_oid_matches_observation(self) -> ComparisonRef:
        if (self.merge_commit_oid is not None) != (
            self.merge_commit_observation is RevisionObservation.observed
        ):
            raise ValueError(
                "merge_commit_oid is present exactly when the provider observed the merge commit"
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
    author: ActorRef | None
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


class GitObjectRef(_HostedReviewModel):
    repository_id: NonEmptyString | None
    oid: GitObjectId | None
    observation: RevisionObservation

    @model_validator(mode="after")
    def _oid_matches_observation(self) -> GitObjectRef:
        if (self.oid is not None) != (self.observation is RevisionObservation.observed):
            raise ValueError("oid is present exactly when the provider observed the Git object")
        return self


class LocalObjectAvailability(StrEnum):
    """Local repository-store state for one object, independent of provider observation."""

    not_requested = "not_requested"
    present = "present"
    missing_fetchable = "missing_fetchable"
    fetch_failed = "fetch_failed"
    unavailable = "unavailable"
    outside_bound = "outside_bound"


class LocalGitObjectAvailability(_HostedReviewModel):
    """Service projection of one provider-observed object's local availability.

    This is not an artifact contract and never appears inside a provider record: fetching an
    object changes this report, not the immutable provider snapshot that observed its ID.
    """

    oid: GitObjectId
    availability: LocalObjectAvailability


def local_git_object_availability(
    revision: RevisionRef | GitObjectRef,
    availability: LocalObjectAvailability,
) -> LocalGitObjectAvailability:
    """Report local state for a revision only when the provider observed its full object ID."""
    if revision.observation is not RevisionObservation.observed or revision.oid is None:
        raise ValueError("local object availability requires a provider-observed object ID")
    return LocalGitObjectAvailability(oid=revision.oid, availability=availability)


def _validate_comment_lifecycle(
    *,
    state: CommentState,
    url: str | None,
    created_at: str,
    updated_at: str,
) -> None:
    if state is not CommentState.deleted and url is None:
        raise ValueError("visible, minimized, and unknown comments require a URL")
    if _parse_rfc3339(updated_at) < _parse_rfc3339(created_at):
        raise ValueError("comment updated_at must not precede created_at")


class ChangeRequestComment(_HostedReviewModel):
    id: NonEmptyString
    provider_ref: ProviderObjectRef
    repository: RepositoryRef
    change_request_id: NonEmptyString
    url: CanonicalHttpsUrl | None
    author: ActorRef | None
    state: CommentState
    created_at: CanonicalTimestamp
    updated_at: CanonicalTimestamp

    @model_validator(mode="after")
    def _relationships_and_lifecycle(self) -> ChangeRequestComment:
        if (self.provider_ref.provider, self.provider_ref.instance) != (
            self.repository.provider,
            self.repository.instance,
        ):
            raise ValueError("comment and repository must use the same provider instance")
        _validate_comment_lifecycle(
            state=self.state,
            url=self.url,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )
        return self


class Review(_HostedReviewModel):
    id: NonEmptyString
    provider_ref: ProviderObjectRef
    repository: RepositoryRef
    change_request_id: NonEmptyString
    url: CanonicalHttpsUrl
    author: ActorRef | None
    disposition: ReviewDisposition
    revision: GitObjectRef
    created_at: CanonicalTimestamp
    submitted_at: CanonicalTimestamp | None
    updated_at: CanonicalTimestamp

    @model_validator(mode="after")
    def _relationships_and_lifecycle(self) -> Review:
        if (self.provider_ref.provider, self.provider_ref.instance) != (
            self.repository.provider,
            self.repository.instance,
        ):
            raise ValueError("review and repository must use the same provider instance")
        if self.revision.observation is RevisionObservation.not_requested:
            raise ValueError("review revision must be requested from the provider")
        created_at = _parse_rfc3339(self.created_at)
        updated_at = _parse_rfc3339(self.updated_at)
        if updated_at < created_at:
            raise ValueError("review updated_at must not precede created_at")
        if self.disposition is ReviewDisposition.pending:
            if self.submitted_at is not None:
                raise ValueError("pending reviews forbid submitted_at")
        elif self.disposition is not ReviewDisposition.unknown and self.submitted_at is None:
            raise ValueError("submitted review dispositions require submitted_at")
        if self.submitted_at is not None:
            submitted_at = _parse_rfc3339(self.submitted_at)
            if submitted_at < created_at or submitted_at > updated_at:
                raise ValueError("review submitted_at must fall within its lifecycle")
        return self


def _validate_review_path(path: str, path_b64: str | None) -> None:
    if "\x00" in path:
        raise ValueError("review anchor paths cannot contain NUL")
    if path_b64 is None:
        try:
            path.encode("utf-8", errors="strict")
        except UnicodeEncodeError as exc:
            raise ValueError("review anchor path must be valid UTF-8 or carry path_b64") from exc
        return
    try:
        raw = b64decode(path_b64, validate=True)
    except (BinasciiError, ValueError) as exc:
        raise ValueError("review anchor path_b64 must be canonical base64") from exc
    if not raw or b"\x00" in raw or b64encode(raw).decode("ascii") != path_b64:
        raise ValueError("review anchor path_b64 must be canonical nonempty Git path bytes")
    if raw.decode("utf-8", errors="replace") != path:
        raise ValueError("review anchor path must display the exact path_b64 bytes")


class _ReviewAnchorBase(_HostedReviewModel):
    path: NonEmptyString
    path_b64: NonEmptyString | None
    comparison: ComparisonRef
    original_revision: GitObjectRef
    current_revision: GitObjectRef
    state: ReviewAnchorState

    @model_validator(mode="after")
    def _path_and_revision_identity(self) -> _ReviewAnchorBase:
        _validate_review_path(self.path, self.path_b64)
        if self.original_revision.observation is RevisionObservation.not_requested:
            raise ValueError("review anchor original revision must be requested from the provider")
        if self.original_revision.repository_id != self.comparison.head.repository_id:
            raise ValueError("review anchor original revision must belong to the comparison head")
        if self.current_revision.repository_id != self.comparison.head.repository_id:
            raise ValueError("review anchor current revision must belong to the comparison head")
        current_is_observed = self.current_revision.observation is RevisionObservation.observed
        if self.state is not ReviewAnchorState.unresolved and not current_is_observed:
            raise ValueError("resolved review anchor states require an observed current revision")
        head = self.comparison.head
        if current_is_observed and (
            head.observation is not RevisionObservation.observed
            or (
                self.current_revision.repository_id,
                self.current_revision.oid,
            )
            != (head.repository_id, head.oid)
        ):
            raise ValueError("review anchor current revision must match comparison head")
        return self


class FileReviewAnchor(_ReviewAnchorBase):
    kind: Literal["file"]


class LineReviewAnchor(_ReviewAnchorBase):
    kind: Literal["line"]
    side: ReviewSide
    line: SafePositiveInteger


class ReviewRangeEndpoint(_HostedReviewModel):
    side: ReviewSide
    line: SafePositiveInteger


class RangeReviewAnchor(_ReviewAnchorBase):
    kind: Literal["range"]
    start: ReviewRangeEndpoint
    end: ReviewRangeEndpoint

    @model_validator(mode="after")
    def _same_side_endpoints_are_ordered(self) -> RangeReviewAnchor:
        if self.start.side is self.end.side and self.start.line >= self.end.line:
            raise ValueError("same-side review ranges require start before end")
        return self


type ReviewAnchor = Annotated[
    FileReviewAnchor | LineReviewAnchor | RangeReviewAnchor,
    Field(discriminator="kind"),
]


class ReviewThread(_HostedReviewModel):
    id: NonEmptyString
    provider_ref: ProviderObjectRef
    repository: RepositoryRef
    change_request_id: NonEmptyString
    anchor: ReviewAnchor
    state: ReviewThreadState
    resolved_by: ActorRef | None
    comment_count: SafeNonNegativeInteger

    @model_validator(mode="after")
    def _relationships_and_resolution(self) -> ReviewThread:
        if (self.provider_ref.provider, self.provider_ref.instance) != (
            self.repository.provider,
            self.repository.instance,
        ):
            raise ValueError("review thread and repository must use the same provider instance")
        if self.resolved_by is not None and self.state is not ReviewThreadState.resolved:
            raise ValueError("resolved_by is allowed only when a review thread is resolved")
        return self


class ReviewComment(_HostedReviewModel):
    id: NonEmptyString
    provider_ref: ProviderObjectRef
    repository: RepositoryRef
    change_request_id: NonEmptyString
    review_id: NonEmptyString | None
    thread_id: NonEmptyString
    in_reply_to_id: NonEmptyString | None
    url: CanonicalHttpsUrl | None
    author: ActorRef | None
    state: CommentState
    anchor: ReviewAnchor
    created_at: CanonicalTimestamp
    updated_at: CanonicalTimestamp

    @model_validator(mode="after")
    def _relationships_and_lifecycle(self) -> ReviewComment:
        if (self.provider_ref.provider, self.provider_ref.instance) != (
            self.repository.provider,
            self.repository.instance,
        ):
            raise ValueError("review comment and repository must use the same provider instance")
        if self.in_reply_to_id == self.id:
            raise ValueError("review comments cannot reply to themselves")
        _validate_comment_lifecycle(
            state=self.state,
            url=self.url,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )
        return self


class Check(_HostedReviewModel):
    id: NonEmptyString
    provider_ref: ProviderObjectRef
    repository: RepositoryRef
    parent_check_id: NonEmptyString | None
    kind: CheckKind
    revision: GitObjectRef
    name: NonEmptyString | None
    status: CheckStatus
    conclusion: CheckConclusion | None
    url: CanonicalHttpsUrl | None
    started_at: CanonicalTimestamp | None
    completed_at: CanonicalTimestamp | None

    @model_validator(mode="after")
    def _relationships_and_lifecycle(self) -> Check:
        if (self.provider_ref.provider, self.provider_ref.instance) != (
            self.repository.provider,
            self.repository.instance,
        ):
            raise ValueError("check and repository must use the same provider instance")
        if self.revision.observation is not RevisionObservation.observed:
            raise ValueError("checks require an observed immutable revision")
        if self.parent_check_id == self.id:
            raise ValueError("checks cannot parent themselves")
        if self.kind is CheckKind.run and self.parent_check_id is None:
            raise ValueError("check runs require a parent suite")
        if self.kind is CheckKind.run and self.name is None:
            raise ValueError("check runs require a name")
        if self.kind is CheckKind.suite and self.parent_check_id is not None:
            raise ValueError("check suites forbid a parent check")
        if self.status is CheckStatus.completed:
            if self.conclusion is None:
                raise ValueError("completed checks require a conclusion")
            if self.kind is CheckKind.run and self.completed_at is None:
                raise ValueError("completed check runs require completed_at")
        elif self.conclusion is not None or self.completed_at is not None:
            raise ValueError("noncompleted checks forbid conclusion and completed_at")
        if (
            self.started_at is not None
            and self.completed_at is not None
            and (_parse_rfc3339(self.completed_at) < _parse_rfc3339(self.started_at))
        ):
            raise ValueError("check completed_at must not precede started_at")
        return self


class CommitStatus(_HostedReviewModel):
    id: NonEmptyString
    provider_ref: ProviderObjectRef
    repository: RepositoryRef
    revision: GitObjectRef
    context: NonEmptyString
    state: CommitStatusState
    description: NonEmptyString | None
    target_url: CanonicalHttpsUrl | None
    created_at: CanonicalTimestamp
    updated_at: CanonicalTimestamp

    @model_validator(mode="after")
    def _relationships_and_lifecycle(self) -> CommitStatus:
        if (self.provider_ref.provider, self.provider_ref.instance) != (
            self.repository.provider,
            self.repository.instance,
        ):
            raise ValueError("commit status and repository must use the same provider instance")
        if self.revision.observation is not RevisionObservation.observed:
            raise ValueError("commit statuses require an observed immutable revision")
        if _parse_rfc3339(self.updated_at) < _parse_rfc3339(self.created_at):
            raise ValueError("commit status updated_at must not precede created_at")
        return self


def validate_change_request_comment(value: dict[str, Any]) -> ChangeRequestComment:
    return ChangeRequestComment.model_validate(value)


def dump_change_request_comment(value: ChangeRequestComment) -> dict[str, Any]:
    return value.model_dump(mode="json")


def validate_review(value: dict[str, Any]) -> Review:
    return Review.model_validate(value)


def dump_review(value: Review) -> dict[str, Any]:
    return value.model_dump(mode="json")


def validate_review_thread(value: dict[str, Any]) -> ReviewThread:
    return ReviewThread.model_validate(value)


def dump_review_thread(value: ReviewThread) -> dict[str, Any]:
    return value.model_dump(mode="json")


def validate_review_comment(value: dict[str, Any]) -> ReviewComment:
    return ReviewComment.model_validate(value)


def dump_review_comment(value: ReviewComment) -> dict[str, Any]:
    return value.model_dump(mode="json")


def validate_check(value: dict[str, Any]) -> Check:
    return Check.model_validate(value)


def dump_check(value: Check) -> dict[str, Any]:
    return value.model_dump(mode="json")


def validate_commit_status(value: dict[str, Any]) -> CommitStatus:
    return CommitStatus.model_validate(value)


def dump_commit_status(value: CommitStatus) -> dict[str, Any]:
    return value.model_dump(mode="json")


type HostedReviewBundleRecord = (
    ChangeRequestComment | Review | ReviewThread | ReviewComment | Check | CommitStatus
)


def validate_hosted_review_bundle(
    *,
    change_request: ChangeRequest,
    change_request_comments: tuple[ChangeRequestComment, ...],
    reviews: tuple[Review, ...],
    review_threads: tuple[ReviewThread, ...],
    review_comments: tuple[ReviewComment, ...],
    checks: tuple[Check, ...],
    commit_statuses: tuple[CommitStatus, ...],
    review_comments_complete: bool,
) -> None:
    """Validate relationships whose targets live in sibling artifact collections."""

    def require_scope(
        *,
        provider_ref: ProviderObjectRef,
        repository: RepositoryRef,
        change_request_id: str | None,
    ) -> None:
        if repository != change_request.repository or (
            provider_ref.provider,
            provider_ref.instance,
        ) != (
            change_request.provider_ref.provider,
            change_request.provider_ref.instance,
        ):
            raise ValueError("hosted-review bundle records must share provider and repository")
        if change_request_id is not None and change_request_id != change_request.id:
            raise ValueError("hosted-review child has a dangling change_request_id")

    families: tuple[tuple[str, tuple[HostedReviewBundleRecord, ...]], ...] = (
        ("change-request comments", change_request_comments),
        ("reviews", reviews),
        ("review threads", review_threads),
        ("review comments", review_comments),
        ("checks", checks),
        ("commit statuses", commit_statuses),
    )
    for family_name, records in families:
        identifiers = tuple(record.id for record in records)
        if len(set(identifiers)) != len(identifiers):
            raise ValueError(f"{family_name} require unique IDs")

    for record in (*change_request_comments, *reviews, *review_threads, *review_comments):
        require_scope(
            provider_ref=record.provider_ref,
            repository=record.repository,
            change_request_id=record.change_request_id,
        )
    if any(
        review.revision.repository_id != change_request.comparison.head.repository_id
        for review in reviews
    ):
        raise ValueError("review revisions must belong to the change request head repository")
    for record in (*checks, *commit_statuses):
        require_scope(
            provider_ref=record.provider_ref,
            repository=record.repository,
            change_request_id=None,
        )

    review_by_id = {review.id: review for review in reviews}
    thread_by_id = {thread.id: thread for thread in review_threads}
    comment_by_id = {comment.id: comment for comment in review_comments}
    comments_by_thread: dict[str, list[ReviewComment]] = {
        thread.id: [] for thread in review_threads
    }
    for comment in review_comments:
        if comment.review_id is not None and comment.review_id not in review_by_id:
            raise ValueError("review comment has a dangling review_id")
        thread = thread_by_id.get(comment.thread_id)
        if thread is None:
            raise ValueError("review comment has a dangling thread_id")
        if comment.anchor.comparison != change_request.comparison or (
            comment.anchor.path,
            comment.anchor.path_b64,
        ) != (thread.anchor.path, thread.anchor.path_b64):
            raise ValueError("review comment anchor does not match its thread")
        if comment.in_reply_to_id is not None:
            parent = comment_by_id.get(comment.in_reply_to_id)
            if parent is None:
                raise ValueError("review comment has a dangling in_reply_to_id")
            if parent.thread_id != comment.thread_id:
                raise ValueError("review comments may reply only within their thread")
        comments_by_thread[thread.id].append(comment)

    reply_parent_by_id = {
        comment.id: comment.in_reply_to_id
        for comment in review_comments
        if comment.in_reply_to_id is not None
    }
    resolved_reply_ids: set[str] = set()
    for start_id in reply_parent_by_id:
        path_ids: set[str] = set()
        path: list[str] = []
        current_id = start_id
        while current_id not in resolved_reply_ids:
            if current_id in path_ids:
                raise ValueError("review comment reply graph cannot contain cycles")
            path_ids.add(current_id)
            path.append(current_id)
            parent_id = reply_parent_by_id.get(current_id)
            if parent_id is None:
                break
            current_id = parent_id
        resolved_reply_ids.update(path)

    for thread in review_threads:
        if thread.anchor.comparison != change_request.comparison:
            raise ValueError("review thread anchor does not match the change request comparison")
        observed_count = len(comments_by_thread[thread.id])
        if observed_count > thread.comment_count:
            raise ValueError("observed review comments exceed the thread comment count")
        if review_comments_complete and observed_count != thread.comment_count:
            raise ValueError("complete review comments must equal the thread comment count")

    check_by_id = {check.id: check for check in checks}
    for check in checks:
        if check.parent_check_id is None:
            continue
        parent = check_by_id.get(check.parent_check_id)
        if parent is None or parent.kind is not CheckKind.suite:
            raise ValueError("check run parent must resolve to a suite in the bundle")
        if check.revision != parent.revision:
            raise ValueError("check run and parent suite must share the same revision")


class AuthorizationMode(StrEnum):
    anonymous = "anonymous"
    authenticated = "authenticated"


class RetrievalTransport(StrEnum):
    provider_cli = "provider_cli"
    direct_http = "direct_http"
    unknown = "unknown"


class RetrievalFailureReason(StrEnum):
    permission_denied = "permission_denied"
    rate_limited = "rate_limited"
    transport_unavailable = "transport_unavailable"
    provider_error = "provider_error"
    malformed_response = "malformed_response"
    output_bound = "output_bound"
    cancelled = "cancelled"
    unknown = "unknown"


class ExplicitDeletionEvidenceKind(StrEnum):
    deletion_event = "deletion_event"
    deleted_marker = "deleted_marker"


class CapabilityObservationState(StrEnum):
    observed = "observed"
    unavailable = "unavailable"
    not_requested = "not_requested"


class RepositoryVisibility(StrEnum):
    public = "public"
    internal = "internal"
    private = "private"
    unknown = "unknown"


class DefaultBranchAvailability(StrEnum):
    present = "present"
    absent = "absent"
    unavailable = "unavailable"
    unknown = "unknown"


class TransactionState(StrEnum):
    staged = "staged"
    committed = "committed"
    failed = "failed"


class ManifestFailureReason(StrEnum):
    invalid = "invalid"
    interrupted = "interrupted"
    publication_failed = "publication_failed"
    unknown = "unknown"


class CollectionCoverage(StrEnum):
    not_requested = "not_requested"
    partial = "partial"
    complete = "complete"
    unavailable = "unavailable"


class TruncationReason(StrEnum):
    item_bound = "item_bound"
    page_bound = "page_bound"
    byte_bound = "byte_bound"
    time_bound = "time_bound"
    provider_limit = "provider_limit"
    provider_failure = "provider_failure"
    malformed_response = "malformed_response"
    cancelled = "cancelled"


class ProviderViewPointerRole(StrEnum):
    current = "current"
    last_complete = "last_complete"


class IndexSortField(StrEnum):
    created_at = "created_at"
    updated_at = "updated_at"


class SortDirection(StrEnum):
    ascending = "ascending"
    descending = "descending"


class AuthorizationContextRef(_HostedReviewModel):
    provider: ProviderKind
    instance: ProviderInstance
    mode: AuthorizationMode
    principal_opaque_id: NonEmptyString | None
    visibility_partition_digest: Sha256Digest | None

    @model_validator(mode="after")
    def _identity_matches_mode(self) -> AuthorizationContextRef:
        if self.mode is AuthorizationMode.authenticated:
            if self.principal_opaque_id is None:
                raise ValueError("authenticated authorization requires a principal opaque ID")
        elif self.principal_opaque_id is not None or self.visibility_partition_digest is not None:
            raise ValueError("anonymous authorization forbids principal and visibility partition")
        return self


def authorization_context_key(value: AuthorizationContextRef) -> str:
    """Return the domain-separated digest for one stable authorization namespace."""
    return _sha256_json_key(
        [
            "AuthorizationContextRef/v1",
            value.provider,
            value.instance,
            value.mode.value,
            value.principal_opaque_id,
            value.visibility_partition_digest,
        ]
    )


class ArtifactSnapshotRef(_HostedReviewModel):
    contract_id: ContractId
    snapshot_id: Sha256Digest


class ProviderCollectionRetrievalTarget(_HostedReviewModel):
    kind: Literal["provider_collection"]
    repository: RepositoryRef
    result_contract_id: ContractId
    query_key: Sha256Digest


class ProviderObjectRetrievalTarget(_HostedReviewModel):
    kind: Literal["provider_object"]
    repository: RepositoryRef
    target: ProviderObjectRef

    @model_validator(mode="after")
    def _namespace_is_consistent(self) -> ProviderObjectRetrievalTarget:
        if (self.target.provider, self.target.instance) != (
            self.repository.provider,
            self.repository.instance,
        ):
            raise ValueError("provider-object retrieval target crosses provider instances")
        return self


class ProviderBindingRetrievalTarget(_HostedReviewModel):
    kind: Literal["provider_binding"]
    source_id: Sha256Digest
    repository: RepositoryRef


type RetrievalTarget = Annotated[
    ProviderCollectionRetrievalTarget
    | ProviderObjectRetrievalTarget
    | ProviderBindingRetrievalTarget,
    Field(discriminator="kind"),
]


class RetrievalSucceeded(_HostedReviewModel):
    kind: Literal["succeeded"]


class RetrievalNotModified(_HostedReviewModel):
    kind: Literal["not_modified"]
    reused_snapshot_id: Sha256Digest


class RetrievalNotFound(_HostedReviewModel):
    kind: Literal["not_found_under_context"]


class RetrievalExplicitlyDeleted(_HostedReviewModel):
    kind: Literal["explicitly_deleted"]
    target: ProviderObjectRef
    repository: RepositoryRef
    evidence_kind: ExplicitDeletionEvidenceKind
    provider_event_opaque_id: NonEmptyString | None
    provider_event_at: CanonicalTimestamp | None

    @model_validator(mode="after")
    def _event_identity_matches_evidence_kind(self) -> RetrievalExplicitlyDeleted:
        is_event = self.evidence_kind is ExplicitDeletionEvidenceKind.deletion_event
        if (self.provider_event_opaque_id is not None) != is_event or (
            self.provider_event_at is not None
        ) != is_event:
            raise ValueError(
                "deletion events require opaque event identity and time; markers forbid both"
            )
        return self


class RetrievalFailed(_HostedReviewModel):
    kind: Literal["failed"]
    reason: RetrievalFailureReason


type RetrievalOutcome = Annotated[
    RetrievalSucceeded
    | RetrievalNotModified
    | RetrievalNotFound
    | RetrievalExplicitlyDeleted
    | RetrievalFailed,
    Field(discriminator="kind"),
]


class HttpValidators(_HostedReviewModel):
    etag: NonEmptyString | None
    last_modified_at: CanonicalTimestamp | None


class RateLimitObservation(_HostedReviewModel):
    limit: SafeNonNegativeInteger
    remaining: SafeNonNegativeInteger
    reset_at: CanonicalTimestamp
    observed_at: CanonicalTimestamp

    @model_validator(mode="after")
    def _remaining_does_not_exceed_limit(self) -> RateLimitObservation:
        if self.remaining > self.limit:
            raise ValueError("remaining rate limit must not exceed the limit")
        return self


class CapabilityObservation(_HostedReviewModel):
    state: CapabilityObservationState
    values: tuple[StableToken, ...]

    @model_validator(mode="after")
    def _values_match_state(self) -> CapabilityObservation:
        if len(set(self.values)) != len(self.values) or tuple(sorted(self.values)) != self.values:
            raise ValueError("capabilities must be sorted and unique")
        if self.state is not CapabilityObservationState.observed and self.values:
            raise ValueError("only observed capabilities may contain values")
        return self


class Retrieval(_HostedReviewModel):
    authorization_context: AuthorizationContextRef
    target: RetrievalTarget
    adapter_id: StableToken
    transport: RetrievalTransport
    operation_id: StableToken
    request_key: Sha256Digest
    started_at: CanonicalTimestamp
    finished_at: CanonicalTimestamp
    api_version: NonEmptyString | None
    normalization_version: NonEmptyString
    outcome: RetrievalOutcome
    validators: HttpValidators
    rate_limit: RateLimitObservation | None
    display_login: NonEmptyString | None
    capabilities: CapabilityObservation

    @model_validator(mode="after")
    def _observation_times_are_ordered(self) -> Retrieval:
        started_at = _parse_rfc3339(self.started_at)
        finished_at = _parse_rfc3339(self.finished_at)
        if finished_at < started_at:
            raise ValueError("retrieval finished_at must not precede started_at")
        if self.rate_limit is not None:
            rate_observed_at = _parse_rfc3339(self.rate_limit.observed_at)
            if not started_at <= rate_observed_at <= finished_at:
                raise ValueError("rate-limit observation must fall within the retrieval")
        target_repository = self.target.repository
        if (target_repository.provider, target_repository.instance) != (
            self.authorization_context.provider,
            self.authorization_context.instance,
        ):
            raise ValueError("retrieval target must share the authorization provider instance")
        if isinstance(self.outcome, RetrievalExplicitlyDeleted):
            namespace = (self.authorization_context.provider, self.authorization_context.instance)
            if (
                self.outcome.target.provider,
                self.outcome.target.instance,
            ) != namespace or (
                self.outcome.repository.provider,
                self.outcome.repository.instance,
            ) != namespace:
                raise ValueError("deletion observation must share the retrieval provider instance")
            if not isinstance(self.target, ProviderObjectRetrievalTarget) or (
                self.target.target != self.outcome.target
                or self.target.repository != self.outcome.repository
            ):
                raise ValueError("deletion outcome must match its provider-object request target")
            if self.outcome.provider_event_at is not None and _parse_rfc3339(
                self.outcome.provider_event_at
            ) > _parse_rfc3339(self.finished_at):
                raise ValueError("provider deletion event cannot follow its retrieval")
        return self


class ProviderBindingProvenance(_HostedReviewModel):
    retrieval_snapshot_id: Sha256Digest


# One conservative, credential-free repository source mapped to a stable repository. It is
# independent of authorization, cache entries, local paths, and mutable coordinates.
class ProviderBinding(_HostedReviewModel):
    source_id: Sha256Digest
    repository: RepositoryRef
    provenance: ProviderBindingProvenance | None


def validate_provider_binding_provenance(
    binding: ProviderBinding,
    retrieval_snapshot_id: str,
    retrieval: Retrieval,
) -> ProviderBinding:
    """Resolve the successful retrieval that established one provider binding."""
    if binding.provenance is None:
        raise ValueError("provider binding has no retrieval provenance")
    if binding.provenance.retrieval_snapshot_id != retrieval_snapshot_id:
        raise ValueError("resolved retrieval does not match provider binding provenance")
    if not isinstance(retrieval.outcome, RetrievalSucceeded):
        raise ValueError("provider binding provenance requires a successful retrieval")
    if not isinstance(retrieval.target, ProviderBindingRetrievalTarget) or (
        retrieval.target.source_id != binding.source_id
        or retrieval.target.repository != binding.repository
    ):
        raise ValueError("provider binding provenance identifies another binding")
    return binding


class DefaultBranch(_HostedReviewModel):
    availability: DefaultBranchAvailability
    name: NonEmptyString | None

    @model_validator(mode="after")
    def _name_matches_availability(self) -> DefaultBranch:
        if (self.name is not None) != (self.availability is DefaultBranchAvailability.present):
            raise ValueError("default branch name is present exactly when availability is present")
        return self


class HostedRepository(_HostedReviewModel):
    provider_ref: ProviderObjectRef
    owner: ActorRef
    name: NonEmptyString
    url: CanonicalHttpsUrl
    clone_url: CanonicalHttpsUrl
    visibility: RepositoryVisibility
    default_branch: DefaultBranch
    created_at: CanonicalTimestamp
    updated_at: CanonicalTimestamp

    @model_validator(mode="after")
    def _repository_times_are_ordered(self) -> HostedRepository:
        if _parse_rfc3339(self.updated_at) < _parse_rfc3339(self.created_at):
            raise ValueError("repository updated_at must not precede created_at")
        return self


def hosted_repository_ref(value: HostedRepository) -> RepositoryRef:
    """Project a hosted repository's sole provider-neutral repository identity."""
    return RepositoryRef(
        provider=value.provider_ref.provider,
        instance=value.provider_ref.instance,
        opaque_id=value.provider_ref.opaque_id,
    )


def validate_repository_successor(
    previous: HostedRepository, successor: HostedRepository
) -> HostedRepository:
    """Reject a repository update that silently changes stable provider identity."""
    if previous.provider_ref != successor.provider_ref:
        raise ValueError("repository successor changes stable provider identity")
    if successor.created_at != previous.created_at:
        raise ValueError("repository successor changes provider creation time")
    if _parse_rfc3339(successor.updated_at) < _parse_rfc3339(previous.updated_at):
        raise ValueError("repository successor moves updated_at backwards")
    return successor


def validate_provider_binding_successor(
    previous: ProviderBinding, successor: ProviderBinding
) -> ProviderBinding:
    """Accept a republished binding only when its source and repository identity are unchanged.

    Provenance is evidence rather than identity, so a successor may cite a newer establishing
    retrieval or none; a consumer that needs evidence resolves the successor's own provenance.
    """
    if successor.source_id != previous.source_id:
        raise ValueError("a binding for another source is not a provider binding successor")
    if successor.repository != previous.repository:
        raise ValueError(
            "provider binding rebind conflict: a source ID cannot move to another repository"
        )
    return successor


def validate_provider_bindings(
    bindings: tuple[ProviderBinding, ...],
) -> tuple[ProviderBinding, ...]:
    """Validate one binding set: many sources may share a repository, one source may not fork."""
    by_source: dict[str, ProviderBinding] = {}
    for binding in bindings:
        existing = by_source.get(binding.source_id)
        if existing is None:
            by_source[binding.source_id] = binding
            continue
        if existing.repository != binding.repository:
            raise ValueError(
                "provider binding rebind conflict: one source ID names different repositories"
            )
        raise ValueError("provider bindings require exactly one binding per source ID")
    return bindings


class AllChangeRequestStates(_HostedReviewModel):
    kind: Literal["all"]


class SelectedChangeRequestStates(_HostedReviewModel):
    kind: Literal["selected"]
    states: tuple[ChangeRequestState, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _states_are_sorted_and_unique(self) -> SelectedChangeRequestStates:
        values = tuple(state.value for state in self.states)
        if len(set(values)) != len(values) or tuple(sorted(values)) != values:
            raise ValueError("selected states must be sorted and unique")
        return self


type ChangeRequestStateFilter = Annotated[
    AllChangeRequestStates | SelectedChangeRequestStates,
    Field(discriminator="kind"),
]


class IndexSort(_HostedReviewModel):
    field: IndexSortField
    direction: SortDirection
    tie_breaker: Literal["provider_opaque_id"]


class IndexBounds(_HostedReviewModel):
    max_items: SafePositiveInteger
    max_pages: SafePositiveInteger
    max_bytes: SafePositiveInteger
    max_duration_ms: SafePositiveInteger


class ChangeRequestIndexQuery(_HostedReviewModel):
    repository: RepositoryRef
    state_filter: ChangeRequestStateFilter
    sort: IndexSort
    bounds: IndexBounds


def change_request_index_query_key(value: ChangeRequestIndexQuery) -> str:
    """Return the domain-separated digest for a normalized index query."""
    if isinstance(value.state_filter, AllChangeRequestStates):
        state_filter: list[object] = ["all"]
    else:
        state_filter = ["selected", *[state.value for state in value.state_filter.states]]
    return _sha256_json_key(
        [
            "ChangeRequestIndexQuery/v1",
            value.repository.provider,
            value.repository.instance,
            value.repository.opaque_id,
            state_filter,
            value.sort.field.value,
            value.sort.direction.value,
            value.sort.tie_breaker,
            value.bounds.max_items,
            value.bounds.max_pages,
            value.bounds.max_bytes,
            value.bounds.max_duration_ms,
        ]
    )


class ChangeRequestIndexRow(_HostedReviewModel):
    provider_ref: ProviderObjectRef
    repository: RepositoryRef
    number: SafePositiveInteger
    url: CanonicalHttpsUrl
    title: NonEmptyString
    state: ChangeRequestState
    draft: StrictBool
    author: ActorRef | None
    base_label: NonEmptyString
    head_label: NonEmptyString
    created_at: CanonicalTimestamp
    updated_at: CanonicalTimestamp

    @model_validator(mode="after")
    def _identity_and_times_are_consistent(self) -> ChangeRequestIndexRow:
        if (self.provider_ref.provider, self.provider_ref.instance) != (
            self.repository.provider,
            self.repository.instance,
        ):
            raise ValueError("index row provider and repository instances must match")
        if _parse_rfc3339(self.updated_at) < _parse_rfc3339(self.created_at):
            raise ValueError("index row updated_at must not precede created_at")
        return self


class ChangeRequestIndex(_HostedReviewModel):
    query_key: Sha256Digest
    query: ChangeRequestIndexQuery
    rows: tuple[ChangeRequestIndexRow, ...]

    @model_validator(mode="after")
    def _query_rows_and_order_are_consistent(self) -> ChangeRequestIndex:
        if self.query_key != change_request_index_query_key(self.query):
            raise ValueError("change-request index query key does not match the query")

        seen: set[str] = set()
        selected_states = (
            None
            if isinstance(self.query.state_filter, AllChangeRequestStates)
            else set(self.query.state_filter.states)
        )
        previous: ChangeRequestIndexRow | None = None
        for row in self.rows:
            if row.repository != self.query.repository:
                raise ValueError("index row belongs to another repository")
            opaque_id = row.provider_ref.opaque_id
            _utf8_sort_key(opaque_id)
            if opaque_id in seen:
                raise ValueError("index rows contain a duplicate stable provider ID")
            seen.add(opaque_id)
            if selected_states is not None and row.state not in selected_states:
                raise ValueError("index row does not match the selected state filter")
            if previous is not None:
                previous_primary = _parse_rfc3339(getattr(previous, self.query.sort.field.value))
                current_primary = _parse_rfc3339(getattr(row, self.query.sort.field.value))
                if self.query.sort.direction is SortDirection.ascending:
                    out_of_order = current_primary < previous_primary
                else:
                    out_of_order = current_primary > previous_primary
                if out_of_order or (
                    current_primary == previous_primary
                    and _utf8_sort_key(opaque_id) <= _utf8_sort_key(previous.provider_ref.opaque_id)
                ):
                    raise ValueError("index rows do not follow the declared deterministic order")
            previous = row
        if len(self.rows) > self.query.bounds.max_items:
            raise ValueError("index rows exceed the declared item bound")
        return self


def validate_change_request_index_row_identity(
    change_request: ChangeRequest, row: ChangeRequestIndexRow
) -> ChangeRequestIndexRow:
    """Require direct and index projections to identify the same hosted change."""
    if (
        change_request.provider_ref != row.provider_ref
        or change_request.repository != row.repository
        or change_request.number != row.number
        or change_request.url != row.url
    ):
        raise ValueError("direct change request and index row identity disagree")
    return row


class OpaqueCursorContinuation(_HostedReviewModel):
    kind: Literal["opaque_cursor"]
    value: NonEmptyString

    @field_validator("value")
    @classmethod
    def _forbid_raw_next_url(cls, value: str) -> str:
        if (
            len(value) > MAX_OPAQUE_CURSOR_LENGTH
            or _OPAQUE_CURSOR_RE.fullmatch(value) is None
            or _URI_SCHEME_RE.match(value) is not None
        ):
            raise ValueError("opaque pagination cursors must be bounded URL-free ASCII tokens")
        return value


class PageNumberContinuation(_HostedReviewModel):
    kind: Literal["page_number"]
    value: SafePositiveInteger


type Continuation = Annotated[
    OpaqueCursorContinuation | PageNumberContinuation,
    Field(discriminator="kind"),
]


class ProviderSnapshotConsistency(_HostedReviewModel):
    kind: Literal["provider_snapshot"]
    token: NonEmptyString


class BestEffortWindowConsistency(_HostedReviewModel):
    kind: Literal["best_effort_window"]


class UnknownRemoteConsistency(_HostedReviewModel):
    kind: Literal["unknown"]


type RemoteConsistency = Annotated[
    ProviderSnapshotConsistency | BestEffortWindowConsistency | UnknownRemoteConsistency,
    Field(discriminator="kind"),
]


class CollectionPage(_HostedReviewModel):
    ordinal: SafePositiveInteger
    requested_with: Continuation | None = Field(json_schema_extra={"unevaluatedProperties": False})
    next: Continuation | None = Field(json_schema_extra={"unevaluatedProperties": False})
    retrieval_snapshot_id: Sha256Digest
    observed_provider_ids: tuple[NonEmptyString, ...]
    provider_exhausted: StrictBool
    provider_snapshot_token: NonEmptyString | None


class PaginationEvidence(_HostedReviewModel):
    pages: tuple[CollectionPage, ...] = Field(min_length=1)
    first_observed_at: CanonicalTimestamp
    last_observed_at: CanonicalTimestamp
    remote_consistency: RemoteConsistency = Field(
        json_schema_extra={"unevaluatedProperties": False}
    )

    @model_validator(mode="after")
    def _page_chain_and_consistency_are_valid(self) -> PaginationEvidence:
        if _parse_rfc3339(self.last_observed_at) < _parse_rfc3339(self.first_observed_at):
            raise ValueError("pagination observation window is inverted")
        retrieval_ids = tuple(page.retrieval_snapshot_id for page in self.pages)
        if len(set(retrieval_ids)) != len(retrieval_ids):
            raise ValueError("pagination pages require distinct retrieval snapshots")
        for index, page in enumerate(self.pages):
            if page.ordinal != index + 1:
                raise ValueError("pagination page ordinals must be contiguous from one")
            expected = None if index == 0 else self.pages[index - 1].next
            if page.requested_with != expected:
                raise ValueError("pagination continuation chain is discontinuous")
            if page.provider_exhausted and page.next is not None:
                raise ValueError("an exhausted page cannot publish a continuation")
            if index < len(self.pages) - 1 and (page.provider_exhausted or page.next is None):
                raise ValueError("only the final page may end pagination")
        if isinstance(self.remote_consistency, ProviderSnapshotConsistency) and any(
            page.provider_snapshot_token != self.remote_consistency.token for page in self.pages
        ):
            raise ValueError("provider snapshot consistency requires one token for every page")
        if not isinstance(self.remote_consistency, ProviderSnapshotConsistency) and any(
            page.provider_snapshot_token is not None for page in self.pages
        ):
            raise ValueError("only provider-snapshot consistency may retain snapshot tokens")
        return self


class Truncation(_HostedReviewModel):
    reason: TruncationReason
    limit: SafePositiveInteger | None

    @model_validator(mode="after")
    def _limit_matches_reason(self) -> Truncation:
        bounded = {
            TruncationReason.item_bound,
            TruncationReason.page_bound,
            TruncationReason.byte_bound,
            TruncationReason.time_bound,
            TruncationReason.provider_limit,
        }
        if (self.reason in bounded) != (self.limit is not None):
            raise ValueError("bounded truncation reasons require exactly one positive limit")
        return self


class ImmutableActivityFreshness(_HostedReviewModel):
    kind: Literal["immutable"]


class ObservedActivityFreshness(_HostedReviewModel):
    kind: Literal["observed"]
    snapshot_id: Sha256Digest
    observed_at: CanonicalTimestamp


type ActivityFreshness = Annotated[
    ImmutableActivityFreshness | ObservedActivityFreshness,
    Field(discriminator="kind"),
]


class CommitActivityDetail(_HostedReviewModel):
    kind: Literal["commit"]
    revision: GitObjectRef


class ChangeRequestActivityDetail(_HostedReviewModel):
    kind: Literal["change_request"]
    change_request_id: NonEmptyString
    provider_ref: ProviderObjectRef
    repository: RepositoryRef
    number: SafePositiveInteger

    @model_validator(mode="after")
    def _namespace_is_consistent(self) -> ChangeRequestActivityDetail:
        if (self.provider_ref.provider, self.provider_ref.instance) != (
            self.repository.provider,
            self.repository.instance,
        ):
            raise ValueError("activity detail crosses provider instances")
        return self


type ActivityDetailTarget = Annotated[
    CommitActivityDetail | ChangeRequestActivityDetail,
    Field(discriminator="kind"),
]


class GitActivityActor(_HostedReviewModel):
    kind: Literal["git"]
    name: NonEmptyString
    email: NonEmptyString | None


class ProviderActivityActor(_HostedReviewModel):
    kind: Literal["provider"]
    actor: ActorRef


type ActivityActor = Annotated[
    GitActivityActor | ProviderActivityActor,
    Field(discriminator="kind"),
]


class ActivityItem(_HostedReviewModel):
    id: NonEmptyString
    kind: ActivityKind
    title: NonEmptyString
    actors: tuple[ActivityActor, ...]
    event_at: CanonicalTimestamp
    updated_at: CanonicalTimestamp
    state: ActivityState | None
    primary_revision: RevisionRef
    base_revision: RevisionRef | None
    head_revision: RevisionRef | None
    comparison_observed: StrictBool
    detail: ActivityDetailTarget
    freshness: ActivityFreshness

    @model_validator(mode="after")
    def _kind_and_relationships_are_consistent(self) -> ActivityItem:
        if _parse_rfc3339(self.updated_at) < _parse_rfc3339(self.event_at):
            raise ValueError("activity updated_at must not precede event_at")
        if self.kind is ActivityKind.commit:
            if self.state is not None:
                raise ValueError("commit activity forbids change-request state")
            if not isinstance(self.detail, CommitActivityDetail) or not isinstance(
                self.freshness, ImmutableActivityFreshness
            ):
                raise ValueError("commit activity requires commit detail and immutable freshness")
            if self.base_revision is not None or self.head_revision is not None:
                raise ValueError("commit activity forbids comparison revisions")
            if self.comparison_observed:
                raise ValueError("commit activity cannot claim an observed comparison")
            if any(not isinstance(actor, GitActivityActor) for actor in self.actors):
                raise ValueError("commit activity requires Git actors")
            if self.primary_revision.observation is not RevisionObservation.observed or (
                self.detail.revision.repository_id,
                self.detail.revision.oid,
            ) != (self.primary_revision.repository_id, self.primary_revision.oid):
                raise ValueError("commit detail must identify the observed primary revision")
            return self

        if self.state is None:
            raise ValueError("change-request activity requires state")
        if any(not isinstance(actor, ProviderActivityActor) for actor in self.actors):
            raise ValueError("change-request activity requires provider actors")
        if not isinstance(self.detail, ChangeRequestActivityDetail) or not isinstance(
            self.freshness, ObservedActivityFreshness
        ):
            raise ValueError(
                "change-request activity requires change-request detail and observed freshness"
            )
        if self.base_revision is None or self.head_revision is None:
            raise ValueError("change-request activity requires base and head revisions")
        if self.base_revision.repository_id != self.detail.repository.opaque_id:
            raise ValueError(
                "change-request activity base revision must belong to its hosted repository"
            )
        if self.primary_revision != self.head_revision:
            raise ValueError("change-request activity primary revision must be its head")
        revisions_are_observed = (
            self.base_revision.observation is RevisionObservation.observed
            and self.head_revision.observation is RevisionObservation.observed
        )
        if self.comparison_observed != revisions_are_observed:
            raise ValueError(
                "comparison_observed is true exactly when base and head revisions are observed"
            )
        return self


class RepositoryActivity(_HostedReviewModel):
    repository_id: NonEmptyString
    included_kinds: tuple[ActivityKind, ...] = Field(min_length=1)
    max_items: SafePositiveInteger
    order: Literal["event_at_desc_id_asc"]
    coverage: ActivityCoverage
    items: tuple[ActivityItem, ...]
    continuation: OpaqueCursorContinuation | None
    truncation: Truncation | None

    @model_validator(mode="after")
    def _page_contract_is_consistent(self) -> RepositoryActivity:
        kind_values = tuple(kind.value for kind in self.included_kinds)
        if len(set(kind_values)) != len(kind_values) or tuple(sorted(kind_values)) != kind_values:
            raise ValueError("activity included kinds must be ASCII-sorted and unique")
        if len(self.items) > self.max_items:
            raise ValueError("activity item count exceeds max_items")
        item_ids = tuple(item.id for item in self.items)
        if len(set(item_ids)) != len(item_ids):
            raise ValueError("activity item IDs must be unique")
        included = set(self.included_kinds)
        if any(item.kind not in included for item in self.items):
            raise ValueError("activity items must use an included kind")
        for item in self.items:
            if (
                item.kind is ActivityKind.commit
                and item.primary_revision.repository_id != self.repository_id
            ):
                raise ValueError("commit activity must belong to the enclosing repository")
        expected = tuple(sorted(self.items, key=lambda item: _utf8_sort_key(item.id)))
        expected = tuple(
            sorted(expected, key=lambda item: _parse_rfc3339(item.event_at), reverse=True)
        )
        if self.items != expected:
            raise ValueError("activity items must use event_at descending, ID ascending order")
        if self.coverage is ActivityCoverage.complete:
            if self.continuation is not None or self.truncation is not None:
                raise ValueError("complete activity forbids continuation and truncation")
        else:
            if self.truncation is None:
                raise ValueError("partial activity requires explicit truncation")
            if self.truncation.reason is TruncationReason.item_bound and (
                self.truncation.limit != self.max_items or len(self.items) != self.max_items
            ):
                raise ValueError("item-bound activity must reach its declared max_items limit")
        return self


def validate_repository_activity(value: dict[str, Any]) -> RepositoryActivity:
    return RepositoryActivity.model_validate(value)


def dump_repository_activity(value: RepositoryActivity) -> dict[str, Any]:
    return value.model_dump(mode="json")


class ResourceCollection(_HostedReviewModel):
    name: StableToken
    coverage: CollectionCoverage
    artifacts: tuple[ArtifactSnapshotRef, ...]
    retrieval_snapshot_ids: tuple[Sha256Digest, ...]
    pagination: PaginationEvidence | None
    truncation: Truncation | None
    failure_retrieval_snapshot_id: Sha256Digest | None

    @model_validator(mode="after")
    def _coverage_is_honest(self) -> ResourceCollection:
        if len(set(self.artifacts)) != len(self.artifacts):
            raise ValueError("collection artifact references must be unique")
        if len(set(self.retrieval_snapshot_ids)) != len(self.retrieval_snapshot_ids):
            raise ValueError("collection retrieval references must be unique")
        if (
            self.failure_retrieval_snapshot_id is not None
            and self.failure_retrieval_snapshot_id not in self.retrieval_snapshot_ids
        ):
            raise ValueError("collection failure must name one of its retrievals")
        if self.pagination is not None:
            page_retrievals = {page.retrieval_snapshot_id for page in self.pagination.pages}
            expected_page_retrievals = set(self.retrieval_snapshot_ids)
            if self.failure_retrieval_snapshot_id is not None:
                expected_page_retrievals.remove(self.failure_retrieval_snapshot_id)
            if page_retrievals != expected_page_retrievals:
                raise ValueError(
                    "pagination pages must exactly cover successful collection retrievals"
                )
        if self.coverage is CollectionCoverage.complete:
            if not self.retrieval_snapshot_ids:
                raise ValueError("complete collection requires retrieval evidence")
            if self.truncation is not None or self.failure_retrieval_snapshot_id is not None:
                raise ValueError("complete collection forbids truncation and failure")
            if self.pagination is not None:
                last_page = self.pagination.pages[-1]
                if not last_page.provider_exhausted or last_page.next is not None:
                    raise ValueError("complete paginated collection must be exhausted")
        elif self.coverage is CollectionCoverage.partial:
            if not self.retrieval_snapshot_ids:
                raise ValueError("partial collection requires retrieval evidence")
            if self.truncation is None:
                raise ValueError("partial collection requires truncation evidence")
            failure_truncations = {
                TruncationReason.provider_failure,
                TruncationReason.malformed_response,
                TruncationReason.cancelled,
            }
            if (self.truncation.reason in failure_truncations) != (
                self.failure_retrieval_snapshot_id is not None
            ):
                raise ValueError("partial failure truncation requires exactly one failed retrieval")
            if self.pagination is not None and self.pagination.pages[-1].provider_exhausted:
                raise ValueError("partial paginated collection cannot claim exhaustion")
        elif self.coverage is CollectionCoverage.unavailable:
            if self.artifacts:
                raise ValueError("unavailable collection cannot contain authoritative artifacts")
            if self.failure_retrieval_snapshot_id is None:
                raise ValueError("unavailable collection requires a failed retrieval")
            if self.pagination is not None or self.retrieval_snapshot_ids != (
                self.failure_retrieval_snapshot_id,
            ):
                raise ValueError(
                    "unavailable collection contains only its failed retrieval attempt"
                )
            if self.truncation is not None:
                raise ValueError("unavailable collection is not a truncated result")
        else:
            if (
                self.artifacts
                or self.retrieval_snapshot_ids
                or self.pagination is not None
                or self.truncation is not None
                or self.failure_retrieval_snapshot_id is not None
            ):
                raise ValueError("not-requested collection cannot contain acquisition evidence")
        return self


class ProviderObjectResourceTarget(_HostedReviewModel):
    kind: Literal["provider_object"]
    target: ProviderObjectRef


class ProviderCollectionResourceTarget(_HostedReviewModel):
    kind: Literal["provider_collection"]
    result_contract_id: ContractId
    query_key: Sha256Digest


type ResourceSetTarget = Annotated[
    ProviderObjectResourceTarget | ProviderCollectionResourceTarget,
    Field(discriminator="kind"),
]


class ResourceSet(_HostedReviewModel):
    repository: RepositoryRef
    authorization_context: AuthorizationContextRef
    target: ResourceSetTarget
    profile: ResourceProfileId
    collections: tuple[ResourceCollection, ...]

    @model_validator(mode="after")
    def _namespace_and_collection_names_are_consistent(self) -> ResourceSet:
        if (self.authorization_context.provider, self.authorization_context.instance) != (
            self.repository.provider,
            self.repository.instance,
        ):
            raise ValueError("resource set authorization and repository instances must match")
        if isinstance(self.target, ProviderObjectResourceTarget) and (
            self.target.target.provider,
            self.target.target.instance,
        ) != (self.repository.provider, self.repository.instance):
            raise ValueError("resource target crosses provider instances")
        names = tuple(collection.name for collection in self.collections)
        if len(set(names)) != len(names):
            raise ValueError("resource set collection names must be unique")
        return self


def _resolve_resource_profile(
    profile_id: str,
    profiles: Mapping[str, ResourceProfileSpec] | None,
) -> ResourceProfileSpec:
    from .resource_profiles import resolve_resource_profile

    return resolve_resource_profile(profile_id, profiles=profiles)


def validate_resource_set_against_profile(
    resource_set: ResourceSet,
    profile: ResourceProfileSpec,
) -> ResourceSet:
    """Apply one trusted profile declaration to an untrusted resource-set record."""
    if resource_set.profile != profile.profile_id:
        raise ValueError("resource set and resolved profile IDs disagree")
    if profile.target_class is ResourceTargetClass.provider_object:
        if not isinstance(resource_set.target, ProviderObjectResourceTarget):
            raise ValueError("resource set target does not match its profile")
    elif not isinstance(resource_set.target, ProviderCollectionResourceTarget):
        raise ValueError("resource set target does not match its profile")
    elif resource_set.target.result_contract_id != profile.target_result_contract_id:
        raise ValueError("collection target result contract does not match its profile")

    if tuple(collection.name for collection in resource_set.collections) != tuple(
        collection.name for collection in profile.collections
    ):
        raise ValueError("resource set collections must exactly match their profile")
    for collection, collection_spec in zip(
        resource_set.collections,
        profile.collections,
        strict=True,
    ):
        if collection.pagination is not None and (
            collection_spec.pagination is CollectionPaginationPolicy.forbidden
        ):
            raise ValueError("resource collection profile forbids pagination")
        if (
            collection.coverage in {CollectionCoverage.complete, CollectionCoverage.partial}
            and collection_spec.pagination is CollectionPaginationPolicy.required
            and collection.pagination is None
        ):
            raise ValueError("available resource collection requires pagination")
        if collection.coverage not in {
            CollectionCoverage.complete,
            CollectionCoverage.partial,
        }:
            continue
        artifact_count = len(collection.artifacts)
        if (
            artifact_count < collection_spec.minimum_artifacts
            or artifact_count > collection_spec.maximum_artifacts
        ):
            raise ValueError("resource collection artifact cardinality violates its profile")
        if any(
            artifact.contract_id != collection_spec.artifact_contract_id
            for artifact in collection.artifacts
        ):
            raise ValueError("resource collection artifact contract violates its profile")
    return resource_set


def resource_set_is_last_complete_eligible(
    value: ResourceSet,
    profiles: Mapping[str, ResourceProfileSpec] | None = None,
) -> bool:
    """Return whether the closed profile is a complete fallback publication."""
    profile = _resolve_resource_profile(value.profile, profiles)
    validate_resource_set_against_profile(value, profile)
    by_name = {collection.name: collection for collection in value.collections}
    has_no_incomplete_attempt = all(
        collection.coverage in {CollectionCoverage.complete, CollectionCoverage.not_requested}
        for collection in value.collections
    )
    required_are_complete = all(
        by_name[collection.name].coverage is CollectionCoverage.complete
        for collection in profile.collections
        if collection.required_for_last_complete
    )
    return has_no_incomplete_attempt and required_are_complete


def resource_set_is_current_eligible(
    value: ResourceSet,
    profiles: Mapping[str, ResourceProfileSpec] | None = None,
) -> bool:
    """Return whether every required collection has an acquisition outcome."""
    profile = _resolve_resource_profile(value.profile, profiles)
    validate_resource_set_against_profile(value, profile)
    by_name = {collection.name: collection for collection in value.collections}
    return all(
        by_name[collection.name].coverage is not CollectionCoverage.not_requested
        for collection in profile.collections
        if collection.required_for_last_complete
    )


def validate_hosted_repository_resource_set(
    resource_set: ResourceSet,
    repository: HostedRepository,
    repository_snapshot_id: str,
) -> ResourceSet:
    """Require a repository resource set to name the resolved repository snapshot."""
    from .resource_profiles import REPOSITORY_SUMMARY_PROFILE

    validate_resource_set_against_profile(resource_set, REPOSITORY_SUMMARY_PROFILE)
    expected_snapshot = ArtifactSnapshotRef(
        contract_id=HOSTED_REPOSITORY_CONTRACT_ID,
        snapshot_id=repository_snapshot_id,
    )
    if not isinstance(resource_set.target, ProviderObjectResourceTarget):
        raise ValueError("hosted repository requires a provider-object resource target")
    if resource_set.repository != hosted_repository_ref(repository):
        raise ValueError("hosted repository and resource set identities disagree")
    if resource_set.target.target != repository.provider_ref:
        raise ValueError("hosted repository and resource target identities disagree")
    if resource_set.collections[0].artifacts != (expected_snapshot,):
        raise ValueError("repository resource set must name the resolved repository snapshot")
    return resource_set


def validate_change_request_index_resource_set(
    resource_set: ResourceSet,
    index: ChangeRequestIndex,
    index_snapshot_id: str,
) -> ResourceSet:
    """Bind stable index rows to their acquisition and pagination evidence."""
    from .resource_profiles import CHANGE_REQUEST_INDEX_PROFILE

    validate_resource_set_against_profile(resource_set, CHANGE_REQUEST_INDEX_PROFILE)
    expected_snapshot = ArtifactSnapshotRef(
        contract_id=CHANGE_REQUEST_INDEX_CONTRACT_ID,
        snapshot_id=index_snapshot_id,
    )
    if not isinstance(resource_set.target, ProviderCollectionResourceTarget):
        raise ValueError("change-request index requires a provider-collection resource target")
    if resource_set.repository != index.query.repository:
        raise ValueError("change-request index and resource set repositories disagree")
    if resource_set.target.query_key != index.query_key:
        raise ValueError("change-request index and resource set query keys disagree")
    collection = resource_set.collections[0]
    if collection.artifacts != (expected_snapshot,):
        raise ValueError("index resource set must name the resolved index snapshot")
    if collection.coverage in {CollectionCoverage.complete, CollectionCoverage.partial}:
        if collection.pagination is None:
            raise ValueError("requested change-request index requires pagination evidence")
        pages = collection.pagination.pages
        if len(pages) > index.query.bounds.max_pages:
            raise ValueError("index pagination exceeds the declared page bound")
        observed_ids: set[str] = set()
        observed_item_count = 0
        for page in pages:
            for opaque_id in page.observed_provider_ids:
                observed_item_count += 1
                observed_ids.add(opaque_id)
        row_ids = {row.provider_ref.opaque_id for row in index.rows}
        if observed_ids != row_ids:
            raise ValueError("index pagination and normalized rows identify different results")
        if observed_item_count > index.query.bounds.max_items:
            raise ValueError("index pagination exceeds the declared item bound")
        if collection.truncation is not None:
            if collection.truncation.reason is TruncationReason.item_bound and (
                collection.truncation.limit != index.query.bounds.max_items
                or observed_item_count != index.query.bounds.max_items
            ):
                raise ValueError("item-bound truncation does not match the index query")
            if collection.truncation.reason is TruncationReason.page_bound and (
                collection.truncation.limit != index.query.bounds.max_pages
                or len(pages) != index.query.bounds.max_pages
            ):
                raise ValueError("page-bound truncation does not match the index query")
            if (
                collection.truncation.reason is TruncationReason.byte_bound
                and collection.truncation.limit != index.query.bounds.max_bytes
            ):
                raise ValueError("byte-bound truncation does not match the index query")
            if (
                collection.truncation.reason is TruncationReason.time_bound
                and collection.truncation.limit != index.query.bounds.max_duration_ms
            ):
                raise ValueError("time-bound truncation does not match the index query")
    return resource_set


class ManifestFailure(_HostedReviewModel):
    reason: ManifestFailureReason


class ProviderSyncManifest(_HostedReviewModel):
    transaction_id: NonEmptyString
    repository: RepositoryRef
    authorization_context: AuthorizationContextRef
    state: TransactionState
    started_at: CanonicalTimestamp
    finished_at: CanonicalTimestamp | None
    retrievals: tuple[ArtifactSnapshotRef, ...]
    resource_sets: tuple[ArtifactSnapshotRef, ...]
    failure: ManifestFailure | None

    @model_validator(mode="after")
    def _transaction_is_consistent(self) -> ProviderSyncManifest:
        if (self.authorization_context.provider, self.authorization_context.instance) != (
            self.repository.provider,
            self.repository.instance,
        ):
            raise ValueError("manifest authorization and repository instances must match")
        if len(set(self.retrievals)) != len(self.retrievals):
            raise ValueError("manifest retrieval references must be unique")
        if len(set(self.resource_sets)) != len(self.resource_sets):
            raise ValueError("manifest resource-set references must be unique")
        if any(reference.contract_id != RETRIEVAL_CONTRACT_ID for reference in self.retrievals):
            raise ValueError("manifest retrieval references must use Retrieval/v1")
        if any(
            reference.contract_id != RESOURCE_SET_CONTRACT_ID for reference in self.resource_sets
        ):
            raise ValueError("manifest resource-set references must use ResourceSet/v1")
        if self.finished_at is not None and _parse_rfc3339(self.finished_at) < _parse_rfc3339(
            self.started_at
        ):
            raise ValueError("manifest finished_at must not precede started_at")
        if self.state is TransactionState.staged:
            if self.finished_at is not None or self.failure is not None:
                raise ValueError("staged manifest forbids finish time and failure")
        elif self.state is TransactionState.committed:
            if self.finished_at is None or self.failure is not None or not self.resource_sets:
                raise ValueError("committed manifest requires finish and resource sets, no failure")
        elif self.finished_at is None or self.failure is None:
            raise ValueError("failed manifest requires finish time and failure")
        return self


class ProviderViewPointer(_HostedReviewModel):
    role: ProviderViewPointerRole
    repository: RepositoryRef
    authorization_context_key: Sha256Digest
    target: ResourceSetTarget
    manifest_snapshot_id: Sha256Digest
    resource_set_snapshot_id: Sha256Digest


def validate_manifest_closure(
    manifest: ProviderSyncManifest,
    resource_sets: Mapping[str, ResourceSet],
    retrievals: Mapping[str, Retrieval],
    profiles: Mapping[str, ResourceProfileSpec] | None = None,
) -> ProviderSyncManifest:
    """Resolve a manifest's immutable references and validate its namespace closure."""
    retrieval_ids = {reference.snapshot_id for reference in manifest.retrievals}
    resource_set_ids = {reference.snapshot_id for reference in manifest.resource_sets}
    if retrieval_ids != set(retrievals):
        raise ValueError("resolved retrievals do not match the manifest closure")
    if resource_set_ids != set(resource_sets):
        raise ValueError("resolved resource sets do not match the manifest closure")
    for resource_set in resource_sets.values():
        validate_resource_set_against_profile(
            resource_set,
            _resolve_resource_profile(resource_set.profile, profiles),
        )
        if resource_set.repository != manifest.repository:
            raise ValueError("manifest resource set belongs to another repository")
        if resource_set.authorization_context != manifest.authorization_context:
            raise ValueError("manifest resource set uses another authorization context")
        used_retrievals = {
            retrieval_id
            for collection in resource_set.collections
            for retrieval_id in collection.retrieval_snapshot_ids
        }
        if not used_retrievals.issubset(retrieval_ids):
            raise ValueError("resource set references retrieval outside the manifest")
        for collection in resource_set.collections:
            for retrieval_id in collection.retrieval_snapshot_ids:
                retrieval_target = retrievals[retrieval_id].target
                if isinstance(resource_set.target, ProviderObjectResourceTarget):
                    target_matches = (
                        isinstance(retrieval_target, ProviderObjectRetrievalTarget)
                        and retrieval_target.repository == resource_set.repository
                        and retrieval_target.target == resource_set.target.target
                    )
                else:
                    target_matches = (
                        isinstance(retrieval_target, ProviderCollectionRetrievalTarget)
                        and retrieval_target.repository == resource_set.repository
                        and retrieval_target.result_contract_id
                        == resource_set.target.result_contract_id
                        and retrieval_target.query_key == resource_set.target.query_key
                    )
                if not target_matches:
                    raise ValueError("collection retrieval identifies another logical target")
            if collection.failure_retrieval_snapshot_id is not None:
                failure_outcome = retrievals[collection.failure_retrieval_snapshot_id].outcome
                allowed_failure = (
                    isinstance(failure_outcome, RetrievalFailed | RetrievalNotFound)
                    if collection.coverage is CollectionCoverage.unavailable
                    else isinstance(failure_outcome, RetrievalFailed)
                )
                if not allowed_failure:
                    raise ValueError(
                        "collection failure reference requires an unavailable retrieval outcome"
                    )
                if collection.coverage is CollectionCoverage.partial:
                    if not isinstance(failure_outcome, RetrievalFailed):
                        raise ValueError("partial collection failure must be a failed retrieval")
                    expected_failure_reasons = {
                        TruncationReason.provider_failure: {
                            RetrievalFailureReason.permission_denied,
                            RetrievalFailureReason.rate_limited,
                            RetrievalFailureReason.transport_unavailable,
                            RetrievalFailureReason.provider_error,
                            RetrievalFailureReason.unknown,
                        },
                        TruncationReason.malformed_response: {
                            RetrievalFailureReason.malformed_response
                        },
                        TruncationReason.cancelled: {RetrievalFailureReason.cancelled},
                    }
                    if (
                        collection.truncation is None
                        or failure_outcome.reason
                        not in expected_failure_reasons[collection.truncation.reason]
                    ):
                        raise ValueError(
                            "partial collection failure does not match its truncation reason"
                        )
            successful_retrieval_ids = set(collection.retrieval_snapshot_ids)
            if collection.failure_retrieval_snapshot_id is not None:
                successful_retrieval_ids.remove(collection.failure_retrieval_snapshot_id)
            if any(
                not isinstance(
                    retrievals[retrieval_id].outcome,
                    RetrievalSucceeded | RetrievalNotModified,
                )
                for retrieval_id in successful_retrieval_ids
            ):
                raise ValueError(
                    "authoritative collection evidence requires successful retrieval outcomes"
                )
            artifact_snapshot_ids = {artifact.snapshot_id for artifact in collection.artifacts}
            for retrieval_id in successful_retrieval_ids:
                outcome = retrievals[retrieval_id].outcome
                if (
                    isinstance(outcome, RetrievalNotModified)
                    and outcome.reused_snapshot_id not in artifact_snapshot_ids
                ):
                    raise ValueError(
                        "not-modified retrieval must reuse an artifact in its collection"
                    )
            if collection.pagination is not None:
                page_retrieval_ids = {
                    page.retrieval_snapshot_id for page in collection.pagination.pages
                }
                if page_retrieval_ids != successful_retrieval_ids:
                    raise ValueError(
                        "pagination does not close over successful collection retrievals"
                    )
                first_observed_at = _parse_rfc3339(collection.pagination.first_observed_at)
                last_observed_at = _parse_rfc3339(collection.pagination.last_observed_at)
                page_observation_times: list[datetime] = []
                for page in collection.pagination.pages:
                    page_retrieval = retrievals[page.retrieval_snapshot_id]
                    if not isinstance(
                        page_retrieval.outcome,
                        RetrievalSucceeded | RetrievalNotModified,
                    ):
                        raise ValueError("pagination pages require successful retrieval outcomes")
                    page_observed_at = _parse_rfc3339(page_retrieval.finished_at)
                    page_observation_times.append(page_observed_at)
                if page_observation_times != sorted(page_observation_times):
                    raise ValueError("pagination retrieval times contradict page order")
                if (
                    page_observation_times[0] != first_observed_at
                    or page_observation_times[-1] != last_observed_at
                ):
                    raise ValueError(
                        "pagination bounds must equal the first and last page observations"
                    )
    for retrieval in retrievals.values():
        if retrieval.authorization_context != manifest.authorization_context:
            raise ValueError("manifest retrieval uses another authorization context")
        if retrieval.target.repository != manifest.repository:
            raise ValueError("manifest retrieval targets another repository")
        retrieval_started_at = _parse_rfc3339(retrieval.started_at)
        if retrieval_started_at < _parse_rfc3339(manifest.started_at):
            raise ValueError("manifest retrieval starts before its transaction")
        if manifest.finished_at is not None and _parse_rfc3339(
            retrieval.finished_at
        ) > _parse_rfc3339(manifest.finished_at):
            raise ValueError("manifest retrieval finishes after its transaction")
    return manifest


def validate_provider_view_pointer_target(
    pointer: ProviderViewPointer,
    manifests: Mapping[str, ProviderSyncManifest],
    resource_sets: Mapping[str, ResourceSet],
    retrievals: Mapping[str, Retrieval],
    profiles: Mapping[str, ResourceProfileSpec] | None = None,
) -> ProviderViewPointer:
    """Resolve one provider-view pointer against immutable publication records."""
    manifest = manifests.get(pointer.manifest_snapshot_id)
    if manifest is None:
        raise ValueError("provider view pointer manifest snapshot is unresolved")
    resource_set = resource_sets.get(pointer.resource_set_snapshot_id)
    if resource_set is None:
        raise ValueError("provider view pointer resource-set snapshot is unresolved")
    if manifest.state is not TransactionState.committed:
        raise ValueError("provider view pointer requires a committed manifest")
    try:
        manifest_resource_sets = {
            reference.snapshot_id: resource_sets[reference.snapshot_id]
            for reference in manifest.resource_sets
        }
        manifest_retrievals = {
            reference.snapshot_id: retrievals[reference.snapshot_id]
            for reference in manifest.retrievals
        }
    except KeyError as exc:
        raise ValueError("provider view pointer manifest closure is unresolved") from exc
    validate_manifest_closure(
        manifest,
        manifest_resource_sets,
        manifest_retrievals,
        profiles,
    )
    validate_resource_set_against_profile(
        resource_set,
        _resolve_resource_profile(resource_set.profile, profiles),
    )
    if pointer.repository != resource_set.repository or pointer.repository != manifest.repository:
        raise ValueError("provider view pointer repository does not match its target")
    if pointer.target != resource_set.target:
        raise ValueError("provider view pointer logical target does not match its resource set")
    if pointer.authorization_context_key != authorization_context_key(
        resource_set.authorization_context
    ):
        raise ValueError("provider view pointer authorization key does not match its resource set")
    if resource_set.authorization_context != manifest.authorization_context:
        raise ValueError("provider view pointer records use different authorization contexts")
    manifest_targets = {reference.snapshot_id for reference in manifest.resource_sets}
    if pointer.resource_set_snapshot_id not in manifest_targets:
        raise ValueError("provider view pointer resource set is outside its manifest")
    if pointer.role is ProviderViewPointerRole.current and not resource_set_is_current_eligible(
        resource_set, profiles
    ):
        raise ValueError("current pointer requires an attempted required collection")
    if (
        pointer.role is ProviderViewPointerRole.last_complete
        and not resource_set_is_last_complete_eligible(resource_set, profiles)
    ):
        raise ValueError("last-complete pointer requires a complete resource set")
    return pointer


class ExplicitProviderDeletionProof(_HostedReviewModel):
    kind: Literal["explicit_provider_deletion"]
    retrieval_snapshot_id: Sha256Digest


class Tombstone(_HostedReviewModel):
    target: ProviderObjectRef
    repository: RepositoryRef
    authorization_context: AuthorizationContextRef
    previous_live_snapshot_id: Sha256Digest
    observed_at: CanonicalTimestamp
    proof: ExplicitProviderDeletionProof

    @model_validator(mode="after")
    def _namespace_is_consistent(self) -> Tombstone:
        namespace = (self.repository.provider, self.repository.instance)
        if (self.target.provider, self.target.instance) != namespace or (
            self.authorization_context.provider,
            self.authorization_context.instance,
        ) != namespace:
            raise ValueError(
                "tombstone target, repository, and authorization must share a provider"
            )
        return self


class LiveSnapshotContext(_HostedReviewModel):
    target: ProviderObjectRef
    repository: RepositoryRef
    authorization_context: AuthorizationContextRef
    observed_at: CanonicalTimestamp


def validate_tombstone_evidence(
    tombstone: Tombstone,
    manifest: ProviderSyncManifest,
    resource_sets: Mapping[str, ResourceSet],
    retrievals: Mapping[str, Retrieval],
    live_snapshots: Mapping[str, LiveSnapshotContext],
    profiles: Mapping[str, ResourceProfileSpec] | None = None,
) -> Tombstone:
    """Resolve tombstone proof without treating filtered or unauthorized absence as deletion."""
    validate_manifest_closure(manifest, resource_sets, retrievals, profiles)
    if manifest.state is not TransactionState.committed or manifest.finished_at is None:
        raise ValueError("tombstone evidence requires a committed manifest")
    previous_live = live_snapshots.get(tombstone.previous_live_snapshot_id)
    if previous_live is None:
        raise ValueError("tombstone requires a previously observed live snapshot")
    if (
        previous_live.target != tombstone.target
        or previous_live.repository != tombstone.repository
        or previous_live.authorization_context != tombstone.authorization_context
    ):
        raise ValueError("previous live snapshot identifies another object or context")
    if tombstone.repository != manifest.repository or (
        tombstone.authorization_context != manifest.authorization_context
    ):
        raise ValueError("tombstone evidence uses another repository or authorization context")

    manifest_retrievals = {reference.snapshot_id for reference in manifest.retrievals}
    proof = tombstone.proof
    if proof.retrieval_snapshot_id not in manifest_retrievals:
        raise ValueError("explicit deletion retrieval is outside the manifest")
    retrieval = retrievals[proof.retrieval_snapshot_id]
    if not isinstance(retrieval.outcome, RetrievalExplicitlyDeleted):
        raise ValueError("tombstone requires a typed provider deletion observation")
    if retrieval.outcome.target != tombstone.target:
        raise ValueError("deletion observation identifies another provider object")
    if retrieval.outcome.repository != tombstone.repository:
        raise ValueError("deletion observation identifies another repository")
    evidence_at = _parse_rfc3339(retrieval.outcome.provider_event_at or retrieval.finished_at)
    if _parse_rfc3339(previous_live.observed_at) > evidence_at:
        raise ValueError("deletion evidence predates the previous live snapshot")

    observed_at = _parse_rfc3339(tombstone.observed_at)
    if observed_at < _parse_rfc3339(retrieval.finished_at):
        raise ValueError("tombstone predates its deletion evidence")
    if observed_at > _parse_rfc3339(manifest.finished_at):
        raise ValueError("tombstone falls outside its committed transaction")
    return tombstone


def validate_authorization_context(value: dict[str, Any]) -> AuthorizationContextRef:
    return AuthorizationContextRef.model_validate(value)


def validate_retrieval(value: dict[str, Any]) -> Retrieval:
    return Retrieval.model_validate(value)


def dump_retrieval(value: Retrieval) -> dict[str, Any]:
    return value.model_dump(mode="json")


def validate_provider_binding(value: dict[str, Any]) -> ProviderBinding:
    return ProviderBinding.model_validate(value)


def dump_provider_binding(value: ProviderBinding) -> dict[str, Any]:
    return value.model_dump(mode="json")


def validate_hosted_repository(value: dict[str, Any]) -> HostedRepository:
    return HostedRepository.model_validate(value)


def dump_hosted_repository(value: HostedRepository) -> dict[str, Any]:
    return value.model_dump(mode="json")


def validate_change_request_index(value: dict[str, Any]) -> ChangeRequestIndex:
    return ChangeRequestIndex.model_validate(value)


def dump_change_request_index(value: ChangeRequestIndex) -> dict[str, Any]:
    return value.model_dump(mode="json")


def validate_resource_set(
    value: dict[str, Any],
    profiles: Mapping[str, ResourceProfileSpec] | None = None,
) -> ResourceSet:
    resource_set = ResourceSet.model_validate(value)
    return validate_resource_set_against_profile(
        resource_set,
        _resolve_resource_profile(resource_set.profile, profiles),
    )


def dump_resource_set(value: ResourceSet) -> dict[str, Any]:
    return value.model_dump(mode="json")


def validate_provider_sync_manifest(value: dict[str, Any]) -> ProviderSyncManifest:
    return ProviderSyncManifest.model_validate(value)


def dump_provider_sync_manifest(value: ProviderSyncManifest) -> dict[str, Any]:
    return value.model_dump(mode="json")


def validate_provider_view_pointer(value: dict[str, Any]) -> ProviderViewPointer:
    return ProviderViewPointer.model_validate(value)


def dump_provider_view_pointer(value: ProviderViewPointer) -> dict[str, Any]:
    return value.model_dump(mode="json")


def validate_tombstone(value: dict[str, Any]) -> Tombstone:
    return Tombstone.model_validate(value)


def dump_tombstone(value: Tombstone) -> dict[str, Any]:
    return value.model_dump(mode="json")
