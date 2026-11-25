"""Browserless coverage for what a page shows when the server refuses a render.

``tests/dom/markdown-render-refusal-session.js`` runs the production Document view and the
folder Overview's README panel over each refusal, and
``tests/dom/github-pull-text-refusal-session.js`` the pull request page's controller over
a refused text. Their transcripts are ``cli-ui-markdown-render-refusal.tryscript.md`` and
``cli-ui-github-pull-text-refusal.tryscript.md``; these check the properties that matter
however the transcripts are worded.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from tests.required_tools import require_node

REPO_ROOT = Path(__file__).resolve().parent.parent
DOM = Path(__file__).resolve().parent / "dom"


def _session(name: str) -> dict[str, Any]:
    result = subprocess.run(
        [require_node(), str(DOM / name), str(REPO_ROOT)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, f"{name} failed:\n{result.stdout}\n{result.stderr}"
    return json.loads(result.stdout)


def test_a_refused_document_shows_its_source_under_one_notice() -> None:
    session = _session("markdown-render-refusal-session.js")
    assert session["recognized"]["kpress_render_error"] is None
    for name in ("documentTab", "partialWindow", "readmePanel"):
        drawn = session[name]
        assert drawn["renderError"] is False, name
        assert drawn["markup"].count('class="notice metabrowser-render-refused"') == 1, name
        assert 'data-severity="warning"' in drawn["markup"], name
        assert len(drawn["sources"]) == 1 and drawn["sources"][0]["continues"] is False, name
        assert "metabrowser-kpress-host" not in drawn["classes"], name
    assert "took too long to render" in session["documentTab"]["markup"]
    assert session["documentTab"]["fetched"] == []
    assert "the Source tab shows the rest" in session["partialWindow"]["markup"]
    assert session["readmePanel"]["fetched"] == ["/api/file?path=README.md"]
    assert 'href="/view/README.md"' in session["readmePanel"]["markup"]
    # A failed render's detail goes to the console, not the box.
    assert session["renderFailure"] == {
        "renderError": True,
        "sources": [],
        "logged": ["metabrowser: the document could not be rendered · KPress render failed"],
    }


def test_a_refused_pull_request_text_stays_plain_and_says_why() -> None:
    session = _session("github-pull-text-refusal-session.js")
    assert session["asked"].count("body") == 1
    body = next(entry for entry in session["told"] if entry["part"] == "body")
    assert body["unavailable"] is True
    assert body["note"] == session["notes"]["recorded"]
    assert body["note"].endswith("so it is shown as written.")
    assert any(entry.get("rendered") for entry in session["told"])
    assert session["notes"]["unknown_part"] is None
    assert session["notes"]["ok"] is None
