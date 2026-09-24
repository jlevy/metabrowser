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
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Final, Literal

from pydantic import BaseModel, ValidationError

from metabrowser.builtin_plugins.github.gh import (
    GhError,
    GhOutputTooLargeError,
    GhResponse,
    gh_account,
    gh_api,
)
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
    UnavailablePart,
    cut_text,
    fit_record,
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
from metabrowser.git.process import GitError, UnsupportedGitVersionError
from metabrowser.home import PrivateStorageError

if TYPE_CHECKING:
    from metabrowser.cache.acquire import PublishedSource

log = logging.getLogger(__name__)

# One re-read when the head moved between the API read and the fetch; a pull request
# pushed to faster than two full reads is reported rather than chased.
_READ_ATTEMPTS: Final = 2
# Page sizes a list steps down through when a page is larger than gh's output cap, each
# a divisor of the one before, so every page starts on a page boundary of its size.
_PAGE_SIZES: Final[tuple[int, ...]] = (API_PAGE_SIZE, 50, 25, 5, 1)
# Requests one list may make: the full pages its cap needs, plus ten asked again smaller
# after an oversized page. Past it the list is marked incomplete.
_EXTRA_PAGE_REQUESTS: Final = 10
# GitHub refusals that fail only the part asked for: 403 or 404 (a token without checks
# access) and anything else it will not answer, such as a 422.
_PART_FAILURES: Final = frozenset({"not_found_or_private", "gh_failed"})
_SHORT_BYTES: Final = 1024
_MAX_URL_CHARS: Final = 4096
_MAX_PATH_CHARS: Final = 4096
_LOGIN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_\[\]-]{0,99}$")
_SHA = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")

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
    "refreshing_elsewhere",
    "git_failed",
    "record_too_large",
    "cache_unwritable",
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


# ── Mapping API answers onto the record ─────────────────────────


class _UnreadableItemError(Exception):
    """A required field is missing or not what GitHub documents."""


def _dict(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _UnreadableItemError
    return value  # pyright: ignore[reportUnknownVariableType]


def _short(value: object) -> str | None:
    """Optional short text, cut to its bound, or ``None``."""

    return cut_text(value, _SHORT_BYTES)[0] if isinstance(value, str) else None


def _required_short(value: object) -> str:
    text = _short(value)
    if text is None:
        raise _UnreadableItemError
    return text


def _url(value: object) -> str | None:
    """An https link, or ``None``: an ``http://`` or over-long link is left out."""

    if isinstance(value, str) and value.startswith("https://") and len(value) <= _MAX_URL_CHARS:
        return value
    return None


def _int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _required_int(value: object) -> int:
    number = _int(value)
    if number is None:
        raise _UnreadableItemError
    return number


def _sha(value: object) -> str | None:
    return value if isinstance(value, str) and _SHA.match(value) else None


def _login(user: object) -> str | None:
    login = user.get("login") if isinstance(user, dict) else None  # pyright: ignore[reportUnknownMemberType]
    return login if isinstance(login, str) and _LOGIN.match(login) else None


def _text(value: object, limit: int = MAX_BODY_BYTES) -> tuple[str, bool]:
    return cut_text(value if isinstance(value, str) else "", limit)


def _side(value: object) -> PullSide:
    side = _dict(value)
    repo = side.get("repo")
    full_name = repo.get("full_name") if isinstance(repo, dict) else None  # pyright: ignore[reportUnknownMemberType]
    return PullSide(
        ref=_required_short(side.get("ref")), sha=side["sha"], repository=_short(full_name)
    )


def _pull(value: object, number: int) -> PullRequest:
    item = _dict(value)
    if item.get("number") != number:
        raise _UnreadableItemError
    body, body_cut = _text(item.get("body"))
    title, _cut = _text(item.get("title"), MAX_TITLE_BYTES)
    labels = item.get("labels")
    names = (
        [_short(_dict(label).get("name")) for label in labels[:MAX_LABELS]]
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
        merge_commit_sha=_sha(item.get("merge_commit_sha")),
        mergeable="mergeable"
        if mergeable is True
        else "conflicting"
        if mergeable is False
        else "unknown",
        labels=tuple(name for name in names if name is not None),
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
        id=_required_int(item.get("id")),
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
        id=_required_int(item.get("id")),
        state=_required_short(item.get("state")),
        author=_login(item.get("user")),
        body=body,
        body_truncated=cut,
        submitted_at=item.get("submitted_at"),
        commit_id=_sha(item.get("commit_id")),
    )


def _review_comment(value: object) -> ReviewComment:
    item = _dict(value)
    body, cut = _text(item.get("body"))
    hunk = item.get("diff_hunk")
    diff_hunk, hunk_cut = cut_text(
        hunk if isinstance(hunk, str) else "", MAX_DIFF_HUNK_BYTES, keep="tail"
    )
    path = item.get("path")
    if not isinstance(path, str) or len(path) > _MAX_PATH_CHARS:
        raise _UnreadableItemError
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
        id=_required_int(item.get("id")),
        name=_required_short(item.get("name")),
        status=_required_short(item.get("status")),
        conclusion=_short(item.get("conclusion")),
        details_url=_url(item.get("details_url")),
        app=_short(app.get("name")) if isinstance(app, dict) else None,  # pyright: ignore[reportUnknownMemberType]
    )


def _commit_status(value: object) -> CommitStatus:
    entry = _dict(value)
    return CommitStatus(
        context=_required_short(entry.get("context")),
        state=_required_short(entry.get("state")),
        description=_short(entry.get("description")),
        target_url=_url(entry.get("target_url")),
    )


_READ_FAILURES: Final = (_UnreadableItemError, KeyError, TypeError, ValidationError)


def _items[M: BaseModel](
    values: Sequence[object], build: Callable[[object], M]
) -> tuple[tuple[M, ...], bool]:
    """The items that could be read, and whether any was left out."""

    kept: list[M] = []
    for value in values:
        try:
            kept.append(build(value))
        except _READ_FAILURES as exc:
            log.debug("left out an item GitHub sent that could not be read: %r", exc)
    return tuple(kept), len(kept) < len(values)


def _status(value: object) -> tuple[CombinedStatus, bool]:
    item = _dict(value)
    entries = item.get("statuses")
    listed: list[object] = entries[:MAX_STATUSES] if isinstance(entries, list) else []  # pyright: ignore[reportUnknownVariableType]
    statuses, dropped = _items(listed, _commit_status)
    total = _int(item.get("total_count"))
    count = len(entries) if isinstance(entries, list) else 0  # pyright: ignore[reportUnknownArgumentType]
    combined = CombinedStatus(state=_required_short(item.get("state")), statuses=statuses)
    return combined, dropped or count > MAX_STATUSES or (total is not None and total > count)


def _unreadable_pull() -> PullDataError:
    return PullDataError("gh_failed", "GitHub answered with a pull request Metabrowser cannot read")


# ── Reading the API ─────────────────────────────────────────────


class _PageTooLargeError(Exception):
    """One page was larger than gh's output cap."""


async def _get(path: str, *, etag: str | None) -> GhResponse:
    try:
        return await gh_api(path, etag=etag, now=utc_now())
    except GhOutputTooLargeError as exc:
        raise _PageTooLargeError from exc
    except GhError as exc:
        raise PullDataError(exc.state, str(exc), reset_at=exc.reset_at) from exc


def _json(response: GhResponse) -> object:
    try:
        return response.json()
    except GhError as exc:
        raise PullDataError("gh_failed", str(exc)) from exc


def _page_items(response: GhResponse, key: str | None) -> list[object]:
    payload = _json(response)
    if key is not None:
        payload = payload.get(key) if isinstance(payload, dict) else None  # pyright: ignore[reportUnknownMemberType]
    if not isinstance(payload, list):
        raise PullDataError("gh_failed", "GitHub answered with a list Metabrowser cannot read")
    return payload  # pyright: ignore[reportUnknownVariableType]


def _unconditional_304() -> PullDataError:
    return PullDataError("gh_failed", "GitHub answered 304 to a request that was not conditional")


@dataclass(frozen=True, slots=True)
class _ListRead:
    """A list read from the API: new items, or ``None`` when the previous one stands."""

    items: list[object] | None
    incomplete: bool
    etag: str | None


async def _read_list(path: str, *, key: str | None, cap: int, etag: str | None) -> _ListRead:
    """Every page of *path* up to *cap* items. *etag* makes the first page conditional.

    A page larger than gh's output cap is asked for again in smaller pages, down to one
    item; an item that alone is too large is left out and the list marked incomplete.
    """

    items: list[object] = []
    first_etag: str | None = None
    incomplete = False
    offset = 0
    size = API_PAGE_SIZE
    for _request in range(cap // API_PAGE_SIZE + _EXTRA_PAGE_REQUESTS):
        conditional = etag if offset == 0 and size == API_PAGE_SIZE else None
        try:
            response = await _get(
                f"{path}?per_page={size}&page={offset // size + 1}", etag=conditional
            )
        except _PageTooLargeError:
            if size > 1:
                size = next(smaller for smaller in _PAGE_SIZES if smaller < size)
            else:
                log.debug("left out item %s of %s: larger than one page may be", offset, path)
                offset += 1
                incomplete = True
            continue
        if response.status == 304:
            if conditional is not None:
                return _ListRead(items=None, incomplete=False, etag=etag)
            raise _unconditional_304()
        if offset == 0 and size == API_PAGE_SIZE:
            first_etag = response.etag
        batch = _page_items(response, key)
        items.extend(batch)
        offset += len(batch)
        if not batch or not response.has_next_page:
            return _ListRead(items[:cap], incomplete or len(items) > cap, first_etag)
        if len(items) >= cap:
            return _ListRead(items[:cap], True, first_etag)
        size = max(candidate for candidate in _PAGE_SIZES if offset % candidate == 0)
    return _ListRead(items[:cap], True, first_etag)


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
    items, dropped = _items(listed.items, build)
    return _ListParts(items, listed.incomplete or dropped, False)


def _degrade(exc: PullDataError) -> bool:
    return exc.state in _PART_FAILURES


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
    unavailable: dict[UnavailablePart, str] = {}
    pull_path = f"{base}/pulls/{number}"
    pull_etag = previous.etags.get(pull_path) if previous is not None else None
    try:
        response = await _get(pull_path, etag=pull_etag)
    except _PageTooLargeError as exc:
        raise _unreadable_pull() from exc
    if response.status == 304:
        if previous is None or pull_etag is None:
            raise _unconditional_304()
        pull = previous.pull
        etags[pull_path] = pull_etag
    else:
        try:
            pull = _pull(_json(response), number)
        except _READ_FAILURES as exc:
            raise _unreadable_pull() from exc
        if response.etag is not None:
            etags[pull_path] = response.etag

    head = pull.head.sha
    comments = await _read_list_of(
        f"{base}/issues/{number}/comments",
        key=None,
        cap=MAX_ISSUE_COMMENTS,
        previous=previous,
        name="issue_comments",
        build=_issue_comment,
        etags=etags,
    )
    reviews = await _read_list_of(
        f"{base}/pulls/{number}/reviews",
        key=None,
        cap=MAX_REVIEWS,
        previous=previous,
        name="reviews",
        build=_review,
        etags=etags,
    )
    review_comments = await _read_list_of(
        f"{base}/pulls/{number}/comments",
        key=None,
        cap=MAX_REVIEW_COMMENTS,
        previous=previous,
        name="review_comments",
        build=_review_comment,
        etags=etags,
    )
    try:
        check_runs = await _read_list_of(
            f"{base}/commits/{head}/check-runs",
            key="check_runs",
            cap=MAX_CHECK_RUNS,
            previous=previous,
            name="check_runs",
            build=_check_run,
            etags=etags,
        )
    except PullDataError as exc:
        if not _degrade(exc):
            raise
        check_runs = _ListParts[CheckRun]((), False, False)
        unavailable["check_runs"] = exc.state

    status_path = _first_page(f"{base}/commits/{head}/status")
    status_etag = previous.etags.get(status_path) if previous is not None else None
    status: CombinedStatus | None = None
    statuses_cut = False
    try:
        response = await _get(status_path, etag=status_etag)
        if response.status == 304:
            if previous is None or status_etag is None:
                raise _unconditional_304()
            status, statuses_cut = previous.status, previous.truncated.statuses
            etags[status_path] = status_etag
        else:
            try:
                status, statuses_cut = _status(_json(response))
            except _READ_FAILURES as exc:
                raise PullDataError(
                    "gh_failed", "GitHub answered with a status Metabrowser cannot read"
                ) from exc
            if response.etag is not None:
                etags[status_path] = response.etag
    except _PageTooLargeError:
        unavailable["status"] = "gh_failed"
    except PullDataError as exc:
        if not _degrade(exc):
            raise
        unavailable["status"] = exc.state

    parts = (comments, reviews, review_comments, check_runs)
    return PullRecord(
        schema_version=PULL_RECORD_SCHEMA,
        source=f"https://github.com/{owner}/{repo}",
        number=number,
        fetched_at=_stamp(utc_now()),
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
    if exc.state == "refreshing_elsewhere":
        return PullDataError("refreshing_elsewhere", str(exc))
    return PullDataError("fetch_failed", str(exc))


def _git_failure(number: int, exc: GitError) -> PullDataError:
    log.debug("a Git command failed for pull request %s: %s", number, exc)
    if isinstance(exc, UnsupportedGitVersionError):
        return PullDataError("git_failed", str(exc))
    return PullDataError(
        "git_failed",
        "a Git command failed while reading it (--log-level debug shows Git's own message)",
    )


async def _comparison(
    published: PublishedSource, pull: PullRequest, unavailable: dict[UnavailablePart, str]
) -> Comparison | None:
    """Files changed, or ``None`` with the reason recorded in *unavailable*."""

    try:
        endpoints = await comparison_endpoints(
            published,
            head=pull.head.sha,
            base_sha=pull.base.sha,
            base_branch=pull.base.ref,
            open_pull=pull.state == "open",
        )
    except PullRefError as exc:
        log.debug("pull request %s has no comparison: %s", pull.number, exc)
        unavailable["comparison"] = exc.state
        return None
    return Comparison(
        base=endpoints.base,
        head=endpoints.head,
        base_commit=endpoints.base_commit,
        base_from=endpoints.base_from,
    )


async def _write(published: PublishedSource, record: PullRecord) -> PullRecord:
    try:
        final = fit_record(record)
        await asyncio.to_thread(write_pull_record, published.home, published.slug, final)
    except RecordTooLargeError as exc:
        raise PullDataError("record_too_large", str(exc)) from exc
    except (PrivateStorageError, OSError) as exc:
        log.debug("could not write pull request %s: %s", record.number, exc)
        raise PullDataError(
            "cache_unwritable", "its record could not be written to the cache"
        ) from exc
    return final


async def _refresh(published: PublishedSource, number: int) -> PullRecord:
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
                "head_mismatch", "its head kept moving while it was read; open it again"
            )
        unavailable = dict(record.unavailable)
        comparison = await _comparison(published, pull, unavailable)
        return await _write(
            published,
            record.model_copy(update={"comparison": comparison, "unavailable": unavailable}),
        )
    raise AssertionError("unreachable")


async def refresh_pull_request(published: PublishedSource, number: int) -> PullRecord:
    """Read pull request *number* of *published* from GitHub and cache it; see the module.

    Raises only :class:`PullDataError`. A failure leaves any previous record in place.
    """

    try:
        return await _refresh(published, number)
    except GitError as exc:
        raise _git_failure(number, exc) from exc


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
    "open_pull_request",
    "refresh_pull_request",
    "utc_now",
]
