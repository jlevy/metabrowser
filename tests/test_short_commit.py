"""One length for a commit ID wherever a line names a commit.

The server draws the navigation heading and the ref chooser's button with
``short_commit`` in ``root_identity.py``; the page names a commit in the chooser's rows,
its button once the module has it, and a mirror's offer of a newer commit with
``shortCommit`` in ``static/formatters.js``. Each holds its own copy of the length, and
this keeps the two equal, so one commit reads the same in the heading and in the list.
"""

from __future__ import annotations

import re
from pathlib import Path

from metabrowser.root_identity import SHORT_COMMIT_CHARS, short_commit

FORMATTERS = Path(__file__).resolve().parents[1] / "src/metabrowser/static/formatters.js"


def test_the_page_and_the_server_shorten_a_commit_to_one_length() -> None:
    found = re.findall(r"^\s*const SHORT_COMMIT_CHARS = (\d+);$", FORMATTERS.read_text(), re.M)
    assert found == [str(SHORT_COMMIT_CHARS)]
    commit = "c7ae2a331f54b3e0c1a5d6e7f8091a2b3c4d5e6f"
    assert short_commit(commit) == commit[:SHORT_COMMIT_CHARS] == "c7ae2a331f54"
