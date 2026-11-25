"""A Markdown document whose front matter is not read shows why once, in a notice.

``tests/dom/markdown-frontmatter-error-session.js`` mounts the production Document view
over a trusted and an inert render of a note whose front matter does not parse; its
transcript is ``cli-ui-markdown-frontmatter-error.tryscript.md``. These check what
matters however the transcript is worded: one Frontmatter error notice with the
server's reason, first in the document's preamble, the Diagnostics disclosure listing
the other diagnostics only, and the text sent to render keeping the front matter as
written.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from tests.required_tools import require_node

REPO_ROOT = Path(__file__).resolve().parent.parent
SESSION = Path(__file__).resolve().parent / "dom" / "markdown-frontmatter-error-session.js"


def _session() -> dict[str, Any]:
    result = subprocess.run(
        [require_node(), str(SESSION), str(REPO_ROOT)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, f"{SESSION.name} failed:\n{result.stdout}\n{result.stderr}"
    return json.loads(result.stdout)


def test_a_front_matter_error_is_one_notice_and_not_a_diagnostic_row() -> None:
    session = _session()
    for name in ("trusted", "inert", "inertOnlyFrontmatterError"):
        shown = session[name]
        assert shown["inProse"] is True, name
        assert shown["notices"] == 1, name
        notice = shown["children"][0]
        assert notice["notice"] == "Frontmatter error", name
        assert notice["role"] == "alert", name
        assert notice["reason"].startswith("Error parsing YAML metadata:"), name
        assert "\n" in notice["reason"], name
        listed = [child["listed"] for child in shown["children"][1:]]
        assert all("frontmatter_error" not in rows for rows in listed), name
    assert session["trusted"]["children"][1]["listed"] == ["broken_anchor"]
    assert len(session["inertOnlyFrontmatterError"]["children"]) == 1
    assert session["inertWithoutFrontmatterError"]["notices"] == 0
    assert session["sentText"]["frontMatterAsWritten"] is True
    assert session["sentText"]["headingAnchored"] is True
