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
- the narrow panes: a title too long for its row cut short at its end, and every
  metadata item on the line whole or wrapped out of sight with its dot, never cut;
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
# The type scale's tokens (static/styles.css), as Chrome computes them.
_PAGE_TITLE_PX = "24px"
_BODY_PX = "14px"
# The view header's rhythm tokens (static/styles.css, `--view-header-*`).
_ROW_GAP_PX = 4
_EYEBROW_PX = 22
_LINE_PX = 22


def _served(root: Path) -> Path:
    notes = root / "docs" / "notes"
    notes.mkdir(parents=True)
    (notes / "a-long-name-for-a-view-header-title.md").write_text(
        "# A note\n\nWith some text.\n", encoding="utf-8"
    )
    (notes / "b.txt").write_text("b\n" * 4000, encoding="utf-8")
    (root / "README.md").write_text("# Served\n", encoding="utf-8")
    when = time.time() - _AGE_S
    for path in [root, *root.rglob("*")]:
        os.utime(path, (when, when))
    return root


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
    run = run_in_own_group(
        [require_node(), str(SESSION), str(_METAB), str(root), str(_free_port()), str(state)],
        timeout_s=SESSION_TIMEOUT_S,
        env={**os.environ, "CHROME_BIN": chrome, "CHROME_PROFILES": str(chrome_profile)},
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

        # The rows, one gap apart, each its token's height, and the tab bar under them.
        eyebrow, heading, line, bar = page["eyebrow"], page["heading"], page["line"], page["bar"]
        assert eyebrow["height"] == _EYEBROW_PX, f"{name}: eyebrow {eyebrow}"
        assert line["height"] == _LINE_PX, f"{name}: line {line}"
        assert abs(heading["top"] - eyebrow["bottom"] - _ROW_GAP_PX) <= TOLERANCE_PX, name
        assert abs(line["top"] - heading["bottom"] - _ROW_GAP_PX) <= TOLERANCE_PX, name
        assert abs(bar["top"] - page["header"]["bottom"]) <= TOLERANCE_PX, name
        # The line starts on the eyebrow's inset, as the title's row does.
        assert abs(line["left"] - eyebrow["left"]) <= TOLERANCE_PX, name
        assert abs(heading["left"] - eyebrow["left"]) <= TOLERANCE_PX, name
        # The icon at the title's size, before the title.
        assert page["iconGlyph"]["width"] == 24, f"{name}: icon {page['iconGlyph']}"
        assert page["icon"]["right"] <= page["title"]["left"], name

        # The type.
        assert page["type"]["title"] == _PAGE_TITLE_PX, f"{name}: title {page['type']}"
        assert int(page["type"]["titleWeight"]) >= 600, f"{name}: title {page['type']}"
        assert page["type"]["line"] == _BODY_PX, f"{name}: line {page['type']}"
        assert page["type"]["eyebrow"] == _BODY_PX, f"{name}: eyebrow {page['type']}"

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
        assert page["title"]["right"] <= page["end"]["left"] + TOLERANCE_PX, name
        # Up: disabled at the root, a control everywhere else.
        assert page["upDisabled"] is (result["kind"] == "root"), name

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
            for key in ("header", "eyebrow", "heading", "title", "end", "line", "bar"):
                moved = _moved(page[key], after[key])
                assert moved <= TOLERANCE_PX, f"{name} {step}: {key} moved {moved} px"
        # The age is last: from "just now" to "59m ago" it moves no item before it.
        fresh, hour = result["relabeled"]["fresh"], result["relabeled"]["hour"]
        assert fresh["items"][-1]["text"].endswith("just now"), f"{name}: {fresh['items']}"
        assert hour["items"][-1]["text"].endswith("59m ago"), f"{name}: {hour['items']}"
        for before, after in zip(fresh["items"][:-1], hour["items"][:-1], strict=True):
            moved = _moved(before["box"], after["box"])
            assert moved <= TOLERANCE_PX, f"{name}: {before['text']} moved {moved} px"
