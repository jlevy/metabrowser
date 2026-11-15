"""The grouped answer the Group by session paints is the route's own.

``tests/dom/files-group-by-session.js`` paints ``tests/fixtures/tree-groups-answer.json``.
That file is a copy of the first answer ``tests/golden/cli-api-tree-groups.tryscript.md``
records from ``/api/tree?group_by=type``, so a change to the route that leaves the copy
behind fails here rather than leaving the session to paint an answer the server no longer
gives.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

TESTS = Path(__file__).resolve().parent
GOLDEN = TESTS / "golden" / "cli-api-tree-groups.tryscript.md"
FIXTURE = TESTS / "fixtures" / "tree-groups-answer.json"
COMMAND = "$ metab groupsroot --api '/api/tree?group_by=type&depth=1'"


def test_the_session_paints_the_answer_the_golden_records() -> None:
    text = GOLDEN.read_text(encoding="utf-8")
    block = text[text.index(COMMAND) :]
    body = re.search(r"^status: 200\n(\{.*?^\})\n\? 0$", block, re.MULTILINE | re.DOTALL)
    assert body is not None, "the golden no longer records the grouped answer"
    assert json.loads(body.group(1)) == json.loads(FIXTURE.read_text(encoding="utf-8"))
