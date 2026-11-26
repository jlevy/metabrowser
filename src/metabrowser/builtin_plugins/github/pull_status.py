"""A pull request's operational status: what GitHub said about whether it can merge.

The core of a pull request (its title, body, author, branches, lifecycle, and
conversation) changes when a person changes it, and moves its ``updated_at``. Its
operational status changes without anyone touching it: a check finishes, the base branch
moves, or GitHub finishes computing ``mergeable``. So the two are separate models.
:class:`PullStatus` is one observation of one head, against its base, at one time; a
status for another head or another base describes nothing current (:func:`describes`,
docs/project/specs/active/plan-2026-11-26-pull-request-merge-readiness.md).

Whether a state counts as passing, failing, or pending is GitHub's call, never
Metabrowser's (the owner's decision of 2026-11-26). Two GitHub sources are exact:

- **The server's rollup**, ``statusCheckRollup.state``, is GitHub's verdict for a commit's
  checks, and :class:`ChecksSummary` keeps it as GitHub gave it. Over this repository's
  813 pull requests with a rollup on 2026-11-26, a cancelled run made the rollup
  ``FAILURE``, and skipped and neutral runs left it ``SUCCESS``.
- **GitHub's CLI**, ``gh`` 2.97.0, sorts each check into a bucket
  (``aggregateChecks`` in ``pkg/cmd/pr/checks/aggregate.go``), which :func:`state_bucket`
  follows: ``SUCCESS`` passes; ``SKIPPED`` and ``NEUTRAL`` are skipping; ``ERROR``,
  ``FAILURE``, ``TIMED_OUT``, and ``ACTION_REQUIRED`` fail; ``CANCELLED`` is its own
  bucket; and everything else, ``STALE`` and ``STARTUP_FAILURE`` among them and any
  state GitHub adds later, is pending.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Final, Literal, TypeGuard

from pydantic import BaseModel, ConfigDict, Field, model_validator

from metabrowser.builtin_plugins.github.pull_record import (
    Login,
    Sha,
    Short,
    Timestamp,
    Url,
)

type Mergeable = Literal["mergeable", "conflicting", "unknown"]
"""GitHub's ``mergeable``, lower case: ``unknown`` while GitHub computes it."""

type MergeState = Literal["clean", "has_hooks", "unstable", "blocked", "behind", "dirty", "unknown"]
"""GitHub's ``mergeStateStatus``, lower case. ``DRAFT`` is deprecated and never reported."""

type ReviewDecision = Literal["approved", "changes_requested", "review_required"]
"""GitHub's ``reviewDecision``, lower case; a status holds ``None`` where GitHub gave none."""

type RollupState = Literal["success", "failure", "error", "pending", "expected", "none"]
"""GitHub's ``statusCheckRollup.state``, lower case, or ``none`` for a head with no checks."""

type Bucket = Literal["pass", "fail", "pending", "skipping", "cancel"]
"""The bucket ``gh pr checks`` sorts a check into, by :func:`state_bucket`."""

type CheckKind = Literal["run", "status"]
"""A check run, made by a GitHub App, or a commit status, posted by an external service."""

type MergeMethod = Literal["merge", "squash", "rebase"]

type QueueState = Literal["queued", "awaiting_checks", "mergeable", "unmergeable", "locked"]
"""GitHub's ``MergeQueueEntryState``, lower case."""

type ObservedBy = Literal["scan", "read"]
"""The Pulls tab's scan of every open pull request, or the pull request page's own read."""

BUCKETS: Final[tuple[Bucket, ...]] = ("pass", "fail", "pending", "skipping", "cancel")

_MERGE_STATES: Final[frozenset[str]] = frozenset(
    ("clean", "has_hooks", "unstable", "blocked", "behind", "dirty")
)
_REVIEW_DECISIONS: Final[frozenset[str]] = frozenset(
    ("approved", "changes_requested", "review_required")
)
_ROLLUP_STATES: Final[frozenset[str]] = frozenset(
    ("success", "failure", "error", "pending", "expected")
)
_QUEUE_STATES: Final[frozenset[str]] = frozenset(
    ("queued", "awaiting_checks", "mergeable", "unmergeable", "locked")
)
_MERGE_METHODS: Final[frozenset[str]] = frozenset(("merge", "squash", "rebase"))

# ``gh`` 2.97.0, ``aggregateChecks``: the one switch every check state goes through.
_PASS: Final = frozenset(("SUCCESS",))
_SKIPPING: Final = frozenset(("SKIPPED", "NEUTRAL"))
_FAIL: Final = frozenset(("ERROR", "FAILURE", "TIMED_OUT", "ACTION_REQUIRED"))
_CANCEL: Final = frozenset(("CANCELLED",))


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def state_bucket(state: str) -> Bucket:
    """The bucket GitHub's CLI sorts a check state into; unknown states are pending.

    *state* is a check run's conclusion once it completed and its status before, a
    commit status's state, or a rollup count's ``CheckRunState``, in any case.
    """

    upper = state.upper()
    if upper in _PASS:
        return "pass"
    if upper in _SKIPPING:
        return "skipping"
    if upper in _FAIL:
        return "fail"
    if upper in _CANCEL:
        return "cancel"
    return "pending"


def check_run_bucket(status: str | None, conclusion: str | None) -> Bucket:
    """A check run's bucket: its conclusion once ``COMPLETED``, its status before."""

    completed = (status or "").upper() == "COMPLETED"
    return state_bucket((conclusion if completed else status) or "")


def merge_state(value: object) -> MergeState:
    """GitHub's ``mergeStateStatus`` or REST's ``mergeable_state``, lower case.

    Anything else, the deprecated ``DRAFT`` among them, is ``unknown``: whether a pull
    request is a draft comes from ``isDraft`` alone.
    """

    text = value.lower() if isinstance(value, str) else ""
    return text if text in _MERGE_STATES else "unknown"  # pyright: ignore[reportReturnType]


def review_decision(value: object) -> ReviewDecision | None:
    """GitHub's ``reviewDecision``, lower case, or ``None`` where it gave none."""

    text = value.lower() if isinstance(value, str) else ""
    return text if text in _REVIEW_DECISIONS else None  # pyright: ignore[reportReturnType]


def rollup_state(value: object) -> RollupState:
    """GitHub's rollup state, lower case; ``none`` where the head has no rollup."""

    text = value.lower() if isinstance(value, str) else ""
    return text if text in _ROLLUP_STATES else "none"  # pyright: ignore[reportReturnType]


def queue_state(value: object) -> QueueState | None:
    """GitHub's ``MergeQueueEntryState``, lower case, or ``None`` for one it did not name."""

    text = value.lower() if isinstance(value, str) else ""
    return text if text in _QUEUE_STATES else None  # pyright: ignore[reportReturnType]


def merge_method(value: object) -> MergeMethod | None:
    """GitHub's ``PullRequestMergeMethod``, lower case, or ``None`` for one it did not name."""

    text = value.lower() if isinstance(value, str) else ""
    return text if text in _MERGE_METHODS else None  # pyright: ignore[reportReturnType]


def bucket_counts(
    run_counts: Mapping[str, int], status_counts: Mapping[str, int]
) -> dict[Bucket, int]:
    """How many checks are in each bucket, from the rollup's counts by state.

    *run_counts* is ``checkRunCountsByState`` and *status_counts*
    ``statusContextCountsByState``, each by GitHub's state name. Every bucket is present.
    """

    counts: dict[Bucket, int] = dict.fromkeys(BUCKETS, 0)
    for state, count in (*run_counts.items(), *status_counts.items()):
        counts[state_bucket(state)] += max(count, 0)
    return counts


class ChecksSummary(_Model):
    """A head's checks as GitHub summarized them.

    ``state`` is GitHub's rollup, which decides whether the checks pass; ``counts`` says
    how many checks are in each bucket. Both come from the rollup alone, so the Pulls
    tab's scan of every open pull request, which lists no check, reads them as the page's
    read does.

    ``listed_at`` is when a read last listed this head's checks and found these counts:
    the checks it kept then (``pulls/<n>.checks.json``, whose ``observed_at`` it equals)
    are the list this summary counts. It is ``None`` when no read listed checks that sum to
    it, as for a status the scan read. ``required_failing`` and ``required_pending`` come
    from that list, so they are known only with it, and only when the list was whole and
    every check said whether it is required; ``None`` otherwise. A cancelled required check
    is among the failing, since a required check must pass, skip, or be neutral. They say
    whether the checks can be why GitHub blocks a merge
    (:func:`.pull_readiness.requirements`); no sentence prints them beside ``counts``, which
    count every context where the list counts each check once
    (:func:`.pull_readiness.checks_sentence`).

    ``moved_at`` is the newest moment an observation kept beside this one summarized the
    pull request's checks otherwise (:func:`same_checks`): another head or base, another
    rollup state, or other counts. A list from then or before may describe checks that
    have moved since, so a summary counts only a list read after it, and ``None`` says no
    observation kept beside it differed (:func:`kept_observation`).
    """

    state: RollupState
    counts: dict[Bucket, Annotated[int, Field(ge=0)]]
    required_failing: Annotated[int, Field(ge=0)] | None = None
    required_pending: Annotated[int, Field(ge=0)] | None = None
    listed_at: Timestamp | None = None
    moved_at: Timestamp | None = None

    @model_validator(mode="after")
    def _every_bucket_and_none_empty(self) -> ChecksSummary:
        if set(self.counts) != set(BUCKETS):
            raise ValueError("counts name every bucket")
        if self.state == "none" and any(self.counts.values()):
            raise ValueError("a head with no rollup has no checks")
        if self.listed_at is None and (
            self.required_failing is not None or self.required_pending is not None
        ):
            raise ValueError("only a list of the checks says which are required")
        listed, moved = self.listed_at, self.moved_at
        if listed is not None and moved is not None and listed <= moved:
            raise ValueError("a list from before the checks moved does not count them")
        return self

    @property
    def total(self) -> int:
        """How many checks the head has."""

        return sum(self.counts.values())


class AutoMerge(_Model):
    """An auto-merge request: GitHub merges the pull request once it can."""

    method: MergeMethod | None
    enabled_by: Login | None = None
    enabled_at: Timestamp | None = None


class QueueEntry(_Model):
    """The pull request's entry in its base branch's merge queue."""

    state: QueueState
    position: Annotated[int, Field(ge=0)] | None = None
    enqueued_at: Timestamp | None = None
    estimated_s: Annotated[int, Field(ge=0)] | None = None
    url: Url | None = None


class PullStatus(_Model):
    """What GitHub said about one pull request's readiness, at one head, at one time.

    ``head`` is the commit it describes. ``conflicts`` is GitHub's ``mergeable``,
    ``merge_state`` its ``mergeStateStatus``, ``review_decision`` its ``reviewDecision``,
    and ``checks`` its rollup of the head's checks. ``auto_merge`` and ``queue`` are
    present only while auto-merge is on and the pull request is queued.
    """

    number: int = Field(ge=1)
    head: Sha
    base_ref: Short
    base: Sha | None = None
    observed_at: Timestamp
    observed_by: ObservedBy
    conflicts: Mergeable
    merge_state: MergeState
    review_decision: ReviewDecision | None = None
    checks: ChecksSummary
    auto_merge: AutoMerge | None = None
    queue: QueueEntry | None = None

    @model_validator(mode="after")
    def _nothing_after_it(self) -> PullStatus:
        # A status knows only of what was observed by then, so keeping several observations
        # never needs a list or a move from after the newest (:func:`kept_observation`).
        for moment in (self.checks.listed_at, self.checks.moved_at):
            if moment is not None and moment > self.observed_at:
                raise ValueError("a status names nothing observed after it")
        return self


def describes(
    status: PullStatus | None, *, head: str | None, base_ref: str | None
) -> TypeGuard[PullStatus]:
    """Whether *status* describes a pull request whose head is *head* and base *base_ref*.

    A status is one observation of one head against one base branch. Another head is a
    push it did not see; another base is a retarget it did not see, as when GitHub
    retargets the layer above a stacked pull request that merged, keeping its head:
    conflicts, the merge verdict, and which checks are required are then the new base's.
    Every surface that judges a status asks this, the verdict, the checks served beside
    it, the freshness verdict, and the Pulls tab's rows, so none shows a status another
    calls stale.
    """

    return (
        status is not None
        and head is not None
        and base_ref is not None
        and (status.head, status.base_ref) == (head, base_ref)
    )


def same_checks(one: PullStatus, other: PullStatus) -> bool:
    """Whether two observations summarize the same checks: one head against one base
    branch, GitHub's same rollup state, and the same number of checks in every bucket.

    The base is part of it because which checks are required is the base branch's rules'
    call (``isRequired``), so a pull request retargeted at another base with the same head
    and checks no longer has the required counts its list gave.
    """

    return (
        one.head == other.head
        and one.base_ref == other.base_ref
        and one.checks.state == other.checks.state
        and one.checks.counts == other.checks.counts
    )


def observation_key(status: PullStatus) -> tuple[str, bool, str]:
    """The order observations of one pull request are kept in, newest last.

    The later ``observed_at``; at one moment, a read before a scan, since a read lists the
    checks too; and then the observation itself, without what keeping it beside others
    gave it (its summary's ``listed_at``, required counts, and ``moved_at``), so two
    observations of one moment are ordered the same whichever is written first, and two
    that differ in nothing else are one.
    """

    bare = status.checks.model_copy(
        update={
            "listed_at": None,
            "required_failing": None,
            "required_pending": None,
            "moved_at": None,
        }
    )
    identity = status.model_copy(update={"checks": bare}).model_dump_json()
    return status.observed_at, status.observed_by == "read", identity


def _later(one: str | None, other: str | None) -> str | None:
    return other if one is None else one if other is None else max(one, other)


def _listing_key(checks: ChecksSummary) -> tuple[str, int, int]:
    """The order of two lists: the later ``listed_at``, then their required counts, so two
    reads of one moment are kept the same way whichever is written first."""

    return (
        checks.listed_at or "",
        -1 if checks.required_failing is None else checks.required_failing,
        -1 if checks.required_pending is None else checks.required_pending,
    )


def kept_observation(kept: PullStatus | None, incoming: PullStatus) -> PullStatus:
    """The status to keep for one pull request when *incoming* is observed and *kept* is held.

    The newest observation is kept, by :func:`observation_key`, whatever its head, so two
    reads that end out of order leave the later.

    What only an older observation can still add is the list behind its checks. The pull
    request page's read lists every check and says which are required; the Pulls tab's
    scan of every open pull request reads the rollup alone (:class:`ChecksSummary`). So the
    status kept counts the latest list (``listed_at``, with its required counts) of an
    observation that summarizes the same checks as the newest (:func:`same_checks`), as
    long as no observation kept beside them summarized them otherwise since: ``moved_at``
    is the newest that did, and a list from then or before counts nothing. A scan that
    finds a read's checks as the read left them takes nothing away from it, and a list is
    never carried to another head or base, to checks that moved, or past checks that moved
    and came back. The page then reads its own again.

    The status kept is the same whatever order the observations are written in: the newest
    and the latest list are each the greatest of their kind, and a move is evidence
    whenever it arrives, since a list is never newer than the observation it came with.
    Equal counts are all a scan can see, so a check that moves out of a bucket while
    another moves in between two observations is not seen: a check run never moves back
    once completed, and a re-run is a context of its own, which raises the total, so only
    a commit status posted back to pending as another check finishes can. The page's own
    read, on every change its probes find, corrects that.
    """

    if kept is None:
        return incoming
    newer, older = (
        (incoming, kept) if observation_key(incoming) >= observation_key(kept) else (kept, incoming)
    )
    if same_checks(newer, older):
        moved = _later(newer.checks.moved_at, older.checks.moved_at)
        lists = (newer.checks, older.checks)
    else:
        # The older observation, and every one kept with it, summarized them otherwise.
        moved = _later(newer.checks.moved_at, older.observed_at)
        lists = (newer.checks,)
    counted = [
        each
        for each in lists
        if each.listed_at is not None and (moved is None or each.listed_at > moved)
    ]
    listing = max(counted, key=_listing_key, default=None)
    checks = ChecksSummary(
        state=newer.checks.state,
        counts=newer.checks.counts,
        required_failing=None if listing is None else listing.required_failing,
        required_pending=None if listing is None else listing.required_pending,
        listed_at=None if listing is None else listing.listed_at,
        moved_at=moved,
    )
    # Validated whole, so a status the rule could not keep is never written.
    return PullStatus.model_validate({**newer.model_dump(), "checks": checks.model_dump()})


class CheckItem(_Model):
    """One check of a head: a check run or a commit status, in GitHub's bucket.

    ``status`` and ``conclusion`` are GitHub's, upper case as GitHub gives them: a run's
    status and its conclusion once completed, and a commit status's state as its
    conclusion. ``required`` is ``None`` when the read did not ask.
    """

    name: Short
    kind: CheckKind
    bucket: Bucket
    status: Short | None = None
    conclusion: Short | None = None
    required: bool | None = None
    details_url: Url | None = None
    app: Short | None = None
    description: Short | None = None


# Measured on ten public pull requests (octocat/Hello-World#1, cli/cli#14462,
# kubernetes/kubernetes#18085 and #102884, rust-lang/rust#69864, #137944, and #162519,
# microsoft/vscode#52707, python/cpython#118450, pytorch/pytorch#196374) with ``gh api``
# on 2026-09-23, when a record kept them: check runs, pytorch#196374 has 159 and
# cli#14462 31, so 300, three pages; commit statuses, at most one on any of them, so one
# page of 100.
MAX_CHECK_ITEMS: Final = 300 + 100
"""A head's checks: 300 check runs and 100 commit statuses, as measured above."""


class PullChecks(_Model):
    """A head's checks, one item for the latest run of each, as ``gh pr checks`` lists them
    (:func:`.pull_status_read.latest_of_each`).

    ``truncated`` says GitHub listed more than :data:`MAX_CHECK_ITEMS`, or an item could
    not be read, so the list is short.
    """

    number: int = Field(ge=1)
    head: Sha
    observed_at: Timestamp
    items: tuple[CheckItem, ...] = Field(max_length=MAX_CHECK_ITEMS)
    truncated: bool = False


def counted_list(status: PullStatus | None, checks: PullChecks | None) -> PullChecks | None:
    """*checks* when they are the list *status*'s summary counts, else ``None``.

    That is a list of the status's head kept by the read its summary names
    (``listed_at``). A status the Pulls tab's scan read for a new head, or with checks that
    moved since the page's read, names none (:func:`kept_observation`).
    """

    if status is None or checks is None or status.checks.listed_at is None:
        return None
    if (checks.head, checks.observed_at) != (status.head, status.checks.listed_at):
        return None
    return checks


__all__ = [
    "BUCKETS",
    "MAX_CHECK_ITEMS",
    "AutoMerge",
    "Bucket",
    "CheckItem",
    "CheckKind",
    "ChecksSummary",
    "MergeMethod",
    "Mergeable",
    "MergeState",
    "ObservedBy",
    "PullChecks",
    "PullStatus",
    "QueueEntry",
    "QueueState",
    "ReviewDecision",
    "RollupState",
    "bucket_counts",
    "check_run_bucket",
    "counted_list",
    "describes",
    "kept_observation",
    "merge_method",
    "merge_state",
    "observation_key",
    "queue_state",
    "review_decision",
    "rollup_state",
    "same_checks",
    "state_bucket",
]
