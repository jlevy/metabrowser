"""The View file session runs production browser code on what a served mirror answers.

``tests/dom/diff-view-file-session.js`` loads the diff plugin whole, as the shell loads
it, mounts the diff of a commit and of a pull request's comparison, reads the View file
controls of each file bar, and follows them; ``tests/golden/cli-ui-diff-view-file.tryscript.md``
pins its transcript. So that the conversation is the real server's and not envelopes a
test wrote by hand, its documents, the block the shell writes into a page, and every
answer of ``POST /api/source/pin`` come from
``tests/fixtures/diff-view-file-responses.json``: what the in-process application
answered while it served ``tests/diff_view_file_fixture.py``'s mirror, then while a
server on another repository, and one on a folder, answered a page left open from it.
The first test here replays that story against real stores and fails when the recording
no longer matches.

Commit IDs are real: both origins are written by ``git fast-import``. Fetch times are
wall-clock values, so each is replaced by one fixed stand-in.

Regenerate the recording after an intended change, then the transcript:

    GOLDEN_UPDATE=1 uv --config-file uv.toml run --frozen pytest tests/test_diff_view_file_session.py
    npx --no-install tryscript run --update tests/golden/cli-ui-diff-view-file.tryscript.md
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient

from metabrowser import server
from metabrowser.cache.acquire import PublishedSource, acquire_source
from metabrowser.cache.records import StoreOperation
from metabrowser.cache.repository_store import open_revision
from metabrowser.cache.served_mirror import StoreMirror
from metabrowser.git.tree_source import GitRevisionSubject
from metabrowser.mirror_refresh import serve_mirror
from metabrowser.source import reset_source_session, serve_subject_opener
from tests import source_mirror_fixture
from tests.diff_view_file_fixture import (
    LATIN1_NAME,
    NEW_NAME,
    OLD_NAME,
    build_origin,
    commits,
    view,
)
from tests.source_mirror_fixture import FETCHED_AT
from tests.test_cache_acquire import _allow_installed_git, _file_source
from tests.test_source_freshness_session import _settle, _stand_in_times, _write_state

REPO_ROOT = Path(__file__).resolve().parent.parent
SESSION_JS = REPO_ROOT / "tests" / "dom" / "diff-view-file-session.js"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "diff-view-file-responses.json"

_JSON = {"content-type": "application/json"}
# What the shell writes into a page on a pin: the commit and ref it was rendered for.
_PAGE_PIN = re.compile(r"window\.METABROWSER_SOURCE_PIN=(\{.*?\});</script>")

posix_only = pytest.mark.skipif(os.name != "posix", reason="owner-only cache is POSIX-only")
pytestmark = [
    posix_only,
    pytest.mark.skipif(shutil.which("git") is None, reason="git executable is required"),
]


def _answer(response: Any) -> dict[str, Any]:
    return {"status": response.status_code, "body": response.json()}


def _page(client: TestClient) -> dict[str, Any] | None:
    """The page block of the shell as served now; ``None`` when it writes none."""

    shell = client.get("/view/")
    assert shell.status_code == 200
    found = _PAGE_PIN.search(shell.text)
    return None if found is None else json.loads(found.group(1))


def _switch(client: TestClient, body: dict[str, str]) -> dict[str, Any]:
    response = client.post("/api/source/pin", json=body, headers=_JSON)
    return {"request": body, **_answer(response)}


def _serve(published: PublishedSource, *, serving: bool = False) -> None:
    async def opener() -> GitRevisionSubject:
        return await open_revision(
            home=published.home,
            store_key=published.store_key,
            commit_oid=published.default_revision,
            store_identity=published.store_id,
            ref=published.default_remote_ref,
        )

    reset_source_session()
    serve_subject_opener(opener)
    serve_mirror(StoreMirror.from_published(published), serving=serving)


def _acquire(origin: Path, home: Path) -> PublishedSource:
    published = asyncio.run(acquire_source(_file_source(origin), home=home))
    _write_state(
        published, operation=StoreOperation(kind="acquire", outcome="succeeded", at=FETCHED_AT)
    )
    return published


def _record(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    home = tmp_path / "home"
    monkeypatch.setenv("METABROWSER_HOME", str(home))
    _allow_installed_git(monkeypatch)
    origin = build_origin(tmp_path)
    ids = commits(origin)
    readme = view("README.md")
    recorded: dict[str, Any] = {
        "commits": ids,
        "views": {
            "readme": readme,
            "old_name": view(OLD_NAME),
            "new_name": view(NEW_NAME),
            "latin1": view(LATIN1_NAME),
        },
    }
    try:
        _serve(_acquire(origin, home))
        with TestClient(server.app) as client:

            def comparison(**params: str) -> dict[str, Any]:
                return _answer(client.get("/api/plugin/diff/comparison", params=params))

            recorded["page"] = _page(client)
            recorded["commit"] = comparison(revision=ids["second"])
            recorded["root"] = comparison(revision=ids["first"])
            # A pull request's Files changed: its base branch against its head, from
            # their merge base.
            recorded["pull"] = comparison(
                left=ids["base"], right=ids["second"], base_policy="merge_base"
            )
            patch = view("changes.patch").removeprefix("/view/")
            recorded["patch"] = _answer(
                client.get("/api/plugin/diff/document", params={"path": patch})
            )
            recorded["switch_parent"] = _switch(
                client, {"oid": ids["first"], "view": recorded["views"]["old_name"]}
            )
            recorded["page_at_parent"] = _page(client)
            recorded["switch_head"] = _switch(
                client, {"oid": ids["second"], "view": recorded["views"]["new_name"]}
            )
        # A page left open while its server was restarted on another repository: that
        # mirror has neither commit. A server fetches once for a commit its mirror
        # lacks, then says the origin does not have it.
        other = tmp_path / "other"
        other.mkdir()
        other_origin = source_mirror_fixture.build_origin(other)
        _serve(_acquire(other_origin, home), serving=True)
        with TestClient(server.app) as client:
            _settle(client)
            lacking = {"oid": ids["first"], "view": readme}
            recorded["other_pending"] = _switch(client, lacking)
            _settle(client)
            recorded["other_not_found"] = _switch(client, lacking)
            # Asked once more with its origin gone, the fetch cannot run.
            shutil.move(other_origin, other / "away.git")
            assert _switch(client, lacking)["status"] == 202
            _settle(client)
            recorded["other_fetch_failed"] = _switch(client, lacking)
        # The same page after its server was restarted on a folder, which has no pin.
        folder = tmp_path / "folder"
        folder.mkdir()
        serve_mirror(None)
        reset_source_session()
        server._set_root_dir(folder)
        with TestClient(server.app) as client:
            recorded["folder_page"] = _page(client)
            recorded["folder_refused"] = _switch(client, lacking)
    finally:
        serve_mirror(None)
        reset_source_session()
    return _stand_in_times(recorded)


def test_recording_is_what_the_servers_answer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorded = _record(tmp_path, monkeypatch)
    ids = recorded["commits"]
    assert recorded["page"] == {"pin": ids["second"], "ref": "refs/remotes/origin/trunk"}
    resolved = recorded["commit"]["body"]["resolved"]
    assert (resolved["base_policy"], resolved["left"]["id"], resolved["right"]["id"]) == (
        "first_parent",
        ids["first"],
        ids["second"],
    )
    kinds = {change["kind"] for change in recorded["commit"]["body"]["manifest"]["files"]}
    assert kinds == {"modified", "added", "deleted", "renamed"}
    assert recorded["root"]["body"]["resolved"]["left"] == {
        "kind": "empty",
        "symbolic": ids["first"],
    }
    pull = recorded["pull"]["body"]["resolved"]
    # The merge base, not the tip of the base branch the comparison named.
    assert (pull["base_policy"], pull["left"]["id"]) == ("merge_base", ids["first"])
    assert pull["left"]["id"] != ids["base"]
    assert recorded["patch"]["body"]["resolved"]["left"]["kind"] == "patch"
    parent = recorded["switch_parent"]
    assert (parent["status"], parent["body"]["view_href"]) == (200, recorded["views"]["old_name"])
    assert recorded["page_at_parent"] == {"pin": ids["first"], "ref": None}
    head = recorded["switch_head"]
    assert (head["status"], head["body"]["view_href"]) == (200, recorded["views"]["new_name"])
    assert recorded["other_pending"]["status"] == 202
    assert recorded["other_pending"]["body"]["code"] == "selection_pending"
    assert recorded["other_not_found"]["status"] == 404
    assert recorded["other_fetch_failed"]["status"] == 502
    assert recorded["other_fetch_failed"]["body"]["code"] == "selection_fetch_failed"
    assert recorded["folder_page"] is None
    assert recorded["folder_refused"]["status"] == 409
    rendered = json.dumps(recorded, indent=2, ensure_ascii=False) + "\n"
    if os.environ.get("GOLDEN_UPDATE") == "1":
        FIXTURE.write_text(rendered, encoding="utf-8")
        return
    assert FIXTURE.read_text(encoding="utf-8") == rendered, (
        "the servers answer differently now; regenerate with GOLDEN_UPDATE=1 "
        "and update tests/golden/cli-ui-diff-view-file.tryscript.md"
    )


def _session() -> dict[str, Any]:
    if shutil.which("node") is None:
        pytest.skip("node not available")
    result = subprocess.run(
        ["node", str(SESSION_JS)], capture_output=True, text=True, timeout=60, check=False
    )
    assert result.returncode == 0, f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    return json.loads(result.stdout)


def test_the_session_runs_on_the_recording() -> None:
    recording = json.loads(FIXTURE.read_text(encoding="utf-8"))
    ids, views = recording["commits"], recording["views"]
    by_name = {step["step"]: step for step in _session()["steps"]}

    shown = by_name["a commit's diff on the page that shows that commit"]["bars"]
    # Deleted: only the parent's side. Added: only the commit's. Renamed: the old path
    # at the parent and the new one at the commit.
    assert [control.split("]")[0] for control in shown["D gone.txt"]] == ["[View at parent"]
    assert [control.split("]")[0] for control in shown["A added.txt"]] == ["[View file"]
    old, new = shown["R100 src/old_name.py → src/new_name.py"]
    assert old.endswith(f"Switch to {ids['first'][:12]} and open {OLD_NAME}")
    assert f"link {views['new_name']} " in new and NEW_NAME in new
    # A name that is not UTF-8 is addressed by its bytes, as the server addresses it.
    assert f"link {views['latin1']} " in shown["M latin1-\ufffd.txt"][1]

    followed = by_name["the link is the browser's to follow"]
    assert (followed["prevented"], followed["requests"]) == (False, [])
    assert (followed["follows"], followed["opens"]) == (views["readme"], "README.md")
    assert followed["barStillOpen"] is True
    assert by_name["the rest of the bar still folds the file"]["barStillOpen"] is False

    asked = by_name["View at parent asks the server to switch"]
    body = json.dumps(recording["switch_parent"]["request"], separators=(",", ":"))
    assert asked["requests"] == [f"POST /api/source/pin {body}"]
    assert asked["barStillOpen"] is True
    assert by_name["a second switch waits for the first"]["requests"] == []
    went = by_name["the page goes where the server says"]
    assert went["navigated"] == [views["old_name"]] and went["opens"] == OLD_NAME

    # On the parent's page the same diff has the sides the other way around.
    on_parent = by_name["the same diff from the page on the parent"]["bars"]
    old, new = on_parent["R100 src/old_name.py → src/new_name.py"]
    assert f"link {views['old_name']} " in old
    assert new.endswith(f"Switch to {ids['second'][:12]} and open {NEW_NAME}")
    assert by_name["View file switches to the commit"]["navigated"] == [views["new_name"]]

    root = by_name["a root commit has only its own side"]["bars"]
    assert all(len(controls) == 1 and "[View file]" in controls[0] for controls in root.values())

    pull = by_name["a pull request's Files changed opens the merge base and the head"]
    assert pull["requests"] == [
        "GET /api/plugin/diff/comparison"
        f"?left={ids['base']}&right={ids['second']}&base_policy=merge_base"
    ]
    base, head = pull["bars"]["M README.md"]
    assert base == f"[View at base] button · Switch to {ids['first'][:12]} and open README.md"
    assert head.startswith(f"[View file] link {views['readme']} ")

    assert by_name["a patch file names no commit"]["bars"] == {"M kept.txt": []}
    refusals = [
        ("a commit the server's mirror lacks is being fetched", "is fetching"),
        ("asked again after the fetch, the origin does not have it", "origin does not have it"),
        ("a fetch that could not run says so", "fetching it failed"),
        ("a server that now serves a folder refuses", "(unsupported_for_subject)"),
        ("a request that fails says so", "The switch request failed."),
    ]
    for name, said in refusals:
        step = by_name[name]
        assert said in step["notices"]["M README.md"], name
        assert "navigated" not in step, name
    assert "notices" not in by_name["asking again clears what the last refusal said"]
    folder = by_name["a served folder's page has no controls"]["bars"]
    assert folder and all(controls == [] for controls in folder.values())
