"""A pull request's operational status: what GitHub said about whether it can merge.

The core of a pull request (its title, body, author, branches, lifecycle, and
conversation) changes when a person changes it, and moves its ``updated_at``. Its
operational status changes without anyone touching it: a check finishes, the base branch
moves, or GitHub finishes computing ``mergeable``. So the two are separate models.
:class:`PullStatus` is one observation of one head, against its base, at one time; a
status for another head describes nothing current
(docs/project/specs/active/plan-2026-11-26-pull-request-merge-readiness.md).

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
from typing import Annotated, Final, Literal

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
    how many checks are in each bucket. ``required_failing`` and ``required_pending`` are
    known only when the read had each check's ``isRequired``, and ``None`` otherwise.
    """

    state: RollupState
    counts: dict[Bucket, Annotated[int, Field(ge=0)]]
    required_failing: Annotated[int, Field(ge=0)] | None = None
    required_pending: Annotated[int, Field(ge=0)] | None = None

    @model_validator(mode="after")
    def _every_bucket_and_none_empty(self) -> ChecksSummary:
        if set(self.counts) != set(BUCKETS):
            raise ValueError("counts name every bucket")
        if self.state == "none" and any(self.counts.values()):
            raise ValueError("a head with no rollup has no checks")
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
    """A head's checks, one item for the latest run of each, as the Checks tab lists them.

    ``truncated`` says GitHub listed more than :data:`MAX_CHECK_ITEMS`, or an item could
    not be read, so the list is short.
    """

    number: int = Field(ge=1)
    head: Sha
    observed_at: Timestamp
    items: tuple[CheckItem, ...] = Field(max_length=MAX_CHECK_ITEMS)
    truncated: bool = False


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
    "merge_method",
    "merge_state",
    "queue_state",
    "review_decision",
    "rollup_state",
    "state_bucket",
]
