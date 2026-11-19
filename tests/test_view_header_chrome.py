"""A file's and a folder's view header, laid out as the design says, in headless Chrome.

The owner, 2026-11-18: the size, file count, and age at the upper right of the main
view's header belong next to the item's name, "much like the nav bar", and the headers of
files, folders, pull requests, and commits should be one design: an eyebrow with the
enclosing folder and the Up control, the item's icon and its name at full size, the
metadata under it, then the tabs, on one ground with one rule (mb-6x33;
docs/design-system.md, "View Headers").

``tests/dom/view-header-chrome.mjs`` serves a folder dated days back, so no age changes
its label during the session, and reads a file's header, its folder's, and the served
root's, in a 1,180, 900, 480, and 260 px main view, in both themes. Then it rewrites the
metadata line in place with the shell's own builders, as the folder header's live refresh
does: the age of something just written ("just now"), an hour later ("59m ago"), and the
pending skeletons of a walk that has not finished. This judges the record:

- the rows: the eyebrow, the heading row, and the metadata line, each its token's height
  and one gap apart; the metadata line starts on the eyebrow's inset, under the title's
  row, and the tab bar right under the header;
- the type: the title at the page title's size and bold, the eyebrow's address and the
  metadata line at the body size;
- the ground and the rules: the header and the tab bar on the body's ground, which is not
  the navigation's, the header with no rule of its own, and the tab bar's one rule under
  it;
- the View on GitHub button (mb-4wqh), on a folder served as a checkout whose origin is
  on github.com: in the header's corner at its tokens' insets and height, inside the room
  the eyebrow leaves it from first paint, its link and its menu's Open in Browser the
  item's page on github.com at the checkout's commit, through the hooks the macOS app
  reads, in the text ink with a muted chevron in a joined chip group's frame; its menu,
  opened with a click and walked with the arrow keys, Home, End, Escape, and Tab, every
  item on top where it is drawn; a file the checkout does not track, whose corner keeps
  its room and draws nothing; and a commit's page, its button placed in the page as a view
  header's is, its subject leaving it room only where the reading column reaches it;
- the narrow panes: a title too long for its row cut short at its end, and every
  metadata item on the line whole or wrapped out of sight with its dot, never cut;
- the title's tooltip, its whole name, shown by the shell's own rule on every page
  exactly while the name is cut short;
- steadiness: as the values change, no box of the header but the line's own items moves
  or changes size: not the header, the eyebrow, the title's row, the title, the button,
  the line, or the tab bar; and the age, last on its line, moves no other item when its
  label's width changes.

Where text sits is computed layout, so this needs a browser; it skips without Chrome
(``docs/e2e-testing.md``), and CI runs it. The session leads a process group of its own,
which Chrome and the server join (``tests/process_group.py``).
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest

from tests.process_group import GROUP_STOP_S, PROFILE_TEARDOWN_S, run_in_own_group
from tests.required_tools import require_chrome, require_node

SESSION = Path(__file__).resolve().parent / "dom" / "view-header-chrome.mjs"
_METAB = Path(sys.executable).with_name("metab")
# One server start, one Chrome, and 24 loads, each with three rewrites of its line, then in
# each theme a menu's walk, a page with no counterpart, and two commit pages: the 24 loads
# took 28 s on a 10-core Mac at a load average near 12. A cold Chrome start in CI has taken
# 28.2 s, and the server's start is bounded at 30 s inside the session.
SESSION_TIMEOUT_S = 180
LIFECYCLE_S = SESSION_TIMEOUT_S + GROUP_STOP_S + PROFILE_TEARDOWN_S
pytestmark = pytest.mark.timeout(LIFECYCLE_S + 10)
# Layout rounds to fractions of a pixel; a box off by more than this has moved.
TOLERANCE_PX = 0.5
# Three days old: every age reads "3d ago" from 2.5 to 3.5 days (`AGE_TIERS` in
# formatters.js rounds), so no age changes its label inside the session's bound.
_AGE_S = 3 * 24 * 60 * 60


# The served checkout's identity and dates, fixed so its commit is the same on every machine.
_GIT_ENV = {
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@example.com",
    "GIT_AUTHOR_DATE": "2026-02-01T00:00:00Z",
    "GIT_COMMITTER_DATE": "2026-02-01T00:00:00Z",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
}


def _git(root: Path, *args: str) -> str:
    env = {name: value for name, value in os.environ.items() if not name.startswith("GIT_")}
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
        env={**env, **_GIT_ENV, "HOME": str(root.parent)},
    ).stdout.strip()


def _served(root: Path) -> tuple[Path, str]:
    """A checkout whose origin is on github.com and has its one commit, and that commit."""

    notes = root / "docs" / "notes"
    notes.mkdir(parents=True)
    (notes / "a-long-name-for-a-view-header-title.md").write_text(
        "# A note\n\nWith some text.\n", encoding="utf-8"
    )
    (notes / "b.txt").write_text("b\n" * 4000, encoding="utf-8")
    (root / "README.md").write_text("# Served\n", encoding="utf-8")
    _git(root, "init", "-q", "--initial-branch=main", ".")
    _git(root, "remote", "add", "origin", "https://github.com/octo/demo.git")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "Serve a long note")
    # Origin has the commit, as a fetch would have it, so every committed page has a
    # counterpart (src/metabrowser/counterpart.py).
    _git(root, "update-ref", "refs/remotes/origin/trunk", "HEAD")
    commit = _git(root, "rev-parse", "HEAD")
    # A file the checkout does not track, which has none.
    (notes / "draft.txt").write_text("Not committed.\n", encoding="utf-8")
    when = time.time() - _AGE_S
    for path in [root, *root.rglob("*")]:
        os.utime(path, (when, when))
    return root, commit


# The least of the heading row the title keeps: 103 px in the 260 px pane, measured.
_TITLE_FLOOR_PX = 96
# The heading row's gap, which the corner's room keeps between the eyebrow and the button.
_GAP_PX = 8
_REPOSITORY = "https://github.com/octo/demo"


def _links(commit: str) -> dict[str, str]:
    """Each page's counterpart: the item's tree or blob at the checkout's commit."""

    return {
        "file": f"{_REPOSITORY}/blob/{commit}/docs/notes/a-long-name-for-a-view-header-title.md",
        "folder": f"{_REPOSITORY}/tree/{commit}/docs/notes",
        "root": f"{_REPOSITORY}/tree/{commit}",
        "commit": f"{_REPOSITORY}/commit/{commit}",
    }


def _button_drawn(name: str, page: dict[str, Any], url: str) -> None:
    """The button's hooks and inks: its link and Open in Browser *url*, as the app reads them."""

    hooks = page["hooks"]
    assert hooks is not None, f"{name}: no button"
    assert hooks["root"] and hooks["label"] == "View on GitHub", f"{name}: {hooks}"
    assert (hooks["open"], hooks["openTarget"], hooks["openRel"]) == (url, "_blank", "noopener")
    assert (hooks["external"], hooks["externalTarget"], hooks["externalRel"]) == (
        url,
        "_blank",
        "noopener",
    ), f"{name}: {hooks}"
    assert hooks["items"] == ["Copy Link", "Open in Browser"], f"{name}: {hooks}"
    assert (hooks["popup"], hooks["expanded"], hooks["menuHidden"]) == ("menu", "false", True)
    inks, want = page["inks"], page["want"]
    assert inks["open"]["ink"] == want["text"], f"{name}: {inks} {want}"
    assert inks["more"]["ink"] == want["muted"], f"{name}: {inks} {want}"
    clear = "rgba(0, 0, 0, 0)"
    assert inks["open"]["fill"] == inks["more"]["fill"] == clear, f"{name}: {inks}"
    frame = inks["frame"]
    assert (frame["border"], frame["ground"], frame["radius"]) == (
        want["border"],
        want["surface"],
        want["radius"],
    ), f"{name}: {frame} {want}"
    assert page["markBox"]["width"] == _px(want["glyph"]), f"{name}: mark {page['markBox']}"


def _px(value: str) -> float:
    assert value.endswith("px"), value
    return float(value[:-2])


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _moved(before: dict[str, Any] | None, after: dict[str, Any] | None) -> float:
    if before is None or after is None:
        return 0.0 if before is after else float("inf")
    return max(abs(before[key] - after[key]) for key in ("left", "top", "width", "height"))


def test_view_headers_hold_their_rows_ground_and_values_in_chrome(
    tmp_path: Path, chrome_profile: Path
) -> None:
    chrome = require_chrome()
    root, commit = _served(tmp_path / "served")
    links = _links(commit)
    state = tmp_path / "state"
    for part in ("cache", "config"):
        (state / part).mkdir(mode=0o700, parents=True)
    # The checkout turns on the Pulls tab, which asks gh for the repository's pull
    # requests: this test's own gh answers as one signed out does, and quietly, so the
    # suite's guard counts no call from it.
    fake_gh = tmp_path / "gh-bin"
    fake_gh.mkdir()
    (fake_gh / "gh").write_text(
        "#!/bin/sh\necho 'You are not logged into any GitHub hosts.' >&2\nexit 4\n",
        encoding="utf-8",
    )
    (fake_gh / "gh").chmod(0o755)
    run = run_in_own_group(
        [
            require_node(),
            str(SESSION),
            str(_METAB),
            str(root),
            str(_free_port()),
            str(state),
            commit,
        ],
        timeout_s=SESSION_TIMEOUT_S,
        env={
            **os.environ,
            "PATH": f"{fake_gh}{os.pathsep}{os.environ.get('PATH', '')}",
            "CHROME_BIN": chrome,
            "CHROME_PROFILES": str(chrome_profile),
        },
    )
    assert not run.timed_out, f"the session ran past {SESSION_TIMEOUT_S} s: {run.stderr}"
    assert run.returncode == 0, run.stderr or run.stdout
    print(run.stderr)
    record: dict[str, Any] = json.loads(run.stdout.strip().splitlines()[-1])
    results: list[dict[str, Any]] = record["results"]
    assert len(results) == 24, len(results)

    for result in results:
        name = f"{result['kind']} {result['pane']}px {result['theme']}"
        page = result["settled"]
        assert page["scheme"] == result["theme"], f"{name}: drawn in {page['scheme']}"
        assert abs(page["paneWidth"] - result["pane"]) <= 1, f"{name}: {page['paneWidth']} px"

        # The rows, one gap apart, each its token's height, and the tab bar under them: the
        # tokens as the page resolves them (static/styles.css, `--view-header-*`).
        tokens = page["tokens"]
        gap = _px(tokens["--view-header-row-gap"])
        eyebrow, heading, line, bar = page["eyebrow"], page["heading"], page["line"], page["bar"]
        assert eyebrow["height"] == _px(tokens["--view-header-eyebrow-height"]), (
            f"{name}: eyebrow {eyebrow}"
        )
        assert line["height"] == _px(tokens["--view-header-line-height"]), f"{name}: line {line}"
        assert abs(heading["top"] - eyebrow["bottom"] - gap) <= TOLERANCE_PX, name
        assert abs(line["top"] - heading["bottom"] - gap) <= TOLERANCE_PX, name
        assert abs(bar["top"] - page["header"]["bottom"]) <= TOLERANCE_PX, name
        # The line starts on the eyebrow's inset, as the title's row does.
        assert abs(line["left"] - eyebrow["left"]) <= TOLERANCE_PX, name
        assert abs(heading["left"] - eyebrow["left"]) <= TOLERANCE_PX, name
        # The icon at the title's size, before the title.
        assert page["iconGlyph"]["width"] == _px(tokens["--page-title-font-size"]), (
            f"{name}: icon {page['iconGlyph']}"
        )
        assert page["icon"]["right"] <= page["title"]["left"], name

        # The type.
        assert page["type"]["title"] == tokens["--page-title-font-size"], (
            f"{name}: title {page['type']}"
        )
        assert int(page["type"]["titleWeight"]) >= 600, f"{name}: title {page['type']}"
        assert page["type"]["line"] == tokens["--body-font-size"], f"{name}: line {page['type']}"
        assert page["type"]["eyebrow"] == tokens["--body-font-size"], (
            f"{name}: eyebrow {page['type']}"
        )

        # One ground, the body's, under the header and its tabs, which is not the
        # navigation's; the header has no rule of its own, and the tab bar's is the one.
        grounds = page["grounds"]
        assert grounds["header"] == grounds["bar"] == grounds["body"], f"{name}: {grounds}"
        assert grounds["nav"] != grounds["body"], f"{name}: {grounds}"
        rules = page["rules"]
        assert rules["headerTop"] == rules["headerBottom"] == "0px", f"{name}: {rules}"
        assert rules["barTop"] == "0px" and rules["barBottom"] == "1px", f"{name}: {rules}"

        # The title: the item's name, cut short only where its row is too narrow.
        expected = {
            "file": "a-long-name-for-a-view-header-title.md",
            "folder": "notes",
            "root": "served",
        }[result["kind"]]
        assert page["titleText"] == expected, f"{name}: {page['titleText']}"
        if result["pane"] >= 900:
            assert not page["titleCut"], f"{name}: the title is cut in a wide pane"
        if result["kind"] == "file" and result["pane"] <= 260:
            assert page["titleCut"], f"{name}: the title overflows its row"
        # Its tooltip, the whole name, shows exactly while the name is cut short
        # (`tipAddsInformation`; "Tooltips Add Information"): a whole title's glyphs
        # overflowing its line box is no cut.
        assert page["titleTip"] is page["titleCut"], (
            f"{name}: tooltip {page['titleTip']}, cut {page['titleCut']}, {page['titleHeights']}"
        )
        # Up: disabled at the root, a control everywhere else.
        assert page["upDisabled"] is (result["kind"] == "root"), name

        # The View on GitHub button in the header's corner: at the corner's insets from the
        # header's top and right edges and its height, inside the room the eyebrow leaves
        # it from first paint with the row's gap before it, the eyebrow's address ending
        # that gap clear of it.
        button = page["button"]
        assert page["endMarked"], f"{name}: the corner is not marked for a button"
        assert button is not None, f"{name}: no button"
        _button_drawn(name, page, links[result["kind"]])
        header = page["header"]
        assert (
            abs(button["top"] - header["top"] - _px(tokens["--view-header-corner-inset-top"]))
            <= TOLERANCE_PX
        ), f"{name}: {button} {header}"
        assert (
            abs(header["right"] - button["right"] - _px(tokens["--view-header-corner-inset-end"]))
            <= TOLERANCE_PX
        ), f"{name}: {button} {header}"
        assert abs(button["height"] - _px(tokens["--view-header-corner-height"])) <= TOLERANCE_PX
        room = _px(tokens["--view-header-corner-room"])
        assert button["width"] + _GAP_PX <= room + TOLERANCE_PX, f"{name}: {button} {room}"
        assert page["eyebrowRoom"] == room, f"{name}: eyebrow room {page['eyebrowRoom']}"
        assert page["addressBox"]["right"] <= button["left"] - _GAP_PX + TOLERANCE_PX, (
            f"{name}: the address {page['addressBox']} runs under the button {button}"
        )
        # Level with the eyebrow: the corner is the eyebrow's height at its top.
        middle = (eyebrow["top"] + eyebrow["bottom"]) / 2
        assert abs((button["top"] + button["bottom"]) / 2 - middle) <= TOLERANCE_PX, name
        # A title cut short keeps at least a floor of the row; a whole one has all it
        # needs. A whole title is not measured against its scroll width, which is whole
        # pixels where its width is fractional: a whole "docs" is 48.94 px and needs 49.
        if page["titleCut"]:
            assert page["title"]["width"] >= _TITLE_FLOOR_PX, f"{name}: title {page['title']}"

        # Every item is whole on the line or wrapped out of sight, never cut; the first is
        # always shown.
        for snapshot in (page, *result["relabeled"].values()):
            for item in snapshot["items"]:
                assert not item["shown"] or item["whole"], f"{name}: cut item {item}"
            shown = [item for item in snapshot["items"] if item["shown"]]
            assert shown and shown[0] is snapshot["items"][0], f"{name}: {snapshot['items']}"
        if result["pane"] >= 900:
            assert all(item["shown"] for item in page["items"]), f"{name}: {page['items']}"
            assert page["items"][-1]["text"].endswith("3d ago"), f"{name}: {page['items']}"

        # Steadiness: as the values change, nothing but the line's items moves.
        for step, after in result["relabeled"].items():
            for key in ("header", "eyebrow", "heading", "title", "end", "button", "line", "bar"):
                moved = _moved(page[key], after[key])
                assert moved <= TOLERANCE_PX, f"{name} {step}: {key} moved {moved} px"
        # The age is last: from "just now" to "59m ago" it moves no item before it.
        fresh, hour = result["relabeled"]["fresh"], result["relabeled"]["hour"]
        assert fresh["items"][-1]["text"].endswith("just now"), f"{name}: {fresh['items']}"
        assert hour["items"][-1]["text"].endswith("59m ago"), f"{name}: {hour['items']}"
        for before, after in zip(fresh["items"][:-1], hour["items"][:-1], strict=True):
            moved = _moved(before["box"], after["box"])
            assert moved <= TOLERANCE_PX, f"{name}: {before['text']} moved {moved} px"

    # The menu, in each theme: a click on the chevron opens it under the button, its right
    # edge on the button's, with focus on Copy Link; the arrow keys, End, and Home move
    # focus among its two items, wrapping; Escape closes it and gives focus back to the
    # chevron; ArrowUp on the chevron opens it at its last item; Tab closes it; and a press
    # outside the button closes it. Each item is the element at its own center.
    menus = record["menus"]
    assert [menu["theme"] for menu in menus] == ["light", "dark"], menus
    for menu in menus:
        name = f"menu {menu['theme']}"
        steps = menu["steps"]
        assert steps["closed"]["hidden"] and steps["closed"]["expanded"] == "false", name
        opened = steps["clicked"]
        assert not opened["hidden"] and opened["expanded"] == "true", f"{name}: {opened}"
        assert opened["focus"] == "Copy Link", f"{name}: {opened}"
        box, group = opened["menu"], opened["group"]
        assert box["top"] >= group["bottom"], f"{name}: {box} {group}"
        assert abs(box["right"] - group["right"]) <= TOLERANCE_PX, f"{name}: {box} {group}"
        assert box["bottom"] <= opened["viewport"]["height"], f"{name}: {box}"
        assert [(item["text"], item["role"]) for item in opened["items"]] == [
            ("Copy Link", "menuitem"),
            ("Open in Browser", "menuitem"),
        ], f"{name}: {opened['items']}"
        assert all(item["topmost"] for item in opened["items"]), f"{name}: {opened['items']}"
        # Open in Browser is a link, and looks like Copy Link, a button: no underline.
        copy_link, open_in_browser = opened["items"]
        assert copy_link["look"] == open_in_browser["look"], f"{name}: {opened['items']}"
        assert open_in_browser["look"][1] == "none", f"{name}: {opened['items']}"
        walked = [
            (step, steps[step]["focus"], steps[step]["hidden"])
            for step in ("arrowDown", "arrowDownAgain", "end", "home", "escape", "arrowUp", "tab")
        ]
        assert walked == [
            ("arrowDown", "Open in Browser", False),
            ("arrowDownAgain", "Copy Link", False),
            ("end", "Open in Browser", False),
            ("home", "Copy Link", False),
            ("escape", "chevron", True),
            ("arrowUp", "Open in Browser", False),
            ("tab", walked[-1][1], True),
        ], f"{name}: {walked}"
        assert steps["escape"]["expanded"] == "false", f"{name}: {steps['escape']}"
        assert not steps["reopened"]["hidden"], f"{name}: {steps['reopened']}"
        assert steps["outside"]["hidden"], f"{name}: {steps['outside']}"
        assert steps["outside"]["expanded"] == "false", f"{name}: {steps['outside']}"

    # A file the checkout does not track: its corner is marked, so the eyebrow keeps the
    # room from first paint, and once the server has answered it holds nothing.
    for absent in record["absent"]:
        name = f"untracked file {absent['theme']}"
        assert absent["answered"] and absent["marked"], f"{name}: {absent}"
        assert absent["children"] == 0, f"{name}: {absent}"
        assert absent["eyebrowRoom"] == _px(
            results[0]["settled"]["tokens"]["--view-header-corner-room"]
        )

    # A commit's page: the button in the page's corner at the same insets as a view
    # header's, after the subject in the reading order, its link the commit's page; the
    # subject leaves it room only where the reading column reaches it, and its text ends
    # the gap clear of it.
    commits = record["commits"]
    assert [(page["theme"], page["pane"]) for page in commits] == [
        ("light", 1180),
        ("light", 480),
        ("dark", 1180),
        ("dark", 480),
    ], commits
    tokens = results[0]["settled"]["tokens"]
    room = _px(tokens["--view-header-corner-room"])
    for page in commits:
        name = f"commit {page['pane']}px {page['theme']}"
        # The page's one corner, placed in the commit's view.
        assert page["corners"] == 1 and page["viewClass"] == "git-commit-view", f"{name}: {page}"
        assert page["marked"] and page["afterSubject"], f"{name}: {page}"
        _button_drawn(name, page, links["commit"])
        button, view = page["button"], page["view"]
        assert (
            abs(button["top"] - view["top"] - _px(tokens["--view-header-corner-inset-top"]))
            <= TOLERANCE_PX
        ), f"{name}: {button} {view}"
        assert (
            abs(view["right"] - button["right"] - _px(tokens["--view-header-corner-inset-end"]))
            <= TOLERANCE_PX
        ), f"{name}: {button} {view}"
        assert abs(button["height"] - _px(tokens["--view-header-corner-height"])) <= TOLERANCE_PX
        if page["pane"] >= 1180:
            assert page["subjectRoom"] == 0, f"{name}: the subject keeps its width"
        else:
            assert page["subjectRoom"] == room, f"{name}: subject room {page['subjectRoom']}"
        assert page["subjectEnd"] <= button["left"] - _GAP_PX + TOLERANCE_PX, f"{name}: {page}"
        assert not page["paneScrolls"], name
