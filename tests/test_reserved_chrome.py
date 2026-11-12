"""Chrome whose box is decided at first paint and does not depend on later data.

Geometry is the browser's, so these pin the rules that decide it: the slot a region
keeps while its content is absent, in line units where text sets the height, so the
same rule holds in WebKit, whose font metrics differ from Chrome's. Each region named
here moved the content beside or below it when it appeared or disappeared; the
measurements are in docs/design-system.md and the rules' comments.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
STATIC = REPO_ROOT / "src" / "metabrowser" / "static"


def _css() -> str:
    return (STATIC / "styles.css").read_text(encoding="utf-8")


def _rule(css: str, selector: str) -> str:
    match = re.search(r"(?m)^" + re.escape(selector) + r"\s*\{([^}]*)\}", css)
    assert match is not None, f"selector not found: {selector}"
    return match.group(1)


def _function(source: str, name: str) -> str:
    """A function declared at any depth, up to the closing brace at its own indent."""

    match = re.search(rf"(?m)^( *)(?:async )?function {name}\(", source)
    assert match is not None, name
    end = source.index(f"\n{match.group(1)}}}\n", match.start())
    return source[match.start() : end]


def test_both_panes_keep_their_scrollbar_gutter() -> None:
    """Scrollbars are classic, so a pane that starts overflowing narrowed by 11 px."""

    css = _css()
    assert "*::-webkit-scrollbar {" in css, "scrollbars are no longer classic; revisit this"
    for selector in (".tree-content", ".preview-pane"):
        assert "scrollbar-gutter: stable;" in _rule(css, selector), selector


def test_the_filter_bar_keeps_its_slot_on_every_tab() -> None:
    css = _css()
    assert "visibility: hidden;" in _rule(css, ".nav-filter-bar[inert]")
    assert "display: none" not in _rule(css, ".nav-filter-bar[inert]")
    tabs = (STATIC / "main-tabs.js").read_text(encoding="utf-8")
    activate = _function(tabs, "activateNavPanel")
    assert 'filterBar.inert = panelId !== "files"' in activate


def test_the_shortcut_strip_keeps_one_row_until_it_is_filled() -> None:
    """The strip always holds Help once filled, so before then it holds a row's height."""

    rule = _rule(_css(), ".nav-shortcut-hints[hidden]")
    assert "visibility: hidden;" in rule
    assert "display: none" not in rule
    # A keycap is 1.5 lines of the strip's own type, so the reservation is in line units.
    assert re.search(r"min-height: calc\([^;]*1\.5em\)", rule), rule
    keycap = _rule(_css(), ".kbd")
    assert "line-height: 1.5;" in keycap
    assert "font-size: var(--kbd-font-size);" in keycap
    assert "--kbd-font-size: var(--ui-small-font-size);" in _css()
    assert "font-size: var(--ui-small-font-size);" in _rule(_css(), ".nav-shortcut-hints")


def test_every_file_has_a_view_tab_bar() -> None:
    """A kind with one view, or none, starts its content where a kind with two does."""

    app = (STATIC / "app.js").read_text(encoding="utf-8")
    render = app[app.index("async function renderFile(") :]
    render = render[: render.index('"renderFile:mount"')]
    assert "views.length > 1" not in render, "single-view kinds lost the tab bar"
    assert "html += '<div class=\"tab-bar\">';" in render
    assert '<span class="tab-btn tab-slot">&nbsp;</span>' in render
    slot = _rule(_css(), ".tab-slot")
    # It takes a tab's padding and type from .tab-btn, and a button's line-height.
    assert "visibility: hidden;" in slot
    assert "line-height: normal;" in slot


def test_the_print_button_keeps_its_slot() -> None:
    """Toggling `hidden` on it moved the header's size label 32 px on a view switch."""

    rule = _rule(_css(), ".file-header-print[hidden]")
    assert "visibility: hidden;" in rule
    assert "display: inline-flex;" in rule
    app = (STATIC / "app.js").read_text(encoding="utf-8")
    assert "btn.hidden = !printable;" in _function(app, "updatePrintButton")


def test_a_runs_status_badge_is_as_wide_as_its_widest_label() -> None:
    """Live becomes Run ended in place; the badge sizes to the widest label from the start."""

    css = _css()
    selector = ":is(.badge-running, .badge-live, .badge-completed, .badge-failed)"
    sizer = _rule(css, f"{selector}::after")
    app = (STATIC / "app.js").read_text(encoding="utf-8")
    labels = set(re.findall(r'badge-(?:running|live|completed|failed)">([^<]+)<', app))
    labels |= set(re.findall(r'badge\.textContent = "([^"]+)"', app))
    assert labels == {"Running", "Live", "Done", "Failed", "Run ended"}, labels
    widest = max(labels, key=len)
    assert f'content: "{widest}" / "";' in sizer
    assert "height: 0;" in sizer and "visibility: hidden;" in sizer
    assert "flex-direction: column;" in _rule(css, selector)
