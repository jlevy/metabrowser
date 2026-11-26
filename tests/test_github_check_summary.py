"""How the pull-request page lists a head's checks: in the server's buckets, as gh does.

Whether a check passes, fails, or waits is GitHub's call, which the server makes once
(``state_bucket`` in ``builtin_plugins/github/pull_status.py``) and the Checks tab only
draws: ``checksInOrder``, ``checksSummary``, and ``checkLabel`` in ``pull-page.js``. These
hold the page to the server, not to a copy of either: every bucket has a badge in the ink
GitHub's CLI gives it, the summary leads with the words ``checks_sentence`` in
``pull_readiness.py`` says for the same counts, and the list is ordered as ``gh pr checks``
orders it.
"""

from __future__ import annotations

import json
import re
import subprocess
from itertools import product
from pathlib import Path
from typing import Any

import pytest

from metabrowser.builtin_plugins.github.pull_readiness import checks_sentence
from metabrowser.builtin_plugins.github.pull_status import (
    BUCKETS,
    ChecksSummary,
    check_run_bucket,
    state_bucket,
)
from tests.required_tools import needs_node

PULL_PAGE_JS = (
    Path(__file__).resolve().parent.parent / "src/metabrowser/builtin_plugins/github/pull-page.js"
)

pytestmark = needs_node

_RUN = r"""
const [pageUrl, input] = process.argv.slice(1);
import(pageUrl).then(({ checkLabel, checksInOrder, checksSummary }) => {
  const { summaries, order, labels } = JSON.parse(input);
  process.stdout.write(JSON.stringify({
    summaries: summaries.map((items) => checksSummary(items)),
    order: checksInOrder(order).map((item) => item.name),
    labels: labels.map((item) => checkLabel(item)),
  }));
});
"""

# Each bucket's count, from none to two: every combination of which buckets have checks.
_COUNTS: list[dict[str, int]] = [
    dict(zip(BUCKETS, counts, strict=True)) for counts in product((0, 1, 2), repeat=len(BUCKETS))
]

# Check runs as GitHub reports them, (status, conclusion), and commit statuses by state,
# each with the words its badge says.
_RUNS: list[tuple[str, str | None, str]] = [
    ("QUEUED", None, "queued"),
    ("IN_PROGRESS", None, "in progress"),
    ("IN_PROGRESS", "SUCCESS", "in progress"),
    ("COMPLETED", "SUCCESS", "success"),
    ("COMPLETED", "STARTUP_FAILURE", "startup failure"),
    ("COMPLETED", "STALE", "stale"),
    ("COMPLETED", "CANCELLED", "cancelled"),
    ("COMPLETED", None, "completed"),
]
_STATUSES: list[tuple[str, str]] = [("SUCCESS", "success"), ("EXPECTED", "expected")]


@pytest.fixture(scope="module")
def drawn() -> dict[str, Any]:
    order = [
        {"name": f"{bucket} {at}", "bucket": bucket}
        for at in range(2)
        for bucket in ("pass", "skipping", "pending", "cancel", "fail")
    ]
    labels = [
        {"kind": "run", "status": status, "conclusion": conclusion}
        for status, conclusion, _ in _RUNS
    ] + [{"kind": "status", "conclusion": state} for state, _ in _STATUSES]
    payload = {
        "summaries": [
            [{"bucket": bucket} for bucket, count in counts.items() for _ in range(count)]
            for counts in _COUNTS
        ],
        "order": order,
        "labels": labels,
    }
    completed = subprocess.run(
        ["node", "-e", _RUN, PULL_PAGE_JS.as_uri(), json.dumps(payload)],
        capture_output=True,
        text=True,
        timeout=50,
        check=True,
    )
    return json.loads(completed.stdout)


@pytest.mark.parametrize(("index", "counts"), list(enumerate(_COUNTS)))
def test_the_summary_leads_with_the_words_the_server_says(
    drawn: dict[str, Any], index: int, counts: dict[str, int]
) -> None:
    """The page's headline and tallies are ``checks_sentence``'s, which the readiness
    requirement says, for the same counts: the order of precedence, the words, and the
    tallies' order, zeros left out."""

    if not any(counts.values()):
        return
    said = drawn["summaries"][index]
    tallies = [f"{count} {word}" for word, count in said["counts"].items()]
    listed = tallies[0] if len(tallies) == 1 else ", ".join(tallies[:-1]) + f", and {tallies[-1]}"
    summary = ChecksSummary(state="pending", counts=counts)  # pyright: ignore[reportArgumentType]
    assert f"{said['headline']}: {listed}." == checks_sentence(summary)


def test_failing_checks_list_first_then_pending_then_the_rest_as_listed(
    drawn: dict[str, Any],
) -> None:
    assert drawn["order"] == [
        "fail 0",
        "fail 1",
        "pending 0",
        "pending 1",
        "pass 0",
        "skipping 0",
        "cancel 0",
        "pass 1",
        "skipping 1",
        "cancel 1",
    ]


@pytest.mark.parametrize(
    ("index", "said"), list(enumerate([words for *_, words in _RUNS] + [w for _, w in _STATUSES]))
)
def test_each_check_says_the_state_github_named(
    drawn: dict[str, Any], index: int, said: str
) -> None:
    """The words are GitHub's state; the ink is the bucket's, not a reading of the words."""

    assert drawn["labels"][index] == said


def test_every_bucket_has_its_badge_in_the_ink_gh_gives_it() -> None:
    """``gh pr checks`` marks pass green, fail red, pending yellow, and skipping and cancel
    muted (plan-2026-11-26-pull-request-merge-readiness.md, "How GitHub Classifies Each
    State"); each bucket the server sorts a check into has exactly that badge ink."""

    css = (PULL_PAGE_JS.parent / "styles.css").read_text(encoding="utf-8")
    inks = {
        "pass": "var(--status-success-text)",
        "fail": "var(--status-error-text)",
        "pending": "var(--status-warning-text)",
        "skipping": "var(--muted)",
        "cancel": "var(--muted)",
    }
    assert set(inks) == set(BUCKETS)
    for bucket, ink in inks.items():
        rule = re.search(
            r'\.github-pull-badge\[data-state="' + bucket + r'"\][^{]*\{\s*color: ([^;]+);', css
        )
        assert rule is not None and rule.group(1) == ink, bucket
    # Every state GitHub reports lands in one of them, a state it adds later among them.
    for status, conclusion, _ in _RUNS:
        assert check_run_bucket(status, conclusion) in BUCKETS
    assert state_bucket("A_STATE_GITHUB_ADDS_LATER") == "pending"
