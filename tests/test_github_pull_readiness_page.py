"""The readiness scenarios the pull request page session draws, as the server decides them.

``tests/fixtures/github-pull-page-responses.json`` records one story of pull request 7,
whose verdict is Checks pending throughout. The page's header badge and its Checks tab's
Merge status section draw every verdict alike, but their links and the checks list differ
by what stands in the way, so ``tests/dom/github-pull-page-session.js`` also draws pull
request 7 as GitHub could have answered it in four more ways, each recorded here
(``tests/fixtures/github-pull-page-readiness.json``) and pinned by
``tests/golden/cli-ui-github-pull-page.tryscript.md``:

- ``conflicts``: merge conflicts, a required check failing, and changes requested;
- ``queued``: in the base branch's merge queue, second, with its estimate;
- ``listing``: a status the Pulls tab's scan read, which counts the head's checks and lists
  none, so the page has no list of its own yet;
- ``ready``: every requirement met.

Each is the recorded status with GitHub's answer changed, validated by the production model
(:class:`~.pull_status.PullStatus`, :class:`~.pull_status.PullChecks`), and its verdict is
the route's own (:func:`~.pull_route.judged_readiness`) on the recorded pull request, so the
session never draws a verdict a test wrote by hand. They are a recording of their own, so
the page's recording stays inside its review budget.
"""

from __future__ import annotations

from typing import Any

from metabrowser.builtin_plugins.github.pull_route import judged_readiness
from metabrowser.builtin_plugins.github.pull_status import (
    CheckItem,
    ChecksSummary,
    PullChecks,
    PullStatus,
    QueueEntry,
)
from metabrowser.builtin_plugins.github.pull_status_store import KeptStatus
from tests.golden_harness import check_recording, read_recording

_COUNTS = {"pass": 0, "fail": 0, "pending": 0, "skipping": 0, "cancel": 0}


def _recorded() -> tuple[dict[str, Any], PullStatus, PullChecks]:
    """Pull request 7 as the page's recording first answered it, its status read back with
    the time its checks were listed, which the recording leaves out when it is the time
    the status was observed."""

    body = read_recording("github-pull-page-responses.json")["current"]["body"]
    status = dict(body["status"])
    status["checks"] = {"listed_at": status["observed_at"], **status["checks"]}
    return (
        body["record"]["pull"],
        PullStatus.model_validate(status),
        PullChecks.model_validate(body["checks"]),
    )


def _summary(listed_at: str | None, **counts: int) -> dict[str, Any]:
    return {"counts": {**_COUNTS, **counts}, "listed_at": listed_at}


def _scenarios() -> dict[str, dict[str, Any]]:
    pull, status, checks = _recorded()
    at = status.observed_at
    by_name = {item.name: item for item in checks.items}
    docs = by_name["docs"]
    failed = docs.model_copy(
        update={"bucket": "fail", "status": "COMPLETED", "conclusion": "FAILURE"}
    )
    passed = docs.model_copy(
        update={"bucket": "pass", "status": "COMPLETED", "conclusion": "SUCCESS"}
    )

    def listed(*items: CheckItem) -> PullChecks:
        return checks.model_copy(update={"items": items})

    built: dict[str, tuple[PullStatus, PullChecks | None]] = {
        "conflicts": (
            status.model_copy(
                update={
                    "conflicts": "conflicting",
                    "merge_state": "dirty",
                    "review_decision": "changes_requested",
                    "auto_merge": None,
                    "checks": ChecksSummary(
                        state="failure",
                        **_summary(at, **{"pass": 2, "fail": 1}),
                        required_failing=1,
                        required_pending=0,
                    ),
                }
            ),
            listed(by_name["tests (3.13)"], failed, by_name["docs/readthedocs.org:demo"]),
        ),
        "queued": (
            status.model_copy(
                update={
                    "merge_state": "clean",
                    "review_decision": "approved",
                    "auto_merge": None,
                    "queue": QueueEntry(
                        state="queued",
                        position=2,
                        enqueued_at=at,
                        estimated_s=540,
                        url="https://github.com/octo/demo/queue/topic",
                    ),
                    "checks": ChecksSummary(
                        state="success",
                        **_summary(at, **{"pass": 3}),
                        required_failing=0,
                        required_pending=0,
                    ),
                }
            ),
            listed(by_name["tests (3.13)"], passed, by_name["docs/readthedocs.org:demo"]),
        ),
        # The scan counts what the rollup counts and lists no check, so it knows none of
        # them is required; the route serves no list of it (`shown_checks`).
        "listing": (
            status.model_copy(
                update={
                    "observed_by": "scan",
                    "checks": ChecksSummary(
                        state="pending", **_summary(None, **{"pass": 2, "pending": 1})
                    ),
                }
            ),
            None,
        ),
        "ready": (
            status.model_copy(
                update={
                    "merge_state": "clean",
                    "review_decision": "approved",
                    "auto_merge": None,
                    "checks": ChecksSummary(
                        state="success",
                        **_summary(at, **{"pass": 3}),
                        required_failing=0,
                        required_pending=0,
                    ),
                }
            ),
            listed(by_name["tests (3.13)"], passed, by_name["docs/readthedocs.org:demo"]),
        ),
    }
    return {
        name: {
            "status": PullStatus.model_validate(shown.model_dump()).model_dump(mode="json"),
            "readiness": judged_readiness(
                pull, KeptStatus(status=shown, checks=listing, unavailable=None)
            ),
            "checks": None if listing is None else listing.model_dump(mode="json"),
        }
        for name, (shown, listing) in built.items()
    }


def test_the_readiness_scenarios_are_what_the_server_decides() -> None:
    scenarios = _scenarios()
    verdicts = {name: scenario["readiness"]["verdict"] for name, scenario in scenarios.items()}
    assert verdicts == {
        "conflicts": "conflicts",
        "queued": "queued",
        "listing": "checks_pending",
        "ready": "ready",
    }
    # A scan's status is drawn as a read's is, so the page's only cue is the list's absence.
    listing = scenarios["listing"]
    assert listing["status"]["observed_by"] == "scan"
    assert listing["status"]["checks"]["listed_at"] is None and listing["checks"] is None
    assert any(item["required"] for item in scenarios["conflicts"]["checks"]["items"])
    check_recording(
        "github-pull-page-readiness.json",
        scenarios,
        transcript="cli-ui-github-pull-page.tryscript.md",
    )
