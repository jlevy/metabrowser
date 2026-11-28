"""Read a pull request with ``gh api``, fetch its commits, and keep its record.

:func:`refresh_pull_request` is the whole network job for one pull request:

1. the active github.com account, from a conditional ``gh api user``
   (:func:`~.gh_lists.active_account`);
2. the pull request, its issue comments, reviews, and review comments, each with
   ``gh api``, 100 per page up to each list's cap, sending ``If-None-Match`` where the
   previous record by the same reader holds an ETag and reusing that record's list on a
   ``304``;
3. the account again: a record read while the active account changed is discarded;
4. ``refs/pull/<n>/head`` into the store, which must name the head the API reported
   (one more full read if it moved meanwhile, then ``head_mismatch``);
5. the comparison endpoints, then the record, written atomically; and
6. its operational status, one GraphQL query kept apart from the record
   (:func:`~.pull_status_read.keep_pull_status`), unless the prefetch asked: the only
   read of whether it conflicts and how its checks stand.

:func:`refresh_pull_status` is that last step alone, for a change only the status shows.

A part that fails on its own does not fail the record. A comparison whose base cannot be
fetched or shares no history with the head is left out and named in the record's
``unavailable``; a status read that fails is kept as how that read ended, and the status
an earlier one kept stays. An item
GitHub sends that cannot be read, or that alone is larger than a page may be, is left
out and its list marked incomplete; an optional field that cannot be read, such as an
``http://`` link, is left empty. Everything else that fails raises
:class:`PullDataError`, and nothing else escapes.

It runs as a refresh-coordinator job keyed by the store and the pull-request number
(:mod:`.served_pull`), which ``POST`` routes start or join. The one-shot CLI also runs it:
the first ``--show`` or ``--api`` of a pull-request URL when no usable record is cached,
and ``--no-serve`` every time.

``gh api`` refuses every request while gh is signed out (checked 2026-09-23 with gh
2.98.0, which exits 4 and asks for ``gh auth login``), so a record is always read by a
signed-in account and ``reader`` is always ``gh:<login>``.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import partial
from time import monotonic_ns
from typing import TYPE_CHECKING, Any, Final, Literal

from pydantic import BaseModel, ValidationError

from metabrowser import event_log
from metabrowser.builtin_plugins.github import gh_budget
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
    asked_repository,
    cache_unwritable,
    get_response,
    login_of,
    read_list,
    readable_items,
    response_json,
    unconditional_304,
    utc_stamp,
)
from metabrowser.builtin_plugins.github.pull_freshness import described, mergeability_pending
from metabrowser.builtin_plugins.github.pull_list import ListedRepository
from metabrowser.builtin_plugins.github.pull_manifest import prepare_pull_manifest
from metabrowser.builtin_plugins.github.pull_record import (
    API_PAGE_SIZE,
    MAX_BODY_BYTES,
    MAX_DIFF_HUNK_BYTES,
    MAX_ISSUE_COMMENTS,
    MAX_LABELS,
    MAX_PULL_COMMITS,
    MAX_REVIEW_COMMENTS,
    MAX_REVIEWS,
    MAX_TITLE_BYTES,
    PULL_RECORD_PROJECTION,
    PULL_RECORD_SCHEMA,
    Comparison,
    IssueComment,
    PullLabel,
    PullObservationSuperseded,
    PullRecord,
    PullRefreshStamp,
    PullRefreshTiming,
    PullRequest,
    PullSide,
    RecordAbsence,
    RecordTooLargeError,
    Review,
    ReviewComment,
    Truncation,
    cut_text,
    fit_record,
    label_color,
    label_description,
    pull_observation_key,
    read_pull_record,
    read_pull_refresh,
    write_pull_record,
    write_pull_refresh,
)
from metabrowser.builtin_plugins.github.pull_status import PullStatus, merge_state
from metabrowser.builtin_plugins.github.pull_status_read import (
    keep_pull_status,
    keep_status_failure,
)
from metabrowser.builtin_plugins.github.pull_status_store import CheckProbes, ProbedPage
from metabrowser.builtin_plugins.github.refresh_metrics import begin_counting, finish_counting
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
# access) and anything else it will not answer, such as a 422. A probe of the checks that
# meets one stops probing that head's checks (:class:`.pull_status_store.CheckProbes`).
_PART_FAILURES: Final = frozenset({"not_found_or_private", "gh_failed"})
_SHORT_BYTES: Final = 1024
_MAX_URL_CHARS: Final = 4096
_MAX_PATH_CHARS: Final = 4096
_SHA = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")


# Selected, initially missing records use a core whose response names its viewer.
# Existing full-record refreshes keep conditional REST and their original two checks.
_CORE_FIELDS: Final = """
      number url title body state isDraft merged createdAt updatedAt closedAt mergedAt
      author { __typename login avatar_url:avatarUrl(size:40) }
      mergedBy { __typename login avatar_url:avatarUrl(size:40) }
      baseRefName baseRefOid baseRepository { nameWithOwner }
      headRefName headRefOid headRepository { nameWithOwner }
      mergeCommit { oid } potentialMergeCommit { oid }
      commits(first:1) { totalCount }
      labels(first:100) { nodes { name color description } }"""
_CORE_QUERY: Final = (
    """query PullCore($owner:String!,$name:String!,$number:Int!) {
  viewer { login }
  rateLimit { cost }
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


def _label(value: object) -> PullLabel | None:
    """A label of the REST or GraphQL answer, or ``None`` for one without a name.

    A color that is not six hex digits is left out, and the label is drawn neutral.
    """

    label = as_dict(value)
    name = _short(label.get("name"))
    if name is None:
        return None
    return PullLabel(
        name=name,
        color=label_color(label.get("color")),
        description=label_description(_short(label.get("description"))),
    )


def _pull(value: object, number: int) -> PullRequest:
    item = as_dict(value)
    if item.get("number") != number:
        raise UnreadableItemError
    body, body_cut = _text(item.get("body"))
    title, _cut = _text(item.get("title"), MAX_TITLE_BYTES)
    labels = item.get("labels")
    listed: list[object] = labels[:MAX_LABELS] if isinstance(labels, list) else []  # pyright: ignore[reportUnknownVariableType]
    read = [_label(label) for label in listed]
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
        labels=tuple(label for label in read if label is not None),
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


type _ListName = Literal["issue_comments", "reviews", "review_comments"]


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


# The apps whose REST login is not ``<GraphQL login>[bot]``, by GraphQL login. The Copilot
# coding agent's pull requests, read 2026-11-23 (makr-code/ThemisDB#8365 and
# t-h-omy/Volcanae#396, review C1 on #709): GraphQL ``author`` answers ``{"__typename":
# "Bot", "login": "copilot-swe-agent"}`` and REST ``user`` answers ``{"login": "Copilot",
# "type": "Bot"}``, with the same account id, 198982749, both ways.
_REST_BOT_LOGINS: Final[dict[str, str]] = {"copilot-swe-agent": "Copilot"}


def _rest_actor(actor: object) -> object:
    """*actor* as REST names it: GraphQL names an app by its slug (``dependabot``) and REST
    by its bot account (``dependabot[bot]``), or by the name :data:`_REST_BOT_LOGINS`
    holds for an app that breaks that rule. A record read either way then compares equal,
    and a probe of a cold open's record does not find the author changed (review B2, #709).
    An app that breaks the rule and is not listed is named ``<slug>[bot]`` until the first
    REST read.
    """

    if not isinstance(actor, dict):
        return actor
    login = actor.get("login")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    if actor.get("__typename") == "Bot" and isinstance(login, str) and not login.endswith("[bot]"):  # pyright: ignore[reportUnknownMemberType]
        rest_login = _REST_BOT_LOGINS.get(login, f"{login}[bot]")
        return {**actor, "login": rest_login}  # pyright: ignore[reportUnknownArgumentType]
    return actor  # pyright: ignore[reportUnknownVariableType]


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
            "merged_by": _rest_actor(item["mergedBy"]),
            "commits": as_dict(item["commits"])["totalCount"],
            "merge_commit_sha": None if merged_commit is None else as_dict(merged_commit)["oid"],
            "labels": as_dict(item["labels"])["nodes"],
            "user": _rest_actor(item["author"]),
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
        identity = repository["id"]
        # No id of the repository is known here, so GitHub's answer for the name is it,
        # renamed or not, as the REST reads after it follow their redirects.
        if (
            not isinstance(identity, str)
            or not 1 <= len(identity) <= 256
            or not asked_repository(repository, None)
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
    conditional; a ``304`` reuses its part. An ETag names one request path.

    Whether it conflicts and how its checks stand are not the record's: the status read
    after it reads them (:func:`~.pull_status_read.keep_pull_status`).
    """

    # A provider ETag identifies its representation, not the fields our older cache
    # retained. Fetch those existing resources unconditionally once for new metadata.
    if previous is not None and previous.projection_version < PULL_RECORD_PROJECTION:
        previous = previous.model_copy(update={"etags": {}})
    base = f"repos/{owner}/{repo}"
    etags: dict[str, str] = {}
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

    # The three parts are in flight together, each `gh` spawn its own connection: 0.44 to
    # 0.93 s each, the same whether it answers 304 or 200, measured 2026-11-02, when a
    # record read five parts and they took 3.0 to 4.0 s in sequence. Three is far inside
    # GitHub's documented limit of 100 concurrent requests, and it is the same requests the
    # sequence made, each page of a long list still after the one before. Each part has its
    # own ETags and the first failure in this order is the one raised, so a record and a
    # refusal read as they did in sequence.
    part_etags: tuple[dict[str, str], ...] = ({}, {}, {})
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
    reading = (reading_comments, reading_reviews, reading_review_comments)
    try:
        # The selected core already named its actual query viewer. Stage that verified
        # core while the existing reads start; callback failure drains them.
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
    for part in part_etags:
        etags.update(part)

    parts = (comments, reviews, review_comments)
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
        comparison=None,
        truncated=Truncation(
            issue_comments=comments.incomplete,
            reviews=reviews.incomplete,
            review_comments=review_comments.incomplete,
            # A reused list keeps any cut the text budget made in it.
            text=previous is not None
            and previous.truncated.text
            and any(part.reused for part in parts),
        ),
        unavailable={},
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
        owner, repo = _owner_and_repo(published)
        raise cache_unwritable(
            f"the record of pull request #{record.number}",
            exc,
            source=f"https://github.com/{owner}/{repo}",
            checkout=isinstance(published, ListedRepository) and published.checkout,
        ) from exc


class NeedsDeepening(Exception):
    """Optional work found an uncertain merge base, which only a reader's request deepens."""


async def _with_comparison(
    published: PublishedSource,
    record: PullRecord,
    *,
    expected: PullRecord | RecordAbsence,
    exact_base: bool = False,
    published_records: list[PullRecord] | None = None,
    optional: bool = False,
) -> PullRecord:
    """Compute Files changed and write the record.

    *published_records* is told the pending record this writes before deepening, so a
    failure after it stamps the observation that is on disk.

    *optional* work publishes only a computed comparison: where this would write the
    comparison's absence it raises :class:`PullDataError` instead, and an uncertain merge
    base is neither written nor deepened but raises :class:`NeedsDeepening`, since
    deepening fetches more than the pull request's head and base.

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
            open_pull=pull.state == "open" and not exact_base,
        )
    except BaseUncertainError as uncertain:
        if optional:
            raise NeedsDeepening from uncertain
        log.debug("pull request %s has an uncertain merge base; deepening", pull.number)
        # A write another writer won raises, so the second write expects the first.
        expected = await _write(published, without(uncertain.state), expected=expected)
        if published_records is not None:
            published_records.append(expected)
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
        if optional:
            raise _fetch_failure(exc) from exc
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
    published: PublishedSource,
    record: PullRecord,
    *,
    optional: bool = False,
) -> PullRecord | None:
    """Prepare the cached observation without repeating its GitHub metadata reads.

    *optional* work publishes nothing but a computed comparison, and raises
    :class:`PullDataError` or :class:`NeedsDeepening` for anything else (see
    :func:`_with_comparison`).
    """
    if record.comparison is not None:
        return record
    try:
        pull = record.pull
        if not await has_commit(published, pull.head.sha):
            fetched = await fetch_pull_head(
                published,
                record.number,
                expected_head=pull.head.sha,
            )
            if fetched != pull.head.sha:
                return None
        return await _with_comparison(
            published,
            record,
            expected=record,
            exact_base=True,
            optional=optional,
        )
    except PullRefError as exc:
        raise _fetch_failure(exc) from exc
    except GitError as exc:
        raise _git_failure(record.number, exc) from exc


async def _refresh(
    published: PublishedSource | ListedRepository,
    number: int,
    *,
    cached: PullRecord | RecordAbsence,
    on_core: Callable[[PullRequest | None, str | None], Awaitable[None]] | None = None,
    observe_reader: Callable[[str], None] | None = None,
    published_records: list[PullRecord] | None = None,
) -> PullRecord:
    owner, repo = _owner_and_repo(published)
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
            # not the cache snapshot taken before the network read: a checkout's read is
            # the newest metadata, and the merge keeps a mirror's comparison that fits it.
            return await _write(published, record)
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
        return await _with_comparison(
            published, record, expected=cached, published_records=published_records
        )
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
            await asyncio.to_thread(invalidate_pull_manifest, published, number, pair)
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
    adopt_current: bool = False,
) -> PullRecord:
    """Read pull request *number* of *published* from GitHub and cache it; see the module.

    *published* is a mirror's source, or a checkout's repository, which has no store: its
    source is published first if it has never been (:func:`~.checkout.claim_source`).
    A checkout preserves a shared comparison only for the same reader and unchanged
    comparison inputs; otherwise its record has no comparison, ``no_store``. Raises only
    :class:`PullDataError` on failure. If another writer published a mirror's record
    first, raises :class:`PullObservationSuperseded` with that record and stamps nothing;
    with *adopt_current* it returns that record instead.
    A failure leaves any previous record in place. How it ended is
    kept beside the record either way; see :func:`last_refresh`.

    What ``updated_at`` does not track, whether it conflicts and how its checks stand, is
    its operational status, read last; :func:`refresh_pull_status` reads that alone.
    """

    cached: PullRecord | RecordAbsence = "not_cached"
    # What this refresh itself published before it failed, which its failure stamp
    # then describes.
    published_records: list[PullRecord] = []
    try:
        try:
            if isinstance(published, ListedRepository):
                published = await claim_source(published)
            cached = await asyncio.to_thread(
                read_pull_record, published.home, published.slug, number
            )
            if recover and not isinstance(published, ListedRepository):
                await _recover_comparison(published, number, recovery_pair)
            started_ns = monotonic_ns()
            answers, measurement = begin_counting()
            try:
                record = await _refresh(
                    published,
                    number,
                    cached=cached,
                    on_core=on_core,
                    observe_reader=observe_reader,
                    published_records=published_records,
                )
            finally:
                finish_counting(measurement)
                finished_at = utc_now()
                duration_ms = round((monotonic_ns() - started_ns) / 1_000_000)
                github = answers.snapshot()
                if github is not None:
                    event_log.current().set(
                        provider="github_cli",
                        request_count=github.request_count,
                        response_body_bytes=github.response_body_bytes,
                        refresh_finished_at=finished_at.isoformat().replace("+00:00", "Z"),
                        refresh_duration_ms=duration_ms,
                    )
        except GitError as exc:
            raise _git_failure(number, exc) from exc
    except PullObservationSuperseded as exc:
        if on_core is not None:
            await on_core(None, None)
        if adopt_current:
            return exc.current
        raise
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
        observed = published_records[-1] if published_records else cached
        await run_lock_section(partial(_keep_stamp, published, number, stamp, observed))
        raise
    succeeded = {"outcome": "succeeded", "at": record.fetched_at}
    timing = (
        None
        if github is None
        else PullRefreshTiming(
            observation=pull_observation_key(record),
            finished_at=finished_at,
            duration_ms=duration_ms,
            github=github,
        )
    )
    await run_lock_section(partial(_keep_stamp, published, number, succeeded, record, timing))
    if not gh_budget.speculating():
        # The page's own read of its operational status, after the record is published,
        # so the record is shown no later than before. A failure fails the status alone.
        # The prefetch's records, which nobody is looking at, leave it to the page's read:
        # their caps are priced without it (``POINTS_PER_RECORD`` in pull_prefetch.py).
        owner, repo = _owner_and_repo(published)
        await keep_pull_status(
            published, owner, repo, number, reader=record.reader, now=lambda: utc_now()
        )
    return record


async def refresh_pull_status(
    published: PublishedSource | ListedRepository, number: int
) -> PullStatus | None:
    """Read pull request *number*'s operational status alone and keep it; the status, or ``None``.

    For what changes the status and not the record: a check a probe saw change, a
    mergeability GitHub has since computed, a status a window old, or a page with no
    status for its record's head. One account check, a conditional read that spends
    nothing while the login is the same, names the reader, and one GraphQL query reads
    the status as that reader (:func:`~.pull_status_read.keep_pull_status`). Nothing of
    the record is read over REST and nothing of it is written, so its revision, its
    comparison, and how its last refresh ended stand.

    A failure fails the status alone: it is kept as how the status's read ended, and the
    status an earlier read kept stays. Raises only :class:`PullDataError`, and only for a
    source that is not a GitHub repository's.
    """

    owner, repo = _owner_and_repo(published)
    started = utc_now()
    try:
        login = await active_account()
    except PullDataError as exc:
        await keep_status_failure(
            published, owner, repo, number, exc, now=lambda: utc_now(), started=started
        )
        return None
    return await keep_pull_status(
        published,
        owner,
        repo,
        number,
        reader=f"gh:{login}",
        now=lambda: utc_now(),
        started=started,
    )


# ── Probing ────────────────────────────────────────────────────

type ProbeOutcome = Literal["unchanged", "changed", "checks_changed", "behind"]


@dataclass(frozen=True, slots=True)
class IssueSeen:
    """The pull request's issue as a probe last saw it: its ``updated_at`` and that answer's ETag.

    It outlives the record it was read beside, since a ``304`` for the ETag says the issue
    still has this ``updated_at`` whichever record is held.

    It is kept in memory alone, so the first probe of a number in a process is one paid
    read, where a probe of the pull sent the record's own ETag for free: one ``core`` per
    number per server run, and one per one-shot automatic ask. Keeping it on disk would
    take a new file beside the record or one more ``gh`` process in every full read, and
    neither is worth that call (review A2 on #726).
    """

    updated_at: str
    etag: str


@dataclass(frozen=True, slots=True)
class PullProbe:
    """What one probe found: whether the record and its status still describe GitHub.

    ``changed`` says the pull request moved past the record, ``checks_changed`` that only
    its operational status did, a check or its mergeability, and ``behind`` that GitHub's
    issue answer is older than the record, which is an answer that lags and not a change.

    ``etags`` holds the ETag of each pull page GitHub answered ``200`` without changing
    the mergeability the status holds, for the next probe to send instead of the record's.
    ``seen`` is the issue as this probe found it, for the next probe to send; ``None``
    when GitHub sent no ETag with it. ``updated_at`` is the issue's, whether or not it came
    with an ETag. ``checks`` is what the probes of the head's checks saw now, for the next
    probe to compare with, when it differs from what this one was given.
    """

    outcome: ProbeOutcome
    etags: dict[str, str]
    seen: IssueSeen | None = None
    updated_at: str | None = None
    checks: CheckProbes | None = None


# What a probe of a pull request reads: its issue, ``repos/o/r/issues/<n>``, not the pull.
# The pull's representation embeds its base and head repository objects, so its ETag moves
# with the whole repository; the issue's embeds no repository, and its ``updated_at`` is
# the pull request's own. Measured 2026-11-23, 01:47 to 02:32 UTC, with gh 2.98.0:
# conditional reads of both representations of ten open pull requests, every 15 to 20 s,
# in NixOS/nixpkgs (six), jlevy/metabrowser (two), pytorch/pytorch, and rust-lang/rust,
# 661 rounds in all.
#
# - The pull answered ``200`` with its ``updated_at`` unchanged 90 times. Across the 86
#   bodies kept after each pull's first, what differed from the one before was the base
#   repository's ``open_issues_count`` (56 times, so any issue or pull request opened or
#   closed), its ``pushed_at`` (40), and the pull's ``mergeable`` as GitHub recomputed
#   it (20). The last is something a page shows and the issue does not carry, which is
#   why a pull request whose status has not settled its mergeability has the pull asked
#   too (:func:`mergeability_probe_path`).
# - The issue answered ``304`` in all 90 of those rounds.
# - The issue answered ``200`` twice, both in the round the pull's ``updated_at`` moved:
#   labels a bot added (02:08:12, seen 02:08:31) and a force-push of the head (02:19:22,
#   seen 02:19:32), where the issue's body differed only in ``updated_at``.
#
# So a probe of the issue costs a ``core`` call when the pull request changes, not when
# its repository does, and the bound on paid probes the plan proposed is not built.
PROBE_RESOURCE: Final = "issues"


def probe_path(published: PublishedSource | ListedRepository, number: int) -> str:
    """The path a probe of pull request *number* asks: its issue (:data:`PROBE_RESOURCE`)."""

    owner, repo = _owner_and_repo(published)
    return f"repos/{owner}/{repo}/{PROBE_RESOURCE}/{number}"


# A time as GitHub's REST API spells one and a record keeps it, so two compare as text.
_TIMESTAMP = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")


def _issue_updated_at(value: object, number: int) -> str:
    item = as_dict(value)
    updated = item.get("updated_at")
    if item.get("number") != number or not isinstance(updated, str):
        raise UnreadableItemError
    if not _TIMESTAMP.match(updated):
        raise UnreadableItemError
    return updated


def mergeability_probe_path(
    published: PublishedSource | ListedRepository,
    record: PullRecord,
    status: PullStatus | None,
) -> str | None:
    """The pull's own path, which a probe asks while GitHub has not settled its mergeability.

    That is while *status*, the kept status of *record*'s head, has an ``unknown``
    ``conflicts`` or ``merge_state`` (:func:`~.pull_freshness.mergeability_pending`).
    ``None`` otherwise: the pull's ETag moves with its whole repository
    (:data:`PROBE_RESOURCE`), so it is asked only for what no other page says.
    """

    if not mergeability_pending(record, status):
        return None
    owner, repo = _owner_and_repo(published)
    return f"repos/{owner}/{repo}/pulls/{record.number}"


def checks_probe_paths(
    published: PublishedSource | ListedRepository,
    record: PullRecord,
    status: PullStatus | None,
    probes: CheckProbes | None = None,
) -> tuple[str, str] | None:
    """The check-run and status pages a probe of *record*'s checks asks, or ``None``.

    Only for a head whose kept *status* counts fewer checks than a page holds, since a
    ``304`` for page one then says the whole list is unchanged, and not for one whose
    pages GitHub refused this reader (*probes*' ``refused``), since a part GitHub refuses
    would be asked again on every probe and could never say anything changed.
    """

    kept = described(record, status)
    if kept is None or kept.checks.total >= API_PAGE_SIZE:
        return None
    if probes is not None and _probes_of(record, probes) and probes.refused:
        return None
    owner, repo = _owner_and_repo(published)
    head = f"repos/{owner}/{repo}/commits/{record.pull.head.sha}"
    return _first_page(f"{head}/check-runs"), _first_page(f"{head}/status")


def _probes_of(record: PullRecord, probes: CheckProbes) -> bool:
    """Whether *probes* were seen of *record*'s head by its reader, so it may be compared."""

    return (probes.number, probes.head, probes.reader) == (
        record.number,
        record.pull.head.sha,
        record.reader,
    )


def _listed(payload: object, key: str) -> list[dict[str, Any]]:
    entries = as_dict(payload).get(key)
    if not isinstance(entries, list):
        raise UnreadableItemError
    return [as_dict(entry) for entry in entries]  # pyright: ignore[reportUnknownVariableType]


def checks_digest(response: GhResponse) -> str:
    """A digest of what a status keeps of a checks page GitHub answered ``200``.

    A check-runs page gives each run's name, status, conclusion, and details link; a
    combined status its state and each context's name, state, description, and link. The
    rest of either answer, a run's output among it, is left out, so an answer that moves
    only that is no change (``CHECKS_PROBE_S`` in :mod:`.served_pull`). Raises one of
    ``READ_FAILURES`` for an answer of neither shape.
    """

    payload = response_json(response)
    item = as_dict(payload)
    if "check_runs" in item:
        seen: object = {
            "total_count": item.get("total_count"),
            "check_runs": [
                [run.get(field) for field in ("name", "status", "conclusion", "details_url")]
                for run in _listed(payload, "check_runs")
            ],
        }
    else:
        seen = {
            "state": item["state"],
            "total_count": item.get("total_count"),
            "statuses": [
                [entry.get(field) for field in ("context", "state", "description", "target_url")]
                for entry in _listed(payload, "statuses")
            ],
        }
    text = json.dumps(seen, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode()).hexdigest()


def _same_mergeability(response: GhResponse, number: int, status: PullStatus | None) -> bool:
    """Whether the pull GitHub answered with says nothing *status* does not.

    Its ``mergeable`` and ``mergeable_state`` are GitHub's REST spelling of the status's
    ``conflicts`` and ``merge_state``. An ``unknown`` answer, which REST also gives a draft's
    ``mergeable_state``, is no news; a known one that differs is a change.
    """

    try:
        payload = response_json(response)
        # A pull this cannot read is no answer, never one that says "still unknown"
        # (review B3 on #726).
        _pull(payload, number)
    except READ_FAILURES:
        return False
    item = as_dict(payload)
    if status is None or "mergeable" not in item:
        return False
    mergeable = item.get("mergeable")
    conflicts = "mergeable" if mergeable is True else "conflicting" if mergeable is False else None
    state = merge_state(item.get("mergeable_state"))
    return (conflicts is None or conflicts == status.conflicts) and (
        state == "unknown" or state == status.merge_state
    )


async def probe_pull_request(
    published: PublishedSource | ListedRepository,
    record: PullRecord,
    *,
    etags: dict[str, str],
    checks: bool,
    seen: IssueSeen | None = None,
    mergeability: bool = False,
    status: PullStatus | None = None,
    probes: CheckProbes | None = None,
) -> PullProbe:
    """Ask GitHub whether *record*, and *status*, still describe pull request ``record.number``.

    Each request is conditional once there is something to compare with, and GitHub does
    not count one it answers ``304`` against the rate limit (measured 2026-11-22; see
    docs/project/specs/active/plan-2026-11-22-pull-request-update-cadence.md).

    The pull request's issue is asked first (:func:`probe_path`), with the ETag of *seen*,
    what the last probe found, whichever record it ran beside. Its ``updated_at`` is the
    pull request's own, and moves with its state, merge, title, body, labels, new comments
    and reviews, and pushes to its head; a later edit of a review comment does not move
    it (review A6 on #726: 7 of 103 recent review comments in rust-lang/rust and
    NixOS/nixpkgs were changed after their pull request's ``updated_at``). So the record
    is ``changed`` when the issue's ``updated_at``, from a ``200`` or else *seen*'s when
    GitHub answers ``304``, is later than the record's, and a ``200`` with the same one,
    as a reaction makes, changes nothing. One earlier than the record's is ``behind``:
    the issue's answer lags the pull's the record was read from, and a full read would
    bring nothing. With no *seen*, the first probe of a number in a server, it is asked
    unconditionally once.

    The issue carries neither the head's checks nor whether the pull request can merge,
    which are its operational status, *status*, the kept status of *record*'s head. Once
    the issue is unchanged:

    - With *mergeability*, the pull itself is asked while GitHub has not settled the
      status's mergeability (:func:`mergeability_probe_path`), on the ETag in *etags* or
      else the record's, and an answer that settles it otherwise is ``checks_changed``
      (:func:`_same_mergeability`). A mergeability GitHub recomputes for a status that
      holds an answer, as when its base moves, waits for the next full read.
    - With *checks*, the first pages of the head's check runs and status are asked
      (:func:`checks_probe_paths`), each on the ETag *probes* keep for it. A ``200`` is
      ``checks_changed`` unless its :func:`checks_digest` is the one kept, and either way
      becomes the page's new baseline, which the result's ``checks`` carries; the first
      ask of a head has none, so its two ``200`` answers seed the baseline and count as a
      change. A page GitHub refuses marks the head's pages ``refused``.

    These and the pull are asked together, and ``checks_changed`` starts a status read
    (:func:`refresh_pull_status`). Runs no account check and writes nothing: the read a
    change starts checks the account and publishes. Raises only :class:`PullDataError`.
    """

    newer: dict[str, str] = {}
    try:
        response = await _get(
            probe_path(published, record.number), etag=seen.etag if seen is not None else None
        )
    except PageTooLargeError as exc:
        raise _unreadable_pull() from exc
    if response.status == 304:
        if seen is None:
            raise unconditional_304()
        found: IssueSeen | None = seen
        updated_at = seen.updated_at
    else:
        try:
            updated_at = _issue_updated_at(response_json(response), record.number)
        except READ_FAILURES as exc:
            raise _unreadable_pull() from exc
        found = IssueSeen(updated_at, response.etag) if response.etag is not None else None
    if updated_at < record.pull.updated_at:
        return PullProbe("behind", newer, found, updated_at)
    if updated_at != record.pull.updated_at:
        return PullProbe("changed", newer, found, updated_at)
    pull_path = mergeability_probe_path(published, record, status) if mergeability else None
    paths = checks_probe_paths(published, record, status, probes) if checks else None
    if pull_path is None and paths is None:
        return PullProbe("unchanged", newer, found, updated_at)
    kept = probes if probes is not None and _probes_of(record, probes) else None
    pages = dict(kept.pages) if kept is not None else {}

    async def ask_pull(path: str) -> GhResponse | None:
        try:
            return await _get(path, etag=etags.get(path) or record.etags.get(path))
        except PageTooLargeError:
            return None

    async def ask_page(path: str) -> GhResponse | None:
        """The page's answer, or ``None`` for one GitHub refused or sent too large."""

        baseline = pages.get(path)
        try:
            return await _get(path, etag=baseline.etag if baseline is not None else None)
        except PageTooLargeError:
            return None
        except PullDataError as exc:
            if not _degrade(exc):
                raise
            return None

    asked_pages = paths or ()
    answers = await asyncio.gather(
        *((ask_pull(pull_path),) if pull_path is not None else ()),
        *(ask_page(path) for path in asked_pages),
    )
    changed = False
    if pull_path is not None:
        answer = answers[0]
        if answer is None or (
            answer.status != 304 and not _same_mergeability(answer, record.number, status)
        ):
            changed = True
        elif answer.status != 304 and answer.etag is not None:
            newer[pull_path] = answer.etag
    refused = False
    for path, answer in zip(asked_pages, answers[1 if pull_path is not None else 0 :], strict=True):
        if answer is None:
            refused = True
            continue
        if answer.status == 304:
            continue
        try:
            digest = checks_digest(answer)
        except READ_FAILURES:
            refused = True
            continue
        baseline = pages.get(path)
        if baseline is None or baseline.digest != digest:
            changed = True
        pages[path] = ProbedPage(etag=answer.etag, digest=digest)
    noticed: CheckProbes | None = None
    if paths is not None:
        noticed = CheckProbes(
            number=record.number,
            head=record.pull.head.sha,
            reader=record.reader,
            seen_at=utc_stamp(utc_now()),
            pages=pages,
            refused=refused,
        )
        if kept is not None and (kept.pages, kept.refused) == (noticed.pages, noticed.refused):
            noticed = None
    return PullProbe(
        "checks_changed" if changed else "unchanged", newer, found, updated_at, noticed
    )


def _keep_stamp(
    published: PublishedSource | ListedRepository,
    number: int,
    fields: dict[str, Any],
    expected: PullRecord | RecordAbsence,
    timing: PullRefreshTiming | None = None,
) -> None:
    try:
        stamp = PullRefreshStamp.model_validate(fields)
        write_pull_refresh(
            published.home, published.slug, number, stamp, expected=expected, timing=timing
        )
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
        fresh = await refresh_pull_request(published, number, adopt_current=False)
    except PullObservationSuperseded as exc:
        # Another writer's record names a head this refresh did not fetch; pin it only
        # when the store has it.
        try:
            if await has_commit(published, exc.current.pull.head.sha):
                return _pin(number, exc.current)
        except GitError as error:
            raise _git_failure(number, error) from error
        if usable and isinstance(record, PullRecord):
            return _pin(number, record)
        raise PullDataError("head_mismatch", "the cached head changed during this open") from exc
    except PullDataError as exc:
        if not usable or not isinstance(record, PullRecord):
            raise
        return _pin(number, record, note=f"; the refresh failed: {exc} ({exc.state})")
    return _pin(number, fresh)


__all__ = [
    "NeedsDeepening",
    "ProbeOutcome",
    "PullDataError",
    "PullDataState",
    "PullProbe",
    "IssueSeen",
    "PROBE_RESOURCE",
    "checks_digest",
    "checks_probe_paths",
    "mergeability_probe_path",
    "probe_path",
    "last_refresh",
    "open_pull_request",
    "probe_pull_request",
    "refresh_pull_request",
    "refresh_pull_status",
    "utc_now",
]
