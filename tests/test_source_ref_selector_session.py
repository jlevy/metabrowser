"""The ref selector session runs production browser code on what a served mirror answers.

``tests/dom/source-ref-selector-session.js`` drives ``static/source-ref-selector.js`` --
opening, the filter's pause, aborted requests, the branch and tag lists, switching,
and where arrow keys move focus --
through a scripted conversation, and
``tests/golden/cli-ui-source-ref-selector.tryscript.md`` pins its transcript. So that the
conversation is the real server's and not envelopes a test wrote by hand, its responses
come from ``tests/fixtures/source-ref-selector-responses.json``: what the in-process
application answered for the listings and the switches the session plays. The first
test here replays them against a real store and fails when the recording no longer
matches.

The origin is ``tests/source_mirror_fixture.py``'s, written by ``git fast-import``, so
every commit ID is the same on every machine, and its last fetch is recorded at the
fixture's fixed time, so every status envelope is literal.

Regenerate the recording after an intended change, then the transcript:

    GOLDEN_UPDATE=1 uv --config-file uv.toml run --frozen pytest tests/test_source_ref_selector_session.py
    npx --no-install tryscript run --update tests/golden/cli-ui-source-ref-selector.tryscript.md
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient

from metabrowser import server
from metabrowser.cache.acquire import acquire_source
from metabrowser.cache.records import StoreOperation
from metabrowser.cache.repository_store import open_revision
from metabrowser.cache.served_mirror import StoreMirror
from metabrowser.git.tree_source import GitPath, GitRevisionSubject
from metabrowser.mirror_refresh import serve_mirror
from metabrowser.source import reset_source_session, serve_subject_opener
from tests.source_mirror_fixture import FETCHED_AT, build_origin
from tests.test_cache_acquire import _allow_installed_git, _file_source
from tests.test_source_freshness_session import _write_state

REPO_ROOT = Path(__file__).resolve().parent.parent
SESSION_JS = REPO_ROOT / "tests" / "dom" / "source-ref-selector-session.js"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "source-ref-selector-responses.json"

_JSON = {"content-type": "application/json"}
TOPIC = "refs/remotes/origin/topic"
FEATURE = "refs/remotes/origin/feature"

posix_only = pytest.mark.skipif(os.name != "posix", reason="owner-only cache is POSIX-only")
pytestmark = [
    posix_only,
    pytest.mark.skipif(shutil.which("git") is None, reason="git executable is required"),
]


def _view(display: str) -> str:
    return "/view/" + GitPath.from_display(display).to_wire()


def _answer(response: Any) -> dict[str, Any]:
    return {"status": response.status_code, "body": response.json()}


def _record(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    monkeypatch.setenv("METABROWSER_HOME", str(tmp_path / "home"))
    _allow_installed_git(monkeypatch)
    origin = build_origin(tmp_path)
    published = asyncio.run(acquire_source(_file_source(origin), home=tmp_path / "home"))
    _write_state(
        published, operation=StoreOperation(kind="acquire", outcome="succeeded", at=FETCHED_AT)
    )

    async def opener() -> GitRevisionSubject:
        return await open_revision(
            home=published.home,
            store_key=published.store_key,
            commit_oid=published.default_revision,
            store_identity=published.store_id,
            ref=published.default_remote_ref,
        )

    serve_subject_opener(opener)
    serve_mirror(StoreMirror.from_published(published))
    recorded: dict[str, Any] = {"views": {"readme": _view("README.md"), "notes": _view("NOTES.md")}}
    try:
        with TestClient(server.app) as client:

            def listing(**params: str) -> dict[str, Any]:
                return _answer(client.get("/api/source/refs", params=params))

            def switch(body: dict[str, str]) -> dict[str, Any]:
                return _answer(client.post("/api/source/pin", json=body, headers=_JSON))

            recorded["branches"] = listing(kind="branch")
            recorded["tags"] = listing(kind="tag")
            recorded["filtered"] = listing(kind="branch", q="feat")
            recorded["nothing"] = listing(kind="branch", q="zzz")
            # The selector sends no limit; this is the page a longer list would answer.
            recorded["page"] = listing(kind="branch", limit="1")
            recorded["refused"] = listing(kind="commit")
            # NOTES.md is only on topic, so a page on it goes to the root on feature.
            recorded["switch_away"] = switch({"ref": FEATURE, "view": _view("NOTES.md")})
            recorded["switch_keep"] = switch({"ref": TOPIC, "view": _view("README.md")})
            recorded["switch_same"] = switch({"ref": TOPIC, "view": _view("README.md")})
            recorded["switch_no_view"] = switch({"ref": FEATURE})
            recorded["switch_missing"] = switch({"ref": "refs/remotes/origin/gone"})
    finally:
        serve_mirror(None)
        reset_source_session()
    return recorded


def test_recording_is_what_a_served_mirror_answers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorded = _record(tmp_path, monkeypatch)
    branches = recorded["branches"]["body"]
    assert [row["name"] for row in branches["refs"]] == ["topic", "feature"]
    assert branches["refs"][0]["default"] and branches["refs"][0]["current"]
    assert recorded["page"]["body"]["truncated"] is True
    assert recorded["refused"]["status"] == 400
    assert recorded["switch_away"]["body"]["view_href"] == "/view/"
    keep = recorded["switch_keep"]["body"]
    assert (keep["changed"], keep["view_href"]) == (True, recorded["views"]["readme"])
    assert recorded["switch_same"]["body"]["changed"] is False
    assert "view_href" not in recorded["switch_no_view"]["body"]
    assert recorded["switch_missing"]["status"] == 404
    rendered = json.dumps(recorded, indent=2, ensure_ascii=False) + "\n"
    if os.environ.get("GOLDEN_UPDATE") == "1":
        FIXTURE.write_text(rendered, encoding="utf-8")
        return
    assert FIXTURE.read_text(encoding="utf-8") == rendered, (
        "a served mirror answers differently now; regenerate with GOLDEN_UPDATE=1 "
        "and update tests/golden/cli-ui-source-ref-selector.tryscript.md"
    )


def test_the_session_runs_on_the_recording() -> None:
    if shutil.which("node") is None:
        pytest.skip("node not available")
    result = subprocess.run(
        ["node", str(SESSION_JS)], capture_output=True, text=True, timeout=60, check=False
    )
    assert result.returncode == 0, f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    recording = json.loads(FIXTURE.read_text(encoding="utf-8"))
    by_name = {step["step"]: step for step in json.loads(result.stdout)["steps"]}
    assert by_name["the button names the served branch"]["requests"] == []
    assert by_name["opening asks for the branches"]["requests"] == [
        "GET /api/source/refs?kind=branch"
    ]
    typed = by_name["typing waits for a pause"]
    assert typed["requests"] == [] and typed["filterPending"] is True
    assert by_name["the pause asks once"]["requests"] == ["GET /api/source/refs?kind=branch&q=feat"]
    body = {"ref": FEATURE, "view": recording["views"]["notes"]}
    assert by_name["a switch is under way"]["requests"] == [
        f"POST /api/source/pin {json.dumps(body, separators=(',', ':'))}"
    ]
    away = by_name["a branch without the page's file opens at the root"]
    assert away["navigated"] == ["/view/"]
    kept = by_name["a branch with the page's file keeps it"]
    assert kept["navigated"] == [recording["views"]["readme"]]
    assert "navigated" not in by_name["choosing what the page shows only closes"]
    assert by_name["a page off /view/ names no address and opens at the root"]["navigated"] == [
        "/view/"
    ]
    assert by_name["a ref gone from the mirror says so"]["paint"]["error"] == (
        "That ref is no longer in the mirror."
    )
    aborted = by_name["a newer filter aborts the older request"]
    assert aborted["requests"] == [
        "GET /api/source/refs?kind=branch&q=zzz",
        "aborted GET /api/source/refs?kind=branch&q=zzz",
        "GET /api/source/refs?kind=branch&q=feat",
    ]
    assert aborted["paint"]["query"] == "feat" and aborted["paint"]["error"] is None
    closed = by_name["closing aborts the request on its way"]
    assert closed["requests"][-1].startswith("aborted GET") and closed["paint"]["open"] is False
