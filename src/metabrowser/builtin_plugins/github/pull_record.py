"""The pull-request record: one validated JSON file per pull request, and its bounds.

A record holds what ``gh api`` said about one pull request, as the reader it names saw
it at ``fetched_at``: the pull request, its issue comments, reviews, review comments,
check runs, and combined status, plus the comparison endpoints Git computed from it.
It lives at ``cache/sources/<slug>/pulls/<n>.json``, written by the home's private
atomic file write and read with a size bound. Pydantic validates it on write and parses
it on read; a record whose ``schema_version`` is not :data:`PULL_RECORD_SCHEMA` is
refetched, never migrated.

Every list and every free-text field is bounded, and a bound that cut something says so
in ``truncated`` or in the item's own ``*_truncated`` flag. The bounds are measured
below, on public pull requests read with ``gh api`` on 2026-09-23.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Annotated, Final, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    field_validator,
)

from metabrowser.cache.atomic import RecordError, read_bytes_bounded
from metabrowser.cache.paths import (
    source_pull_record,
    source_pull_refresh,
    source_pulls_directory,
)
from metabrowser.home import (
    PrivateStorageError,
    SharedEntryPolicy,
    ensure_private_directory,
    write_private_file_atomic,
)

PULL_RECORD_SCHEMA: Final = 1

# Measured on ten public pull requests (octocat/Hello-World#1, cli/cli#14462,
# kubernetes/kubernetes#18085 and #102884, rust-lang/rust#69864, #137944, and #162519,
# microsoft/vscode#52707, python/cpython#118450, pytorch/pytorch#196374):
#
# - issue comments: Hello-World#1 has 2,498 and kubernetes#18085 908; the rest 262 or
#   fewer. 1,000 (ten pages) keeps every real discussion and cuts the spam magnet.
# - reviews: Hello-World#1 has 1,437 and kubernetes#102884 408; 500 (five pages).
# - review comments: kubernetes#102884 has 593, cpython#118450 275; 1,000 (ten pages).
# - check runs: pytorch#196374 has 159, cli#14462 31; 300 (three pages).
# - statuses: at most one on any of them; one page of 100.
MAX_ISSUE_COMMENTS: Final = 1000
MAX_REVIEWS: Final = 500
MAX_REVIEW_COMMENTS: Final = 1000
MAX_CHECK_RUNS: Final = 300
MAX_STATUSES: Final = 100
MAX_LABELS: Final = 100
API_PAGE_SIZE: Final = 100

# Text, in UTF-8 bytes. The largest body measured was a 60,830-byte bot comment
# (rust#69864) and the largest description 13,082 bytes (kubernetes#102884); GitHub
# itself refuses bodies over 65,536 characters, so 64 KiB cuts nothing a person wrote.
# Diff hunks reach 61,562 bytes (kubernetes#102884, 95th percentile 12,475); a review
# comment's line is at the hunk's end, so 16 KiB of its tail is kept.
MAX_BODY_BYTES: Final = 64 * 1024
MAX_DIFF_HUNK_BYTES: Final = 16 * 1024
MAX_TITLE_BYTES: Final = 1024
# All bodies and hunks of one record together, as written: JSON escaping counts, so a
# body of control characters costs six bytes a character. The most measured was about
# 2.0 MB (kubernetes#102884: 1.72 MB of hunks before the hunk cap, 0.23 MB of bodies);
# 4 MiB leaves about twice that. Past it, later text is cut, in record order.
MAX_TEXT_BYTES: Final = 4 * 1024 * 1024
# The read bound. The text budget shrinks when the other fields leave less than it of
# this, so every record written can be read back.
MAX_PULL_RECORD_BYTES: Final = 16 * 1024 * 1024
# A cut flag written as ``false`` is one byte longer than ``true``, and a record carries
# about 3,500 of them.
_FLAG_SLACK_BYTES: Final = 16 * 1024

type Sha = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")]
type Timestamp = Annotated[str, StringConstraints(pattern=r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")]
type Login = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9_\[\]-]{0,99}$")]
type Short = Annotated[str, StringConstraints(max_length=1024)]
type Url = Annotated[str, StringConstraints(pattern=r"^https://", max_length=4096)]
type Mergeable = Literal["mergeable", "conflicting", "unknown"]
type UnavailablePart = Literal["check_runs", "status", "comparison"]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PullSide(_Model):
    """One end of a pull request: the branch name, its commit, and its repository.

    ``repository`` is ``owner/name``, or ``None`` when a fork was deleted.
    """

    ref: Short
    sha: Sha
    repository: Short | None


class PullRequest(_Model):
    """The pull request itself. ``mergeable`` is ``unknown`` while GitHub computes it."""

    number: int = Field(ge=1)
    title: str
    body: str
    body_truncated: bool
    state: Literal["open", "closed"]
    draft: bool
    merged: bool
    merge_commit_sha: Sha | None
    mergeable: Mergeable
    labels: tuple[Short, ...] = Field(max_length=MAX_LABELS)
    author: Login | None
    created_at: Timestamp
    updated_at: Timestamp
    merged_at: Timestamp | None
    closed_at: Timestamp | None
    base: PullSide
    head: PullSide
    html_url: Url


class IssueComment(_Model):
    """A comment in the pull request's conversation."""

    id: int
    author: Login | None
    body: str
    body_truncated: bool
    created_at: Timestamp
    updated_at: Timestamp


class Review(_Model):
    """A review. ``submitted_at`` is ``None`` for one still pending."""

    id: int
    state: Short
    author: Login | None
    body: str
    body_truncated: bool
    submitted_at: Timestamp | None
    commit_id: Sha | None


class ReviewComment(_Model):
    """A review comment. ``line`` is ``None`` when the comment is outdated."""

    id: int
    review_id: int | None
    in_reply_to: int | None
    path: Annotated[str, StringConstraints(max_length=4096)]
    line: int | None
    original_line: int | None
    start_line: int | None
    original_start_line: int | None
    side: Literal["LEFT", "RIGHT"] | None
    commit_id: Sha
    original_commit_id: Sha
    diff_hunk: str
    diff_hunk_truncated: bool
    author: Login | None
    body: str
    body_truncated: bool
    created_at: Timestamp
    updated_at: Timestamp


class CheckRun(_Model):
    """A check run on the head commit. ``conclusion`` is ``None`` until it completes."""

    id: int
    name: Short
    status: Short
    conclusion: Short | None
    details_url: Url | None
    app: Short | None


class CommitStatus(_Model):
    """One context of the head commit's combined status."""

    context: Short
    state: Short
    description: Short | None
    target_url: Url | None


class CombinedStatus(_Model):
    """The head commit's combined status: an overall state and its contexts."""

    state: Short
    statuses: tuple[CommitStatus, ...] = Field(max_length=MAX_STATUSES)


class Comparison(_Model):
    """The pinned endpoints of the pull request's Files changed.

    ``base`` is the merge base of ``base_commit`` and ``head``; ``base_commit`` is the
    mirror's base branch for an open pull request and the API's ``base.sha`` otherwise.
    """

    base: Sha
    head: Sha
    base_commit: Sha
    base_from: Literal["base_branch", "base_sha"]


class Truncation(_Model):
    """Which lists are incomplete, and whether the text budget cut anything.

    A list is incomplete when it reached its cap or its page cap, or when GitHub sent an
    item too large to read or one Metabrowser could not read, which is left out.
    """

    issue_comments: bool
    reviews: bool
    review_comments: bool
    check_runs: bool
    statuses: bool
    text: bool


class PullRecord(_Model):
    """Everything cached about one pull request."""

    schema_version: int
    source: Url
    number: int = Field(ge=1)
    fetched_at: Timestamp
    reader: Annotated[str, StringConstraints(pattern=r"^gh:[A-Za-z0-9][A-Za-z0-9_-]{0,99}$")]
    etags: dict[
        Annotated[str, StringConstraints(max_length=512)],
        Annotated[str, StringConstraints(max_length=300)],
    ] = Field(max_length=64)
    pull: PullRequest
    issue_comments: tuple[IssueComment, ...] = Field(max_length=MAX_ISSUE_COMMENTS)
    reviews: tuple[Review, ...] = Field(max_length=MAX_REVIEWS)
    review_comments: tuple[ReviewComment, ...] = Field(max_length=MAX_REVIEW_COMMENTS)
    check_runs: tuple[CheckRun, ...] = Field(max_length=MAX_CHECK_RUNS)
    status: CombinedStatus | None
    comparison: Comparison | None
    truncated: Truncation
    unavailable: dict[UnavailablePart, Short]
    """Parts that could not be read, each with the typed state that said why.

    ``check_runs`` and ``status`` when GitHub refused them (a token without checks
    access answers 403); ``comparison`` when the base could not be fetched
    (``not_found_or_private``, ``network_error``, ``fetch_failed``) or shares no history
    with the head (``no_merge_base``). The rest of the record stands.
    """


type RecordAbsence = Literal["not_cached", "schema_mismatch", "unreadable"]


class RecordTooLargeError(Exception):
    """A record would be larger than :data:`MAX_PULL_RECORD_BYTES`; nothing was written."""


def cut_text(text: str, limit: int, *, keep: Literal["head", "tail"] = "head") -> tuple[str, bool]:
    """*text* cut to at most *limit* UTF-8 bytes on a character boundary; whether it was.

    ``tail`` keeps the end and starts it at a line boundary, for a diff hunk whose
    commented line is last.
    """

    data = text.encode("utf-8")
    if len(data) <= limit:
        return text, False
    if keep == "head":
        return data[:limit].decode("utf-8", errors="ignore"), True
    tail = data[len(data) - limit :].decode("utf-8", errors="ignore")
    newline = tail.find("\n")
    return (tail[newline + 1 :] if newline >= 0 else tail), True


_JSON_SHORT_ESCAPES: Final = frozenset('"\\\b\f\n\r\t')


def _escaped_char_size(char: str) -> int:
    if char in _JSON_SHORT_ESCAPES:
        return 2
    if ord(char) < 0x20:
        return 6
    return len(char.encode("utf-8", errors="surrogatepass"))


def escaped_size(text: str) -> int:
    """The bytes *text* takes inside a JSON string of the written record.

    Control characters escape to six bytes and quotes and backslashes to two, so a
    budget on raw bytes could be exceeded several times over.
    """

    return len(json.dumps(text, ensure_ascii=False).encode("utf-8", errors="surrogatepass")) - 2


def cut_escaped(
    text: str, limit: int, *, keep: Literal["head", "tail"] = "head"
) -> tuple[str, bool]:
    """*text* cut so its :func:`escaped_size` is at most *limit*; whether it was.

    ``tail`` keeps the end and starts it at a line boundary, as :func:`cut_text` does.
    """

    if escaped_size(text) <= limit:
        return text, False
    chars = reversed(text) if keep == "tail" else iter(text)
    kept: list[str] = []
    used = 0
    for char in chars:
        size = _escaped_char_size(char)
        if used + size > limit:
            break
        kept.append(char)
        used += size
    if keep == "head":
        return "".join(kept), True
    tail = "".join(reversed(kept))
    newline = tail.find("\n")
    return (tail[newline + 1 :] if newline >= 0 else tail), True


def apply_text_budget(record: PullRecord, budget: int = MAX_TEXT_BYTES) -> PullRecord:
    """Cut bodies and hunks, in record order, once they pass *budget* written bytes."""

    remaining = budget
    cut_any = False

    def take(
        text: str, truncated: bool, *, keep: Literal["head", "tail"] = "head"
    ) -> tuple[str, bool]:
        nonlocal remaining, cut_any
        kept, cut = cut_escaped(text, max(remaining, 0), keep=keep)
        remaining -= escaped_size(kept)
        cut_any = cut_any or cut
        return kept, truncated or cut

    body, body_cut = take(record.pull.body, record.pull.body_truncated)
    pull = record.pull.model_copy(update={"body": body, "body_truncated": body_cut})
    comments: list[IssueComment] = []
    for comment in record.issue_comments:
        text, cut = take(comment.body, comment.body_truncated)
        comments.append(comment.model_copy(update={"body": text, "body_truncated": cut}))
    reviews: list[Review] = []
    for review in record.reviews:
        text, cut = take(review.body, review.body_truncated)
        reviews.append(review.model_copy(update={"body": text, "body_truncated": cut}))
    review_comments: list[ReviewComment] = []
    for comment in record.review_comments:
        text, cut = take(comment.body, comment.body_truncated)
        hunk, hunk_cut = take(comment.diff_hunk, comment.diff_hunk_truncated, keep="tail")
        review_comments.append(
            comment.model_copy(
                update={
                    "body": text,
                    "body_truncated": cut,
                    "diff_hunk": hunk,
                    "diff_hunk_truncated": hunk_cut,
                }
            )
        )
    truncated = record.truncated.model_copy(update={"text": record.truncated.text or cut_any})
    return record.model_copy(
        update={
            "pull": pull,
            "issue_comments": tuple(comments),
            "reviews": tuple(reviews),
            "review_comments": tuple(review_comments),
            "truncated": truncated,
        }
    )


def fit_record(record: PullRecord) -> PullRecord:
    """*record* with its text budgeted so the written record fits the read bound.

    The budget is :data:`MAX_TEXT_BYTES`, or what the record's other fields leave of
    :data:`MAX_PULL_RECORD_BYTES` when that is less.
    """

    fixed = len(apply_text_budget(record, 0).model_dump_json().encode("utf-8"))
    budget = min(MAX_TEXT_BYTES, MAX_PULL_RECORD_BYTES - fixed - _FLAG_SLACK_BYTES)
    if budget < 0:
        raise RecordTooLargeError(
            f"the pull-request record would be {fixed:,} bytes without any text, more than "
            f"{MAX_PULL_RECORD_BYTES:,}"
        )
    return apply_text_budget(record, budget)


def serialize_pull_record(record: PullRecord) -> bytes:
    """Validate *record* again and serialize it, refusing one past the read bound."""

    data = PullRecord.model_validate(record.model_dump()).model_dump_json().encode("utf-8")
    if len(data) > MAX_PULL_RECORD_BYTES:
        raise RecordTooLargeError(
            f"the pull-request record would be {len(data):,} bytes, more than "
            f"{MAX_PULL_RECORD_BYTES:,}"
        )
    return data


def write_pull_record(home: Path, slug: str, record: PullRecord) -> None:
    """Publish *record* atomically under its source. Blocking; run it off the event loop.

    Raises :class:`RecordTooLargeError`, or the home's ``PrivateStorageError`` or an
    ``OSError`` when the cache cannot take it.
    """

    data = serialize_pull_record(record)
    ensure_private_directory(home, source_pulls_directory(slug))
    write_private_file_atomic(home, source_pull_record(slug, record.number), data)


def read_pull_record(
    home: Path, slug: str, number: int, *, shared: SharedEntryPolicy = "keep"
) -> PullRecord | RecordAbsence:
    """The cached record, or why there is none. Blocking and bounded; run it off the loop.

    A record another schema wrote is ``schema_mismatch``. One that is too large,
    malformed, outside the model, or not a private regular file (a symbolic link, one
    shared with other users) is ``unreadable``; either way the caller refetches.
    """

    try:
        data = read_bytes_bounded(
            home, source_pull_record(slug, number), max_bytes=MAX_PULL_RECORD_BYTES, shared=shared
        )
    except FileNotFoundError:
        return "not_cached"
    except (RecordError, PrivateStorageError, OSError):
        return "unreadable"
    try:
        payload = json.loads(data)
    except ValueError:
        return "unreadable"
    if not isinstance(payload, dict) or payload.get("schema_version") != PULL_RECORD_SCHEMA:
        return "schema_mismatch"
    try:
        record = PullRecord.model_validate(payload)
    except ValidationError:
        return "unreadable"
    if record.number != number:
        return "unreadable"
    return record


# How a pull request's last refresh ended, kept beside its record so a later command
# can report it and not ask gh again within the freshness window. One small object;
# the message is the user-facing one, which names no path, token, or gh output.
MAX_PULL_REFRESH_BYTES: Final = 4096


class PullRefreshStamp(_Model):
    """``succeeded`` or a failure state, why, when GitHub's limit lifts, and when."""

    outcome: Annotated[str, StringConstraints(pattern=r"^[a-z_]{1,40}$")]
    message: Annotated[str, StringConstraints(max_length=1000)] | None = None
    reset_at: Timestamp | None = None
    at: Timestamp

    @field_validator("reset_at", "at")
    @classmethod
    def _a_real_moment(cls, value: str | None) -> str | None:
        # The pattern admits a month 13 or a minute 61; only a real moment is kept.
        if value is not None:
            datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
        return value


def write_pull_refresh(home: Path, slug: str, number: int, stamp: PullRefreshStamp) -> None:
    """Publish *stamp* atomically beside the record. Blocking; run it off the event loop."""

    ensure_private_directory(home, source_pulls_directory(slug))
    write_private_file_atomic(
        home, source_pull_refresh(slug, number), stamp.model_dump_json().encode("utf-8")
    )


def read_pull_refresh(home: Path, slug: str, number: int) -> PullRefreshStamp | None:
    """The last refresh's stamp, or ``None`` when there is no usable one. Blocking."""

    try:
        data = read_bytes_bounded(
            home, source_pull_refresh(slug, number), max_bytes=MAX_PULL_REFRESH_BYTES
        )
        return PullRefreshStamp.model_validate_json(data)
    except (FileNotFoundError, RecordError, PrivateStorageError, OSError, ValueError):
        # ValueError covers pydantic's ValidationError: anything unusable is no stamp.
        return None


__all__ = [
    "API_PAGE_SIZE",
    "MAX_BODY_BYTES",
    "MAX_CHECK_RUNS",
    "MAX_DIFF_HUNK_BYTES",
    "MAX_ISSUE_COMMENTS",
    "MAX_LABELS",
    "MAX_PULL_RECORD_BYTES",
    "MAX_PULL_REFRESH_BYTES",
    "MAX_REVIEWS",
    "MAX_REVIEW_COMMENTS",
    "MAX_STATUSES",
    "MAX_TEXT_BYTES",
    "MAX_TITLE_BYTES",
    "PULL_RECORD_SCHEMA",
    "PullRefreshStamp",
    "CheckRun",
    "CombinedStatus",
    "CommitStatus",
    "Comparison",
    "IssueComment",
    "PullRecord",
    "PullRequest",
    "PullSide",
    "RecordAbsence",
    "RecordTooLargeError",
    "Review",
    "ReviewComment",
    "Truncation",
    "UnavailablePart",
    "apply_text_budget",
    "cut_escaped",
    "cut_text",
    "escaped_size",
    "fit_record",
    "read_pull_record",
    "read_pull_refresh",
    "serialize_pull_record",
    "write_pull_record",
    "write_pull_refresh",
]
