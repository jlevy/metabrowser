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
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Final, Literal

from pydantic import BaseModel, ValidationError

from metabrowser.builtin_plugins.github.gh import GhError, GhResponse, gh_account, gh_api
from metabrowser.builtin_plugins.github.pull_record import (
    API_PAGE_SIZE,
    MAX_BODY_BYTES,
    MAX_CHECK_RUNS,
    MAX_DIFF_HUNK_BYTES,
    MAX_ISSUE_COMMENTS,
    MAX_LABELS,
    MAX_REVIEW_COMMENTS,
    MAX_REVIEWS,
    MAX_STATUSES,
    MAX_TITLE_BYTES,
    PULL_RECORD_SCHEMA,
    CheckRun,
    CombinedStatus,
    CommitStatus,
    Comparison,
    IssueComment,
    PullRecord,
    PullRequest,
    PullSide,
    RecordTooLargeError,
    Review,
    ReviewComment,
    Truncation,
    apply_text_budget,
    cut_text,
    read_pull_record,
    write_pull_record,
)
from metabrowser.builtin_plugins.github.urls import parse_repository_url
from metabrowser.cache.providers import PullRequestFetch, PullRequestPin
from metabrowser.cache.pull_refs import (
    PullRefError,
    comparison_endpoints,
    fetch_pull_head,
    has_commit,
    pull_head_ref,
)

if TYPE_CHECKING:
    from metabrowser.cache.acquire import PublishedSource

log = logging.getLogger(__name__)

# One re-read when the head moved between the API read and the fetch; a pull request
# pushed to faster than two full reads is reported rather than chased.
_READ_ATTEMPTS: Final = 2

type PullDataState = Literal[
    "gh_missing",
    "gh_too_old",
    "not_logged_in",
    "rate_limited",
    "not_found_or_private",
    "network_error",
    "gh_failed",
    "account_changed",
    "head_mismatch",
    "fetch_failed",
    "record_too_large",
    "not_github",
]


class PullDataError(Exception):
    """A pull request could not be read or fetched; ``state`` says why.

    The message is for the user: it names the pull request and never a local path, a
    token, or gh's or Git's own text.
    """

    def __init__(self, state: PullDataState, message: str, *, reset_at: str | None = None) -> None:
        super().__init__(message)
        self.state: PullDataState = state
        self.reset_at = reset_at


def utc_now() -> datetime:
    """The clock records are stamped with; a seam for transcripts."""

    return datetime.now(UTC)


def _stamp(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class _UnexpectedShapeError(Exception):
    pass


def _dict(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _UnexpectedShapeError
    return value  # pyright: ignore[reportUnknownVariableType]


def _login(user: object) -> str | None:
    if not isinstance(user, dict):
        return None
    login: object = user.get("login")  # pyright: ignore[reportUnknownMemberType]
    return login if isinstance(login, str) else None


def _text(value: object, limit: int = MAX_BODY_BYTES) -> tuple[str, bool]:
    return cut_text(value if isinstance(value, str) else "", limit)


def _side(value: object) -> PullSide:
    side = _dict(value)
    repo = side.get("repo")
    full_name = repo.get("full_name") if isinstance(repo, dict) else None  # pyright: ignore[reportUnknownMemberType]
    return PullSide(ref=side["ref"], sha=side["sha"], repository=full_name)


def _pull(value: object, number: int) -> PullRequest:
    item = _dict(value)
    if item.get("number") != number:
        raise _UnexpectedShapeError
    body, body_cut = _text(item.get("body"))
    title, _cut = _text(item.get("title"), MAX_TITLE_BYTES)
    labels = item.get("labels") or []
    mergeable = item.get("mergeable")
    return PullRequest(
        number=number,
        title=title,
        body=body,
        body_truncated=body_cut,
        state=item["state"],
        draft=bool(item.get("draft")),
        merged=bool(item.get("merged")),
        merge_commit_sha=item.get("merge_commit_sha"),
        mergeable="mergeable"
        if mergeable is True
        else "conflicting"
        if mergeable is False
        else "unknown",
        labels=tuple(_dict(label)["name"] for label in labels[:MAX_LABELS]),
        author=_login(item.get("user")),
        created_at=item["created_at"],
        updated_at=item["updated_at"],
        merged_at=item.get("merged_at"),
        closed_at=item.get("closed_at"),
        base=_side(item["base"]),
        head=_side(item["head"]),
        html_url=item["html_url"],
    )


def _issue_comment(value: object) -> IssueComment:
    item = _dict(value)
    body, cut = _text(item.get("body"))
    return IssueComment(
        id=item["id"],
        author=_login(item.get("user")),
        body=body,
        body_truncated=cut,
        created_at=item["created_at"],
        updated_at=item["updated_at"],
    )


def _review(value: object) -> Review:
    item = _dict(value)
    body, cut = _text(item.get("body"))
    return Review(
        id=item["id"],
        state=item["state"],
        author=_login(item.get("user")),
        body=body,
        body_truncated=cut,
        submitted_at=item.get("submitted_at"),
        commit_id=item.get("commit_id"),
    )


def _review_comment(value: object) -> ReviewComment:
    item = _dict(value)
    body, cut = _text(item.get("body"))
    hunk = item.get("diff_hunk")
    diff_hunk, hunk_cut = cut_text(
        hunk if isinstance(hunk, str) else "", MAX_DIFF_HUNK_BYTES, keep="tail"
    )
    return ReviewComment(
        id=item["id"],
        review_id=item.get("pull_request_review_id"),
        in_reply_to=item.get("in_reply_to_id"),
        path=item["path"],
        line=item.get("line"),
        original_line=item.get("original_line"),
        start_line=item.get("start_line"),
        original_start_line=item.get("original_start_line"),
        side=item.get("side"),
        commit_id=item["commit_id"],
        original_commit_id=item["original_commit_id"],
        diff_hunk=diff_hunk,
        diff_hunk_truncated=hunk_cut,
        author=_login(item.get("user")),
        body=body,
        body_truncated=cut,
        created_at=item["created_at"],
        updated_at=item["updated_at"],
    )


def _check_run(value: object) -> CheckRun:
    item = _dict(value)
    app = item.get("app")
    return CheckRun(
        id=item["id"],
        name=item["name"],
        status=item["status"],
        conclusion=item.get("conclusion"),
        details_url=item.get("details_url") or None,
        app=app.get("name") if isinstance(app, dict) else None,  # pyright: ignore[reportUnknownMemberType]
    )


def _status(value: object) -> tuple[CombinedStatus, bool]:
    item = _dict(value)
    statuses = [_dict(entry) for entry in item.get("statuses") or []]
    total = item.get("total_count")
    combined = CombinedStatus(
        state=item["state"],
        statuses=tuple(
            CommitStatus(
                context=entry["context"],
                state=entry["state"],
                description=entry.get("description"),
                target_url=entry.get("target_url") or None,
            )
            for entry in statuses[:MAX_STATUSES]
        ),
    )
    truncated = len(statuses) > MAX_STATUSES or (isinstance(total, int) and total > len(statuses))
    return combined, truncated


def _mapped[T](build: Callable[[object], T], value: object) -> T:
    try:
        return build(value)
    except (_UnexpectedShapeError, KeyError, TypeError, ValidationError) as exc:
        raise PullDataError(
            "gh_failed", "GitHub answered with a pull request Metabrowser cannot read"
        ) from exc


@dataclass(frozen=True, slots=True)
class _Page:
    """A list read from the API: new items, or the previous record's when unchanged."""

    items: list[object] | None
    truncated: bool
    etag: str | None


async def _get(path: str, *, etag: str | None) -> GhResponse:
    try:
        return await gh_api(path, etag=etag, now=utc_now())
    except GhError as exc:
        raise PullDataError(exc.state, str(exc), reset_at=exc.reset_at) from exc


def _page_items(response: GhResponse, key: str | None) -> list[object]:
    payload = response.json()
    if key is not None:
        payload = _dict(payload).get(key) if isinstance(payload, dict) else None
    if not isinstance(payload, list):
        raise PullDataError("gh_failed", "GitHub answered with a list Metabrowser cannot read")
    return payload  # pyright: ignore[reportUnknownVariableType]


def _unconditional_304() -> PullDataError:
    return PullDataError("gh_failed", "GitHub answered 304 to a request that was not conditional")


async def _read_list(path: str, *, key: str | None, cap: int, etag: str | None) -> _Page:
    """Every page of *path* up to *cap* items. *etag* makes the first page conditional."""

    items: list[object] = []
    first_etag: str | None = None
    page = 1
    while True:
        response = await _get(
            f"{path}?per_page={API_PAGE_SIZE}&page={page}", etag=etag if page == 1 else None
        )
        if response.status == 304:
            if page == 1 and etag is not None:
                return _Page(items=None, truncated=False, etag=etag)
            raise _unconditional_304()
        if page == 1:
            first_etag = response.etag
        items.extend(_page_items(response, key))
        if not response.has_next_page:
            return _Page(items=items[:cap], truncated=len(items) > cap, etag=first_etag)
        if len(items) >= cap:
            return _Page(items=items[:cap], truncated=True, etag=first_etag)
        page += 1


def _first_page(path: str) -> str:
    return f"{path}?per_page={API_PAGE_SIZE}&page=1"


def _reusable_etag(
    previous: PullRecord | None, path: str, items: Sequence[object], truncated: bool
) -> str | None:
    """The ETag worth sending for a list: only when the previous one fit on one page.

    A ``304`` for page one then means the whole list is unchanged.
    """

    if previous is None or truncated or len(items) >= API_PAGE_SIZE:
        return None
    return previous.etags.get(_first_page(path))


async def _read_list_of[M: BaseModel](
    path: str,
    *,
    key: str | None,
    cap: int,
    previous: PullRecord | None,
    name: Literal["issue_comments", "reviews", "review_comments", "check_runs"],
    build: Callable[[object], M],
    etags: dict[str, str],
) -> tuple[tuple[M, ...], bool]:
    """One list's models and whether it was cut, reusing *previous*'s on a ``304``."""

    etag = None
    if previous is not None:
        etag = _reusable_etag(
            previous, path, getattr(previous, name), getattr(previous.truncated, name)
        )
    page = await _read_list(path, key=key, cap=cap, etag=etag)
    if page.etag is not None:
        etags[_first_page(path)] = page.etag
    if page.items is None:
        # Only a conditional request, which needs a previous record, is answered 304.
        assert previous is not None
        return getattr(previous, name), getattr(previous.truncated, name)
    return tuple(_mapped(build, item) for item in page.items), page.truncated


async def _read_api(
    owner: str, repo: str, number: int, *, previous: PullRecord | None, reader: str
) -> PullRecord:
    """Read every part of the pull request into a record with no comparison yet.

    *previous* is the cached record by the same reader, whose ETags make each request
    conditional; a ``304`` reuses its part. An ETag names one request path, and the
    check-run and status paths name the head commit, so a moved head asks afresh.
    """

    base = f"repos/{owner}/{repo}"
    etags: dict[str, str] = {}
    pull_path = f"{base}/pulls/{number}"
    pull_etag = previous.etags.get(pull_path) if previous is not None else None
    response = await _get(pull_path, etag=pull_etag)
    if response.status == 304:
        if previous is None or pull_etag is None:
            raise _unconditional_304()
        pull = previous.pull
        etags[pull_path] = pull_etag
    else:
        pull = _mapped(lambda value: _pull(value, number), response.json())
        if response.etag is not None:
            etags[pull_path] = response.etag

    head = pull.head.sha
    issue_comments, comments_cut = await _read_list_of(
        f"{base}/issues/{number}/comments",
        key=None,
        cap=MAX_ISSUE_COMMENTS,
        previous=previous,
        name="issue_comments",
        build=_issue_comment,
        etags=etags,
    )
    reviews, reviews_cut = await _read_list_of(
        f"{base}/pulls/{number}/reviews",
        key=None,
        cap=MAX_REVIEWS,
        previous=previous,
        name="reviews",
        build=_review,
        etags=etags,
    )
    review_comments, review_comments_cut = await _read_list_of(
        f"{base}/pulls/{number}/comments",
        key=None,
        cap=MAX_REVIEW_COMMENTS,
        previous=previous,
        name="review_comments",
        build=_review_comment,
        etags=etags,
    )
    check_runs, check_runs_cut = await _read_list_of(
        f"{base}/commits/{head}/check-runs",
        key="check_runs",
        cap=MAX_CHECK_RUNS,
        previous=previous,
        name="check_runs",
        build=_check_run,
        etags=etags,
    )

    status_path = _first_page(f"{base}/commits/{head}/status")
    status_etag = previous.etags.get(status_path) if previous is not None else None
    response = await _get(status_path, etag=status_etag)
    if response.status == 304:
        if previous is None or status_etag is None:
            raise _unconditional_304()
        status, statuses_cut = previous.status, previous.truncated.statuses
        etags[status_path] = status_etag
    else:
        status, statuses_cut = _mapped(_status, response.json())
        if response.etag is not None:
            etags[status_path] = response.etag

    return PullRecord(
        schema_version=PULL_RECORD_SCHEMA,
        source=f"https://github.com/{owner}/{repo}",
        number=number,
        fetched_at=_stamp(utc_now()),
        reader=reader,
        etags=etags,
        pull=pull,
        issue_comments=issue_comments,
        reviews=reviews,
        review_comments=review_comments,
        check_runs=check_runs,
        status=status,
        comparison=None,
        truncated=Truncation(
            issue_comments=comments_cut,
            reviews=reviews_cut,
            review_comments=review_comments_cut,
            check_runs=check_runs_cut,
            statuses=statuses_cut,
            text=False,
        ),
    )


async def _account() -> str:
    try:
        return await gh_account()
    except GhError as exc:
        raise PullDataError(exc.state, str(exc)) from exc


def _owner_and_repo(published: PublishedSource) -> tuple[str, str]:
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
    return PullDataError("fetch_failed", str(exc))


async def refresh_pull_request(published: PublishedSource, number: int) -> PullRecord:
    """Read pull request *number* of *published* from GitHub and cache it; see the module.

    Raises :class:`PullDataError`. A failure leaves any previous record in place.
    """

    owner, repo = _owner_and_repo(published)
    cached = await asyncio.to_thread(read_pull_record, published.home, published.slug, number)
    for attempt in range(_READ_ATTEMPTS):
        login = await _account()
        reader = f"gh:{login}"
        previous = cached if isinstance(cached, PullRecord) and cached.reader == reader else None
        record = await _read_api(owner, repo, number, previous=previous, reader=reader)
        if await _account() != login:
            raise PullDataError(
                "account_changed",
                "the active gh account changed during the read, so what was read is "
                "discarded; open it again",
            )
        pull = record.pull
        try:
            fetched = await fetch_pull_head(
                published, number, base_branch=pull.base.ref if pull.state == "open" else None
            )
        except PullRefError as exc:
            raise _fetch_failure(exc) from exc
        if fetched != pull.head.sha:
            if attempt + 1 < _READ_ATTEMPTS:
                continue
            raise PullDataError(
                "head_mismatch",
                "its head kept moving while it was read; open it again",
            )
        comparison: Comparison | None = None
        try:
            endpoints = await comparison_endpoints(
                published,
                head=pull.head.sha,
                base_sha=pull.base.sha,
                base_branch=pull.base.ref,
                open_pull=pull.state == "open",
            )
        except PullRefError as exc:
            if exc.state != "no_merge_base":
                raise _fetch_failure(exc) from exc
            log.debug("pull request %s has no merge base", number)
        else:
            comparison = Comparison(
                base=endpoints.base,
                head=endpoints.head,
                base_commit=endpoints.base_commit,
                base_from=endpoints.base_from,
            )
        final = apply_text_budget(record.model_copy(update={"comparison": comparison}))
        try:
            await asyncio.to_thread(write_pull_record, published.home, published.slug, final)
        except RecordTooLargeError as exc:
            raise PullDataError("record_too_large", str(exc)) from exc
        return final
    raise AssertionError("unreachable")


def _summary(record: PullRecord) -> str:
    pull = record.pull
    if pull.merged:
        state = "merged"
    elif pull.state == "closed":
        state = "closed"
    else:
        state = "draft" if pull.draft else "open"
    return f"{state}; fetched {record.fetched_at} by {record.reader}"


async def open_pull_request(
    published: PublishedSource, number: int, *, fetch: PullRequestFetch
) -> PullRequestPin:
    """The pin of pull request *number*, from its record, fetching only as *fetch* allows.

    ``if_missing`` answers from a cached record whose head the store has, with no call
    to gh or the network; otherwise, and always for ``always``, it refreshes first.
    """

    record = await asyncio.to_thread(read_pull_record, published.home, published.slug, number)
    usable = (
        isinstance(record, PullRecord)
        and fetch == "if_missing"
        and await has_commit(published, record.pull.head.sha)
    )
    if not usable or not isinstance(record, PullRecord):
        try:
            record = await refresh_pull_request(published, number)
        except PullDataError as exc:
            if not isinstance(record, PullRecord):
                raise
            kept = f"{exc}; the record fetched {record.fetched_at} is kept"
            raise PullDataError(exc.state, kept, reset_at=exc.reset_at) from exc
    return PullRequestPin(
        number=number,
        head=record.pull.head.sha,
        ref=pull_head_ref(number),
        summary=_summary(record),
    )


__all__ = [
    "PullDataError",
    "PullDataState",
    "open_pull_request",
    "refresh_pull_request",
    "utc_now",
]
