"""Read a pull request's operational status from GitHub, with one GraphQL query.

:func:`read_pull_status` asks GitHub for what decides whether a pull request can merge
(:mod:`.pull_status`): its head and base, ``mergeable``, ``mergeStateStatus``,
``reviewDecision``, the merge queue entry, auto-merge, and its head's
``statusCheckRollup`` with every check, each with ``isRequired`` for this pull request.
It runs through :func:`~.gh.gh_graphql`, as the core read does, so GitHub's
``rateLimit { cost }`` is counted against the process's ceiling, a rate limit holds
everything after it, and the query's ``viewer { login }`` must be the account the job
read as, or the answer is discarded as ``account_changed``.

The checks are the rollup's ``contexts``, :data:`CONTEXTS_PAGE` a page, read until GitHub
says there are no more or :data:`~.pull_status.MAX_CHECK_ITEMS` are read; past that, or
when an item cannot be read, the list says it is ``truncated``. Every page asks the whole
query again, and a later page whose head is not the first page's ends the list there,
``truncated``: the checks of another head would be mixed in. Like ``gh pr checks``
(``eliminateDuplicates`` in ``pkg/cmd/pr/checks/aggregate.go``, ``gh`` 2.97.0), only the
latest run of each check is kept, the latest ``startedAt`` winning (:func:`latest_of_each`):
a check run is one check by its name, its workflow, and the event that ran it, and a
commit status, which has no start, by its context, apart from the runs. So one job that a
``push`` and a ``pull_request`` both ran is two checks: psf/requests#7619 has two failing
``lint`` runs of one workflow, and both ``gh`` and this list show 61 checks of its 61
contexts (2026-11-26).

The counts in :class:`~.pull_status.ChecksSummary` are GitHub's own, folded from
``checkRunCountsByState`` and ``statusContextCountsByState`` (:func:`~.pull_status.bucket_counts`),
so the Pulls tab's scan, which reads them without the checks, counts the same way. They
count every context of the rollup, as ``gh pr status`` does, so a check GitHub ran again
for one head counts twice there and is listed once, as ``gh pr checks`` lists it:
python/cpython#162697 counted 5 failing contexts where both listed 2 (2026-11-26). The
page's sentence counts its list (:func:`~.pull_readiness.checks_sentence`).
``required_failing`` and ``required_pending`` are counted from the listed checks, a
cancelled required check among the failing, as the rollup counts a cancelled run; they
are ``None`` when the list is truncated or a check did not say whether it is required.
``listed_at`` is when the read answered, the ``observed_at`` of the checks it keeps, so
the summary names the list it counts. The Pulls tab's scan of every open pull request
(:mod:`.pull_status_scan`) builds its statuses from the same fields with
:func:`operational_status` and :func:`rollup_summary`, and lists no check.

The answer's repository is the one asked for when :func:`~.gh_lists.asked_repository`
says so: GitHub's id, when the catalog the status is kept in knows the repository's, or
else GitHub's answer for the name, which follows a rename as the REST read follows its
redirect.

What GitHub answers is validated: a field that is not what GitHub documents makes the
whole answer unreadable (``gh_failed``), never a status that guesses, and a check that
cannot be read is left out and the list marked truncated. Only :class:`.PullDataError`
escapes.
"""

from __future__ import annotations

import asyncio
import logging
import re
import sqlite3
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from functools import partial
from typing import TYPE_CHECKING, Any, Final

from metabrowser.builtin_plugins.github.gh import GhError, gh_graphql
from metabrowser.builtin_plugins.github.gh_lists import (
    READ_FAILURES,
    PullDataError,
    UnreadableItemError,
    as_dict,
    asked_repository,
    cache_unwritable,
    login_of,
    newer_cache,
    unknown_cache,
    utc_stamp,
)
from metabrowser.builtin_plugins.github.pull_catalog import (
    CatalogUnusableError,
    NewerCatalogError,
    UnknownCatalogError,
    failure_line,
    read_catalog,
    write_pull_status,
)
from metabrowser.builtin_plugins.github.pull_list import ListedRepository
from metabrowser.builtin_plugins.github.pull_record import MAX_REFRESH_MESSAGE_CHARS, cut_text
from metabrowser.builtin_plugins.github.pull_status import (
    MAX_CHECK_ITEMS,
    AutoMerge,
    Bucket,
    CheckItem,
    CheckKind,
    ChecksSummary,
    ObservedBy,
    PullChecks,
    PullStatus,
    QueueEntry,
    RollupState,
    bucket_counts,
    check_run_bucket,
    merge_method,
    merge_state,
    queue_state,
    review_decision,
    rollup_state,
    state_bucket,
)
from metabrowser.builtin_plugins.github.pull_status_store import (
    StatusOutcome,
    write_pull_checks,
    write_status_outcome,
)
from metabrowser.cache.locks import run_lock_section
from metabrowser.home import PrivateStorageError

if TYPE_CHECKING:
    from metabrowser.cache.acquire import PublishedSource

log = logging.getLogger(__name__)

# The contexts one page asks for: the most a GitHub GraphQL connection returns.
CONTEXTS_PAGE: Final = 100
_PAGES: Final = -(-MAX_CHECK_ITEMS // CONTEXTS_PAGE)

# Read on 2026-11-26 from a cloud container with gh 2.97.0, against jlevy/metabrowser's
# pull requests (#380, #498, #508, #679, #870, #872), 14 reads in all: every one reported
# ``rateLimit { cost }`` 1 and took 0.46 to 1.17 s, most near 0.6 s. An answer was 5.6 to
# 11.5 KB for 15 to 35 checks, about 310 bytes a check. ``mergeStateStatus`` needed no
# preview header, and ``statusCheckRollup`` is a field of the pull request itself, so one
# query reads it.
# Each run's workflow and event, which ``gh pr checks`` keys a run by, and the repository's
# ``id`` cost nothing more: read again on 2026-11-26 with and without them, the same six
# pull requests, psf/requests#7619, kubernetes/enhancements#6506, python/cpython#162697,
# and a full page of pytorch/pytorch#196374's checks each reported ``cost`` 1 both ways,
# and 1 in a dry run. They add about 65 bytes a check, so a check is about 375 bytes and
# pytorch's page of 100 was 40.9 KB where it was 34.2 KB, far inside ``GH_API_MAX_BYTES``.
# Whether ``mergeStateStatus`` depends on who asks, as for an admin who may bypass a rule,
# was not settled: the only reader was the repository's admin, and its ``main`` has no
# protection or ruleset, so no rule could block anyone. The schema gives the bypass a
# field of its own, ``viewerCanMergeAsAdmin``, which suggests the verdict is the rules'
# and the bypass the viewer's, but that is a reading of the schema, not a measurement.
_STATUS_QUERY: Final = """query PullStatus($owner:String!,$name:String!,$number:Int!,$cursor:String) {
  viewer { login }
  rateLimit { cost }
  repository(owner:$owner,name:$name) {
    id nameWithOwner
    pull:pullRequest(number:$number) {
      number headRefOid baseRefName baseRefOid isDraft mergeable mergeStateStatus
      reviewDecision isInMergeQueue
      mergeQueueEntry { state position enqueuedAt estimatedTimeToMerge mergeQueue { url } }
      autoMergeRequest { mergeMethod enabledAt enabledBy { login } }
      statusCheckRollup {
        state
        contexts(first:100,after:$cursor) {
          pageInfo { hasNextPage endCursor }
          checkRunCountsByState { state count }
          statusContextCountsByState { state count }
          nodes {
            __typename
            ... on CheckRun {
              name status conclusion isRequired(pullRequestNumber:$number) detailsUrl startedAt
              checkSuite { app { name } workflowRun { event workflow { name } } }
            }
            ... on StatusContext {
              context state isRequired(pullRequestNumber:$number) targetUrl description
            }
          }
        }
      }
    }
  }
}"""

_SHORT_BYTES: Final = 1024
_MAX_URL_CHARS: Final = 4096
_MAX_CURSOR_CHARS: Final = 1024
_SHA = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")
_TIMESTAMP = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
_MERGEABLE: Final[dict[str, str]] = {
    "MERGEABLE": "mergeable",
    "CONFLICTING": "conflicting",
    "UNKNOWN": "unknown",
}


@dataclass(frozen=True, slots=True)
class StatusRead:
    """One read's status, and the checks of the same head."""

    status: PullStatus
    checks: PullChecks


def _short(value: object) -> str | None:
    return cut_text(value, _SHORT_BYTES)[0] if isinstance(value, str) else None


def _required_short(value: object) -> str:
    text = _short(value)
    if not text:
        raise UnreadableItemError
    return text


def _url(value: object) -> str | None:
    """An https link, or ``None``: an ``http://`` or over-long link is left out."""

    if isinstance(value, str) and value.startswith("https://") and len(value) <= _MAX_URL_CHARS:
        return value
    return None


def _stamp(value: object) -> str | None:
    """A time as GitHub spells one, or ``None`` for anything else."""

    if not isinstance(value, str) or not _TIMESTAMP.match(value):
        return None
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return None
    return value


def _sha(value: object) -> str:
    if not isinstance(value, str) or not _SHA.match(value):
        raise UnreadableItemError
    return value


def _count(value: object) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return None


def _counts(value: object) -> dict[str, int]:
    """``checkRunCountsByState`` or ``statusContextCountsByState``, by state."""

    if not isinstance(value, list):
        raise UnreadableItemError
    counts: dict[str, int] = {}
    for entry in value:  # pyright: ignore[reportUnknownVariableType]
        item = as_dict(entry)
        state, count = item.get("state"), _count(item.get("count"))
        if not isinstance(state, str) or not state or count is None:
            raise UnreadableItemError
        counts[state] = counts.get(state, 0) + count
    return counts


def _required(value: object) -> bool | None:
    return value if isinstance(value, bool) else None


def _field(value: object, key: str) -> object:
    """*value*'s *key* when *value* is an object, and ``None`` otherwise."""

    return value.get(key) if isinstance(value, dict) else None  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]


@dataclass(frozen=True, slots=True)
class ListedCheck:
    """One context as read: its item, when it started, and which check it is a run of.

    ``started`` is ``""`` for a commit status or a run not yet started. ``key`` is how
    ``gh pr checks`` tells one check from another (``eliminateDuplicates``, ``gh``
    2.97.0): a check run by ``<name>/<workflow>/<event>``, each ``""`` where GitHub gave
    none, as for a run no workflow made; a commit status by its context, in a namespace of
    its own.
    """

    item: CheckItem
    started: str
    key: tuple[CheckKind, str]


def _check_item(value: object) -> ListedCheck:
    """One context as a :class:`ListedCheck`; unreadable if GitHub sent it otherwise."""

    node = as_dict(value)
    kind = node.get("__typename")
    if kind == "CheckRun":
        status, conclusion = _required_short(node.get("status")), _short(node.get("conclusion"))
        suite = node.get("checkSuite")
        run = _field(suite, "workflowRun")
        workflow = _short(_field(_field(run, "workflow"), "name")) or ""
        event = _short(_field(run, "event")) or ""
        name = _required_short(node.get("name"))
        item = CheckItem(
            name=name,
            kind="run",
            bucket=check_run_bucket(status, conclusion),
            status=status,
            conclusion=conclusion,
            required=_required(node.get("isRequired")),
            details_url=_url(node.get("detailsUrl")),
            app=_short(_field(_field(suite, "app"), "name")),
        )
        started = _stamp(node.get("startedAt")) or ""
        return ListedCheck(item, started, ("run", f"{name}/{workflow}/{event}"))
    if kind == "StatusContext":
        state = _required_short(node.get("state"))
        name = _required_short(node.get("context"))
        item = CheckItem(
            name=name,
            kind="status",
            bucket=state_bucket(state),
            conclusion=state,
            required=_required(node.get("isRequired")),
            details_url=_url(node.get("targetUrl")),
            description=_short(node.get("description")),
        )
        return ListedCheck(item, "", ("status", name))
    raise UnreadableItemError


def latest_of_each(contexts: Sequence[ListedCheck]) -> tuple[CheckItem, ...]:
    """The latest run of each check, by its ``key``, in the order GitHub listed the kept ones.

    Of two runs of one check the later start is kept, and of two that started together, or
    never, the one GitHub listed first, as ``gh pr checks`` keeps the first of its checks
    sorted newest first.
    """

    chosen: dict[tuple[CheckKind, str], int] = {}
    for index, each in enumerate(contexts):
        kept = chosen.get(each.key)
        if kept is None or each.started > contexts[kept].started:
            chosen[each.key] = index
    return tuple(contexts[index].item for index in sorted(chosen.values()))


def _required_counts(
    items: Sequence[CheckItem], *, complete: bool
) -> tuple[int | None, int | None]:
    """How many required checks fail and are pending, when every check said whether it is."""

    if not complete or any(item.required is None for item in items):
        return None, None
    required = [item for item in items if item.required]
    failing = sum(item.bucket in ("fail", "cancel") for item in required)
    return failing, sum(item.bucket == "pending" for item in required)


def _queue(pull: Mapping[str, Any]) -> QueueEntry | None:
    entry = pull.get("mergeQueueEntry")
    if pull.get("isInMergeQueue") is not True or not isinstance(entry, dict):
        return None
    state = queue_state(entry.get("state"))  # pyright: ignore[reportUnknownMemberType]
    if state is None:
        return None
    queue = entry.get("mergeQueue")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    return QueueEntry(
        state=state,
        position=_count(entry.get("position")),  # pyright: ignore[reportUnknownMemberType]
        enqueued_at=_stamp(entry.get("enqueuedAt")),  # pyright: ignore[reportUnknownMemberType]
        estimated_s=_count(entry.get("estimatedTimeToMerge")),  # pyright: ignore[reportUnknownMemberType]
        url=_url(queue.get("url")) if isinstance(queue, dict) else None,  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
    )


def _auto_merge(pull: Mapping[str, Any]) -> AutoMerge | None:
    request = pull.get("autoMergeRequest")
    if not isinstance(request, dict):
        return None
    return AutoMerge(
        method=merge_method(request.get("mergeMethod")),  # pyright: ignore[reportUnknownMemberType]
        enabled_by=login_of(request.get("enabledBy")),  # pyright: ignore[reportUnknownMemberType]
        enabled_at=_stamp(request.get("enabledAt")),  # pyright: ignore[reportUnknownMemberType]
    )


def answered_repository(
    data: Mapping[str, Any], reader: str, *, repository_id: str | None
) -> dict[str, Any]:
    """The answer's repository, once its ``viewer`` is *reader* and it is the one asked for.

    Another viewer is ``account_changed``: the status was read as someone else, and is
    discarded. No repository is ``not_found_or_private``. A repository whose ``id`` is not
    *repository_id*, the one the catalog the status is kept in describes, is unreadable, as
    is any other shape; with no id known, GitHub's answer for the name asked is the
    repository, renamed or not (:func:`~.gh_lists.asked_repository`).
    """

    viewer = login_of(data.get("viewer"))
    if viewer is None:
        raise UnreadableItemError
    if f"gh:{viewer}" != reader:
        raise PullDataError(
            "account_changed",
            "the query viewer changed during the read, so the status was discarded",
        )
    raw = data["repository"]
    if raw is None:
        raise PullDataError("not_found_or_private", "GitHub has no readable pull request here")
    repository = as_dict(raw)
    if not asked_repository(repository, repository_id):
        raise UnreadableItemError
    return repository


def rollup_summary(raw: object) -> tuple[RollupState, dict[Bucket, int]]:
    """GitHub's rollup state of a head's checks and its counts by bucket, from
    ``statusCheckRollup``: ``none`` and no checks for a head GitHub gave none."""

    if raw is None:
        return rollup_state(None), bucket_counts({}, {})
    rollup = as_dict(raw)
    state = rollup_state(rollup.get("state"))
    if state == "none":
        # A rollup in a state GitHub has not documented is not one this can judge.
        raise UnreadableItemError
    contexts = as_dict(rollup["contexts"])
    counts = bucket_counts(
        _counts(contexts["checkRunCountsByState"]),
        _counts(contexts["statusContextCountsByState"]),
    )
    return state, counts


def operational_status(
    pull: Mapping[str, Any],
    *,
    head: str,
    checks: ChecksSummary,
    observed_at: str,
    observed_by: ObservedBy,
) -> PullStatus:
    """The status one pull request's fields say, at *head*, with its *checks* summarized.

    The page's read and the Pulls tab's scan ask GitHub for the same fields of a pull
    request, so both build their statuses here. Raises :class:`.UnreadableItemError`, or a
    model's ``ValueError``, for a field GitHub did not send as it documents.
    """

    mergeable = pull["mergeable"]
    if mergeable not in _MERGEABLE:
        raise UnreadableItemError
    base = pull.get("baseRefOid")
    return PullStatus(
        number=pull["number"],
        head=head,
        base_ref=_required_short(pull["baseRefName"]),
        base=base if isinstance(base, str) and _SHA.match(base) else None,
        observed_at=observed_at,
        observed_by=observed_by,
        conflicts=_MERGEABLE[mergeable],  # pyright: ignore[reportArgumentType]
        merge_state=merge_state(pull["mergeStateStatus"]),
        review_decision=review_decision(pull.get("reviewDecision")),
        checks=checks,
        auto_merge=_auto_merge(pull),
        queue=_queue(pull),
    )


def head_of(pull: Mapping[str, Any]) -> str:
    """The pull request's ``headRefOid``, a full commit ID, or unreadable."""

    return _sha(pull["headRefOid"])


@dataclass(frozen=True, slots=True)
class _Page:
    """One answer: the pull request's fields, and its page of contexts."""

    pull: dict[str, Any]
    head: str
    rollup: dict[str, Any] | None
    nodes: list[object]
    cursor: str | None


def _page(data: Mapping[str, Any], number: int, reader: str, *, repository_id: str | None) -> _Page:
    """The answer's pull request and contexts, once its viewer and repository are checked."""

    repository = answered_repository(data, reader, repository_id=repository_id)
    if repository["pull"] is None:
        raise PullDataError("not_found_or_private", "GitHub has no readable pull request here")
    pull = as_dict(repository["pull"])
    if type(pull.get("number")) is not int or pull["number"] != number:
        raise UnreadableItemError
    head = head_of(pull)
    raw_rollup = pull["statusCheckRollup"]
    if raw_rollup is None:
        return _Page(pull, head, None, [], None)
    rollup = as_dict(raw_rollup)
    contexts = as_dict(rollup["contexts"])
    info = as_dict(contexts["pageInfo"])
    nodes = contexts["nodes"]
    if not isinstance(nodes, list) or len(nodes) > CONTEXTS_PAGE:  # pyright: ignore[reportUnknownArgumentType]
        raise UnreadableItemError
    cursor = info.get("endCursor")
    more = info.get("hasNextPage") is True and isinstance(cursor, str)
    if more and not 1 <= len(cursor) <= _MAX_CURSOR_CHARS:  # pyright: ignore[reportArgumentType]
        raise UnreadableItemError
    return _Page(pull, head, rollup, nodes, cursor if more else None)  # pyright: ignore[reportUnknownArgumentType]


async def ask_github(
    query: str, variables: Mapping[str, str | int | None], *, now: datetime
) -> dict[str, Any]:
    """*query*'s answer through :func:`~.gh.gh_graphql`; a refusal is a :class:`PullDataError`."""

    try:
        return await gh_graphql(query, variables, now=now)
    except GhError as exc:
        raise PullDataError(exc.state, str(exc), reset_at=exc.reset_at) from exc


async def _ask(
    owner: str, repo: str, number: int, cursor: str | None, *, now: datetime
) -> dict[str, Any]:
    variables = {"owner": owner, "name": repo, "number": number, "cursor": cursor}
    return await ask_github(_STATUS_QUERY, variables, now=now)


def unreadable_status() -> PullDataError:
    """The refusal of an answer GitHub gave in a shape it does not document."""

    return PullDataError(
        "gh_failed", "GitHub answered with a pull request status Metabrowser cannot read"
    )


def _status_of(
    first: _Page, nodes: Sequence[object], *, truncated: bool, observed_at: str
) -> StatusRead:
    """The status and checks *first*'s pull request and these *nodes* of its contexts say."""

    pull = first.pull
    read: list[ListedCheck] = []
    dropped = False
    for node in nodes:
        try:
            read.append(_check_item(node))
        except READ_FAILURES as exc:
            log.debug("left out a check GitHub sent that could not be read: %r", exc)
            dropped = True
    items = latest_of_each(read)
    cut = truncated or dropped
    state, counts = rollup_summary(first.rollup)
    failing, pending = _required_counts(items, complete=not cut)
    summary = ChecksSummary(
        state=state,
        counts=counts,
        required_failing=failing,
        required_pending=pending,
        listed_at=observed_at,
    )
    status = operational_status(
        pull, head=first.head, checks=summary, observed_at=observed_at, observed_by="read"
    )
    checks = PullChecks(
        number=status.number,
        head=status.head,
        observed_at=observed_at,
        items=items[:MAX_CHECK_ITEMS],
        truncated=cut or len(items) > MAX_CHECK_ITEMS,
    )
    return StatusRead(status, checks)


async def read_pull_status(
    owner: str,
    repo: str,
    number: int,
    *,
    reader: str,
    now: Callable[[], datetime],
    repository_id: str | None = None,
) -> StatusRead:
    """Read pull request *number*'s status and checks as *reader*; see the module.

    *now* is the clock records are stamped with; ``observed_at`` is when the first page
    answered. *repository_id* is GitHub's id of the repository, when it is known, which
    every page's must be. Raises only :class:`PullDataError`.
    """

    nodes: list[object] = []
    first: _Page | None = None
    observed_at = ""
    cursor: str | None = None
    truncated = False
    try:
        for _index in range(_PAGES):
            data = await _ask(owner, repo, number, cursor, now=now())
            page = _page(data, number, reader, repository_id=repository_id)
            if first is None:
                first, observed_at = page, utc_stamp(now())
            elif page.head != first.head:
                # A push between two pages: the rest would be another head's checks.
                truncated = True
                break
            nodes.extend(page.nodes)
            cursor = page.cursor
            if cursor is None:
                break
        else:
            truncated = cursor is not None
        assert first is not None
        return _status_of(first, nodes, truncated=truncated, observed_at=observed_at)
    except READ_FAILURES as exc:
        raise unreadable_status() from exc
    except ValueError as exc:
        # A model's own check: a field GitHub sent in a shape it does not document.
        raise unreadable_status() from exc


_STATUS: Final = "the status of the pull request"


def _keep(repository: ListedRepository, read: StatusRead) -> bool:
    """Keep *read*'s status and then its checks, each under the alias lock. Blocking.

    The checks are kept only when the status kept then counts them
    (:func:`~.pull_status_store.write_pull_checks`), so the order two reads end in never
    leaves a status naming a list the file no longer holds.
    """

    kept = write_pull_status(repository, read.status)
    write_pull_checks(repository.home, repository.slug, read.checks)
    return kept


def known_repository_id(repository: ListedRepository) -> str | None:
    """GitHub's id of the repository whose catalog the status is kept in, or ``None`` with
    no readable catalog of this source. Blocking and bounded: one checkpoint read."""

    catalog = read_catalog(repository.home, repository.slug)
    return (
        catalog.repository_id
        if catalog is not None and catalog.source == repository.source
        else None
    )


async def keep_pull_status(
    published: PublishedSource | ListedRepository,
    owner: str,
    repo: str,
    number: int,
    *,
    reader: str,
    now: Callable[[], datetime],
    started: datetime | None = None,
) -> PullStatus | None:
    """Read pull request *number*'s status as *reader* and keep it; the status, or ``None``.

    A failure fails only the status, as a part GitHub refuses fails only that part of a
    record: it is kept as how the read ended (:func:`.pull_status_store.read_status_outcome`),
    the status and checks an earlier read kept stay, and nothing is raised. A catalog a
    newer release wrote, or one whose versions cannot be read, is left as it is, as the
    list's refresh leaves it. *started* is when the attempt began, *now* by default; how
    it ended is kept unless a newer attempt's is (:func:`.pull_status_store.write_status_outcome`).
    """

    started_at = utc_stamp(started or now())
    repository = _repository(published, owner, repo)
    checkout = repository.checkout
    status: PullStatus | None = None
    try:
        try:
            known = await asyncio.to_thread(known_repository_id, repository)
            read = await read_pull_status(
                owner, repo, number, reader=reader, now=now, repository_id=known
            )
            await run_lock_section(partial(_keep, repository, read))
            status = read.status
        except NewerCatalogError as exc:
            raise newer_cache(
                _STATUS, str(exc), source=repository.source, checkout=checkout
            ) from exc
        except UnknownCatalogError as exc:
            raise unknown_cache(
                _STATUS, str(exc), source=repository.source, checkout=checkout
            ) from exc
        except (PrivateStorageError, OSError, sqlite3.Error, CatalogUnusableError) as exc:
            log.warning(
                "the status of pull request %s of %s could not be kept: %s",
                number,
                repository.source,
                failure_line(exc),
            )
            raise cache_unwritable(
                _STATUS, exc, source=repository.source, checkout=checkout
            ) from exc
        stamp = StatusOutcome(
            outcome="succeeded", at=status.observed_at, started_at=started_at, reader=reader
        )
    except PullDataError as exc:
        log.debug("reading the status of pull request %s failed: %s", number, exc)
        stamp = _failure_stamp(exc, now=now, reader=reader, started_at=started_at)
    await _keep_outcome(repository, number, stamp)
    return status


def _repository(
    published: PublishedSource | ListedRepository, owner: str, repo: str
) -> ListedRepository:
    if isinstance(published, ListedRepository):
        return published
    return ListedRepository(published.home, published.slug, owner, repo)


def _failure_stamp(
    exc: PullDataError, *, now: Callable[[], datetime], reader: str | None, started_at: str
) -> StatusOutcome:
    return StatusOutcome(
        outcome=exc.state,
        message=str(exc)[:MAX_REFRESH_MESSAGE_CHARS],
        reset_at=exc.reset_at,
        at=utc_stamp(now()),
        started_at=started_at,
        reader=reader,
    )


async def _keep_outcome(repository: ListedRepository, number: int, stamp: StatusOutcome) -> None:
    try:
        await run_lock_section(
            partial(write_status_outcome, repository.home, repository.slug, number, stamp)
        )
    except (PrivateStorageError, OSError) as exc:
        # Only the report of the read is lost; a status it read is kept.
        log.debug("could not keep how pull request %s's status read ended: %s", number, exc)


async def keep_status_failure(
    published: PublishedSource | ListedRepository,
    owner: str,
    repo: str,
    number: int,
    failure: PullDataError,
    *,
    now: Callable[[], datetime],
    started: datetime,
) -> None:
    """Keep *failure*, which ended a read of pull request *number*'s status before it asked.

    As :func:`keep_pull_status` keeps a failure of its own: the status and checks an
    earlier read kept stay, and nothing is raised. The read named no reader yet; it began
    at *started*.
    """

    log.debug("reading the status of pull request %s failed: %s", number, failure)
    stamp = _failure_stamp(failure, now=now, reader=None, started_at=utc_stamp(started))
    await _keep_outcome(_repository(published, owner, repo), number, stamp)


__all__ = [
    "CONTEXTS_PAGE",
    "ListedCheck",
    "StatusRead",
    "answered_repository",
    "ask_github",
    "head_of",
    "keep_pull_status",
    "keep_status_failure",
    "known_repository_id",
    "latest_of_each",
    "operational_status",
    "read_pull_status",
    "rollup_summary",
    "unreadable_status",
]
