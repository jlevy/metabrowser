"""How the pull-request page lists a head's checks: in the server's buckets, as gh does.

Whether a check passes, fails, or waits is GitHub's call, which the server makes once
(``state_bucket`` in ``builtin_plugins/github/pull_status.py``) and the Checks tab only
draws: ``checksInOrder``, ``checksSummary``, and ``checkLabel`` in ``pull-page.js``. These
hold the page to the server and to what ``gh pr checks`` means, not to a copy of either:
every bucket has a badge inked by what it means, by the design tokens' own names, the
summary over a list says what ``checks_sentence`` in ``pull_readiness.py`` says of the same
list, which the merge status section's checks row says above it, and every list of checks
is ordered as ``gh pr checks`` orders it.
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
    CheckItem,
    PullChecks,
    check_run_bucket,
    state_bucket,
)
from tests.required_tools import needs_node
from tests.test_design_vocabulary import _rules_of, _theme_tokens

PULL_PAGE_JS = (
    Path(__file__).resolve().parent.parent / "src/metabrowser/builtin_plugins/github/pull-page.js"
)

pytestmark = needs_node

_RUN = r"""
const fs = require("node:fs");
const [pageUrl] = process.argv.slice(1);
const { summaries, orders, labels } = JSON.parse(fs.readFileSync(0, "utf8"));
import(pageUrl).then(({ checkLabel, checksInOrder, checksSummary }) => {
  process.stdout.write(JSON.stringify({
    summaries: summaries.map((items) => checksSummary(items)),
    orders: orders.map((items) => checksInOrder(items).map((item) => item.name)),
    labels: labels.map((item) => checkLabel(item)),
  }));
});
"""

# Each bucket's count, from none to two: every combination of which buckets have checks.
_COUNTS: list[dict[str, int]] = [
    dict(zip(BUCKETS, counts, strict=True)) for counts in product((0, 1, 2), repeat=len(BUCKETS))
]

# Every list of up to four checks over the buckets, each check named by its place in it.
_ORDERS: list[list[dict[str, str]]] = [
    [{"name": str(at), "bucket": bucket} for at, bucket in enumerate(buckets)]
    for size in range(5)
    for buckets in product(BUCKETS, repeat=size)
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

# A design token's name says its family: a status's text ink is `--status-<family>-text`.
_TOKEN = re.compile(r"var\((?P<name>--[\w-]+)\)")
_STATUS_INK = re.compile(r"--status-(?P<family>[a-z]+)-text")


@pytest.fixture(scope="module")
def drawn() -> dict[str, Any]:
    labels = [
        {"kind": "run", "status": status, "conclusion": conclusion}
        for status, conclusion, _ in _RUNS
    ] + [{"kind": "status", "conclusion": state} for state, _ in _STATUSES]
    payload = {
        "summaries": [
            [{"bucket": bucket} for bucket, count in counts.items() for _ in range(count)]
            for counts in _COUNTS
        ],
        "orders": _ORDERS,
        "labels": labels,
    }
    completed = subprocess.run(
        ["node", "-e", _RUN, PULL_PAGE_JS.as_uri()],
        input=json.dumps(payload),
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
    """The page's headline and tallies over a list are ``checks_sentence``'s over the same
    list, which the readiness requirement says above it: the order of precedence, the
    words, and the tallies' order, zeros left out."""

    if not any(counts.values()):
        return
    said = drawn["summaries"][index]
    tallies = [f"{count} {word}" for word, count in said["counts"].items()]
    listed = tallies[0] if len(tallies) == 1 else ", ".join(tallies[:-1]) + f", and {tallies[-1]}"
    items = tuple(
        CheckItem(name=f"{bucket} {at}", kind="run", bucket=bucket)  # pyright: ignore[reportArgumentType]
        for bucket, count in counts.items()
        for at in range(count)
    )
    checks = PullChecks(number=1, head="a" * 40, observed_at="2026-11-26T12:00:00Z", items=items)
    assert f"{said['headline']}: {listed}." == checks_sentence(checks)


def _rank(bucket: str) -> int:
    """Where ``gh pr checks`` lists a check of *bucket*: failing ones first, then pending
    ones, then the rest (plan-2026-11-26-pull-request-merge-readiness.md)."""

    return 0 if bucket == "fail" else 1 if bucket == "pending" else 2


def test_failing_checks_list_first_then_pending_then_the_rest_each_as_given(
    drawn: dict[str, Any],
) -> None:
    """Over every list of up to four checks: the page lists each check once, none after a
    check gh lists later, and the checks gh lists together in the order they were given."""

    for items, listed in zip(_ORDERS, drawn["orders"], strict=True):
        places = [int(name) for name in listed]
        assert sorted(places) == list(range(len(items))), listed
        ranks = [_rank(items[at]["bucket"]) for at in places]
        assert ranks == sorted(ranks), listed
        for rank in set(ranks):
            together = [at for at in places if _rank(items[at]["bucket"]) == rank]
            assert together == sorted(together), listed


@pytest.mark.parametrize(
    ("index", "said"), list(enumerate([words for *_, words in _RUNS] + [w for _, w in _STATUSES]))
)
def test_each_check_says_the_state_github_named(
    drawn: dict[str, Any], index: int, said: str
) -> None:
    """The words are GitHub's state; the ink is the bucket's, not a reading of the words."""

    assert drawn["labels"][index] == said


def _badge_tokens() -> dict[str, str]:
    """The design token each bucket's badge is inked with: the ``color`` of the plugin's
    rule for ``.github-pull-badge`` in that state, by its token's name."""

    colors = {
        selector: declarations["color"]
        for selector, declarations in _rules_of(PULL_PAGE_JS.parent / "styles.css")
        if "color" in declarations
    }
    tokens: dict[str, str] = {}
    for bucket in BUCKETS:
        ink = colors.get(f'.github-pull-badge[data-state="{bucket}"]')
        assert ink is not None, f"no badge rule inks {bucket}"
        token = _TOKEN.fullmatch(ink)
        assert token is not None, f"{bucket}'s badge is inked {ink}, not a token"
        tokens[bucket] = token.group("name")
    return tokens


def test_every_bucket_has_a_badge_inked_by_what_it_means() -> None:
    """``gh pr checks`` marks pass green, fail red, pending yellow, and skipping and cancel
    muted (plan-2026-11-26-pull-request-merge-readiness.md, "How GitHub Classifies Each
    State"). Each bucket's badge takes a token the shell defines; pass, fail, and pending
    take status text inks, of the success family, the error family, and a third, as the
    tokens' names say; skipping and cancel take the muted ink, no status's."""

    tokens = _badge_tokens()
    defined = _theme_tokens()["light"]
    for bucket, token in tokens.items():
        assert token in defined, f"{bucket}'s badge ink {token} is no shell token"
    families = {
        bucket: found.group("family")
        for bucket, token in tokens.items()
        if (found := _STATUS_INK.fullmatch(token)) is not None
    }
    assert set(families) == {"pass", "fail", "pending"}, families
    assert (families["pass"], families["fail"]) == ("success", "error")
    assert families["pending"] not in {families["pass"], families["fail"]}
    for bucket in ("skipping", "cancel"):
        assert "muted" in tokens[bucket], bucket


def test_every_state_github_reports_lands_in_a_bucket() -> None:
    """Every state GitHub reports lands in a bucket, and one it adds later is pending, as
    ``gh`` counts any state it does not name."""

    for status, conclusion, _ in _RUNS:
        assert check_run_bucket(status, conclusion) in BUCKETS
    assert state_bucket("A_STATE_GITHUB_ADDS_LATER") == "pending"
