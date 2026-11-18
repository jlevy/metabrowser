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
- the GitHub toggle (mb-zp7y), on a folder served as a checkout whose origin is on
  github.com: in the header's upper right corner at its inset tokens, level with the
  eyebrow, which leaves it its room, and not with the title (mb-70d6: the owner, "the
  toggle between mb and github should be in upper right, not lower just because the
  file title is lower on the page"); two segments of its tokens' size in their pill's
  border at every width, the Metabrowser mark the view the page is in and the GitHub
  mark a link to the item's page; and drawn as the shared toggles are, the page's view
  selected in `--link` on `--highlight-bg`, the GitHub segment at rest in `--muted` with
  no fill and under the pointer in `--text` on `--hover-bg`, in both themes ("a
  consistent color, where the active one is clearer ... like our other toggles, not
  gray");
- the narrow panes: a title too long for its row cut short at its end, and every
  metadata item on the line whole or wrapped out of sight with its dot, never cut;
- the title's tooltip, its whole name, shown by the shell's own rule on every page
  exactly while the name is cut short;
- steadiness: as the values change, no box of the header but the line's own items moves
  or changes size: not the header, the eyebrow, the title's row, the title, the line, or
  the tab bar; and the age, last on its line, moves no other item when its label's width
  changes.

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
# One server start, one Chrome, and 24 loads, each with three rewrites of its line: the
# test took 28 s on a 10-core Mac at a load average near 12. A cold Chrome start in CI
# has taken 28.2 s, and the server's start is bounded at 30 s inside the session.
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


# The least of the heading row a title cut short keeps: the whole row less the icon and
# its gap, 169 px in the 260 px pane, measured, since the toggle left the row (mb-70d6).
_TITLE_FLOOR_PX = 160
# The space the heading row's gap leaves between the eyebrow and the toggle.
_TOGGLE_GAP_PX = 8
# Each page's link: the branch origin has, then the item's tree or blob.
_LINKS = {
    "file": "https://github.com/octo/demo/blob/main/docs/notes/a-long-name-for-a-view-header-title.md",
    "folder": "https://github.com/octo/demo/tree/main/docs/notes",
    "root": "https://github.com/octo/demo/tree/main",
}


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
        # The heading row has the header's whole width: the toggle is not in it.
        inset = _px(tokens["--content-padding-x"])
        assert abs(heading["right"] - (page["header"]["right"] - inset)) <= TOLERANCE_PX, name
        assert page["title"]["right"] <= heading["right"] + TOLERANCE_PX, name
        # Up: disabled at the root, a control everywhere else.
        assert page["upDisabled"] is (result["kind"] == "root"), name

        # The GitHub toggle is in the header's corner, a child of the header and not of its
        # heading row, at its inset tokens from the header's top and right edges, whatever
        # the rows under it hold: its height is the eyebrow's, and it is level with the
        # eyebrow, not centered on the title's row as it was. Two segments of the toggle's
        # width at every pane width, in their pill's border, the Metabrowser mark the view
        # the page is in and the GitHub mark a link to the item's page.
        toggle, end = page["toggle"], page["end"]
        assert toggle is not None, f"{name}: no toggle"
        assert page["cornerInHeader"], f"{name}: the toggle is not in the header's corner"
        header = page["header"]
        top, right = (
            _px(tokens["--view-header-toggle-inset-top"]),
            _px(tokens["--view-header-toggle-inset-end"]),
        )
        assert top == _px(tokens["--view-header-padding-top"]), tokens
        assert right == inset, tokens
        assert abs(toggle["top"] - (header["top"] + top)) <= TOLERANCE_PX, f"{name}: {toggle}"
        assert abs(toggle["right"] - (header["right"] - right)) <= TOLERANCE_PX, (
            f"{name}: {toggle} {header}"
        )
        assert abs(toggle["right"] - end["right"]) <= TOLERANCE_PX, f"{name}: {toggle} {end}"
        assert toggle["height"] == _px(tokens["--view-header-toggle-height"]), (
            f"{name}: toggle {toggle}"
        )
        assert toggle["height"] == eyebrow["height"], f"{name}: toggle {toggle}"
        assert abs(toggle["top"] - eyebrow["top"]) <= TOLERANCE_PX, f"{name}: {toggle}"
        option, border = (
            _px(tokens["--view-header-toggle-option-width"]),
            _px(tokens["--chip-border"]),
        )
        assert toggle["width"] == 2 * option + 2 * border, f"{name}: toggle {toggle}"
        assert toggle["width"] == _px(tokens["--view-header-toggle-width"]), name
        # The eyebrow leaves the toggle its room, its width and the heading row's gap.
        room = _px(tokens["--view-header-toggle-room"])
        assert room == toggle["width"] + _TOGGLE_GAP_PX, tokens
        assert _px(page["eyebrowPadEnd"]) == room, f"{name}: {page['eyebrowPadEnd']}"
        assert eyebrow["right"] - room <= toggle["left"] - _TOGGLE_GAP_PX + TOLERANCE_PX, name
        assert "view-header-toggle-metabrowser" in (page["toggleCurrent"] or ""), name
        assert page["toggleHref"] == _LINKS[result["kind"]], f"{name}: {page['toggleHref']}"
        glyph = _px(tokens["--icon-glyph"])
        marks = [mark["height"] for mark in page["marks"]]
        assert marks == [glyph, glyph], f"{name}: marks {marks}"
        # The shared toggles' states, in this theme's tokens: the page's view selected, the
        # other segment at rest, the frame and ground a joined chip group's.
        states = page["states"]
        want = states["want"]
        assert states["here"] == {"ink": want["link"], "fill": want["highlight"]}, (
            f"{name}: selected {states['here']} against {want}"
        )
        assert states["there"] == {"ink": want["muted"], "fill": "rgba(0, 0, 0, 0)"}, (
            f"{name}: at rest {states['there']} against {want}"
        )
        assert states["frame"]["fill"] == want["surface"], f"{name}: {states['frame']}"
        assert states["frame"]["border"] == want["border"], f"{name}: {states['frame']}"
        if result["hovered"] is not None:
            hovered = result["hovered"]
            assert hovered["hovered"], f"{name}: the pointer is not on the GitHub segment"
            assert hovered["ink"] == want["text"], f"{name}: hovered {hovered} against {want}"
            assert hovered["fill"] == want["hover"], f"{name}: hovered {hovered} against {want}"
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
            for key in ("header", "eyebrow", "heading", "title", "end", "toggle", "line", "bar"):
                moved = _moved(page[key], after[key])
                assert moved <= TOLERANCE_PX, f"{name} {step}: {key} moved {moved} px"
        # The age is last: from "just now" to "59m ago" it moves no item before it.
        fresh, hour = result["relabeled"]["fresh"], result["relabeled"]["hour"]
        assert fresh["items"][-1]["text"].endswith("just now"), f"{name}: {fresh['items']}"
        assert hour["items"][-1]["text"].endswith("59m ago"), f"{name}: {hour['items']}"
        for before, after in zip(fresh["items"][:-1], hour["items"][:-1], strict=True):
            moved = _moved(before["box"], after["box"])
            assert moved <= TOLERANCE_PX, f"{name}: {before['text']} moved {moved} px"
