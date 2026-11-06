"""A selected pull request's bounded GitHub timeline, separate from its discussion record."""

from __future__ import annotations

import asyncio
import hashlib
import json
from functools import partial
from pathlib import Path
from typing import Annotated, Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError

from metabrowser.builtin_plugins.github.gh import GhError, gh_graphql
from metabrowser.builtin_plugins.github.gh_lists import UnreadableItemError, as_dict
from metabrowser.builtin_plugins.github.pull_record import (
    PullRecord,
    Timestamp,
    cut_text,
    ensure_pulls_directory,
)
from metabrowser.builtin_plugins.github.pull_route import cached_pull_record
from metabrowser.builtin_plugins.github.served_pull import ServedPulls
from metabrowser.builtin_plugins.github.urls import parse_repository_url
from metabrowser.cache.atomic import RecordError, read_bytes_bounded
from metabrowser.cache.locks import run_lock_section, source_alias_lock
from metabrowser.cache.paths import MAX_PULL_REQUEST_NUMBER, source_pull_timeline
from metabrowser.home import PrivateStorageError, write_private_file_atomic

# Public timeline samples and the 50/100 request comparison are in the Pulls plan.
PAGE_SIZE: Final = 100
MAX_PAGES: Final = 2
MAX_PROVIDER_BYTES: Final = 96 * 1024
MAX_SIDECAR_BYTES: Final = 128 * 1024
MAX_SUBJECT_BYTES: Final = 240
TIMEOUT_S: Final = 12
_GRAPHQL_MAX_NUMBER: Final = (1 << 31) - 1

_QUERY: Final = """
query MetabrowserPullTimeline($owner: String!, $name: String!, $number: Int!, $cursor: String) {
  viewer { login }
  repository(owner: $owner, name: $name) {
    nameWithOwner
    pullRequest(number: $number) {
      number baseRefOid headRefOid
      timelineItems(first: 100, after: $cursor,
        itemTypes: [PULL_REQUEST_COMMIT, ISSUE_COMMENT, PULL_REQUEST_REVIEW]) {
        pageInfo { hasNextPage endCursor }
        nodes {
          __typename
          ... on PullRequestCommit { commit { oid messageHeadline committedDate } }
          ... on IssueComment { fullDatabaseId }
          ... on PullRequestReview { fullDatabaseId state }
        }
      }
    }
  }
}
"""

type _Revision = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class TimelineRequest(_Model):
    number: int = Field(ge=1, le=MAX_PULL_REQUEST_NUMBER)
    record_revision: _Revision
    cached_only: bool = False


class _Commit(_Model):
    kind: Literal["commit"] = "commit"
    oid: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{40}$")]
    subject: Annotated[str, StringConstraints(max_length=MAX_SUBJECT_BYTES)]
    committed_at: Timestamp | None


class _Discussion(_Model):
    kind: Literal["comment", "review"]
    id: Annotated[str, StringConstraints(pattern=r"^[1-9][0-9]{0,19}$")]


type _Event = Annotated[_Commit | _Discussion, Field(discriminator="kind")]


class _Timeline(_Model):
    record_revision: _Revision
    state: Literal["complete", "partial", "unavailable"]
    events: tuple[_Event, ...] = Field(default=(), max_length=PAGE_SIZE * MAX_PAGES)


class _StoredTimeline(_Model):
    discussion_revision: _Revision
    timeline: _Timeline


def _discussion_revision(record: PullRecord) -> str:
    # These are the inputs the projection orders. Edits to displayed text, checks, or
    # a comparison leave their provider order intact.
    identity = (
        record.source,
        record.number,
        record.reader,
        record.pull.base.sha,
        record.pull.head.sha,
        [(comment.id, comment.created_at) for comment in record.issue_comments],
        [(review.id, review.submitted_at) for review in record.reviews if review.submitted_at],
    )
    return hashlib.sha256(json.dumps(identity, separators=(",", ":")).encode()).hexdigest()


def unavailable(ask: TimelineRequest) -> _Timeline:
    return _Timeline(record_revision=ask.record_revision, state="unavailable")


def _event(raw: object) -> _Event | None:
    node = as_dict(raw)
    kind = node["__typename"]
    if kind == "PullRequestCommit":
        commit = as_dict(node["commit"])
        subject = commit["messageHeadline"]
        if not isinstance(subject, str):
            raise ValueError("invalid commit subject")
        subject, _ = cut_text(subject, MAX_SUBJECT_BYTES)
        return _Commit(
            oid=commit["oid"],
            subject=subject.partition("\n")[0],
            committed_at=commit.get("committedDate"),
        )
    if kind == "PullRequestReview" and node["state"] == "PENDING":
        return None
    if kind not in ("IssueComment", "PullRequestReview"):
        raise ValueError("invalid timeline event")
    ident = node["fullDatabaseId"]
    if type(ident) is int:
        ident = str(ident)
    return _Discussion(kind="comment" if kind == "IssueComment" else "review", id=ident)


def _page(
    data: dict[str, Any],
    owner: str,
    name: str,
    record: PullRecord,
    cursor: str | None,
) -> tuple[list[_Event], str | None]:
    repository = as_dict(data["repository"])
    request = as_dict(repository["pullRequest"])
    repository_name = repository["nameWithOwner"]
    if (
        f"gh:{as_dict(data['viewer'])['login']}" != record.reader
        or not isinstance(repository_name, str)
        or repository_name.casefold() != f"{owner}/{name}".casefold()
        or type(request["number"]) is not int
        or request["number"] != record.number
        or request["baseRefOid"] != record.pull.base.sha
        or request["headRefOid"] != record.pull.head.sha
    ):
        raise ValueError("the timeline describes another record")
    page = as_dict(request["timelineItems"])
    nodes = page["nodes"]
    if not isinstance(nodes, list) or len(nodes) > PAGE_SIZE:
        raise ValueError("invalid timeline page")
    events = [event for raw in nodes if (event := _event(raw)) is not None]
    info = as_dict(page["pageInfo"])
    more = info["hasNextPage"]
    if type(more) is not bool:
        raise ValueError("invalid timeline pagination")
    following = info.get("endCursor")
    if not more:
        return events, None
    if (
        not nodes
        or not isinstance(following, str)
        or not 1 <= len(following) <= 1024
        or following == cursor
    ):
        raise ValueError("timeline cursor did not advance")
    return events, following


async def _project(owner: str, name: str, record: PullRecord, ask: TimelineRequest) -> _Timeline:
    events: list[_Event] = []
    seen: set[tuple[str, str]] = set()
    cursor = None
    for _ in range(MAX_PAGES):
        data = await gh_graphql(
            _QUERY,
            {"owner": owner, "name": name, "number": ask.number, "cursor": cursor},
            max_bytes=MAX_PROVIDER_BYTES,
        )
        page, cursor = _page(data, owner, name, record, cursor)
        for event in page:
            key = (event.kind, event.oid if isinstance(event, _Commit) else event.id)
            if key not in seen:
                seen.add(key)
                events.append(event)
        if cursor is None:
            break
    return _Timeline(
        record_revision=ask.record_revision,
        state="complete" if cursor is None else "partial",
        events=tuple(events),
    )


def _current_record(home: Path, slug: str, source: str, ask: TimelineRequest) -> PullRecord | None:
    record, _, revision = cached_pull_record(home, slug, ask.number)
    if (
        isinstance(record, PullRecord)
        and record.source == source
        and revision == ask.record_revision
    ):
        return record
    return None


def _read_sidecar(
    home: Path, slug: str, ask: TimelineRequest, record: PullRecord
) -> _Timeline | None:
    try:
        data = read_bytes_bounded(
            home, source_pull_timeline(slug, ask.number), max_bytes=MAX_SIDECAR_BYTES
        )
        stored = _StoredTimeline.model_validate_json(data)
    except (OSError, RecordError, PrivateStorageError, ValidationError):
        return None
    if stored.timeline.state == "unavailable" or stored.discussion_revision != _discussion_revision(
        record
    ):
        return None
    return stored.timeline.model_copy(update={"record_revision": ask.record_revision})


def _snapshot(
    home: Path, slug: str, source: str, ask: TimelineRequest
) -> tuple[PullRecord | None, _Timeline | None]:
    record = _current_record(home, slug, source, ask)
    return record, None if record is None else _read_sidecar(home, slug, ask, record)


def _publish(
    home: Path, slug: str, source: str, ask: TimelineRequest, timeline: _Timeline
) -> _Timeline:
    with source_alias_lock(home, slug):
        record, cached = _snapshot(home, slug, source, ask)
        if record is None:
            return unavailable(ask)
        if cached is not None:
            return cached
        stored = _StoredTimeline(
            discussion_revision=_discussion_revision(record), timeline=timeline
        )
        data = stored.model_dump_json().encode("utf-8")
        if len(data) <= MAX_SIDECAR_BYTES:
            ensure_pulls_directory(home, slug)
            write_private_file_atomic(home, source_pull_timeline(slug, ask.number), data)
    return timeline


async def read_timeline(served: ServedPulls, ask: TimelineRequest, gate: asyncio.Lock) -> _Timeline:
    """Read a held projection or verify and cache it through a bounded selected read."""

    publication = served.published
    home, slug, source = served.home, served.slug, served.source
    record, cached = await asyncio.to_thread(_snapshot, home, slug, source, ask)
    if cached is not None:
        return cached
    if ask.cached_only or record is None or ask.number > _GRAPHQL_MAX_NUMBER:
        return unavailable(ask)
    try:
        async with asyncio.timeout(TIMEOUT_S), gate:
            record, cached = await asyncio.to_thread(_snapshot, home, slug, source, ask)
            if cached is not None:
                return cached
            if record is None or served.published is not publication:
                return unavailable(ask)
            repository = parse_repository_url(source)
            if repository is None:
                return unavailable(ask)
            timeline = await _project(*repository, record, ask)
            if served.published is not publication:
                return unavailable(ask)
            return await run_lock_section(partial(_publish, home, slug, source, ask, timeline))
    except (
        GhError,
        KeyError,
        OSError,
        PrivateStorageError,
        UnreadableItemError,
        ValueError,
    ):
        return unavailable(ask)
