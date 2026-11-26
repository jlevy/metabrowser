"""A pull request's readiness, held by invariants over every status GitHub can report.

The statuses are generated from what each ``mergeStateStatus`` means, in GitHub's own
descriptions (plan-2026-11-26-pull-request-merge-readiness.md, "GitHub's Verdict"), rather
than pinned case by case, so a test never restates the table it checks: every claim below
must hold for each of the thousands of statuses :func:`_reportable` builds, and for the
answers GitHub gave for three real pull requests (``tests/fixtures/github-status-answers.json``).
"""

from __future__ import annotations

import asyncio
import copy
import itertools
import re
from collections.abc import Iterator, Mapping
from datetime import datetime
from typing import Any, get_args

import pytest

from metabrowser.builtin_plugins.github import pull_status_read
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
    Bucket,
    CheckItem,
    ChecksSummary,
    MergeState,
    PullChecks,
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
from metabrowser.builtin_plugins.github.pull_status_read import StatusRead, read_pull_status
from tests.github_pull_fixture import READER, LiveStatusAnswer, live_status_answers

HEAD = "a" * 40
OTHER_HEAD = "b" * 40
BASE_REF = "main"
URL = "https://github.com/octo/demo/pull/7"
OBSERVED_AT = "2026-11-26T08:00:00Z"

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

# The states GitHub lets merge now: mergeable, and any check not passing is not required.
_MERGES_NOW: frozenset[MergeState] = frozenset(("clean", "has_hooks", "unstable"))
# Of those, the ones whose commit status is passing.
_PASSING: frozenset[MergeState] = frozenset(("clean", "has_hooks"))

type Required = tuple[int, int] | None
"""How many required checks fail and are pending, as a whole list says, or unknown."""


def _summary(rollup: RollupState, required: Required) -> ChecksSummary:
    """A summary whose counts agree with its rollup, as GitHub's do, with *required*'s
    counts when a list of the checks gave them."""

    runs = {
        "success": {"SUCCESS": 3, "SKIPPED": 1},
        "failure": {"SUCCESS": 2, "FAILURE": 1},
        "error": {"SUCCESS": 2},
        "pending": {"SUCCESS": 2, "IN_PROGRESS": 1},
        "expected": {"SUCCESS": 2},
        "none": {},
    }[rollup]
    statuses = {"error": {"ERROR": 1}, "expected": {"EXPECTED": 1}}.get(rollup, {})
    failing, pending = required if required is not None else (None, None)
    return ChecksSummary(
        state=rollup,
        counts=bucket_counts(runs, statuses),
        required_failing=failing,
        required_pending=pending,
        listed_at=None if required is None else OBSERVED_AT,
    )


def _required_counts(rollup: RollupState, *, merges_now: bool) -> Iterator[Required]:
    """What a list can say of the required checks under *rollup*: unknown, none failing or
    pending, or the one failing or pending check required, which a pull request GitHub
    lets merge never has."""

    yield None
    yield (0, 0)
    if merges_now or rollup == "none":
        return
    if state_bucket(rollup) == "fail":
        yield (1, 0)
    elif state_bucket(rollup) == "pending":
        yield (0, 1)


def _reportable() -> Iterator[PullStatus]:
    """Every status GitHub can report, by what each ``mergeStateStatus`` means.

    ``CLEAN`` and ``HAS_HOOKS`` are mergeable with passing checks; ``UNSTABLE`` mergeable
    with checks not passing, none of them required; ``BLOCKED`` and ``BEHIND`` mergeable,
    a rule unmet; ``DIRTY`` conflicting, since conflicts win over everything else; and
    ``UNKNOWN`` anything, while GitHub computes. A required review not yet given blocks a
    merge, so a pull request GitHub lets merge has no review decision or an approval.
    """

    reviews: tuple[ReviewDecision | None, ...] = (None, *get_args(ReviewDecision.__value__))
    queues: tuple[QueueState | None, ...] = (None, *get_args(QueueState.__value__))
    for merge in get_args(MergeState.__value__):
        merges_now = merge in _MERGES_NOW
        conflicts = (
            ("conflicting",)
            if merge == "dirty"
            else ("mergeable", "conflicting", "unknown")
            if merge == "unknown"
            else ("mergeable",)
        )
        for mergeable, review, rollup, queue, auto in itertools.product(
            conflicts,
            (None, "approved") if merges_now else reviews,
            get_args(RollupState.__value__),
            queues,
            (False, True),
        ):
            passing = state_bucket(rollup) == "pass" or rollup == "none"
            if (merge in _PASSING and not passing) or (merge == "unstable" and passing):
                continue
            for required in _required_counts(rollup, merges_now=merges_now):
                yield _status(
                    conflicts=mergeable,
                    merge=merge,
                    review=review,
                    checks=_summary(rollup, required),
                    queue=queue,
                    auto=auto,
                )


def _status(
    *,
    conflicts: str,
    merge: MergeState,
    review: ReviewDecision | None,
    checks: ChecksSummary,
    queue: QueueState | None = None,
    auto: bool = False,
    head: str = HEAD,
    base_ref: str = BASE_REF,
) -> PullStatus:
    return PullStatus.model_validate(
        {
            "number": 7,
            "head": head,
            "base_ref": base_ref,
            "observed_at": OBSERVED_AT,
            "observed_by": "read",
            "conflicts": conflicts,
            "merge_state": merge,
            "review_decision": review,
            "checks": checks,
            "auto_merge": AutoMerge(method="squash") if auto else None,
            "queue": QueueEntry(state=queue, position=2) if queue else None,
        }
    )


STATUSES = tuple(_reportable())


def _judged(
    status: PullStatus, state: DisplayState = "open", listed: PullChecks | None = None
) -> Readiness:
    judged = readiness(
        state=state,
        head=status.head,
        base_ref=status.base_ref,
        status=status,
        listed=listed,
        html_url=URL,
    )
    assert judged is not None
    return judged


def _rows(judged: Readiness) -> dict[str, str]:
    return {row.kind: row.status for row in judged.requirements}


def _holds_githubs_verdict(status: PullStatus, judged: Readiness) -> None:
    """The verdict agrees with ``mergeStateStatus`` and the required checks' counts."""

    rows = _rows(judged)
    # A pull request GitHub lets merge is never blocked, and never conflicts.
    if status.merge_state in _MERGES_NOW:
        assert judged.verdict != "blocked" and "rules" not in rows, status
        assert rows["conflicts"] == "met", status
    # One whose merge commit cannot be made always shows its conflicts, in red.
    if status.merge_state == "dirty" or status.conflicts == "conflicting":
        assert rows["conflicts"] == "unmet" and judged.tone == "danger", status
    # A block no required check explains is a review's or a rule's, and says which.
    known_clear = (status.checks.required_failing, status.checks.required_pending) == (0, 0)
    if status.merge_state == "blocked" and status.queue is None and known_clear:
        assert rows.get("reviews", "met") != "met" or rows.get("rules") == "unmet", status
        if rows.get("reviews", "met") == "met" and rows["checks"] != "unmet":
            assert judged.verdict == "blocked", status
    # A block with a required check failing or pending is the checks'.
    if status.merge_state == "blocked" and not known_clear and status.checks.listed_at:
        assert rows["checks"] != "met" and "rules" not in rows, status
    # A block with every other requirement met is blocked, never ready.
    others = [state for kind, state in rows.items() if kind != "rules"]
    if status.merge_state == "blocked" and all(state == "met" for state in others):
        assert judged.verdict == "blocked", status
    # Only an update the rules require is behind, and nothing GitHub has not answered is
    # judged.
    assert ("up_to_date" in rows) == (status.merge_state == "behind"), status
    if status.merge_state == "unknown":
        assert rows["rules"] == "unknown", status


def test_the_reportable_statuses_cover_every_merge_state_and_rollup() -> None:
    assert {status.merge_state for status in STATUSES} == set(get_args(MergeState.__value__))
    assert {status.checks.state for status in STATUSES} == set(get_args(RollupState.__value__))
    assert len(STATUSES) > 1000


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


def test_every_verdict_agrees_with_githubs_merge_state_and_required_checks() -> None:
    for status in STATUSES:
        _holds_githubs_verdict(status, _judged(status))


def test_closed_and_merged_pull_requests_have_no_readiness() -> None:
    for state in ("closed", "merged"):
        for status in STATUSES[:50]:
            judged = readiness(state=state, head=HEAD, base_ref=BASE_REF, status=status)
            assert judged is None


def test_a_status_of_another_head_or_base_or_none_is_never_shown_as_current() -> None:
    """A push GitHub has not been read since, a retarget that kept the head, as when the
    layer below a stacked pull request merges, and no status at all are each ``checking``."""

    clean = _summary("success", (0, 0))
    pushed = _status(
        conflicts="mergeable", merge="clean", review=None, checks=clean, head=OTHER_HEAD
    )
    retargeted = _status(
        conflicts="conflicting", merge="dirty", review=None, checks=clean, base_ref="layer-1"
    )
    for status in (pushed, retargeted, None):
        judged = readiness(state="open", head=HEAD, base_ref=BASE_REF, status=status)
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


def test_conflicts_link_to_where_github_resolves_them() -> None:
    for status in STATUSES:
        rows = {row.kind: row for row in _judged(status).requirements}
        if rows["conflicts"].status == "unmet":
            assert rows["conflicts"].github_url == f"{URL}/conflicts"


def test_the_checks_row_says_what_githubs_rollup_means() -> None:
    """Failing is the author's to fix, pending waits, and passing, or no checks, is met: by
    the bucket ``gh`` sorts the rollup's own state into, never by a reading of the counts."""

    meaning = {"fail": "unmet", "pending": "waiting", "pass": "met"}
    for status in STATUSES:
        rollup = status.checks.state
        expected = "met" if rollup == "none" else meaning[state_bucket(rollup)]
        assert _rows(_judged(status))["checks"] == expected, status


def test_rows_appear_only_where_githubs_merge_box_would_show_them() -> None:
    for status in STATUSES:
        kinds = {row.kind for row in _judged(status).requirements}
        assert ("reviews" in kinds) == (status.review_decision is not None)
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


# ── What GitHub answered ─────────────────────────────────────────


def _read(monkeypatch: pytest.MonkeyPatch, answer: LiveStatusAnswer) -> StatusRead:
    async def graph(
        _query: str, _variables: Mapping[str, Any], *, now: datetime | None = None
    ) -> dict[str, Any]:
        return copy.deepcopy(answer.data)

    monkeypatch.setattr(pull_status_read, "gh_graphql", graph)
    return asyncio.run(
        read_pull_status(
            answer.owner,
            answer.repo,
            answer.number,
            reader=f"gh:{READER}",
            now=lambda: datetime.fromisoformat("2026-11-26T12:00:00+00:00"),
        )
    )


@pytest.mark.parametrize("answer", live_status_answers(), ids=lambda answer: answer.name)
def test_githubs_own_answers_get_the_verdict_their_merge_state_says(
    monkeypatch: pytest.MonkeyPatch, answer: LiveStatusAnswer
) -> None:
    read = _read(monkeypatch, answer)
    judged = _judged(read.status, listed=read.checks)
    _holds_githubs_verdict(read.status, judged)


def test_an_approved_block_with_every_required_check_passing_is_a_rules_block(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """kubernetes/enhancements#6506: GitHub says BLOCKED, and its only pending check, tide,
    is not required, so the pending checks are not why."""

    (answer,) = [each for each in live_status_answers() if each.repo == "enhancements"]
    read = _read(monkeypatch, answer)
    assert (read.status.checks.required_failing, read.status.checks.required_pending) == (0, 0)
    judged = _judged(read.status, listed=read.checks)
    assert (judged.verdict, _rows(judged)["rules"], _rows(judged)["checks"]) == (
        "blocked",
        "unmet",
        "waiting",
    )


# ── The checks sentence ──────────────────────────────────────────

_TALLY = re.compile(
    r"(?P<count>\d+) (?P<word>cancelled|failing|successful|skipped|pending)"
    r"(?: \((?P<required>\d+) required\))?"
)
_WORDS: dict[str, Bucket] = {
    "cancelled": "cancel",
    "failing": "fail",
    "successful": "pass",
    "skipped": "skipping",
    "pending": "pending",
}


def _tallies(sentence: str) -> dict[Bucket, tuple[int, int]]:
    """Each bucket the sentence counts: its checks, and the required ones it names."""

    return {
        _WORDS[found["word"]]: (int(found["count"]), int(found["required"] or 0))
        for found in _TALLY.finditer(sentence)
    }


def _lists() -> Iterator[PullChecks]:
    """Every list of up to three checks over the buckets, each required or not."""

    for size in range(4):
        for buckets in itertools.product(BUCKETS, repeat=size):
            for required in itertools.product((False, True), repeat=size):
                items = tuple(
                    CheckItem(name=str(at), kind="run", bucket=bucket, required=flag)
                    for at, (bucket, flag) in enumerate(zip(buckets, required, strict=True))
                )
                yield PullChecks(number=7, head=HEAD, observed_at=OBSERVED_AT, items=items)


def test_the_page_sentence_tallies_exactly_the_checks_it_lists() -> None:
    """Each bucket's tally is how many listed checks are in it, as ``gh pr checks`` counts
    them; the required ones are named beside the cancelled and the failing, each in its own
    bucket; and it leads with the worst bucket that has a check."""

    for listed in _lists():
        sentence = checks_sentence(listed)
        if not listed.items:
            assert sentence == "No checks."
            continue
        counted = {
            bucket: (
                sum(item.bucket == bucket for item in listed.items),
                sum(item.bucket == bucket and item.required is True for item in listed.items)
                if bucket in ("cancel", "fail")
                else 0,
            )
            for bucket in BUCKETS
        }
        assert _tallies(sentence) == {b: tally for b, tally in counted.items() if tally[0]}
        assert ("not successful" in sentence) == bool(counted["fail"][0])


def test_a_list_that_does_not_say_which_checks_are_required_names_none() -> None:
    items = (
        CheckItem(name="a", kind="run", bucket="fail", required=True),
        CheckItem(name="b", kind="run", bucket="fail", required=None),
    )
    listed = PullChecks(number=7, head=HEAD, observed_at=OBSERVED_AT, items=items)
    assert _tallies(checks_sentence(listed)) == {"fail": (2, 0)}


def test_the_rollups_sentence_counts_every_context_and_never_a_list_s_required_ones() -> None:
    """GitHub's counts, as ``gh pr status`` reads them, beside which a list's required counts
    would count other checks: a run GitHub made twice is two contexts and one listed check."""

    for counts in itertools.product(range(3), repeat=len(BUCKETS)):
        by_bucket = dict(zip(BUCKETS, counts, strict=True))
        summary = ChecksSummary(
            state="none" if not any(counts) else "failure",
            counts=by_bucket,  # pyright: ignore[reportArgumentType]
            required_failing=None if not any(counts) else 1,
            required_pending=None if not any(counts) else 1,
            listed_at=None if not any(counts) else OBSERVED_AT,
        )
        sentence = checks_sentence(summary)
        if not any(counts):
            assert sentence == "No checks."
            continue
        assert _tallies(sentence) == {b: (n, 0) for b, n in by_bucket.items() if n}


def test_the_checks_row_counts_the_whole_list_the_page_shows_and_otherwise_the_rollup() -> None:
    """Beside the list the status counts, the row says what the list says; beside a list cut
    short, of another read, or none, what GitHub's rollup says."""

    summary = _summary("failure", (1, 0))
    status = _status(conflicts="mergeable", merge="blocked", review=None, checks=summary)
    run = CheckItem(name="build", kind="run", bucket="fail", required=True)
    whole = PullChecks(number=7, head=HEAD, observed_at=OBSERVED_AT, items=(run,))
    for listed, counted in (
        (whole, whole),
        (whole.model_copy(update={"truncated": True}), summary),
        (whole.model_copy(update={"observed_at": "2026-11-26T07:00:00Z"}), summary),
        (None, summary),
    ):
        row = {row.kind: row for row in _judged(status, listed=listed).requirements}["checks"]
        assert row.summary.startswith(checks_sentence(counted)), listed
