"""Mermaid diagrams are drawn, with a size, in Chrome, trusted and ``--untrusted``.

KPress draws the figures, their states, toolbar, dialog, and theme redraw, and its own
tests pin them; how Metabrowser binds KPress is browserless
(``tests/dom/markdown-diagrams-session.js``). Mermaid lays a diagram out by measuring its
labels in the page's fonts, and an inert render's image of that SVG paints only in a
browser, so ``tests/dom/markdown-diagrams-chrome.mjs`` checks in headless Chrome that a
trusted document draws SVG, an untrusted one draws images that loaded, a broken diagram
shows its error, every control's glyph is in the page, the dialog draws the diagram
fitted and centered, a ``.mmd`` file draws as a document does, a document with no
diagram fetches nothing of Mermaid's, and untrusted text's diagrams drawn isolated, as a
pull request's page draws them, load nothing their image shape or their own CSS names
(``builtin_plugins/markdown/diagram-frame.js``). Without Chrome this
skips (``require_chrome`` in ``tests/required_tools.py``).
"""

from __future__ import annotations

import os
import re
import socket
import sys
from pathlib import Path

import pytest

from tests.process_group import GROUP_STOP_S, PROFILE_TEARDOWN_S, run_in_own_group
from tests.required_tools import require_chrome, require_node

SESSION = Path(__file__).resolve().parent / "dom" / "markdown-diagrams-chrome.mjs"
# Two server starts and two Chrome launches, each opening three pages: the same shape as
# tests/test_document_print_chrome.py with fewer pages, so its bound, which leaves room
# for a cold first Chrome launch in CI, holds here too.
SESSION_TIMEOUT_S = 120
# The longest the test can take: the session's bound, its process group stopped after it
# (Chrome and both servers are in it), and the profile's teardown (tests/process_group.py).
LIFECYCLE_S = SESSION_TIMEOUT_S + GROUP_STOP_S + PROFILE_TEARDOWN_S
pytestmark = pytest.mark.timeout(LIFECYCLE_S + 10)
_METAB = Path(sys.executable).with_name("metab")

DIAGRAMS = """# Diagrams

A flowchart:

```mermaid
flowchart LR
  A[Start here] -->|a long edge label| B{Decide}
  B -->|yes| C[Done]
  B -->|no| A
```

A sequence diagram:

```mermaid
sequenceDiagram
  Alice->>Bob: Hello, Bob
  Bob-->>Alice: Hello, Alice
```

A broken one:

```mermaid
flowchart LR
  A -->
```
"""
PLAIN = "# Plain\n\nNo diagrams here.\n\n```python\nprint('flowchart LR')\n```\n"
FLOW = "flowchart TD\n  Read --> Draw\n  Draw --> Show\n"


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def test_mermaid_diagrams_draw_in_chrome(tmp_path: Path, chrome_profile: Path) -> None:
    chrome = require_chrome()
    root = tmp_path / "served"
    root.mkdir()
    (root / "diagrams.md").write_text(DIAGRAMS, encoding="utf-8")
    (root / "plain.md").write_text(PLAIN, encoding="utf-8")
    (root / "flow.mmd").write_text(FLOW, encoding="utf-8")
    state = tmp_path / "state"
    state.mkdir()
    result = run_in_own_group(
        [require_node(), str(SESSION), str(_METAB), str(root), str(_free_port()), str(state)],
        timeout_s=SESSION_TIMEOUT_S,
        env={**os.environ, "CHROME_BIN": chrome, "CHROME_PROFILES": str(chrome_profile)},
    )
    if result.timed_out:
        pytest.fail(f"ran past {SESSION_TIMEOUT_S} s; its steps:\n{result.stderr}")
    # Each step's time, shown with the output when it fails.
    print(result.stderr)
    assert result.returncode == 0, result.stdout or result.stderr
    passed = re.fullmatch(r"markdown diagrams in Chrome: (\d+) checks passed\n", result.stdout)
    assert passed is not None and int(passed.group(1)) > 0, result.stdout
