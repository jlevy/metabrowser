"""The CLI says a change's lines as the browser does (mb-ox6a).

The owner, 2026-11-25: "removing the -0 and +0 in summaries should be a single change that
works everywhere". The browser's rule is ``changeLine`` in ``static/formatters.js``: a total
of zero is left out, a count not known is "?", and a change of no lines reads "0 lines".
``metab --diff``'s text form writes line totals in one place, ``line_totals`` in
``cli/diff_cli.py``, with ASCII signs. This runs the shipped ``formatters.js`` on the same
cases and holds the two to one answer, the minus sign aside.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from metabrowser.cli.diff_cli import line_totals
from tests.required_tools import require_node

FORMATTERS = (
    Path(__file__).resolve().parents[1] / "src" / "metabrowser" / "static" / "formatters.js"
)

# Every kind of pair: one side zero, both nonzero, both zero, and a count not known.
CASES: list[tuple[int | None, int | None]] = [
    (1234, 0),
    (0, 567),
    (3, 1),
    (0, 0),
    (0, None),
    (None, 2),
    (12, None),
    (None, None),
]

_SCRIPT = """
const vm = require("node:vm");
const fs = require("node:fs");
const [path, cases] = process.argv.slice(1);
const window = {};
vm.runInNewContext(fs.readFileSync(path, "utf8"), { window, Intl });
const formatters = window.MetabrowserFormatters;
const texts = JSON.parse(cases).map(([additions, deletions]) =>
  formatters.changeLine({ statuses: [], additions, deletions }, String).text,
);
process.stdout.write(JSON.stringify(texts));
"""


def test_the_cli_leaves_out_a_zero_total_as_the_browser_does() -> None:
    require_node()
    result = subprocess.run(
        ["node", "-e", _SCRIPT, str(FORMATTERS), json.dumps(CASES)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    browser = [text.replace("−", "-") for text in json.loads(result.stdout)]
    cli = [line_totals(additions, deletions) for additions, deletions in CASES]
    assert cli == browser
    assert cli == ["+1234", "-567", "+3 -1", "0 lines", "-?", "+? -2", "+12 -?", "+? -?"]
