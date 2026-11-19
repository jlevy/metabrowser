"""A file's and a folder's view header, laid out as the design says, in headless Chrome.

The owner, 2026-11-18: the size, file count, and age at the upper right of the main
view's header belong next to the item's name, "much like the nav bar", and the headers of
files, folders, pull requests, and commits should be one design: an eyebrow with the
enclosing folder and the Up control, the item's icon and its name at full size, the
metadata, then the tabs, on one ground with one rule (mb-6x33). Then the line with the size
and age goes "just to the right of the filename, with a gap", and an extremely long name
wraps (mb-tgmc; docs/design-system.md, "View Headers").

``tests/dom/view-header-chrome.mjs`` serves a folder dated days back, so no age changes
its label during the session, and reads a file's header, its folder's, the served root's,
and the header of a file whose name no pane holds on one line, in a 1,400, 800, 360, and
260 px main view, in both themes. Then it rewrites the metadata line in place with the
shell's own builders, as the folder header's live refresh does: the age of something just
written ("just now"), an hour later ("59m ago"), and the pending skeletons of a walk that
has not finished. This judges the record:

- the rows: the eyebrow, its token's height, then the heading row a gap under it and the
  header's bottom pad under that, with no row of the line's own, and the tab bar right
  under the header. Where the name and the line share one line, the heading row is the
  title's line high, so the header is that line, the eyebrow, the gap, and the two pads;
- the line after the name: where the room after the name's last line holds it, the line
  sits there, the title gap after the name's text and on its baseline; where it does not,
  the line starts the next line, at the name's start. The file's, the folder's, and the
  root's names are one line with the line after them in every pane from 800 px; the long
  name wraps, in every pane, and is whole;
- the type and ink: the title at the page title's size and bold, the eyebrow's address and
  the metadata line at the body size, the line in muted ink;
- the ground and the rules: the header and the tab bar on the body's ground, which is not
  the navigation's, the header with no rule of its own, and the tab bar's one rule under
  it;
- the View on GitHub button (mb-4wqh), on a folder served as a checkout whose origin is
  on github.com: in the header's corner at its tokens' insets and height, inside the room
  the eyebrow leaves it from first paint and above the heading row, its link and its
  menu's Open in Browser the item's page on github.com at the checkout's commit, through
  the hooks the macOS app reads, in the text ink with a muted chevron in a joined chip
  group's frame, at a chip's size rather than the title's; its menu, opened with a click
  and walked with the arrow keys, Home, End, Escape, and Tab, every item on top where it
  is drawn; a file the checkout does not track, whose corner keeps its room and draws
  nothing; and a commit's page, its button placed in the page as a view header's is, its
  subject leaving it room only where the reading column reaches it;
- whole: no name cut short or run past its row, so no name has a tooltip, every metadata
  item shown whole inside the header, and nothing in the header past its box. The long
  name has an unbroken run, a digest's 64 hex digits, so it wraps inside a word too;
- the line wrapped: at least one page and pane takes the branch where the line starts
  the next line at the name's start, which holds the title gap to padding after the
  name rather than a margin before the line;
- steadiness: while the line stays after the name, as the values change no box of the
  header but the line's own items moves or changes size: not the header, the eyebrow, the
  heading row, the title, the corner, the button, or the tab bar; the age, last on its
  line, moves no other item when its label's width changes. At the width where the line
  no longer fits after the name, it wraps as above, and every pane from 800 px keeps it
  after the name through every value the session writes.

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
# A name no pane's row holds on one line, with a run no hyphen or space breaks, a SHA-256
# digest's 64 hex digits, wider than the 260 px and 360 px panes' rows, which wrap it inside
# that run (`overflow-wrap: anywhere` on `.page-heading`), as a content-addressed name
# needs. Its lines are 2,384 px at the title's size, three lines in the 1,400 px pane
# (`WRAPPED` in the session; Chrome 152, 2026-11-18).
_WRAPPED = (
    "a-file-name-so-long-that-no-pane-the-session-draws-holds-it-on-one-line-"
    "3f9a0c5be1d2476a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a-"
    "of-the-view-header-so-it-wraps-and-its-size-and-age-follow-its-last-line.md"
)
# One server start, one Chrome, and 32 loads, each with three rewrites of its line, then in
# each theme a menu's walk, a page with no counterpart, and two commit pages: the 32 loads
# alone took 37 s to 50 s on a 10-core Mac (24 loads took 28 s there at a load average
# near 12). A cold Chrome start in CI has taken 28.2 s, and the server's start is bounded
# at 30 s inside the session.
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
    (notes / _WRAPPED).write_text("# A long name\n", encoding="utf-8")
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


# The heading row's gap, which the corner's room keeps between the eyebrow and the button.
_GAP_PX = 8
_REPOSITORY = "https://github.com/octo/demo"
# Each page's title.
_TITLES = {
    "file": "a-long-name-for-a-view-header-title.md",
    "folder": "notes",
    "root": "served",
    "wrapped": _WRAPPED,
}
# The panes whose rows hold every name but the long one with its line after it, through
# every value the session writes: the 800 px pane's row holds 643 px of title, and the
# widest of those names, the file's, is 426 px, with the title gap and its widest line,
# "26 B · just now", 535 px (Chrome 152, 2026-11-18).
_INLINE_FROM_PX = 800


def _links(commit: str) -> dict[str, str]:
    """Each page's counterpart: the item's tree or blob at the checkout's commit."""

    return {
        "file": f"{_REPOSITORY}/blob/{commit}/docs/notes/a-long-name-for-a-view-header-title.md",
        "folder": f"{_REPOSITORY}/tree/{commit}/docs/notes",
        "root": f"{_REPOSITORY}/tree/{commit}",
        "wrapped": f"{_REPOSITORY}/blob/{commit}/docs/notes/{_WRAPPED}",
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
    inks, want = page["buttonInks"], page["want"]
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
    # A chip's size, not the title's: nothing of the heading row's type reaches the corner.
    assert page["buttonFont"] == want["chipFont"], f"{name}: {page['buttonFont']} {want}"


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


def _after_name(snapshot: dict[str, Any]) -> bool:
    """Whether the line sits beside the name's last line rather than under it: its middle
    within half a title line of that line's text's middle. The text's box is its glyphs',
    taller than the line it sits in, so its edges do not say which line a box is on."""
    last = max(snapshot["titleTextRects"], key=lambda rect: rect["top"])
    line = snapshot["line"]
    middle = (line["top"] + line["bottom"]) / 2
    return abs(middle - (last["top"] + last["bottom"]) / 2) < snapshot["titleLineHeight"] / 2


def _check_line_placement(name: str, snapshot: dict[str, Any]) -> bool:
    """The line follows the name's last line where the room after it holds the line, the
    title gap after the text and on its baseline; otherwise it starts the next line at the
    name's start. Either way it is whole inside the title's group, and so the header.
    Whether it wrapped to the next line."""
    gap = _px(snapshot["tokens"]["--view-header-title-gap"])
    rects, line, group = snapshot["titleTextRects"], snapshot["line"], snapshot["group"]
    assert rects, f"{name}: the title has no text"
    last = max(rect["top"] for rect in rects)
    text_right = max(rect["right"] for rect in rects if rect["top"] == last)
    room = group["right"] - text_right - gap
    wrapped = line["width"] > room + TOLERANCE_PX
    if not wrapped:
        assert abs(line["left"] - text_right - gap) <= TOLERANCE_PX, (
            f"{name}: the line is {line['left'] - text_right:.2f} px after the name, not {gap}"
        )
        assert _after_name(snapshot), f"{name}: the line is not on the name's last line"
    else:
        assert abs(line["left"] - group["left"]) <= TOLERANCE_PX, (
            f"{name}: a wrapped line starts at {line['left']}, not the name's {group['left']}"
        )
        assert not _after_name(snapshot), f"{name}: the line overlaps the name's last line"
    assert group["left"] - TOLERANCE_PX <= line["left"], f"{name}: line {line} group {group}"
    assert line["right"] <= group["right"] + TOLERANCE_PX, f"{name}: line {line} group {group}"
    for item in snapshot["items"]:
        box = item["box"]
        assert box["width"] > 0 and box["height"] > 0, f"{name}: hidden item {item}"
        assert line["left"] - TOLERANCE_PX <= box["left"], f"{name}: cut item {item}"
        assert box["right"] <= line["right"] + TOLERANCE_PX, f"{name}: cut item {item}"
        assert line["top"] - TOLERANCE_PX <= box["top"], f"{name}: cut item {item}"
        assert box["bottom"] <= line["bottom"] + TOLERANCE_PX, f"{name}: cut item {item}"
    assert not snapshot["headerOverflows"], f"{name}: the header runs past its box"
    return wrapped


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
    assert len(results) == 32, len(results)
    # Which pages and panes wrap the line to the next line (A3 of review A on #592).
    wrapped_lines: list[str] = []

    for result in results:
        name = f"{result['kind']} {result['pane']}px {result['theme']}"
        page = result["settled"]
        assert page["scheme"] == result["theme"], f"{name}: drawn in {page['scheme']}"
        assert abs(page["paneWidth"] - result["pane"]) <= 1, f"{name}: {page['paneWidth']} px"

        # The rows: the eyebrow its token's height, the heading row a gap under it, the
        # header's bottom pad under that, and the tab bar right under the header. The line
        # has no row of its own: it is inside the heading row (static/styles.css,
        # `--view-header-*`).
        tokens = page["tokens"]
        gap = _px(tokens["--view-header-row-gap"])
        eyebrow, heading, line, bar = page["eyebrow"], page["heading"], page["line"], page["bar"]
        header, title_line = page["header"], page["titleLineHeight"]
        assert eyebrow["height"] == _px(tokens["--view-header-eyebrow-height"]), (
            f"{name}: eyebrow {eyebrow}"
        )
        pad_top = _px(tokens["--view-header-padding-top"])
        pad_bottom = _px(tokens["--view-header-padding-bottom"])
        assert abs(eyebrow["top"] - header["top"] - pad_top) <= TOLERANCE_PX, name
        assert abs(heading["top"] - eyebrow["bottom"] - gap) <= TOLERANCE_PX, name
        assert abs(header["bottom"] - heading["bottom"] - pad_bottom) <= TOLERANCE_PX, (
            f"{name}: heading {heading}, header {header}"
        )
        assert abs(bar["top"] - header["bottom"]) <= TOLERANCE_PX, name
        assert heading["top"] - TOLERANCE_PX <= line["top"], f"{name}: line {line}"
        assert line["bottom"] <= heading["bottom"] + TOLERANCE_PX, f"{name}: line {line}"
        assert abs(heading["left"] - eyebrow["left"]) <= TOLERANCE_PX, name
        # The icon at the title's size, before the title, on its first line.
        assert page["iconGlyph"]["width"] == _px(tokens["--page-title-font-size"]), (
            f"{name}: icon {page['iconGlyph']}"
        )
        assert page["icon"]["right"] <= page["title"]["left"], name
        assert abs(page["icon"]["top"] - heading["top"]) <= TOLERANCE_PX, name
        assert abs(page["icon"]["height"] - title_line) <= TOLERANCE_PX, name

        # The type and the line's ink, the muted ink metadata has everywhere.
        assert page["type"]["title"] == tokens["--page-title-font-size"], (
            f"{name}: title {page['type']}"
        )
        assert int(page["type"]["titleWeight"]) >= 600, f"{name}: title {page['type']}"
        assert page["type"]["line"] == tokens["--body-font-size"], f"{name}: line {page['type']}"
        assert page["type"]["eyebrow"] == tokens["--body-font-size"], (
            f"{name}: eyebrow {page['type']}"
        )
        assert page["inks"]["line"] == page["inks"]["muted"], f"{name}: {page['inks']}"

        # One ground, the body's, under the header and its tabs, which is not the
        # navigation's; the header has no rule of its own, and the tab bar's is the one.
        grounds = page["grounds"]
        assert grounds["header"] == grounds["bar"] == grounds["body"], f"{name}: {grounds}"
        assert grounds["nav"] != grounds["body"], f"{name}: {grounds}"
        rules = page["rules"]
        assert rules["headerTop"] == rules["headerBottom"] == "0px", f"{name}: {rules}"
        assert rules["barTop"] == "0px" and rules["barBottom"] == "1px", f"{name}: {rules}"

        # The title: the item's whole name, never cut short or run past its row, so the
        # shell's own rule shows no tooltip for it (`tipAddsInformation`; "Tooltips Add
        # Information").
        kind = result["kind"]
        assert page["titleText"] == _TITLES[kind], f"{name}: {page['titleText']}"
        assert not page["titleCut"], f"{name}: the title is cut short"
        assert not page["titleClipped"], f"{name}: the title runs past its row"
        assert page["titleTip"] is False, f"{name}: the title has a tooltip"
        # The corner is above the heading row, so the row keeps the header's width.
        if page["button"] is not None:
            assert page["button"]["bottom"] <= heading["top"] + TOLERANCE_PX, name
        # Up: disabled at the root, a control everywhere else.
        assert page["upDisabled"] is (kind == "root"), name

        # The View on GitHub button in the header's corner: at the corner's insets from the
        # header's top and right edges and its height, inside the room the eyebrow leaves
        # it from first paint with the row's gap before it, the eyebrow's address ending
        # that gap clear of it.
        button = page["button"]
        assert page["endMarked"], f"{name}: the corner is not marked for a button"
        assert button is not None, f"{name}: no button"
        _button_drawn(name, page, links[kind])
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

        # The line after the name, or under it where the row has no room after the name.
        if _check_line_placement(name, page):
            wrapped_lines.append(f"{result['theme']} {kind} {result['pane']}")
        if kind == "wrapped":
            # The long name wraps in every pane, its line after its last line or under it.
            assert page["titleLines"] >= 2, f"{name}: {page['titleLines']} lines"
        elif result["pane"] >= _INLINE_FROM_PX:
            # A name that fits its row is one line, the line after it on its baseline, so
            # the heading row is the title's line high and the header holds no other row.
            assert page["titleLines"] == 1, f"{name}: {page['titleLines']} lines"
            assert _after_name(page), f"{name}: the line is not after the name: {line}"
            assert abs(page["lineBaseline"] - page["titleBaseline"]) <= TOLERANCE_PX, (
                f"{name}: line baseline {page['lineBaseline']}, title {page['titleBaseline']}"
            )
            assert abs(heading["height"] - title_line) <= TOLERANCE_PX, f"{name}: {heading}"
            one_line = pad_top + eyebrow["height"] + gap + title_line + pad_bottom
            assert abs(header["height"] - one_line) <= TOLERANCE_PX, f"{name}: {header}"

        # Every item is whole inside the header, the age last, after each value the session
        # writes, and the line after the name or under it.
        assert page["items"][-1]["text"].endswith("3d ago"), f"{name}: {page['items']}"
        for step, after in result["relabeled"].items():
            _check_line_placement(f"{name} {step}", after)

        # Steadiness: while the line stays after the name, as the values change nothing but
        # the line's items moves. Every pane from 800 px keeps it there for every page but
        # the long name's.
        for step, after in result["relabeled"].items():
            if kind != "wrapped" and result["pane"] >= _INLINE_FROM_PX:
                assert _after_name(after), f"{name} {step}: the line left the name's line"
            if not (_after_name(page) and _after_name(after)):
                continue
            for key in ("header", "eyebrow", "heading", "title", "end", "button", "bar"):
                moved = _moved(page[key], after[key])
                assert moved <= TOLERANCE_PX, f"{name} {step}: {key} moved {moved} px"
            for key in ("left", "top", "height"):
                assert abs(page["line"][key] - after["line"][key]) <= TOLERANCE_PX, (
                    f"{name} {step}: the line's {key} moved: {page['line']} {after['line']}"
                )
        # The age is last: from "just now" to "59m ago" it moves no item before it.
        fresh, hour = result["relabeled"]["fresh"], result["relabeled"]["hour"]
        assert fresh["items"][-1]["text"].endswith("just now"), f"{name}: {fresh['items']}"
        assert hour["items"][-1]["text"].endswith("59m ago"), f"{name}: {hour['items']}"
        if _after_name(fresh) == _after_name(hour):
            for before, after in zip(fresh["items"][:-1], hour["items"][:-1], strict=True):
                moved = _moved(before["box"], after["box"])
                assert moved <= TOLERANCE_PX, f"{name}: {before['text']} moved {moved} px"

    # A3 of review A on #592: the branch that holds the title gap to padding is taken. In
    # the 260 px pane the folder's and the root's one-line names leave too little room for
    # their lines, which wrap to the next line at the name's start, in both themes (Chrome
    # 152, 2026-11-18, with the View on GitHub button in the corner).
    for theme in ("light", "dark"):
        for kind in ("folder", "root"):
            assert f"{theme} {kind} 260" in wrapped_lines, (kind, theme, wrapped_lines)

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
