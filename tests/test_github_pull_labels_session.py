"""A page whose record names its labels alone asks for the label set once and polls fast.

``tests/dom/github-pull-labels-behavior.js`` drives the production ``pull-page.js``
controller; ``tests/golden/cli-ui-github-pull-page.tryscript.md`` pins its transcript.
This holds the decisions that transcript shows (``mb-varu``): the ask on the first read
that shows a label without an entry, the fast poll while ``labels_pending`` holds, the
colored chip once the set is cached, and no ask where none is needed.
"""

from __future__ import annotations

from tests.golden_harness import run_session

PULL = "GET /api/plugin/github/pull?number=7"
ASK = "POST /api/plugin/github/labels-refresh {}"


def test_a_label_named_alone_asks_once_then_polls_fast_until_colored() -> None:
    steps = {
        step["step"]: step
        for step in run_session("github-pull-labels-behavior.js")["labelsPending"]
    }
    first = steps["a first read of labels named alone"]
    assert (first["requests"], first["poll"]) == ([PULL, ASK], "fast")
    assert first["labels"] == ["enhancement neutral no tip", "deleted-on-github neutral no tip"]
    running = steps["the set's job runs"]
    assert (running["requests"], running["poll"]) == ([f"{PULL} (If-None-Match)"], "fast")
    cached = steps["the set is cached"]
    assert cached["poll"] == "slow" and ASK not in cached["requests"]
    assert cached["labels"] == ["enhancement #2700af tip", "deleted-on-github neutral no tip"]
    assert ASK not in steps["nothing changes"]["requests"]
    # Already being read: nothing to ask, and a fast poll.
    joined = steps["a first read while the job runs"]
    assert (joined["requests"], joined["poll"]) == ([PULL], "fast")
    # Not due: one ask, and the slow poll, which asks no more.
    held = steps["a label the set does not hold"]
    assert (held["requests"], held["poll"]) == ([PULL, ASK], "slow")
    assert steps["the next poll"]["requests"] == [f"{PULL} (If-None-Match)"]
    assert steps["labels with their own colors"]["requests"] == [PULL]
