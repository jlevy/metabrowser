"""The run's Chrome warm-up, and every headless Chrome start the suite made, summarized.

A CI runner's first Chrome start is cold, and a start cut off before it finishes leaves
the next one cold too. Over the newest 200 runs of ci.yml on 2026-11-18 (44041121764 to
44232615626, every attempt):

- Of the 150 Chrome jobs whose part opens with a test that only drives Chrome, that test
  took 4.6 to 28.8 s (median 9.3) more than its warm median of 1.5 to 3.2 s in 102, one
  of them cut off at the start's bound. The part's second test took its usual time after
  a slow first start as after a fast one.
- All 8 "Chrome wrote no DevTools port" failures, one in a Chrome job and seven in the
  earlier whole-suite ``test`` jobs, came at the start's 30 s bound in the job's first
  Chrome test, with Chrome still running. The next start in the job took 13 to 67 s more
  than warm, or was cut off as well (in two jobs; five in a row in one).

So a second start after the bound would have saved at most one of the 8 within its
test's budget. Instead, before the first test that drives Chrome, the run starts Chrome
once and closes it, under a bound of its own that no test's budget has to hold
(``warm_up``).

``tests/dom/chrome-session.mjs`` appends one JSON line per start, the warm-up's too, to
the file that ``METABROWSER_CHROME_STARTS`` names, which ``chrome_profile``
(``tests/conftest.py``) sets for each test that drives Chrome. A start that fails is made
again, so a run that a retry kept green would not otherwise show that one failed. The
summary says how many starts there were, the slowest, and each that failed with the end
of Chrome's stderr: how long a runner's cold start takes and how often a start fails,
measured on every run.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, cast

import pytest

from tests.process_group import GROUP_STOP_S, owned_profile, run_in_own_group
from tests.required_tools import find_chrome, require_node

STARTS_ENV = "METABROWSER_CHROME_STARTS"
LOG_NAME = "chrome-starts.jsonl"
# Under pytest-xdist each worker's base is ``popen-gw<N>`` in the run's.
_LOG_PATTERNS = (LOG_NAME, f"popen-gw*/{LOG_NAME}")
# The lines of a failed start's stderr the summary repeats; the start keeps about 20.
TAIL_LINES = 12

WARM_UP = Path(__file__).resolve().parent / "dom" / "chrome-warm-up.mjs"
# The warm-up's one start: more than the longest start measured above, the 67 s more than
# warm that one took after a start cut off at 30 s, while a Chrome job's longest part
# (4.4 minutes, ci.yml's note) with this added still ends inside the job's timeout-minutes.
WARM_UP_BOUND_S = 90.0
# After the start: the close, which gives Chrome 5 s to exit (EXIT_WAIT_MS in
# chrome-session.mjs) before removing its profile.
WARM_UP_CLOSE_S = 10.0
WARM_UP_LABEL = "the run's Chrome warm-up"


def log_path(basetemp: Path) -> Path:
    """Where this process's Chrome starts are noted, under its pytest base directory."""

    return basetemp / LOG_NAME


def warm_up(basetemp: Path) -> None:
    """Start Chrome once and close it, so the tests that follow start a warm one.

    Without Chrome there is nothing to warm, and the tests skip on their own. Without
    Node the run stops here, as the first test would stop it, or, where Node may be
    missing, the tests skip and so does the warm-up (``tests/required_tools.py``). A
    warm-up that fails is noted like any start and the run goes on: each test's start
    keeps its own bound and retry.
    """

    chrome = find_chrome()
    if chrome is None:
        return
    try:
        node = require_node()
    except pytest.skip.Exception:
        return
    log = log_path(basetemp)
    try:
        with owned_profile("metab-chrome-warm-up-") as profile:
            run = run_in_own_group(
                [node, str(WARM_UP), str(int(WARM_UP_BOUND_S * 1000))],
                timeout_s=WARM_UP_BOUND_S + WARM_UP_CLOSE_S,
                env={
                    **os.environ,
                    "CHROME_BIN": chrome,
                    "CHROME_PROFILES": str(profile),
                    STARTS_ENV: str(log),
                    "PYTEST_CURRENT_TEST": WARM_UP_LABEL,
                },
            )
    except AssertionError as error:
        # owned_profile's report of a process left on the profile, or of the profile
        # left behind: the warm-up is not a test, so it is noted, not raised.
        _note(log, f"left something behind: {error}", "")
        return
    if run.timed_out:
        limit = WARM_UP_BOUND_S + WARM_UP_CLOSE_S + GROUP_STOP_S
        _note(log, f"ran past {limit:g} s and was stopped", run.stderr)


def _note(log: Path, failure: str, tail: str) -> None:
    record = {"test": WARM_UP_LABEL, "attempt": 1, "ok": False, "failure": failure, "tail": tail}
    with log.open("a", encoding="utf-8") as out:
        out.write(json.dumps(record) + "\n")


def _test(record: dict[str, Any]) -> str:
    # PYTEST_CURRENT_TEST, less the phase pytest appends: "tests/x.py::test_y (call)".
    test = record.get("test")
    return str(test).rsplit(" (", 1)[0] if test else "outside a test"


def summary(basetemp: Path) -> list[str]:
    """The summary's lines, none when no Chrome started."""

    records: list[dict[str, Any]] = []
    unreadable = 0
    for pattern in _LOG_PATTERNS:
        for log in sorted(basetemp.glob(pattern)):
            for line in log.read_text(encoding="utf-8").splitlines():
                try:
                    records.append(cast(dict[str, Any], json.loads(line)))
                except json.JSONDecodeError:
                    # A session killed while it wrote leaves part of a line.
                    unreadable += 1
    if not records and not unreadable:
        return []
    failed = [record for record in records if not record.get("ok")]
    head = f"chrome starts: {len(records)}, {len(failed)} failed"
    answered = [record for record in records if record.get("ok")]
    if answered:
        slowest = max(answered, key=lambda record: float(record["ms"]))
        head += (
            f"; slowest {float(slowest['ms']) / 1000:.1f} s"
            f" ({_test(slowest)}, start {slowest['attempt']})"
        )
    if unreadable:
        head += f"; {unreadable} unreadable line(s)"
    lines = [head]
    for record in failed:
        lines.append(f"  {_test(record)}: start {record['attempt']} {record['failure']}")
        tail = str(record.get("tail") or "").splitlines()[-TAIL_LINES:]
        lines.extend(f"    {line}" for line in tail)
    return lines
