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
- the GitHub toggle (mb-zp7y), on a folder served as a checkout whose origin is on
  github.com: at the heading row's far end, centered on the title's first line, two
  segments of its tokens' size in their pill's border, the Metabrowser mark the view the
  page is in and the GitHub mark a link to the item's page;
- whole: no name cut short or run past its row, so no name has a tooltip, every metadata
  item shown whole inside the header, and nothing in the header past its box;
- steadiness: while the line stays after the name, as the values change no box of the
  header but the line's own items moves or changes size: not the header, the eyebrow, the
  heading row, the title, the end, the toggle, or the tab bar; the age, last on its line,
  moves no other item when its label's width changes. At the width where the line no
  longer fits after the name, it wraps as above, and every pane from 800 px keeps it after
  the name through every value the session writes.

Where text sits is computed layout, so this needs a browser; it skips without Chrome
(``docs/e2e-testing.md``), and CI runs it. The session leads a process group of its own,
which Chrome and the server join (``tests/process_group.py``).
"""

from __future__ import annotations

import json
import os
import socket
import sys
import time
from pathlib import Path
from typing import Any

import pytest

from tests.process_group import GROUP_STOP_S, PROFILE_TEARDOWN_S, run_in_own_group
from tests.required_tools import require_chrome, require_node

SESSION = Path(__file__).resolve().parent / "dom" / "view-header-chrome.mjs"
_METAB = Path(sys.executable).with_name("metab")
# A name no pane's row holds on one line: 1,585 px at the title's size, and the widest row,
# the 1,400 px pane's, holds 1,243 px of title (`WRAPPED` in the session; Chrome 152,
# 2026-11-18).
_WRAPPED = (
    "a-file-name-so-long-that-no-pane-the-session-draws-holds-it-on-one-line-of-the-view-header-"
    "so-it-wraps-and-its-size-and-age-follow-its-last-line.md"
)
# One server start, one Chrome, and 32 loads, each with three rewrites of its line: the
# test took 37 s to 50 s on a 10-core Mac (24 loads took 28 s there at a load average near
# 12). A cold Chrome start in CI has taken 28.2 s, and the server's start is bounded at
# 30 s inside the session.
SESSION_TIMEOUT_S = 180
LIFECYCLE_S = SESSION_TIMEOUT_S + GROUP_STOP_S + PROFILE_TEARDOWN_S
pytestmark = pytest.mark.timeout(LIFECYCLE_S + 10)
# Layout rounds to fractions of a pixel; a box off by more than this has moved.
TOLERANCE_PX = 0.5
# Three days old: every age reads "3d ago" from 2.5 to 3.5 days (`AGE_TIERS` in
# formatters.js rounds), so no age changes its label inside the session's bound.
_AGE_S = 3 * 24 * 60 * 60


def _served(root: Path) -> Path:
    notes = root / "docs" / "notes"
    notes.mkdir(parents=True)
    (notes / "a-long-name-for-a-view-header-title.md").write_text(
        "# A note\n\nWith some text.\n", encoding="utf-8"
    )
    (notes / "b.txt").write_text("b\n" * 4000, encoding="utf-8")
    (notes / _WRAPPED).write_text("# A long name\n", encoding="utf-8")
    (root / "README.md").write_text("# Served\n", encoding="utf-8")
    # A checkout whose origin is on github.com, as far as the server reads one
    # (repository_context.py), so its pages carry the GitHub toggle.
    git = root / ".git"
    (git / "refs" / "heads").mkdir(parents=True)
    (git / "config").write_text(
        '[remote "origin"]\n\turl = https://github.com/octo/demo.git\n', encoding="utf-8"
    )
    (git / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (git / "refs" / "heads" / "main").write_text(f"{'0' * 40}\n", encoding="utf-8")
    # Origin has the branch, so the toggle links at it rather than at the commit.
    (git / "refs" / "remotes" / "origin").mkdir(parents=True)
    (git / "refs" / "remotes" / "origin" / "main").write_text(f"{'0' * 40}\n", encoding="utf-8")
    when = time.time() - _AGE_S
    for path in [root, *root.rglob("*")]:
        os.utime(path, (when, when))
    return root


# The toggle's narrow rule (`@container view-header (width < 400px)` in styles.css).
_TOGGLE_NARROW_PX = 400
# Each page's link: the branch origin has, then the item's tree or blob.
_LINKS = {
    "file": "https://github.com/octo/demo/blob/main/docs/notes/a-long-name-for-a-view-header-title.md",
    "folder": "https://github.com/octo/demo/tree/main/docs/notes",
    "root": "https://github.com/octo/demo/tree/main",
    "wrapped": f"https://github.com/octo/demo/blob/main/docs/notes/{_WRAPPED}",
}
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


def _check_line_placement(name: str, snapshot: dict[str, Any]) -> None:
    """The line follows the name's last line where the room after it holds the line, the
    title gap after the text and on its baseline; otherwise it starts the next line at the
    name's start. Either way it is whole inside the title's group, and so the header."""
    gap = _px(snapshot["tokens"]["--view-header-title-gap"])
    rects, line, group = snapshot["titleTextRects"], snapshot["line"], snapshot["group"]
    assert rects, f"{name}: the title has no text"
    last = max(rect["top"] for rect in rects)
    text_right = max(rect["right"] for rect in rects if rect["top"] == last)
    room = group["right"] - text_right - gap
    if line["width"] <= room + TOLERANCE_PX:
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


def test_view_headers_hold_their_rows_ground_and_values_in_chrome(
    tmp_path: Path, chrome_profile: Path
) -> None:
    chrome = require_chrome()
    root = _served(tmp_path / "served")
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
        [require_node(), str(SESSION), str(_METAB), str(root), str(_free_port()), str(state)],
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
    results: list[dict[str, Any]] = json.loads(run.stdout.strip().splitlines()[-1])["results"]
    assert len(results) == 32, len(results)

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
        assert page["group"]["right"] <= page["end"]["left"] + TOLERANCE_PX, name
        # Up: disabled at the root, a control everywhere else.
        assert page["upDisabled"] is (kind == "root"), name

        # The line after the name, or under it where the row has no room after the name.
        _check_line_placement(name, page)
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

        # The GitHub toggle ends the heading row, centered on the title's first line: two
        # segments of the Up control's height and the toggle's width, in their pill's
        # border, the Metabrowser mark the view the page is in and the GitHub mark a link
        # to the item's page. A header whose rows are under 400 px keeps the GitHub segment
        # alone.
        toggle, end = page["toggle"], page["end"]
        assert toggle is not None, f"{name}: no toggle"
        up, option = (
            _px(tokens["--view-header-up-size"]),
            _px(tokens["--view-header-toggle-option-width"]),
        )
        border, inset = _px(tokens["--chip-border"]), _px(tokens["--content-padding-x"])
        assert toggle["height"] == up + 2 * border, f"{name}: toggle {toggle}"
        narrow = header["width"] - 2 * inset < _TOGGLE_NARROW_PX
        segments = 1 if narrow else 2
        assert toggle["width"] == segments * option + 2 * border, f"{name}: toggle {toggle}"
        assert abs(toggle["right"] - end["right"]) <= TOLERANCE_PX, f"{name}: {toggle} {end}"
        assert abs(end["right"] - header["right"] + inset) <= TOLERANCE_PX, name
        middle = heading["top"] + title_line / 2
        assert abs((toggle["top"] + toggle["bottom"]) / 2 - middle) <= TOLERANCE_PX, name
        assert "view-header-toggle-metabrowser" in (page["toggleCurrent"] or ""), name
        assert page["toggleHref"] == _LINKS[kind], f"{name}: {page['toggleHref']}"
        glyph = _px(tokens["--icon-glyph"])
        marks = [mark["height"] for mark in page["marks"]]
        assert marks == ([0, glyph] if narrow else [glyph, glyph]), f"{name}: marks {marks}"

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
            for key in ("header", "eyebrow", "heading", "title", "end", "toggle", "bar"):
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
