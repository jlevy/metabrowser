"""Whether a pull request is ready to merge: its requirements, then one verdict.

:func:`readiness` is the only place readiness is decided. The pull request page, its
Pulls row, a stack's member, and ``metab`` all show what it decided, so no two can
disagree (docs/project/specs/active/plan-2026-11-26-pull-request-merge-readiness.md).

GitHub decides; Metabrowser explains. Whether a pull request can merge is GitHub's
``mergeStateStatus``, never a reconstruction of branch protection, most of which a reader
without admin rights cannot read. Its inputs say why, one :class:`Requirement` for each
row github.com's merge box would show, each with a status:

- ``met``;
- ``waiting``: nothing the author must change; it waits on a check, a reviewer, the
  queue, or a one-click branch update;
- ``unmet``: the author must change something;
- ``unknown``: GitHub has not answered yet.

The verdict's tone is the worst status among them, and its headline the first
requirement at that status in :data:`REQUIREMENT_ORDER`, so a red verdict always names
something the author must change. Each status takes the color GitHub's CLI gives it:
``unmet`` red, ``waiting`` and ``unknown`` yellow (``gh pr status`` prints an unknown
mergeability in yellow), ``met`` green. The labels and sentences are ``gh``'s words where
``gh`` has them (``pkg/cmd/pr/status/status.go`` and ``pkg/cmd/pr/checks/output.go`` in
``gh`` 2.97.0).

A Rules row says GitHub blocks the merge for a reason no other row gives. A row explains a
block only when it could be the reason: a check no rule requires never blocks a merge, so
once the page's read found every required check passing, pending or failing checks
explain nothing. On kubernetes/enhancements#6506, approved and every required check
passing with only the unrequired ``tide`` pending, GitHub answered ``BLOCKED``
(2026-11-26), and the verdict is ``blocked``.

A draft is judged as an open pull request is, as GitHub's ``mergeStateStatus`` and
``gh pr status`` judge it: a draft reports the state it would have if it were ready.
GitHub never merges a draft, so a draft with every requirement met is
``ready_for_review`` rather than ``ready``.
"""

from __future__ import annotations

from typing import Final, Literal

from pydantic import BaseModel, ConfigDict

from metabrowser.builtin_plugins.github.pull_record import Sha, Short, Timestamp, Url
from metabrowser.builtin_plugins.github.pull_status import (
    BUCKETS,
    AutoMerge,
    Bucket,
    ChecksSummary,
    PullChecks,
    PullStatus,
    QueueEntry,
    counted_list,
    describes,
)

type DisplayState = Literal["open", "draft", "merged", "closed"]
"""A pull request's lifecycle, as its state badge names it."""


def lifecycle(*, closed: bool, draft: bool, merged: bool) -> DisplayState:
    """The state badge of a pull request: merged and draft come before open and closed, as
    GitHub's badge shows them."""

    if merged:
        return "merged"
    if closed:
        return "closed"
    return "draft" if draft else "open"


type RequirementKind = Literal["queue", "conflicts", "checks", "reviews", "up_to_date", "rules"]

type RequirementStatus = Literal["met", "waiting", "unmet", "unknown"]

type Tone = Literal["success", "attention", "danger"]

type Verdict = Literal[
    "ready",
    "ready_for_review",
    "conflicts",
    "checks_failing",
    "changes_requested",
    "blocked",
    "queue_failing",
    "queued",
    "checks_pending",
    "review_required",
    "behind",
    "checking",
]

REQUIREMENT_ORDER: Final[tuple[RequirementKind, ...]] = (
    "queue",
    "conflicts",
    "checks",
    "reviews",
    "up_to_date",
    "rules",
)
"""Which requirement heads the verdict when several share the worst status."""

STATUS_ORDER: Final[tuple[RequirementStatus, ...]] = ("unmet", "waiting", "unknown", "met")
"""Requirement statuses from worst to best."""

STATUS_TONES: Final[dict[RequirementStatus, Tone]] = {
    "unmet": "danger",
    "waiting": "attention",
    "unknown": "attention",
    "met": "success",
}

_HEADLINES: Final[dict[tuple[RequirementKind, RequirementStatus], Verdict]] = {
    ("queue", "unmet"): "queue_failing",
    ("queue", "waiting"): "queued",
    ("conflicts", "unmet"): "conflicts",
    ("checks", "unmet"): "checks_failing",
    ("checks", "waiting"): "checks_pending",
    ("reviews", "unmet"): "changes_requested",
    ("reviews", "waiting"): "review_required",
    ("up_to_date", "waiting"): "behind",
    ("rules", "unmet"): "blocked",
}
"""The verdict a requirement heads at a status; any requirement unknown heads ``checking``."""

LABELS: Final[dict[Verdict, str]] = {
    "ready": "Ready to merge",
    "ready_for_review": "Ready for review",
    "conflicts": "Merge conflicts",
    "checks_failing": "Checks failing",
    "changes_requested": "Changes requested",
    "blocked": "Blocked",
    "queue_failing": "Leaving queue",
    "queued": "Queued",
    "checks_pending": "Checks pending",
    "review_required": "Review required",
    "behind": "Not up to date",
    "checking": "Checking",
}

_REVIEW_STATUS: Final[dict[str, RequirementStatus]] = {
    "approved": "met",
    "review_required": "waiting",
    "changes_requested": "unmet",
}
_REVIEW_SUMMARY: Final[dict[str, str]] = {
    "approved": "Approved.",
    "review_required": "Review required.",
    "changes_requested": "Changes requested.",
}
_QUEUE_SUMMARY: Final[dict[str, str]] = {
    "queued": "Queued to merge",
    "awaiting_checks": "Queued to merge, waiting for its checks",
    "mergeable": "Queued to merge, and next to merge",
    "locked": "Queued to merge; the queue is locked",
    "unmergeable": "Leaving the merge queue: its checks did not pass",
}
_METHOD_WORDS: Final[dict[str, str]] = {"merge": "merge", "squash": "squash", "rebase": "rebase"}


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Requirement(_Model):
    """One row of the merge box: what it needs, whether it has it, and where to act.

    ``summary`` is one sentence. ``github_url`` is the page on GitHub where the reader
    can act on it, when the pull request's address is known.
    """

    kind: RequirementKind
    status: RequirementStatus
    summary: Short
    github_url: Url | None = None


class Readiness(_Model):
    """A pull request's verdict, its tone, and the requirements behind it.

    ``head`` is the commit it judged. A ``checking`` verdict with no requirements and no
    ``observed_at`` says no status describes that head yet.
    """

    verdict: Verdict
    tone: Tone
    label: Short
    head: Sha
    observed_at: Timestamp | None = None
    requirements: tuple[Requirement, ...] = ()
    auto_merge: AutoMerge | None = None
    auto_merge_summary: Short | None = None


def _link(html_url: str | None, suffix: str = "") -> str | None:
    return f"{html_url}{suffix}" if html_url else None


def _conflicts(status: PullStatus, base: str, html_url: str | None) -> Requirement:
    if status.conflicts == "conflicting" or status.merge_state == "dirty":
        return Requirement(
            kind="conflicts",
            status="unmet",
            summary=f"Merge conflicts with {base} must be resolved.",
            github_url=_link(html_url, "/conflicts"),
        )
    if status.conflicts == "unknown":
        return Requirement(
            kind="conflicts",
            status="unknown",
            summary="Merge conflict status unknown: GitHub is still checking.",
            github_url=_link(html_url),
        )
    return Requirement(kind="conflicts", status="met", summary=f"No merge conflicts with {base}.")


# ``gh pr checks``'s tallies, in its order, each bucket's word (``printSummary`` in
# ``pkg/cmd/pr/checks/output.go``), and the buckets whose required checks a tally names.
_TALLIES: Final[tuple[tuple[Bucket, str], ...]] = (
    ("cancel", "cancelled"),
    ("fail", "failing"),
    ("pass", "successful"),
    ("skipping", "skipped"),
    ("pending", "pending"),
)
_NAMES_REQUIRED: Final[frozenset[Bucket]] = frozenset(("cancel", "fail"))


def _tally(checks: ChecksSummary | PullChecks) -> tuple[dict[Bucket, int], dict[Bucket, int]]:
    """Each bucket's checks, and the required ones among them where that is known."""

    if isinstance(checks, ChecksSummary):
        return dict(checks.counts), {}
    counts: dict[Bucket, int] = dict.fromkeys(BUCKETS, 0)
    required: dict[Bucket, int] = dict.fromkeys(BUCKETS, 0)
    for item in checks.items:
        counts[item.bucket] += 1
        required[item.bucket] += item.required is True
    known = all(item.required is not None for item in checks.items)
    return counts, required if known else {}


def checks_sentence(checks: ChecksSummary | PullChecks) -> str:
    """``gh``'s summary of a head's checks, with its tallies, zeros left out.

    A list, :class:`PullChecks`, is counted as ``gh pr checks`` counts the checks it lists:
    each listed check once, in its bucket, and, when every one said whether it is
    required, the required ones among the cancelled and the failing, each beside its own
    tally. A :class:`ChecksSummary` is counted as ``gh pr status`` counts: GitHub's rollup
    counts, over every context, with no required count, since only a list says which are
    required and it counts a check GitHub ran twice once. So no sentence mixes the two.
    """

    counts, required = _tally(checks)
    if not sum(counts.values()):
        return "No checks."
    if counts["fail"]:
        headline = "Some checks were not successful"
    elif counts["pending"]:
        headline = "Some checks are still pending"
    elif counts["cancel"]:
        headline = "Some checks were cancelled"
    else:
        headline = "All checks were successful"
    parts: list[str] = []
    for bucket, word in _TALLIES:
        if not counts[bucket]:
            continue
        named = required.get(bucket, 0) if bucket in _NAMES_REQUIRED else 0
        parts.append(f"{counts[bucket]} {word}" + (f" ({named} required)" if named else ""))
    listed = parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + f", and {parts[-1]}"
    return f"{headline}: {listed}."


def _counted(status: PullStatus, listed: PullChecks | None) -> ChecksSummary | PullChecks:
    """What the checks row counts: *listed* when it is the whole list *status* counts, as
    the page shows it under the row, and GitHub's rollup otherwise, as the Pulls tab has
    it. A list cut short counts fewer checks than the rollup judges, so it is not used."""

    whole = counted_list(status, listed)
    return status.checks if whole is None or whole.truncated else whole


def _checks(status: PullStatus, listed: PullChecks | None, html_url: str | None) -> Requirement:
    rollup = status.checks.state
    summary = checks_sentence(_counted(status, listed))
    if rollup in ("failure", "error"):
        if status.merge_state == "unstable":
            summary += " GitHub allows merging, since no failing check is required."
        return Requirement(
            kind="checks", status="unmet", summary=summary, github_url=_link(html_url, "/checks")
        )
    if rollup in ("pending", "expected"):
        return Requirement(
            kind="checks", status="waiting", summary=summary, github_url=_link(html_url, "/checks")
        )
    return Requirement(kind="checks", status="met", summary=summary)


def _reviews(status: PullStatus, html_url: str | None) -> Requirement | None:
    decision = status.review_decision
    if decision is None:
        return None
    met = _REVIEW_STATUS[decision] == "met"
    return Requirement(
        kind="reviews",
        status=_REVIEW_STATUS[decision],
        summary=_REVIEW_SUMMARY[decision],
        github_url=None if met else _link(html_url),
    )


def _up_to_date(status: PullStatus, base: str, html_url: str | None) -> Requirement | None:
    if status.merge_state != "behind":
        return None
    return Requirement(
        kind="up_to_date",
        status="waiting",
        summary=f"Not up to date with {base}: a rule requires updating the branch first.",
        github_url=_link(html_url),
    )


def _queue(queue: QueueEntry | None) -> Requirement | None:
    if queue is None:
        return None
    summary = _QUEUE_SUMMARY[queue.state]
    if queue.state != "unmergeable" and queue.position is not None:
        summary += f", position {queue.position}"
    if queue.state != "unmergeable" and queue.estimated_s:
        summary += f", in about {max(1, round(queue.estimated_s / 60))} min"
    return Requirement(
        kind="queue",
        status="unmet" if queue.state == "unmergeable" else "waiting",
        summary=summary + ".",
        github_url=queue.url,
    )


def _rules(
    status: PullStatus, base: str, html_url: str | None, explained: bool
) -> Requirement | None:
    if status.merge_state == "unknown":
        return Requirement(
            kind="rules",
            status="unknown",
            summary="GitHub has not said yet whether this can merge.",
            github_url=_link(html_url),
        )
    if status.merge_state == "blocked" and not explained:
        return Requirement(
            kind="rules",
            status="unmet",
            summary=f"Merging is blocked by a rule on {base}.",
            github_url=_link(html_url),
        )
    return None


def _required_pass(checks: ChecksSummary) -> bool:
    """Whether the list behind *checks* found no required check failing or pending."""

    return checks.required_failing == 0 and checks.required_pending == 0


def _explains_block(row: Requirement, checks: ChecksSummary) -> bool:
    """Whether *row* can be why GitHub reports ``blocked``: it waits or is unmet, and, for
    the checks, no list found every required one passing. Checks no rule requires never
    block a merge (``unstable``), so once the read knows the required ones pass, a check
    still pending or failing says nothing of the block."""

    if row.status not in ("waiting", "unmet"):
        return False
    return row.kind != "checks" or not _required_pass(checks)


def requirements(
    status: PullStatus, *, listed: PullChecks | None = None, html_url: str | None = None
) -> tuple[Requirement, ...]:
    """The rows github.com's merge box would show for *status*, in :data:`REQUIREMENT_ORDER`.

    A row is present only where GitHub would show one: Reviews only when it gave a
    review decision, Up to date only when it reports ``behind``, Queue only while
    queued, and Rules only when GitHub reports a block no other row explains
    (:func:`_explains_block`), or has not answered. *listed* is the page's list of the
    head's checks, which the checks row's sentence counts when it is the whole list the
    status counts (:func:`checks_sentence`).
    """

    base = status.base_ref
    rows = [
        _queue(status.queue),
        _conflicts(status, base, html_url),
        _checks(status, listed, html_url),
        _reviews(status, html_url),
        _up_to_date(status, base, html_url),
    ]
    present = [row for row in rows if row is not None]
    explained = any(_explains_block(row, status.checks) for row in present)
    rules = _rules(status, base, html_url, explained)
    return (*present, *((rules,) if rules else ()))


def worst(rows: tuple[Requirement, ...]) -> RequirementStatus:
    """The worst status among *rows*; ``met`` when there are none."""

    present = {row.status for row in rows}
    for status in STATUS_ORDER:
        if status in present:
            return status
    return "met"


def headline(rows: tuple[Requirement, ...]) -> Requirement | None:
    """The first requirement, in :data:`REQUIREMENT_ORDER`, at the worst status of *rows*."""

    status = worst(rows)
    if status == "met":
        return None
    at_worst = [row for row in rows if row.status == status]
    return min(at_worst, key=lambda row: REQUIREMENT_ORDER.index(row.kind))


def auto_merge_summary(auto_merge: AutoMerge | None) -> str | None:
    """``gh``'s words for auto-merge, with its method."""

    if auto_merge is None:
        return None
    method = _METHOD_WORDS.get(auto_merge.method or "")
    return f"Auto-merge enabled ({method})." if method else "Auto-merge enabled."


def readiness(
    *,
    state: DisplayState,
    head: str,
    base_ref: str | None,
    status: PullStatus | None,
    listed: PullChecks | None = None,
    html_url: str | None = None,
) -> Readiness | None:
    """The verdict for a pull request at *head* into *base_ref*, or ``None`` when it is
    closed or merged.

    *status* counts only when it describes that head and base (:func:`.pull_status.describes`):
    a status for another head or base, or none, gives ``checking`` with no requirements,
    since a verdict is never shown for a pull request it does not describe. *listed* is
    the page's list of the head's checks, for the checks row (:func:`requirements`).
    """

    if state in ("closed", "merged"):
        return None
    if not describes(status, head=head, base_ref=base_ref):
        return Readiness(verdict="checking", tone="attention", label=LABELS["checking"], head=head)
    rows = requirements(status, listed=listed, html_url=html_url)
    worst_status = worst(rows)
    first = headline(rows)
    if first is None:
        verdict: Verdict = "ready_for_review" if state == "draft" else "ready"
    else:
        verdict = _HEADLINES.get((first.kind, first.status), "checking")
    return Readiness(
        verdict=verdict,
        tone=STATUS_TONES[worst_status],
        label=LABELS[verdict],
        head=head,
        observed_at=status.observed_at,
        requirements=rows,
        auto_merge=status.auto_merge,
        auto_merge_summary=auto_merge_summary(status.auto_merge),
    )


__all__ = [
    "LABELS",
    "REQUIREMENT_ORDER",
    "STATUS_ORDER",
    "STATUS_TONES",
    "DisplayState",
    "Readiness",
    "Requirement",
    "RequirementKind",
    "RequirementStatus",
    "Tone",
    "Verdict",
    "auto_merge_summary",
    "checks_sentence",
    "headline",
    "lifecycle",
    "readiness",
    "requirements",
    "worst",
]
