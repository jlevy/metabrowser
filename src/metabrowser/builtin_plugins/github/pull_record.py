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
from pathlib import Path
from typing import Annotated, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError

from metabrowser.cache.atomic import RecordError, read_bytes_bounded
from metabrowser.cache.paths import source_pull_record, source_pulls_directory
from metabrowser.home import SharedEntryPolicy, ensure_private_directory, write_private_file_atomic

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
# All bodies and hunks of one record together. The most measured was about 2.0 MB
# (kubernetes#102884: 1.72 MB of hunks before the hunk cap, 0.23 MB of bodies); 4 MiB
# leaves about twice that. Past it, later text is cut, in record order.
MAX_TEXT_BYTES: Final = 4 * 1024 * 1024
# The read bound. The text budget plus the fixed-size fields of at most 2,900 items
# stays well under it; a record that would not is refused rather than written.
MAX_PULL_RECORD_BYTES: Final = 16 * 1024 * 1024

type Sha = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")]
type Timestamp = Annotated[str, StringConstraints(pattern=r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")]
type Login = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9_\[\]-]{0,99}$")]
type Short = Annotated[str, StringConstraints(max_length=1024)]
type Url = Annotated[str, StringConstraints(pattern=r"^https://", max_length=4096)]
type Mergeable = Literal["mergeable", "conflicting", "unknown"]


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
    """Which lists stopped at their cap, and whether the text budget cut anything."""

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
    status: CombinedStatus
    comparison: Comparison | None
    truncated: Truncation


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


def apply_text_budget(record: PullRecord, budget: int = MAX_TEXT_BYTES) -> PullRecord:
    """Cut bodies and hunks, in record order, once they pass *budget* bytes together."""

    remaining = budget
    cut_any = False

    def take(
        text: str, truncated: bool, *, keep: Literal["head", "tail"] = "head"
    ) -> tuple[str, bool]:
        nonlocal remaining, cut_any
        kept, cut = cut_text(text, max(remaining, 0), keep=keep)
        remaining -= len(kept.encode("utf-8"))
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
    """Publish *record* atomically under its source. Blocking; run it off the event loop."""

    data = serialize_pull_record(record)
    ensure_private_directory(home, source_pulls_directory(slug))
    write_private_file_atomic(home, source_pull_record(slug, record.number), data)


def read_pull_record(
    home: Path, slug: str, number: int, *, shared: SharedEntryPolicy = "keep"
) -> PullRecord | RecordAbsence:
    """The cached record, or why there is none. Blocking and bounded; run it off the loop.

    A record another schema wrote is ``schema_mismatch`` and one that is too large,
    malformed, or outside the model is ``unreadable``; either way the caller refetches.
    """

    try:
        data = read_bytes_bounded(
            home, source_pull_record(slug, number), max_bytes=MAX_PULL_RECORD_BYTES, shared=shared
        )
    except FileNotFoundError:
        return "not_cached"
    except RecordError:
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


__all__ = [
    "API_PAGE_SIZE",
    "MAX_BODY_BYTES",
    "MAX_CHECK_RUNS",
    "MAX_DIFF_HUNK_BYTES",
    "MAX_ISSUE_COMMENTS",
    "MAX_LABELS",
    "MAX_PULL_RECORD_BYTES",
    "MAX_REVIEWS",
    "MAX_REVIEW_COMMENTS",
    "MAX_STATUSES",
    "MAX_TEXT_BYTES",
    "MAX_TITLE_BYTES",
    "PULL_RECORD_SCHEMA",
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
    "apply_text_budget",
    "cut_text",
    "read_pull_record",
    "serialize_pull_record",
    "write_pull_record",
]
