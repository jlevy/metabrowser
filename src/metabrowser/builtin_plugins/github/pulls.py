"""Read a pull request with ``gh api``, fetch its commits, and keep its record.

:func:`refresh_pull_request` is the whole network job for one pull request:

1. the active github.com account, from ``gh auth status``;
2. the pull request, its issue comments, reviews, review comments, and the head
   commit's check runs and combined status, each with ``gh api``, 100 per page up to
   each list's cap, sending ``If-None-Match`` where the previous record by the same
   reader holds an ETag and reusing that record's list on a ``304``;
3. the account again: a record read while the active account changed is discarded;
4. ``refs/pull/<n>/head`` into the store, which must name the head the API reported
   (one more full read if it moved meanwhile, then ``head_mismatch``); and
5. the comparison endpoints, then the record, written atomically.

A part that fails on its own does not fail the record. Check runs or a combined status
GitHub refuses, and a comparison whose base cannot be fetched or shares no history with
the head, are left out and named in the record's ``unavailable``. An item GitHub sends
that cannot be read, or that alone is larger than a page may be, is left out and its
list marked incomplete; an optional field that cannot be read, such as an ``http://``
link, is left empty. Everything else that fails raises :class:`PullDataError`, and
nothing else escapes.

Its integration point is the background refresh coordinator: a job keyed by the store
and the pull-request number that ``POST`` routes start or join. Until that lands, the
CLI is its only caller: the first ``--show`` or ``--api`` of a pull-request URL runs it
when no usable record is cached, and ``--no-serve`` runs it every time.

``gh api`` refuses every request while gh is signed out (checked 2026-09-23 with gh
2.98.0, which exits 4 and asks for ``gh auth login``), so a record is always read by a
signed-in account and ``reader`` is always ``gh:<login>``.
"""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import partial
from typing import TYPE_CHECKING, Any, Final, Literal

from pydantic import BaseModel, ValidationError

from metabrowser.builtin_plugins.github.avatars import avatar_of
from metabrowser.builtin_plugins.github.checkout import claim_source
from metabrowser.builtin_plugins.github.gh import GhError, GhResponse, gh_graphql
from metabrowser.builtin_plugins.github.gh_lists import (
    READ_FAILURES,
    ListRead,
    PageTooLargeError,
    PullDataError,
    PullDataState,
    UnreadableItemError,
    active_account,
    as_dict,
    get_response,
    login_of,
    read_list,
    readable_items,
    response_json,
    unconditional_304,
    utc_stamp,
)
from metabrowser.builtin_plugins.github.pull_list import ListedRepository
from metabrowser.builtin_plugins.github.pull_manifest import prepare_pull_manifest
from metabrowser.builtin_plugins.github.pull_record import (
    API_PAGE_SIZE,
    MAX_BODY_BYTES,
    MAX_CHECK_RUNS,
    MAX_DIFF_HUNK_BYTES,
    MAX_ISSUE_COMMENTS,
    MAX_LABELS,
    MAX_PULL_COMMITS,
    MAX_REVIEW_COMMENTS,
    MAX_REVIEWS,
    MAX_STATUSES,
    MAX_TITLE_BYTES,
    PULL_RECORD_PROJECTION,
    PULL_RECORD_SCHEMA,
    CheckRun,
    CombinedStatus,
    CommitStatus,
    Comparison,
    IssueComment,
    PullRecord,
    PullRefreshStamp,
    PullRequest,
    PullSide,
    RecordAbsence,
    RecordTooLargeError,
    Review,
    ReviewComment,
    Truncation,
    UnavailablePart,
    cut_text,
    fit_record,
    read_pull_record,
    read_pull_refresh,
    write_pull_record,
    write_pull_refresh,
)
from metabrowser.builtin_plugins.github.urls import parse_repository_url
from metabrowser.cache.locks import run_lock_section
from metabrowser.cache.providers import PullRequestFetch, PullRequestPin
from metabrowser.cache.pull_refs import (
    BaseUncertainError,
    PullEndpoints,
    PullRefError,
    comparison_endpoints,
    deepen_until_certain,
    fetch_pull_head,
    has_commit,
    pull_head_ref,
)
from metabrowser.git.process import GitError, UnsupportedGitVersionError
from metabrowser.home import PrivateStorageError

if TYPE_CHECKING:
    from metabrowser.cache.acquire import PublishedSource

log = logging.getLogger(__name__)

# One re-read when the head moved between the API read and the fetch; a pull request
# pushed to faster than two full reads is reported rather than chased.
_READ_ATTEMPTS: Final = 2
# GitHub refusals that fail only the part asked for: 403 or 404 (a token without checks
# access) and anything else it will not answer, such as a 422.
_PART_FAILURES: Final = frozenset({"not_found_or_private", "gh_failed"})
_SHORT_BYTES: Final = 1024
_MAX_URL_CHARS: Final = 4096
_MAX_PATH_CHARS: Final = 4096
_SHA = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")


# Selected, initially missing records use a core whose response names its viewer.
# Existing full-record refreshes keep conditional REST and their original two checks.
_CORE_FIELDS: Final = """
      number url title body state isDraft merged createdAt updatedAt closedAt mergedAt
      author { login avatar_url:avatarUrl(size:40) }
      mergedBy { login avatar_url:avatarUrl(size:40) }
      baseRefName baseRefOid baseRepository { nameWithOwner }
      headRefName headRefOid headRepository { nameWithOwner }
      mergeable mergeCommit { oid } potentialMergeCommit { oid }
      commits(first:1) { totalCount }
      labels(first:100) { nodes { name } }"""
_CORE_QUERY: Final = (
    """query PullCore($owner:String!,$name:String!,$number:Int!) {
  viewer { login }
  repository(owner:$owner,name:$name) {
    id nameWithOwner
    pull:pullRequest(number:$number) {"""
    + _CORE_FIELDS
    + "\n    }\n  }\n}"
)


def utc_now() -> datetime:
    """The clock records are stamped with; a seam for transcripts."""

    return datetime.now(UTC)


# ── Mapping API answers onto the record ─────────────────────────


def _short(value: object) -> str | None:
    """Optional short text, cut to its bound, or ``None``."""

    return cut_text(value, _SHORT_BYTES)[0] if isinstance(value, str) else None


def _required_short(value: object) -> str:
    text = _short(value)
    if text is None:
        raise UnreadableItemError
    return text


def _url(value: object) -> str | None:
    """An https link, or ``None``: an ``http://`` or over-long link is left out."""

    if isinstance(value, str) and value.startswith("https://") and len(value) <= _MAX_URL_CHARS:
        return value
    return None


def _int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _count(value: object) -> int | None:
    """A commit count within the record's bound, or ``None``."""

    number = _int(value)
    return number if number is not None and 0 <= number <= MAX_PULL_COMMITS else None


def _required_int(value: object) -> int:
    number = _int(value)
    if number is None:
        raise UnreadableItemError
    return number


def _sha(value: object) -> str | None:
    return value if isinstance(value, str) and _SHA.match(value) else None


def _text(value: object, limit: int = MAX_BODY_BYTES) -> tuple[str, bool]:
    return cut_text(value if isinstance(value, str) else "", limit)


def _side(value: object) -> PullSide:
    side = as_dict(value)
    repo = side.get("repo")
    full_name = repo.get("full_name") if isinstance(repo, dict) else None  # pyright: ignore[reportUnknownMemberType]
    return PullSide(
        ref=_required_short(side.get("ref")), sha=side["sha"], repository=_short(full_name)
    )


def _pull(value: object, number: int) -> PullRequest:
    item = as_dict(value)
    if item.get("number") != number:
        raise UnreadableItemError
    body, body_cut = _text(item.get("body"))
    title, _cut = _text(item.get("title"), MAX_TITLE_BYTES)
    labels = item.get("labels")
    names = (
        [_short(as_dict(label).get("name")) for label in labels[:MAX_LABELS]]
        if isinstance(labels, list)
        else []
    )  # pyright: ignore[reportUnknownArgumentType, reportUnknownVariableType]
    mergeable = item.get("mergeable")
    return PullRequest(
        number=number,
        title=title,
        body=body,
        body_truncated=body_cut,
        state=item["state"],
        draft=item.get("draft") is True,
        merged=item.get("merged") is True,
        merged_by=login_of(item.get("merged_by")),
        merged_by_avatar_url=avatar_of(item.get("merged_by")),
        commits=_count(item.get("commits")),
        merge_commit_sha=_sha(item.get("merge_commit_sha")),
        mergeable="mergeable"
        if mergeable is True
        else "conflicting"
        if mergeable is False
        else "unknown",
        labels=tuple(name for name in names if name is not None),
        author=login_of(item.get("user")),
        author_avatar_url=avatar_of(item.get("user")),
        created_at=item["created_at"],
        updated_at=item["updated_at"],
        merged_at=item.get("merged_at"),
        closed_at=item.get("closed_at"),
        base=_side(item["base"]),
        head=_side(item["head"]),
        html_url=item["html_url"],
    )


def _issue_comment(value: object) -> IssueComment:
    item = as_dict(value)
    body, cut = _text(item.get("body"))
    return IssueComment(
        id=_required_int(item.get("id")),
        author=login_of(item.get("user")),
        author_avatar_url=avatar_of(item.get("user")),
        body=body,
        body_truncated=cut,
        created_at=item["created_at"],
        updated_at=item["updated_at"],
    )


def _review(value: object) -> Review:
    item = as_dict(value)
    body, cut = _text(item.get("body"))
    return Review(
        id=_required_int(item.get("id")),
        state=_required_short(item.get("state")),
        author=login_of(item.get("user")),
        author_avatar_url=avatar_of(item.get("user")),
        body=body,
        body_truncated=cut,
        submitted_at=item.get("submitted_at"),
        commit_id=_sha(item.get("commit_id")),
    )


def _review_comment(value: object) -> ReviewComment:
    item = as_dict(value)
    body, cut = _text(item.get("body"))
    hunk = item.get("diff_hunk")
    diff_hunk, hunk_cut = cut_text(
        hunk if isinstance(hunk, str) else "", MAX_DIFF_HUNK_BYTES, keep="tail"
    )
    path = item.get("path")
    if not isinstance(path, str) or len(path) > _MAX_PATH_CHARS:
        raise UnreadableItemError
    side = item.get("side")
    return ReviewComment(
        id=_required_int(item.get("id")),
        review_id=_int(item.get("pull_request_review_id")),
        in_reply_to=_int(item.get("in_reply_to_id")),
        path=path,
        line=_int(item.get("line")),
        original_line=_int(item.get("original_line")),
        start_line=_int(item.get("start_line")),
        original_start_line=_int(item.get("original_start_line")),
        side=side if side in {"LEFT", "RIGHT"} else None,
        commit_id=item["commit_id"],
        original_commit_id=item["original_commit_id"],
        diff_hunk=diff_hunk,
        diff_hunk_truncated=hunk_cut,
        author=login_of(item.get("user")),
        author_avatar_url=avatar_of(item.get("user")),
        body=body,
        body_truncated=cut,
        created_at=item["created_at"],
        updated_at=item["updated_at"],
    )


def _check_run(value: object) -> CheckRun:
    item = as_dict(value)
    app = item.get("app")
    return CheckRun(
        id=_required_int(item.get("id")),
        name=_required_short(item.get("name")),
        status=_required_short(item.get("status")),
        conclusion=_short(item.get("conclusion")),
        details_url=_url(item.get("details_url")),
        app=_short(app.get("name")) if isinstance(app, dict) else None,  # pyright: ignore[reportUnknownMemberType]
    )


def _commit_status(value: object) -> CommitStatus:
    entry = as_dict(value)
    return CommitStatus(
        context=_required_short(entry.get("context")),
        state=_required_short(entry.get("state")),
        description=_short(entry.get("description")),
        target_url=_url(entry.get("target_url")),
    )


def _status(value: object) -> tuple[CombinedStatus, bool]:
    item = as_dict(value)
    entries = item.get("statuses")
    listed: list[object] = entries[:MAX_STATUSES] if isinstance(entries, list) else []  # pyright: ignore[reportUnknownVariableType]
    statuses, dropped = readable_items(listed, _commit_status)
    total = _int(item.get("total_count"))
    count = len(entries) if isinstance(entries, list) else 0  # pyright: ignore[reportUnknownArgumentType]
    combined = CombinedStatus(state=_required_short(item.get("state")), statuses=statuses)
    return combined, dropped or count > MAX_STATUSES or (total is not None and total > count)


def _unreadable_pull() -> PullDataError:
    return PullDataError("gh_failed", "GitHub answered with a pull request Metabrowser cannot read")


# ── Reading the API ─────────────────────────────────────────────


async def _get(path: str, *, etag: str | None) -> GhResponse:
    return await get_response(path, etag=etag, now=utc_now())


async def _read_list(path: str, *, key: str | None, cap: int, etag: str | None) -> ListRead:
    # A lambda, so the clock is this module's seam when the call is made.
    return await read_list(path, key=key, cap=cap, etag=etag, now=lambda: utc_now())


def _first_page(path: str) -> str:
    return f"{path}?per_page={API_PAGE_SIZE}&page=1"


def _reusable_etag(
    previous: PullRecord | None, path: str, items: Sequence[object], incomplete: bool
) -> str | None:
    """The ETag worth sending for a list: only when the previous one fit on one page.

    A ``304`` for page one then means the whole list is unchanged.
    """

    if previous is None or incomplete or len(items) >= API_PAGE_SIZE:
        return None
    return previous.etags.get(_first_page(path))


type _ListName = Literal["issue_comments", "reviews", "review_comments", "check_runs"]


@dataclass(frozen=True, slots=True)
class _ListParts[M: BaseModel]:
    items: tuple[M, ...]
    incomplete: bool
    reused: bool


async def _read_list_of[M: BaseModel](
    path: str,
    *,
    key: str | None,
    cap: int,
    previous: PullRecord | None,
    name: _ListName,
    build: Callable[[object], M],
    etags: dict[str, str],
) -> _ListParts[M]:
    """One list's models and whether it is incomplete, reusing *previous*'s on a ``304``."""

    etag = None
    if previous is not None:
        etag = _reusable_etag(
            previous, path, getattr(previous, name), getattr(previous.truncated, name)
        )
    listed = await _read_list(path, key=key, cap=cap, etag=etag)
    if listed.etag is not None:
        etags[_first_page(path)] = listed.etag
    if listed.items is None:
        # Only a conditional request, which needs a previous record, is answered 304.
        assert previous is not None
        return _ListParts(getattr(previous, name), getattr(previous.truncated, name), True)
    items, dropped = readable_items(listed.items, build)
    return _ListParts(items, listed.incomplete or dropped, False)


def _degrade(exc: PullDataError) -> bool:
    return exc.state in _PART_FAILURES


@dataclass(frozen=True, slots=True)
class _Unavailable:
    """A part of the pull request that could not be read, and the record stands without."""

    state: PullDataState


def _graph_pull(value: object, number: int) -> PullRequest:
    """Project the fixed GraphQL core through the same validated core model."""
    item = as_dict(value)
    if type(item.get("number")) is not int or item["number"] != number:
        raise UnreadableItemError

    def side(prefix: str) -> dict[str, Any]:
        repository = item[f"{prefix}Repository"]
        return {
            "ref": item[f"{prefix}RefName"],
            "sha": item[f"{prefix}RefOid"],
            "repo": None
            if repository is None
            else {"full_name": as_dict(repository)["nameWithOwner"]},
        }

    merged_commit = item["mergeCommit"] if item["merged"] is True else item["potentialMergeCommit"]
    return _pull(
        {
            "number": item["number"],
            "title": item["title"],
            "body": item["body"],
            "state": {"OPEN": "open", "CLOSED": "closed", "MERGED": "closed"}[item["state"]],
            "draft": item["isDraft"],
            "merged": item["merged"],
            "merged_by": item["mergedBy"],
            "commits": as_dict(item["commits"])["totalCount"],
            "merge_commit_sha": None if merged_commit is None else as_dict(merged_commit)["oid"],
            "mergeable": {"MERGEABLE": True, "CONFLICTING": False, "UNKNOWN": None}[
                item["mergeable"]
            ],
            "labels": as_dict(item["labels"])["nodes"],
            "user": item["author"],
            "created_at": item["createdAt"],
            "updated_at": item["updatedAt"],
            "closed_at": item["closedAt"],
            "merged_at": item["mergedAt"],
            "base": side("base"),
            "head": side("head"),
            "html_url": item["url"],
        },
        number,
    )


async def _read_graph_core(
    owner: str,
    repo: str,
    number: int,
    reader: str,
    *,
    observe_reader: Callable[[str], None] | None = None,
) -> PullRequest:
    """Attribute a selected core to the actual query viewer before staging it."""
    try:
        data = await gh_graphql(
            _CORE_QUERY, {"owner": owner, "name": repo, "number": number}, now=utc_now()
        )
    except GhError as exc:
        raise PullDataError(exc.state, str(exc), reset_at=exc.reset_at) from exc
    try:
        viewer = login_of(as_dict(data["viewer"]))
        if viewer is None:
            raise UnreadableItemError
        observed = f"gh:{viewer}"
        if observe_reader is not None:
            observe_reader(observed)
        if reader != observed:
            raise PullDataError(
                "account_changed",
                "the query viewer changed during the read, so the provisional core was discarded",
            )
        raw_repository = data["repository"]
        if raw_repository is None:
            raise PullDataError("not_found_or_private", "GitHub has no readable pull request here")
        repository = as_dict(raw_repository)
        identity, name = repository["id"], repository["nameWithOwner"]
        if (
            not isinstance(identity, str)
            or not 1 <= len(identity) <= 256
            or not isinstance(name, str)
            or name.casefold() != f"{owner}/{repo}".casefold()
        ):
            raise UnreadableItemError
        if repository["pull"] is None:
            raise PullDataError("not_found_or_private", "GitHub has no readable pull request here")
        return _graph_pull(repository["pull"], number)
    except READ_FAILURES as exc:
        raise _unreadable_pull() from exc


async def _read_api(
    owner: str,
    repo: str,
    number: int,
    *,
    previous: PullRecord | None,
    reader: str,
    on_core: Callable[[PullRequest], Awaitable[None]] | None = None,
    observe_reader: Callable[[str], None] | None = None,
) -> PullRecord:
    """Read every part of the pull request into a record with no comparison yet.

    *previous* is the cached record by the same reader, whose ETags make each request
    conditional; a ``304`` reuses its part. An ETag names one request path, and the
    check-run and status paths name the head commit, so a moved head asks afresh.
    """

    # A provider ETag identifies its representation, not the fields our older cache
    # retained. Fetch those existing resources unconditionally once for new metadata.
    if previous is not None and previous.projection_version < PULL_RECORD_PROJECTION:
        previous = previous.model_copy(update={"etags": {}})
    base = f"repos/{owner}/{repo}"
    etags: dict[str, str] = {}
    unavailable: dict[UnavailablePart, str] = {}
    pull_path = f"{base}/pulls/{number}"
    pull_etag = previous.etags.get(pull_path) if previous is not None else None
    if on_core is not None:
        # _refresh enables this only when no full record was cached. The actual
        # response viewer replaces a third local account subprocess; no REST ETag
        # is invented for this GraphQL representation.
        pull = await _read_graph_core(owner, repo, number, reader, observe_reader=observe_reader)
    else:
        try:
            response = await _get(pull_path, etag=pull_etag)
        except PageTooLargeError as exc:
            raise _unreadable_pull() from exc
        if response.status == 304:
            if previous is None or pull_etag is None:
                raise unconditional_304()
            pull = previous.pull
            etags[pull_path] = pull_etag
        else:
            try:
                pull = _pull(response_json(response), number)
            except READ_FAILURES as exc:
                raise _unreadable_pull() from exc
            if response.etag is not None:
                etags[pull_path] = response.etag

    head = pull.head.sha
    status_path = _first_page(f"{base}/commits/{head}/status")
    status_etag = previous.etags.get(status_path) if previous is not None else None

    async def read_check_runs(part_etags: dict[str, str]) -> _ListParts[CheckRun] | _Unavailable:
        try:
            return await _read_list_of(
                f"{base}/commits/{head}/check-runs",
                key="check_runs",
                cap=MAX_CHECK_RUNS,
                previous=previous,
                name="check_runs",
                build=_check_run,
                etags=part_etags,
            )
        except PullDataError as exc:
            if not _degrade(exc):
                raise
            return _Unavailable(exc.state)

    async def read_status(
        part_etags: dict[str, str],
    ) -> tuple[CombinedStatus | None, bool] | _Unavailable:
        try:
            response = await _get(status_path, etag=status_etag)
            if response.status == 304:
                if previous is None or status_etag is None:
                    raise unconditional_304()
                part_etags[status_path] = status_etag
                return previous.status, previous.truncated.statuses
            try:
                read = _status(response_json(response))
            except READ_FAILURES as exc:
                raise PullDataError(
                    "gh_failed", "GitHub answered with a status Metabrowser cannot read"
                ) from exc
            if response.etag is not None:
                part_etags[status_path] = response.etag
            return read
        except PageTooLargeError:
            return _Unavailable("gh_failed")
        except PullDataError as exc:
            if not _degrade(exc):
                raise
            return _Unavailable(exc.state)

    # The five parts are in flight together, each `gh` spawn its own connection: 0.44 to 0.93 s
    # each, 3.0 to 4.0 s in sequence, measured 2026-11-02, the same whether it answers 304 or
    # 200. Five is far inside GitHub's documented limit of 100 concurrent requests, and it is
    # the same requests the sequence made, each page of a long list still after the one before.
    # Each part has its own ETags and the first failure in this order is the one raised, so a
    # record and a refusal read as they did in sequence.
    part_etags: tuple[dict[str, str], ...] = ({}, {}, {}, {}, {})
    reading_comments = asyncio.ensure_future(
        _read_list_of(
            f"{base}/issues/{number}/comments",
            key=None,
            cap=MAX_ISSUE_COMMENTS,
            previous=previous,
            name="issue_comments",
            build=_issue_comment,
            etags=part_etags[0],
        )
    )
    reading_reviews = asyncio.ensure_future(
        _read_list_of(
            f"{base}/pulls/{number}/reviews",
            key=None,
            cap=MAX_REVIEWS,
            previous=previous,
            name="reviews",
            build=_review,
            etags=part_etags[1],
        )
    )
    reading_review_comments = asyncio.ensure_future(
        _read_list_of(
            f"{base}/pulls/{number}/comments",
            key=None,
            cap=MAX_REVIEW_COMMENTS,
            previous=previous,
            name="review_comments",
            build=_review_comment,
            etags=part_etags[2],
        )
    )
    reading_runs = asyncio.ensure_future(read_check_runs(part_etags[3]))
    reading_status = asyncio.ensure_future(read_status(part_etags[4]))
    reading = (
        reading_comments,
        reading_reviews,
        reading_review_comments,
        reading_runs,
        reading_status,
    )
    try:
        # The selected core already named its actual query viewer. Stage that verified
        # core while the existing five reads start; callback failure drains them.
        if on_core is not None:
            await on_core(pull)
        await asyncio.gather(*reading, return_exceptions=True)
    except BaseException:
        for task in reading:
            task.cancel()
        await asyncio.gather(*reading, return_exceptions=True)
        raise
    comments = reading_comments.result()
    reviews = reading_reviews.result()
    review_comments = reading_review_comments.result()
    read_runs = reading_runs.result()
    read_state = reading_status.result()
    for part in part_etags:
        etags.update(part)

    if isinstance(read_runs, _Unavailable):
        check_runs = _ListParts[CheckRun]((), False, False)
        unavailable["check_runs"] = read_runs.state
    else:
        check_runs = read_runs
    status: CombinedStatus | None = None
    statuses_cut = False
    if isinstance(read_state, _Unavailable):
        unavailable["status"] = read_state.state
    else:
        status, statuses_cut = read_state

    parts = (comments, reviews, review_comments, check_runs)
    return PullRecord(
        schema_version=PULL_RECORD_SCHEMA,
        projection_version=PULL_RECORD_PROJECTION,
        source=f"https://github.com/{owner}/{repo}",
        number=number,
        fetched_at=utc_stamp(utc_now()),
        reader=reader,
        etags=etags,
        pull=pull,
        issue_comments=comments.items,
        reviews=reviews.items,
        review_comments=review_comments.items,
        check_runs=check_runs.items,
        status=status,
        comparison=None,
        truncated=Truncation(
            issue_comments=comments.incomplete,
            reviews=reviews.incomplete,
            review_comments=review_comments.incomplete,
            check_runs=check_runs.incomplete,
            statuses=statuses_cut,
            # A reused list keeps any cut the text budget made in it.
            text=previous is not None
            and previous.truncated.text
            and any(part.reused for part in parts),
        ),
        unavailable=unavailable,
    )


# ── The refresh ─────────────────────────────────────────────────


def _owner_and_repo(published: PublishedSource | ListedRepository) -> tuple[str, str]:
    if isinstance(published, ListedRepository):
        return published.owner, published.repo
    parsed = parse_repository_url(published.source.normalized)
    if parsed is None:
        raise PullDataError(
            "not_github", f"{published.source.normalized} is not a GitHub repository"
        )
    return parsed


def _fetch_failure(exc: PullRefError) -> PullDataError:
    if exc.state == "not_found_or_private":
        return PullDataError("not_found_or_private", str(exc))
    if exc.state == "network_error":
        return PullDataError("network_error", str(exc))
    if exc.state == "refreshing_elsewhere":
        return PullDataError("refreshing_elsewhere", str(exc))
    if exc.state == "lender_missing":
        return PullDataError("lender_missing", str(exc))
    return PullDataError("fetch_failed", str(exc))


def _git_failure(number: int, exc: GitError) -> PullDataError:
    log.debug("a Git command failed for pull request %s: %s", number, exc)
    if isinstance(exc, UnsupportedGitVersionError):
        return PullDataError("git_failed", str(exc))
    return PullDataError(
        "git_failed",
        "a Git command failed while reading it (--log-level debug shows Git's own message)",
    )


def _comparison_of(endpoints: PullEndpoints) -> Comparison:
    return Comparison(
        base=endpoints.base,
        head=endpoints.head,
        base_commit=endpoints.base_commit,
        base_from=endpoints.base_from,
    )


async def _write(
    published: PublishedSource | ListedRepository,
    record: PullRecord,
    *,
    expected: PullRecord | RecordAbsence | None = None,
) -> PullRecord:
    try:
        final = fit_record(record)
        if not isinstance(published, ListedRepository):
            await prepare_pull_manifest(published, final)
        return await run_lock_section(
            partial(
                write_pull_record,
                published.home,
                published.slug,
                final,
                metadata_only=isinstance(published, ListedRepository),
                store_id=None if isinstance(published, ListedRepository) else published.store_id,
                expected=expected,
            )
        )
    except RecordTooLargeError as exc:
        raise PullDataError("record_too_large", str(exc)) from exc
    except (PrivateStorageError, OSError) as exc:
        log.debug("could not write pull request %s: %s", record.number, exc)
        raise PullDataError(
            "cache_unwritable", "its record could not be written to the cache"
        ) from exc


async def _with_comparison(
    published: PublishedSource, record: PullRecord, *, expected: PullRecord | RecordAbsence
) -> PullRecord:
    """Compute Files changed and write the record.

    A comparison that cannot be computed is left out and named in the record's
    ``unavailable``. One whose merge base is uncertain writes that record first, so a
    reader sees ``base_uncertain`` and not nothing while the store deepens within this job,
    and writes the record again if deepening settles it. Offline, the fetch fails at once
    and the first record stands: a guess is never shown.
    """

    pull = record.pull
    unavailable = dict(record.unavailable)

    def without(state: str) -> PullRecord:
        return record.model_copy(
            update={"comparison": None, "unavailable": {**unavailable, "comparison": state}}
        )

    try:
        endpoints = await comparison_endpoints(
            published,
            head=pull.head.sha,
            base_sha=pull.base.sha,
            base_branch=pull.base.ref,
            open_pull=pull.state == "open",
        )
    except BaseUncertainError as uncertain:
        log.debug("pull request %s has an uncertain merge base; deepening", pull.number)
        pending = without(uncertain.state)
        expected = await _write(published, pending, expected=expected)
        if expected != pending:
            return expected
        try:
            endpoints = await deepen_until_certain(
                published,
                pull.number,
                head=pull.head.sha,
                base_branch=pull.base.ref,
                uncertain=uncertain,
            )
        except PullRefError as exc:
            # Why it could not be settled goes to the log. What the reader needs is that
            # the base is uncertain, whatever stopped the deepening.
            log.debug("deepening pull request %s stopped: %s (%s)", pull.number, exc, exc.state)
            return await _write(published, without(uncertain.state), expected=expected)
    except PullRefError as exc:
        log.debug("pull request %s has no comparison: %s", pull.number, exc)
        return await _write(published, without(exc.state), expected=expected)
    return await _write(
        published,
        record.model_copy(
            update={
                "comparison": _comparison_of(endpoints),
                "unavailable": {
                    part: state for part, state in unavailable.items() if part != "comparison"
                },
            }
        ),
        expected=expected,
    )


async def prepare_pull_comparison(
    published: PublishedSource, record: PullRecord
) -> PullRecord | None:
    """Prepare the cached observation without repeating its GitHub metadata reads."""
    if record.comparison is not None:
        return record
    try:
        pull = record.pull
        if not await has_commit(published, pull.head.sha):
            fetched = await fetch_pull_head(
                published,
                record.number,
                base_branch=pull.base.ref if pull.state == "open" else None,
            )
            if fetched != pull.head.sha:
                return None
        return await _with_comparison(published, record, expected=record)
    except PullRefError as exc:
        raise _fetch_failure(exc) from exc
    except GitError as exc:
        raise _git_failure(record.number, exc) from exc


async def _refresh(
    published: PublishedSource | ListedRepository,
    number: int,
    *,
    on_core: Callable[[PullRequest | None, str | None], Awaitable[None]] | None = None,
    observe_reader: Callable[[str], None] | None = None,
) -> PullRecord:
    owner, repo = _owner_and_repo(published)
    cached = await asyncio.to_thread(read_pull_record, published.home, published.slug, number)
    # An existing full record always retains the original two-check refresh path.
    progress = on_core if not isinstance(cached, PullRecord) else None
    for attempt in range(_READ_ATTEMPTS):
        if progress is not None:
            await progress(None, None)
        login = await active_account()
        reader = f"gh:{login}"
        if observe_reader is not None:
            observe_reader(reader)
        previous = cached if isinstance(cached, PullRecord) and cached.reader == reader else None

        async def core_ready(pull: PullRequest, selected_reader: str = reader) -> None:
            if progress is not None:
                await progress(pull, selected_reader)

        record = await _read_api(
            owner,
            repo,
            number,
            previous=previous,
            reader=reader,
            on_core=core_ready if progress is not None else None,
            observe_reader=observe_reader,
        )
        final_login = await active_account()
        if observe_reader is not None:
            observe_reader(f"gh:{final_login}")
        if final_login != login:
            raise PullDataError(
                "account_changed",
                "the active gh account changed during the read, so what was read is "
                "discarded; open it again",
            )
        if isinstance(published, ListedRepository):
            # Merge against the latest shared comparison inside the publication lock,
            # not the cache snapshot taken before the network read.
            return await _write(published, record, expected=cached)
        pull = record.pull
        try:
            fetched = await fetch_pull_head(
                published, number, base_branch=pull.base.ref if pull.state == "open" else None
            )
        except PullRefError as exc:
            raise _fetch_failure(exc) from exc
        if fetched != pull.head.sha:
            if attempt + 1 < _READ_ATTEMPTS:
                if progress is not None:
                    await progress(None, None)
                continue
            raise PullDataError(
                "head_mismatch", "its head kept moving while it was read; open it again"
            )
        return await _with_comparison(published, record, expected=cached)
    raise AssertionError("unreachable")


async def _recover_comparison(
    published: PublishedSource, number: int, pair: tuple[str, str] | None
) -> None:
    """An explicit retry's displayed selection, or the cached selection for number-only retry."""
    from metabrowser.builtin_plugins.github.pull_manifest import invalidate_pull_manifest
    from metabrowser.cache.object_recovery import recover_comparison_objects
    from metabrowser.cache.origin import BRANCH_MIRROR_PREFIX
    from metabrowser.cache.pull_refs import base_branch_usable, ref_commit
    from metabrowser.git.object_failures import observed_object_failures
    from metabrowser.git.process import repository_store_target

    if pair is None:
        cached = await asyncio.to_thread(read_pull_record, published.home, published.slug, number)
        if not isinstance(cached, PullRecord):
            return
        if cached.comparison is not None:
            pair = (cached.comparison.base, cached.comparison.head)
        else:
            base = cached.pull.base.sha
            branch = cached.pull.base.ref
            if cached.pull.state == "open" and await base_branch_usable(published, branch):
                base = await ref_commit(published, BRANCH_MIRROR_PREFIX + branch) or base
            pair = (base, cached.pull.head.sha)
    target = repository_store_target(git_dir=published.git_dir)
    failures = observed_object_failures.pending(target, pair)
    if any(failure.state == "object_corrupt" for failure in failures):
        try:
            await asyncio.to_thread(invalidate_pull_manifest, published, pair)
        except (OSError, PrivateStorageError) as exc:
            raise PullDataError(
                "cache_unwritable", "the comparison cache could not discard damaged metadata"
            ) from exc
    try:
        await recover_comparison_objects(published, pair)
    except PullRefError as exc:
        state: PullDataState
        match exc.state:
            case "object_corrupt":
                state = "object_corrupt"
            case "commits_unavailable":
                state = "commits_unavailable"
            case "comparison_too_large":
                state = "comparison_too_large"
            case _:
                state = _fetch_failure(exc).state
        raise PullDataError(state, str(exc)) from exc


async def refresh_pull_request(
    published: PublishedSource | ListedRepository,
    number: int,
    *,
    recover: bool = False,
    recovery_pair: tuple[str, str] | None = None,
    on_core: Callable[[PullRequest | None, str | None], Awaitable[None]] | None = None,
    observe_reader: Callable[[str], None] | None = None,
) -> PullRecord:
    """Read pull request *number* of *published* from GitHub and cache it; see the module.

    *published* is a mirror's source, or a checkout's repository, which has no store: its
    source is published first if it has never been (:func:`~.checkout.claim_source`).
    A checkout preserves a shared comparison only for the same reader and unchanged
    comparison inputs; otherwise its record has no comparison, ``no_store``. Raises only
    :class:`PullDataError`. A failure leaves any previous record in place. How it ended is
    kept beside the record either way; see :func:`last_refresh`.
    """

    try:
        try:
            if isinstance(published, ListedRepository):
                published = await claim_source(published)
            elif recover:
                await _recover_comparison(published, number, recovery_pair)
            record = await _refresh(
                published, number, on_core=on_core, observe_reader=observe_reader
            )
        except GitError as exc:
            raise _git_failure(number, exc) from exc
    except PullDataError as exc:
        # A failed attempt cannot serve a provisional core while its stamp is written.
        if on_core is not None:
            await on_core(None, None)
        stamp = {
            "outcome": exc.state,
            "message": str(exc)[:1000],
            "reset_at": exc.reset_at,
            "at": utc_stamp(utc_now()),
        }
        await asyncio.to_thread(_keep_stamp, published, number, stamp)
        raise
    succeeded = {"outcome": "succeeded", "at": record.fetched_at}
    await asyncio.to_thread(_keep_stamp, published, number, succeeded)
    return record


def _keep_stamp(
    published: PublishedSource | ListedRepository, number: int, fields: dict[str, Any]
) -> None:
    try:
        stamp = PullRefreshStamp.model_validate(fields)
        write_pull_refresh(published.home, published.slug, number, stamp)
    except (PrivateStorageError, OSError, ValidationError) as exc:
        # Only the report of the refresh is lost; the record, if any, is written.
        log.debug("could not keep how pull request %s's refresh ended: %s", number, exc)


def last_refresh(
    published: PublishedSource | ListedRepository, number: int
) -> PullRefreshStamp | None:
    """How the last refresh of pull request *number* ended, in any process. Blocking."""

    return read_pull_refresh(published.home, published.slug, number)


def _summary(record: PullRecord) -> str:
    pull = record.pull
    if pull.merged:
        state = "merged"
    elif pull.state == "closed":
        state = "closed"
    else:
        state = "draft" if pull.draft else "open"
    return f"{state}; fetched {record.fetched_at} by {record.reader}"


def _pin(number: int, record: PullRecord, *, note: str = "") -> PullRequestPin:
    return PullRequestPin(
        number=number,
        head=record.pull.head.sha,
        ref=pull_head_ref(number),
        summary=_summary(record) + note,
    )


async def open_pull_request(
    published: PublishedSource, number: int, *, fetch: PullRequestFetch
) -> PullRequestPin:
    """The pin of pull request *number*, from its record, fetching only as *fetch* allows.

    ``if_missing`` answers from a cached record whose head the store has, with no call
    to gh or the network; otherwise, and always for ``always``, it refreshes first. A
    refresh that fails beside such a record answers from it and says why. Raises only
    :class:`PullDataError`.
    """

    record = await asyncio.to_thread(read_pull_record, published.home, published.slug, number)
    try:
        usable = isinstance(record, PullRecord) and await has_commit(
            published, record.pull.head.sha
        )
    except GitError as exc:
        raise _git_failure(number, exc) from exc
    if usable and isinstance(record, PullRecord) and fetch == "if_missing":
        return _pin(number, record)
    try:
        fresh = await refresh_pull_request(published, number)
    except PullDataError as exc:
        if not usable or not isinstance(record, PullRecord):
            raise
        return _pin(number, record, note=f"; the refresh failed: {exc} ({exc.state})")
    return _pin(number, fresh)


__all__ = [
    "PullDataError",
    "PullDataState",
    "last_refresh",
    "open_pull_request",
    "refresh_pull_request",
    "utc_now",
]
