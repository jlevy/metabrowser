"""Every menu closes through the one helper (docs/design-system.md, "Every Menu Closes Alike").

A menu is a surface with the shared floating class ``menu`` (styles.css's ``.menu``). Each
one the shell, its startup page, and its built-in plugins draw is found here by its class
list, and each must be in ``WIRED`` with the file that gives it the closing every menu
has: a ``dismissible({ name: "<surface>", ... })`` call there, through
``metabrowser.menus`` (static/filter-controls.js), whose ``name`` is the surface's own
class. A new menu fails this until it is wired so; a menu that went fails its stale entry.

Its behavior is ``tests/dom/menu-dismissal-session.js``'s and
``tests/test_menu_dismissal_chrome.py``'s. ``metabrowser.menus`` is optional, since a
load whose ``filter-controls.js`` failed has none, and the shell still starts without it.
"""

from __future__ import annotations

import re
from pathlib import Path

from devtools import check_startup_scripts as check
from tests.required_tools import needs_node

PACKAGE = Path(__file__).resolve().parents[1] / "src" / "metabrowser"

# Each menu surface, by its own class beside `menu`, and the file that wires its closing.
WIRED = {
    "chip-menu-panel": "static/filter-controls.js",
    "settings-menu": "static/app.js",
    "root-details-panel": "static/app.js",
    "source-ref-selector-panel": "static/source-ref-selector.js",
    "git-ref-menu": "static/plugin-sdk-views.js",
    "counterpart-menu": "static/plugin-sdk-views.js",
    "github-pull-stack-menu": "builtin_plugins/github/pull-page.js",
    "table-menu": "builtin_plugins/table/table-view.js",
}

# A class list given in markup (`class="..."`) or in code (`class: "..."`, `className =
# "..."`), in any quotes.
_CLASS_LIST = re.compile(r"""\bclass(?:Name)?\s*[=:]\s*(["'`])([^"'`]*)\1""")


def _sources() -> list[Path]:
    """The shell's scripts, its built-in plugins' scripts, and the page server.py writes."""

    scripts = [
        path
        for path in [*PACKAGE.glob("static/*.js"), *PACKAGE.glob("builtin_plugins/**/*.js")]
        if "vendor" not in path.parts
    ]
    return sorted([*scripts, PACKAGE / "server.py"])


def _menu_surfaces() -> dict[str, set[str]]:
    """Each menu surface's own class, and the files that draw it."""

    found: dict[str, set[str]] = {}
    for path in _sources():
        for match in _CLASS_LIST.finditer(path.read_text(encoding="utf-8")):
            classes = match.group(2).split()
            if "menu" not in classes:
                continue
            others = [name for name in classes if name != "menu"]
            assert len(others) == 1, (
                f"{path.relative_to(PACKAGE)}: a menu names its surface with one class beside "
                f"`menu`, which its closing names too: {match.group(0)}"
            )
            found.setdefault(others[0], set()).add(str(path.relative_to(PACKAGE)))
    return found


def test_every_menu_surface_is_wired_to_close_alike() -> None:
    surfaces = _menu_surfaces()
    unwired = sorted(set(surfaces) - set(WIRED))
    assert not unwired, (
        f"menus that do not close as every menu does: {unwired}; wire each through "
        '`metabrowser.menus.dismissible({name: "<surface>", ...})` (docs/plugins.md, '
        '"Menus") and add it to WIRED'
    )
    stale = sorted(set(WIRED) - set(surfaces))
    assert not stale, f"WIRED names menus nothing draws now: {stale}"


def test_each_wiring_file_calls_the_helper_with_its_surface() -> None:
    for surface, wiring in WIRED.items():
        source = (PACKAGE / wiring).read_text(encoding="utf-8")
        call = re.compile(r"\bdismissible\(\{\s*name:\s*\"" + re.escape(surface) + r"\"")
        assert len(call.findall(source)) == 1, (
            f"{wiring} wires {surface} through `dismissible({{ name: {surface!r}, ... }})` once"
        )


def test_the_check_reads_the_shapes_menus_are_drawn_in() -> None:
    # Markup, an object of attributes, and a property, each with the class first or last.
    for text in (
        '<div class="menu root-details-panel" hidden>',
        'el("div", { class: "menu table-menu" })',
        'panel.className = "source-ref-selector-panel menu";',
        '`<span class="menu chip-menu-panel" id="${id}">`',
    ):
        classes = [match.group(2).split() for match in _CLASS_LIST.finditer(text)]
        assert any("menu" in names for names in classes), text
    assert not any(
        "menu" in match.group(2).split()
        for match in _CLASS_LIST.finditer('<div class="menu-separator">')
    )


@needs_node
def test_a_load_whose_filter_controls_failed_still_starts() -> None:
    # The shell holds its tree only until a bound while filter-controls.js has not run
    # (tests/test_files_totals_stable_chrome.py, `failOpen`), and that script is what sets
    # `metabrowser.menus`. A gear that read the helper unguarded threw at
    # DOMContentLoaded, and nothing after it ran: no tree request, no tally.
    html = check.render_folder_shell()
    tag = re.search(r'<script\b[^>]*src="/static/filter-controls\.js[^"]*"[^>]*>\s*</script>', html)
    assert tag, "the folder shell loads filter-controls.js"
    report = check.run_startup_session(html.replace(tag.group(0), ""), check.FOLDER_ADDRESS)
    assert report["errors"] == []
    assert "/api/tree" in report["fetches"]
