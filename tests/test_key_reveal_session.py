"""The key reveal session runs the production keymap on what the server says a page shows.

``tests/dom/key-reveal-session.js`` drives the shortcut registry, the Shift reveal, the
shell keymap, Help, the main tabs, and the Pulls tab's keys through a scripted page, and
``tests/golden/cli-ui-key-reveal.tryscript.md`` pins its transcript. Which keys are live
depends on the server's answers: the views and their keys in a file's ``/api/file``
envelope, whether ``/api/git/repo`` finds a repository, and whether
``/api/source/status`` names a pin. So the session plays those answers from
``tests/fixtures/key-reveal-responses.json``, which the first test here records from the
in-process application and fails when the recording drifts. A recording keeps of each
answer what the keymap reads, the status and the envelope's kind, path, and views (or
the repository and pin fields), because the rest names the sandbox and the clock.

The transcript prints the shell keys the session's registry registered, and
``tests/test_keymap.py`` holds them to the reserved table in ``src/metabrowser/keymap.py``.
``make golden-update`` rewrites the recording and then the transcript.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient

from metabrowser import server
from metabrowser.cache.acquire import acquire_source
from metabrowser.cache.records import StoreOperation
from metabrowser.capabilities import Capabilities, set_capabilities
from metabrowser.mirror_refresh import serve_mirror
from metabrowser.source import reset_source_session
from tests.golden_harness import (
    check_recording,
    pinned_git_env,
    read_recording,
    run_session,
    serve_published,
    stand_in_sandbox,
)
from tests.required_tools import needs_git
from tests.source_mirror_fixture import FETCHED_AT, build_origin
from tests.test_cache_acquire import _allow_installed_git, _file_source
from tests.test_source_freshness_session import _write_state

RECORDING = "key-reveal-responses.json"
TRANSCRIPT = "cli-ui-key-reveal.tryscript.md"

posix_only = pytest.mark.skipif(os.name != "posix", reason="owner-only cache is POSIX-only")
pytestmark = [posix_only, needs_git]

# A folder of every multi-view kind the session opens, as `cli-show.tryscript.md` builds.
FILES = {
    "README.md": "# Sample\n\nHello.\n",
    "data.json": '{"name": "sample", "version": 1}\n',
    "session.jsonl": '{"type":"system","subtype":"init","session_id":"s1","model":"m1"}\n',
    "page.html": "<!doctype html>\n<title>Page</title>\n<p>Hello</p>\n",
    "docs/guide.md": "# Guide\n",
}
STATUS_FIELDS = ("pin", "ref", "ref_name")


def _file(client: TestClient, path: str) -> dict[str, Any]:
    response = client.get("/api/file", params={"path": path})
    body = response.json()
    return {
        "status": response.status_code,
        "body": {"kind": body["kind"], "path": body["path"], "views": body.get("views", [])},
    }


def _repo(client: TestClient) -> dict[str, Any]:
    response = client.get("/api/git/repo")
    body = response.json()
    return {"status": response.status_code, "body": {"is_repo": body["is_repo"]}}


def _status(client: TestClient) -> dict[str, Any]:
    response = client.get("/api/source/status")
    body = response.json()
    return {
        "status": response.status_code,
        "body": {field: body.get(field) for field in STATUS_FIELDS},
    }


def _folder(tmp_path: Path, name: str, *, repository: bool) -> Path:
    root = tmp_path / name
    for relative, text in FILES.items():
        (root / relative).parent.mkdir(parents=True, exist_ok=True)
        (root / relative).write_text(text)
    if repository:
        env = pinned_git_env()
        subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True, env=env)
        subprocess.run(["git", "-C", str(root), "add", "-A"], check=True, env=env)
        subprocess.run(
            ["git", "-C", str(root), "commit", "-q", "-m", "Sample"], check=True, env=env
        )
    return root


def _record(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    recorded: dict[str, Any] = {}

    # A plain folder: every multi-view kind, and HTML with its active content on and off.
    reset_source_session()
    server._set_root_dir(_folder(tmp_path, "plain", repository=False))  # pyright: ignore[reportPrivateUsage]
    with TestClient(server.app) as client:
        recorded["folder"] = {
            "status": _status(client),
            "repo": _repo(client),
            "files": {
                path: _file(client, path)
                for path in ("", "docs", "README.md", "data.json", "session.jsonl", "page.html")
            },
        }
        set_capabilities(Capabilities(active_content=False, mutations=False))
        recorded["folder"]["inactive_html"] = _file(client, "page.html")

    # The same folder as a Git repository, where the Commits tab appears.
    reset_source_session()
    set_capabilities(Capabilities(active_content=True, mutations=False))
    server._set_root_dir(  # pyright: ignore[reportPrivateUsage]
        _folder(tmp_path, "repository", repository=True)
    )
    with TestClient(server.app) as client:
        recorded["repository"] = {"status": _status(client), "repo": _repo(client)}

    # A served mirror's pin, which has a branch switcher and no modified-within filter.
    reset_source_session()
    monkeypatch.setenv("METABROWSER_CACHE_DIR", str(tmp_path / "home"))
    _allow_installed_git(monkeypatch)
    origin = build_origin(tmp_path)
    published = asyncio.run(acquire_source(_file_source(origin), home=tmp_path / "home"))
    _write_state(
        published, operation=StoreOperation(kind="acquire", outcome="succeeded", at=FETCHED_AT)
    )
    serve_published(published)
    try:
        with TestClient(server.app) as client:
            recorded["pin"] = {
                "status": _status(client),
                "repo": _repo(client),
                "files": {"": _file(client, "")},
            }
    finally:
        serve_mirror(None)
    return stand_in_sandbox(recorded, tmp_path, published.store_key, home=published.home)


def test_recording_is_what_the_application_answers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorded = _record(tmp_path, monkeypatch)
    files = recorded["folder"]["files"]
    keys = {
        path: [view.get("key") for view in answer["body"]["views"]]
        for path, answer in files.items()
    }
    assert keys == {
        "": ["o", "m"],
        "docs": ["o", "m"],
        "README.md": ["v", "s"],
        "data.json": ["a", "v", "s"],
        "session.jsonl": ["e", "v", "c", "s"],
        "page.html": ["v", "s"],
    }
    assert [view["id"] for view in recorded["folder"]["inactive_html"]["body"]["views"]] == [
        "source"
    ]
    assert recorded["folder"]["repo"]["body"]["is_repo"] is False
    assert recorded["folder"]["status"]["body"]["pin"] is None
    assert recorded["repository"]["repo"]["body"]["is_repo"] is True
    assert recorded["pin"]["status"]["body"]["pin"]
    check_recording(RECORDING, recorded, transcript=TRANSCRIPT)


def test_the_session_runs_on_the_recording() -> None:
    parts = [run_session("key-reveal-session.js", *part) for part in ((), ("gestures",), ("tabs",))]
    recording = read_recording(RECORDING)
    assert recording["pin"]["status"]["body"]["pin"]

    # What each part printed is what its golden pins, which tests/test_keymap.py holds to
    # the reserved shell keys.
    assert {key for part in parts for key in part["shellKeys"]} == set("0123456789fhjkptuw") | {
        "control-n",
        "control-p",
    }

    by_name = {step["step"]: step for part in parts for step in part["steps"]}
    root = by_name["the root folder has no Up"]
    assert "header.parent" not in [command for _key, command, _target in root["keys"]]
    assert root["pressed"] == {"key": "u", "handled": False}
    # Copying is ancillary: its controls are on screen, and none has a key.
    for copying in (
        "copying is ancillary: the Copy path button has no key, and Y does nothing",
        "a commit view's Copy revision is ancillary and has no key",
    ):
        assert by_name[copying]["pressed"] == {"key": "y", "handled": False}, copying
        assert by_name[copying]["ancillary"], copying
    preview = by_name["the Preview tab is V, and Control-P outside a stack does nothing"]
    assert ["V", "view-tabs.v", "Preview tab"] in preview["keys"]
    assert preview["controlP"] is False
    # On a pull request in a stack, Control-N and Control-P walk it (mb-lnqj): listed on
    # the strip as a Mac writes them, the session's navigator, and the only platform kind
    # that binds them; a chord ends the reveal and still walks; the letters alone and
    # AltGr's Control-Alt walk nothing.
    listed = by_name["a pull request in a stack lists Control-N or Control-P on the strip"]
    assert "⌃N or ⌃P Stack" in listed["strip"]["items"]
    assert ["⌃N", "pulls.stack.top", None] in listed["keys"]
    shifted = by_name["Control-N with Shift held walks the stack and ends the reveal"]
    assert shifted["pressed"] == {"key": "Control-n", "handled": True}
    assert shifted["did"] == ["moved toward the stack's top"]
    assert shifted["reveal"] == "idle"
    toward_base = by_name["Control-P walks the stack toward its base"]
    assert toward_base["pressed"] == {"key": "Control-p", "handled": True}
    assert toward_base["did"] == ["moved toward its base"]
    alone = by_name["N alone and Control-Alt-N walk nothing, and P alone is the Pulls tab"]
    assert (alone["n"], alone["altGr"], alone.get("did")) == (False, False, None)
    assert alone["p"] == {"handled": True, "active": "pulls", "focus": "#7"}
    # P is the Pulls tab (mb-6rfu): from a file it opens the tab, and again it moves focus
    # to the selected row.
    to_pulls = by_name["P opens the Pulls tab from a file"]
    assert (to_pulls["pressed"], to_pulls["active"]) == ({"key": "p", "handled": True}, "pulls")
    again = by_name["P again, once the list has rows, moves focus to the selected row"]
    assert (again["pressed"], again["focus"]) == ({"key": "p", "handled": True}, "#7")
    # The main tabs in their order, each with its letter.
    hosted = by_name["a repository with a hosted origin shows Files, Pulls, and Commits"]
    assert hosted["tabs"] == ["Files", "Pulls", "Commits"]
    assert [key for key, command, _target in hosted["keys"] if command.startswith("main-")] == [
        "F",
        "P",
        "H",
    ]
    # The numbers are positional, and Help gives one digit a fixed meaning: 0, Home.
    positional = by_name["Help lists the numbers once, as positional"]
    assert positional["helpDigits"] == [
        {"keys": "0", "range": False, "action": "Home"},
        {"keys": "1–9", "range": True, "action": "Numbered links and actions"},
    ]
    # 0 is Home on any screen, and so is US Shift-0, which types ")" (mb-5lzl).
    for step, typed in (
        ("0 goes home, through the folder's name's own path", "0"),
        ("Shift-0, which types ) on a US keyboard, goes home too", ")"),
    ):
        assert by_name[step]["pressed"] == {"key": typed, "handled": True}, step
        assert by_name[step]["did"] == ["went home"], step
        assert ["0", "shell.home", "squares"] in by_name[step]["keys"], step
    # The navigation's Refresh is 1, first in reading order on every screen; then a pin's
    # bar: Group by first, then its one filter (no Modified within on a pin).
    assert positional["numbers"] == ["Refresh", "Group by", "File type"]
    # Its badge sits beside the icon, in the header that anchors it, as Home's does.
    assert ["1", "beside, in app-header"] in positional["badges"]
    assert ["2", "Group by"] in positional["badges"]
    assert ["3", "File type"] in positional["badges"]
    # A pin has no By age, so Group by registers N and T only, as app.js does.
    assert [key for key, _action, _description in positional["menus"]] == ["N", "T"]
    assert by_name["Shift held past the threshold reveals"]["rootMarked"] is True
    # The resting strip lists Shift first, ahead of Help, on every screen (mb-k8am); the
    # revealed layer, shown while Shift is held, lists only commands.
    steps = [step for part in parts for step in part["steps"]]
    resting = [step for step in steps if step["strip"]["surface"] == "nav"]
    assert resting
    for step in resting:
        assert step["strip"]["items"][:2] == ["Shift Reveal keys", "? Help"], step["step"]
    for step in steps:
        if step["strip"]["surface"] == "reveal":
            assert "Shift Reveal keys" not in step["strip"]["items"], step["step"]
    for chord in (
        "a capital typed within the threshold never reveals",
        "? within the threshold opens Help and never reveals",
        "Shift+wheel never reveals",
        "Shift with the pointer travelling to a click never reveals",
        "Shift during a press that moved focus never reveals",
        "Shift in Quick Search's field never reveals",
    ):
        assert by_name[chord]["reveal"] == "idle", chord
    # A handled key that moves focus keeps the reveal: only the window's own blur ends it.
    for moved in (
        "↑ on a tree row moves one row and keeps the reveal",
        "a held J moves rows and does no reveal work on its repeats",
        "H with Shift still held opens Commits, focuses its row, and keeps the reveal",
        "F during the reveal shows the filter bar, and Group by and its filters gain 2 to 4",
    ):
        assert by_name[moved]["reveal"] == "revealed", moved
    assert by_name["the window losing focus ends the reveal"]["reveal"] == "idle"
    files = by_name[
        "F during the reveal shows the filter bar, and Group by and its filters gain 2 to 4"
    ]
    assert ["1", "beside, in app-header"] in files["badges"]
    assert ["2", "Group by"] in files["badges"]
    assert ["3", "Modified within"] in files["badges"]
    assert ["4", "File type"] in files["badges"]
    assert files["numbers"] == ["Refresh", "Group by", "Modified within", "File type"]
    opened = by_name[
        "4 opens the closed drawer and the file type filter, and focuses its checked row"
    ]
    # The drawer's filters keep their numbers while it is closed; a number opens it.
    assert opened["drawerBefore"] is False
    assert opened["drawerAfter"] is True
    assert opened["focus"] == {
        "menu": "filter-type-menu",
        "row": "Any type",
        "checked": "true",
        "open": "true",
    }

    # Every way a menu opens focuses its checked row, through the filter controls' one
    # path; Escape, a second click, and a choice that closes it give focus to the trigger;
    # and a pick or a rebuild while a row has focus keeps it on that row (mb-spqw).
    kept = by_name[
        "↓ moves to the next row, a pick or a rebuild keeps focus there, and Escape closes "
        "the menu onto its trigger"
    ]
    next_row = {"menu": "filter-type-menu", "row": ".md", "checked": "false", "open": "true"}
    assert kept["next"] == kept["picked"] == kept["rebuilt"] == next_row
    assert kept["escaped"] == "the types trigger"
    ways = by_name[
        "each way a menu opens focuses its checked row, and each way it closes its trigger"
    ]
    group_checked = {
        "menu": "filter-group-menu",
        "row": "No grouping",
        "checked": "true",
        "open": "true",
    }
    assert ways["byNumber"] == {
        "menu": "filter-recency-menu",
        "row": "Any age",
        "checked": "true",
        "open": "true",
    }
    assert ways["byArrow"] == ways["byClick"] == group_checked
    assert ways["byNumberEscaped"] == "the recency trigger"
    assert ways["byArrowEscaped"] == ways["byClickClosed"] == "the group trigger"

    # Group by's rows take N, A, and T, in its own scope, while its menu is open and has
    # focus; Help lists them under Menus; each runs the row's click path; and T is Quick
    # Search's whenever the menu is closed or focus is outside it (mb-ibo4).
    assert by_name["Help lists Group by's letters under Menus"]["menus"] == [
        ["N", "No grouping", "Choose No grouping in the Group by menu."],
        ["A", "By age", "Choose By age in the Group by menu."],
        ["T", "By file type", "Choose By file type in the Group by menu."],
    ]
    group_open = by_name["2 opens Group by and focuses its checked row, whose letters are live"]
    assert [key for key in group_open["keys"] if key[1].startswith("menu.")] == [
        ["N", "menu.group.n", "No grouping row"],
        ["A", "menu.group.a", "By age row"],
        ["T", "menu.group.t", "By file type row"],
    ]
    revealed = by_name["Shift held in the open menu badges its rows' letters"]
    for badge in (["N", "No grouping row"], ["A", "By age row"], ["T", "By file type row"]):
        assert badge in revealed["badges"], badge
    # T reaches the row, so the strip offers Quick Search by / alone.
    assert "/ Quick Search" in revealed["strip"]["items"]
    assert "T By file type" in revealed["strip"]["items"]
    age = by_name["A chooses By age and closes the menu"]
    assert age["pressed"] == {"key": "a", "handled": True}
    # The choice closed the menu, so focus is back on its trigger (mb-spqw).
    assert age["focus"] == "the group trigger"
    assert age["did"] == ["chose age in the group menu"]
    assert age["trigger"] == "By age"
    for quick in (
        "with the menu closed, T is Quick Search",
        "with focus outside the open menu, T is Quick Search, which closes it",
    ):
        assert by_name[quick]["pressed"] == {"key": "t", "handled": True}, quick
        assert by_name[quick]["focus"] == "combobox", quick
    by_type = by_name["2 focuses By age, the checked row, and T chooses By file type"]
    assert by_type["focus"]["row"] == "By age" and by_type["focus"]["checked"] == "true"
    assert by_type["trigger"] == "By file type"
    outside = by_name["with focus outside the open menu, T is Quick Search, which closes it"]
    assert outside["trigger"] == "By file type"
    # Quick Search's box taking focus closes the menu, as focus arriving outside any menu
    # does (docs/design-system.md, "Every Menu Closes Alike").
    assert outside["did"] == ["opened the group menu", "closed the group menu"]
    assert by_name["N chooses No grouping"]["trigger"] == "No grouping"

    # What a navigation and a key cost: one publication, and while revealed one pass.
    same_kind = by_name["a move between two files of one kind registers nothing"]["cost"]
    assert same_kind == {"publications": ["batch(target)"], "targetReads": 0, "keycapsCreated": 0}
    moved_revealed = by_name["a navigation while revealed moves the badges in one pass"]["cost"]
    assert len(moved_revealed["publications"]) == 1
    assert by_name["a held J moves rows and does no reveal work on its repeats"]["repeats"] == {
        "publications": [],
        "targetReads": 0,
        "keycapsCreated": 0,
    }

    late = by_name["Commits registered while the registry is down gets its tab, then its key"]
    assert late["whileDown"] == {"threw": None, "tab": True, "container": True, "key": None}
    assert late["key"] == "H"
    assert late["pressed"] == {"key": "h", "handled": True}
    cancelled = by_name["V follows the committed bar, and a cancelled stage changes nothing"]
    assert cancelled["v"] == {
        "structured": "Tree",
        "agentLog": "Log",
        "back": "Tree",
        "whileStaged": "Tree",
        "afterCancel": "Tree",
    }
    assert by_name["the keymap after a pageshow rebuild"]["sameAsBefore"] is True


def test_backslash_hides_the_navigation_pane_and_its_keys() -> None:
    """`\\` hides the pane: its keys leave the keymap, focus leaves it, and `|` undoes it.

    ``tests/dom/nav-collapse-session.js`` runs the production static/nav-collapse.js under
    the shell keymap (``cli-ui-nav-collapse.tryscript.md``; docs/design-system.md, "Hiding
    the Navigation Pane").
    """
    steps = {step["step"]: step for step in run_session("nav-collapse-session.js")["steps"]}
    shown, hidden, back, other_key, turned, menu = steps.values()
    commands = {
        name: [command for _key, command, _target in step["keys"]] for name, step in steps.items()
    }
    shown_nav = {
        "inert": False,
        "inLayout": True,
        "expanded": "true",
        "label": "Hide navigation",
    }
    hidden_nav = {
        "inert": True,
        "inLayout": False,
        "expanded": "false",
        "label": "Show navigation",
        "focus": "preview-pane",
    }

    assert shown["nav"] == shown_nav
    assert ["\\", "shell.nav-toggle", "Hide navigation"] in shown["keys"]
    assert hidden["pressed"] == {"key": "\\", "handled": True}
    assert hidden["nav"] == hidden_nav
    # The slide runs the pane's whole width over --motion-reveal's time.
    assert (hidden["slide"]["from"], hidden["slide"]["to"]) == (300, 0)
    assert ["\\", "shell.nav-toggle", "Show navigation"] in hidden["keys"]
    hidden_commands = commands[hidden["step"]]
    # The pane's own keys are gone while it is hidden; the main page's stay.
    for gone in ("shell.home", "main-tabs.files", "numbered"):
        assert gone in commands[shown["step"]] and gone not in hidden_commands, gone
    assert {"help.open", "view-tabs.v", "header.parent"} <= set(hidden_commands)
    # Shift-\, which types `|`, shows it again with every key it had: the pane is live as
    # the slide starts and back in the layout when it ends.
    assert back["pressed"] == {"key": "|", "handled": True}
    assert back["sliding"]["nav"] == {**shown_nav, "inLayout": False}
    assert back["nav"] == shown_nav
    assert commands[back["step"]] == commands[shown["step"]]
    # The ISO key in US `\`'s place types `#`, which is not `\`.
    assert other_key["pressed"] == {"key": "#", "handled": False}
    assert other_key["slide"] is None and other_key["nav"] == shown_nav
    # Turned back halfway, the slide runs from where the frame is, for half the time.
    assert turned["slide"]["from"] == 150 and turned["slide"]["to"] == 300
    assert turned["slide"]["duration"] * 2 == hidden["slide"]["duration"]
    assert turned["slide"]["cancelled"] == 1
    assert turned["nav"] == shown_nav
    # Hiding the pane closes the menu it held open.
    assert menu["menu"] == {"before": "group", "after": None}
    assert menu["nav"] == hidden_nav
