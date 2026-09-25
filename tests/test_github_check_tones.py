"""How the pull-request page labels and counts each check run and commit status.

``checkRunResult`` and ``commitStatusResult`` in ``builtin_plugins/github/pull-page.js``
decide the tone a check is painted with and the count it joins in the Checks summary.
This table runs them over every status and conclusion GitHub documents for a check run
(REST ``check-runs``, and GraphQL's ``CheckConclusionState`` for ``startup_failure``)
and every state of a commit status, plus the values GitHub does not send, so a new or
missing value lands somewhere stated rather than in neutral.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

PULL_PAGE_JS = (
    Path(__file__).resolve().parent.parent / "src/metabrowser/builtin_plugins/github/pull-page.js"
)

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not available")

# (status, conclusion) of a check run -> (tone, label).
CHECK_RUNS: list[tuple[Any, Any, str, str]] = [
    # Not completed: every status GitHub documents, and none at all, is pending.
    ("queued", None, "pending", "queued"),
    ("in_progress", None, "pending", "in progress"),
    ("waiting", None, "pending", "waiting"),
    ("requested", None, "pending", "requested"),
    ("pending", None, "pending", "pending"),
    ("", None, "pending", "pending"),
    (None, None, "pending", "pending"),
    # A conclusion is read only once the run completed.
    ("in_progress", "success", "pending", "in progress"),
    # Completed: each documented conclusion.
    ("completed", "success", "success", "success"),
    ("completed", "failure", "failure", "failure"),
    ("completed", "timed_out", "failure", "timed out"),
    ("completed", "action_required", "failure", "action required"),
    ("completed", "startup_failure", "failure", "startup failure"),
    ("completed", "cancelled", "cancelled", "cancelled"),
    ("completed", "skipped", "skipped", "skipped"),
    ("completed", "stale", "stale", "stale"),
    ("completed", "neutral", "neutral", "neutral"),
    # Completed with no conclusion, or one GitHub does not document.
    ("completed", None, "unknown", "no conclusion"),
    ("completed", "", "unknown", "no conclusion"),
    ("completed", "exploded", "unknown", "exploded"),
    ("completed", "constructor", "unknown", "constructor"),
]

# state of a commit status -> (tone, label).
STATUSES: list[tuple[Any, str, str]] = [
    ("success", "success", "success"),
    ("failure", "failure", "failure"),
    ("error", "failure", "error"),
    ("pending", "pending", "pending"),
    ("", "unknown", "unknown"),
    (None, "unknown", "unknown"),
    ("toString", "unknown", "toString"),
]

_RUN = r"""
const [pageUrl, input] = process.argv.slice(1);
import(pageUrl).then(({ checkRunResult, commitStatusResult }) => {
  const { runs, statuses } = JSON.parse(input);
  process.stdout.write(JSON.stringify({
    runs: runs.map((run) => checkRunResult(run)),
    statuses: statuses.map((status) => commitStatusResult(status)),
  }));
});
"""


@pytest.fixture(scope="module")
def results() -> dict[str, list[dict[str, str]]]:
    payload = {
        "runs": [
            {"status": status, "conclusion": conclusion} for status, conclusion, *_ in CHECK_RUNS
        ],
        "statuses": [{"state": state} for state, *_ in STATUSES],
    }
    completed = subprocess.run(
        ["node", "-e", _RUN, PULL_PAGE_JS.as_uri(), json.dumps(payload)],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    return json.loads(completed.stdout)


@pytest.mark.parametrize(("index", "case"), list(enumerate(CHECK_RUNS)))
def test_each_check_run_is_labeled_and_counted(
    results: dict[str, list[dict[str, str]]], index: int, case: tuple[Any, Any, str, str]
) -> None:
    _status, _conclusion, tone, label = case
    assert results["runs"][index] == {"tone": tone, "label": label}


@pytest.mark.parametrize(("index", "case"), list(enumerate(STATUSES)))
def test_each_commit_status_is_labeled_and_counted(
    results: dict[str, list[dict[str, str]]], index: int, case: tuple[Any, str, str]
) -> None:
    _state, tone, label = case
    assert results["statuses"][index] == {"tone": tone, "label": label}


def test_every_tone_has_a_badge_color() -> None:
    css = (PULL_PAGE_JS.parent / "styles.css").read_text(encoding="utf-8")
    tones = {tone for *_, tone, _label in CHECK_RUNS} | {tone for _state, tone, _label in STATUSES}
    for tone in tones:
        assert f'.github-pull-badge[data-state="{tone}"]' in css, tone
