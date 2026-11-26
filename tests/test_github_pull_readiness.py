"""A pull request's readiness, held by invariants over every combination GitHub can report.

The derivation is generated over each enum GitHub defines rather than pinned case by
case, so a test never restates the table it checks: every claim below must hold for all
of the many thousands of statuses the cross product builds.
"""

from __future__ import annotations

import itertools
from collections.abc import Iterator
from typing import get_args

import pytest

from metabrowser.builtin_plugins.github.pull_readiness import (
    LABELS,
    REQUIREMENT_ORDER,
    STATUS_ORDER,
    STATUS_TONES,
    DisplayState,
    Readiness,
    Verdict,
    checks_sentence,
    readiness,
)
from metabrowser.builtin_plugins.github.pull_status import (
    BUCKETS,
    AutoMerge,
    ChecksSummary,
    MergeState,
    PullStatus,
    QueueEntry,
    QueueState,
    ReviewDecision,
    RollupState,
    bucket_counts,
    check_run_bucket,
    merge_state,
    review_decision,
    rollup_state,
    state_bucket,
)

HEAD = "a" * 40
OTHER_HEAD = "b" * 40
URL = "https://github.com/octo/demo/pull/7"

# Every value of each GitHub enum, read from the GraphQL schema on 2026-11-26.
CHECK_CONCLUSION_STATES = (
    "ACTION_REQUIRED",
    "TIMED_OUT",
    "CANCELLED",
    "FAILURE",
    "SUCCESS",
    "NEUTRAL",
    "SKIPPED",
    "STARTUP_FAILURE",
    "STALE",
)
CHECK_STATUS_STATES = ("REQUESTED", "QUEUED", "IN_PROGRESS", "COMPLETED", "WAITING", "PENDING")
CHECK_RUN_STATES = (
    "ACTION_REQUIRED",
    "CANCELLED",
    "COMPLETED",
    "FAILURE",
    "IN_PROGRESS",
    "NEUTRAL",
    "PENDING",
    "QUEUED",
    "SKIPPED",
    "STALE",
    "STARTUP_FAILURE",
    "SUCCESS",
    "TIMED_OUT",
    "WAITING",
)
STATUS_STATES = ("EXPECTED", "ERROR", "FAILURE", "PENDING", "SUCCESS")
MERGE_STATE_STATUSES = (
    "DIRTY",
    "UNKNOWN",
    "BLOCKED",
    "BEHIND",
    "DRAFT",
    "UNSTABLE",
    "HAS_HOOKS",
    "CLEAN",
)


def _checks(rollup: RollupState) -> ChecksSummary:
    """A summary whose counts agree with its rollup, as GitHub's do."""

    runs = {
        "success": {"SUCCESS": 3, "SKIPPED": 1},
        "failure": {"SUCCESS": 2, "FAILURE": 1},
        "error": {"SUCCESS": 2},
        "pending": {"SUCCESS": 2, "IN_PROGRESS": 1},
        "expected": {"SUCCESS": 2},
        "none": {},
    }[rollup]
    statuses = {"error": {"ERROR": 1}, "expected": {"EXPECTED": 1}}.get(rollup, {})
    return ChecksSummary(state=rollup, counts=bucket_counts(runs, statuses))


def _status(
    *,
    conflicts: str,
    merge: MergeState,
    review: ReviewDecision | None,
    rollup: RollupState,
    queue: QueueState | None,
    auto: bool,
    head: str = HEAD,
) -> PullStatus:
    return PullStatus.model_validate(
        {
            "number": 7,
            "head": head,
            "base_ref": "main",
            "observed_at": "2026-11-26T08:00:00Z",
            "observed_by": "read",
            "conflicts": conflicts,
            "merge_state": merge,
            "review_decision": review,
            "checks": _checks(rollup),
            "auto_merge": AutoMerge(method="squash") if auto else None,
            "queue": QueueEntry(state=queue, position=2) if queue else None,
        }
    )


def _all_statuses() -> Iterator[PullStatus]:
    for conflicts, merge, review, rollup, queue, auto in itertools.product(
        ("mergeable", "conflicting", "unknown"),
        get_args(MergeState.__value__),
        (None, *get_args(ReviewDecision.__value__)),
        get_args(RollupState.__value__),
        (None, *get_args(QueueState.__value__)),
        (False, True),
    ):
        yield _status(
            conflicts=conflicts, merge=merge, review=review, rollup=rollup, queue=queue, auto=auto
        )


STATUSES = tuple(_all_statuses())


def _judged(status: PullStatus, state: DisplayState = "open") -> Readiness:
    judged = readiness(state=state, head=HEAD, status=status, html_url=URL)
    assert judged is not None
    return judged


# ── GitHub's buckets ─────────────────────────────────────────────


def test_every_state_github_defines_has_a_bucket_and_an_unknown_one_is_pending() -> None:
    every = {*CHECK_CONCLUSION_STATES, *CHECK_STATUS_STATES, *CHECK_RUN_STATES, *STATUS_STATES}
    assert {state_bucket(state) for state in every} == set(BUCKETS)
    assert state_bucket("A_STATE_GITHUB_ADDS_LATER") == "pending"


def test_a_completed_run_takes_its_conclusions_bucket_and_a_running_one_its_statuss() -> None:
    for conclusion in CHECK_CONCLUSION_STATES:
        assert check_run_bucket("COMPLETED", conclusion) == state_bucket(conclusion)
    for status in CHECK_STATUS_STATES:
        if status != "COMPLETED":
            assert check_run_bucket(status, None) == state_bucket(status) == "pending"


def test_what_githubs_rollup_calls_success_never_counts_a_failure() -> None:
    # The rollups this repository's pull requests reported on 2026-11-26: skipped and
    # neutral runs left a rollup SUCCESS, and a cancelled one made it FAILURE.
    for state in ("SUCCESS", "SKIPPED", "NEUTRAL"):
        assert state_bucket(state) in ("pass", "skipping")
    assert state_bucket("CANCELLED") not in ("pass", "skipping")


def test_counts_name_every_bucket_and_keep_every_check() -> None:
    runs: dict[str, int] = dict.fromkeys(CHECK_RUN_STATES, 2)
    statuses: dict[str, int] = dict.fromkeys(STATUS_STATES, 3)
    counts = bucket_counts(runs, statuses)
    assert set(counts) == set(BUCKETS)
    assert sum(counts.values()) == sum(runs.values()) + sum(statuses.values())


def test_githubs_spellings_read_in_any_case_and_drafts_merge_state_is_unknown() -> None:
    for value in MERGE_STATE_STATUSES:
        assert merge_state(value) == merge_state(value.lower())
    assert merge_state("DRAFT") == "unknown"
    assert review_decision(None) is None and review_decision("APPROVED") == "approved"
    assert rollup_state(None) == "none" and rollup_state("EXPECTED") == "expected"


def test_a_head_with_no_rollup_cannot_count_checks() -> None:
    with pytest.raises(ValueError, match="no checks"):
        ChecksSummary(state="none", counts=bucket_counts({"SUCCESS": 1}, {}))


# ── The verdict ──────────────────────────────────────────────────


def test_closed_and_merged_pull_requests_have_no_readiness() -> None:
    for state in ("closed", "merged"):
        assert all(readiness(state=state, head=HEAD, status=s) is None for s in STATUSES[:50])


def test_a_status_for_another_head_or_none_is_never_shown_as_current() -> None:
    stale = _status(
        conflicts="mergeable",
        merge="clean",
        review=None,
        rollup="success",
        queue=None,
        auto=False,
        head=OTHER_HEAD,
    )
    for status in (stale, None):
        judged = readiness(state="open", head=HEAD, status=status)
        assert judged is not None
        assert (judged.verdict, judged.requirements, judged.observed_at) == ("checking", (), None)


def test_the_tone_is_the_worst_requirement_and_the_headline_is_first_at_it() -> None:
    for status in STATUSES:
        judged = _judged(status)
        ranks = [STATUS_ORDER.index(row.status) for row in judged.requirements]
        worst = STATUS_ORDER[min(ranks)]
        assert judged.tone == STATUS_TONES[worst]
        kinds = [row.kind for row in judged.requirements]
        assert kinds == sorted(kinds, key=REQUIREMENT_ORDER.index)
        at_worst = [row for row in judged.requirements if row.status == worst]
        if worst == "met":
            assert judged.verdict in ("ready", "ready_for_review")
        elif worst == "unknown":
            assert judged.verdict == "checking"
        else:
            assert judged.verdict != "checking"
            assert at_worst[0].kind == _headline_kind(judged.verdict)


def _headline_kind(verdict: Verdict) -> str:
    """The requirement a verdict's label names, read from the label, not a table."""

    words = LABELS[verdict].lower()
    for kind, word in (
        ("queue", "queue"),
        ("conflicts", "conflict"),
        ("checks", "checks"),
        ("reviews", "review"),
        ("reviews", "changes"),
        ("up_to_date", "up to date"),
        ("rules", "blocked"),
    ):
        if word in words:
            return kind
    raise AssertionError(verdict)


def test_a_red_verdict_always_names_something_the_author_must_change() -> None:
    for status in STATUSES:
        judged = _judged(status)
        if judged.tone == "danger":
            assert any(row.status == "unmet" for row in judged.requirements)


def test_ready_means_every_requirement_is_met_and_for_review_means_a_draft() -> None:
    for status in STATUSES:
        for state in ("open", "draft"):
            judged = _judged(status, state)
            met = all(row.status == "met" for row in judged.requirements)
            assert (judged.verdict in ("ready", "ready_for_review")) == met
            if met:
                assert (judged.verdict == "ready_for_review") == (state == "draft")


def test_a_draft_is_judged_as_an_open_pull_request_is() -> None:
    swap = {"ready": "ready_for_review"}
    for status in STATUSES:
        opened, draft = _judged(status), _judged(status, "draft")
        assert swap.get(opened.verdict, opened.verdict) == draft.verdict
        assert opened.requirements == draft.requirements


def test_conflicts_are_always_an_unmet_requirement() -> None:
    for status in STATUSES:
        if status.conflicts == "conflicting" or status.merge_state == "dirty":
            rows = {row.kind: row for row in _judged(status).requirements}
            assert rows["conflicts"].status == "unmet"
            assert rows["conflicts"].github_url == f"{URL}/conflicts"


def test_the_checks_requirement_follows_githubs_rollup_alone() -> None:
    seen: dict[str, str] = {}
    for status in STATUSES:
        rows = {row.kind: row for row in _judged(status).requirements}
        assert seen.setdefault(status.checks.state, rows["checks"].status) == rows["checks"].status
    assert seen["failure"] == seen["error"] == "unmet"


def test_a_block_nothing_else_explains_is_blocked_never_ready() -> None:
    for status in STATUSES:
        judged = _judged(status)
        others = [row for row in judged.requirements if row.kind != "rules"]
        if status.merge_state == "blocked" and all(row.status == "met" for row in others):
            assert judged.verdict == "blocked"


def test_rows_appear_only_where_githubs_merge_box_would_show_them() -> None:
    for status in STATUSES:
        kinds = {row.kind for row in _judged(status).requirements}
        assert ("reviews" in kinds) == (status.review_decision is not None)
        assert ("up_to_date" in kinds) == (status.merge_state == "behind")
        assert ("queue" in kinds) == (status.queue is not None)
        assert {"conflicts", "checks"} <= kinds


def test_every_verdict_is_reachable_and_has_a_label() -> None:
    reached = {_judged(status, state).verdict for status in STATUSES for state in ("open", "draft")}
    assert reached == set(get_args(Verdict.__value__)) == set(LABELS)


def test_auto_merge_keeps_the_verdict_and_says_so() -> None:
    for status in STATUSES:
        if status.auto_merge is None:
            continue
        without = _judged(status.model_copy(update={"auto_merge": None}))
        judged = _judged(status)
        assert (judged.verdict, judged.tone) == (without.verdict, without.tone)
        assert judged.auto_merge_summary is not None and "squash" in judged.auto_merge_summary


# ── The checks sentence ──────────────────────────────────────────


def test_the_checks_sentence_leads_with_the_worst_bucket_and_counts_every_check() -> None:
    for counts in itertools.product(range(3), repeat=len(BUCKETS)):
        by_bucket = dict(zip(BUCKETS, counts, strict=True))
        summary = ChecksSummary(
            state="none" if not any(counts) else "success",
            counts=by_bucket,
        )
        sentence = checks_sentence(summary)
        if not any(counts):
            assert sentence == "No checks."
            continue
        numbers = [int(word) for word in sentence.replace(",", " ").split() if word.isdigit()]
        assert sum(numbers) == sum(counts)
        assert ("not successful" in sentence) == bool(by_bucket["fail"])
