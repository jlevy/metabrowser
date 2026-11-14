"""No page key handler takes a key held with Command, Control, or Option (mb-i1wy).

Command-R reloads, in a browser and in the macOS app. A browser lets a page's ``keydown``
handler cancel most chords, and the app's web view hands each key to the page before
its menu, so a handler that calls ``preventDefault()`` on a chord keeps that chord from
the browser and from View > Reload Page alike. The shortcut registry never matches a
chord (``DISQUALIFYING_MODIFIERS`` in ``static/keyboard-shortcuts.js``), and every other
listener leaves chords alone: the tree map, the filter bar's groups and menus, and the
pull request page's stack menu each moved on Command-Up or Command-Left as on the plain
arrow, and the overlay's focus trap took Command-Tab and Control-Tab.

The one exception is Option-Tab in a modal's or a menu's focus trap: Safari moves focus
with it, so a trap that let it pass would let focus leave the dialog.

Every ``keydown`` listener in the browser code is listed below, by file, with what keeps
chords from it and the browserless check that presses chords through it, where one
mounts it. ``tests/dom/key-reveal-session.js modified`` presses every key with each chord
wherever the shell puts focus, through the production registry, Quick Search, Help, the
tree, and the filter bar. A listener added without a row fails here, naming its file.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from metabrowser import server

_PACKAGE = Path(server.__file__).parent
_REPO = _PACKAGE.parents[1]
_SESSION = "tests/dom/key-reveal-session.js"
# A listener registered by name, or through a list of event types it loops over.
_KEYDOWN_LISTENER = re.compile(r'addEventListener\(\s*"keydown"|\[[^\]\[]*"keydown"[^\]\[]*\]')


@dataclass(frozen=True)
class Listener:
    """One ``keydown`` listener: what keeps chords from it, as its source says it."""

    what: str
    # Text in the file that leaves chords to the browser, compared without whitespace:
    # the guard, or the options or body of a listener that never cancels a key.
    source: str
    # The browserless checks that press chords through it; none where no check mounts it.
    checks: tuple[str, ...] = ()


_LISTENERS: dict[str, tuple[Listener, ...]] = {
    "static/keyboard-shortcuts.js": (
        Listener(
            "the registry's one document listener",
            'const DISQUALIFYING_MODIFIERS = Object.freeze(["altKey", "ctrlKey", "metaKey"]);',
            ("tests/dom/keyboard-shortcuts-behavior.js", _SESSION),
        ),
    ),
    "static/filter-controls.js": (
        Listener(
            "a segmented group's arrows and a menu's rows",
            'typeof target.closest !== "function" || ev.altKey || ev.ctrlKey || ev.metaKey',
            ("tests/dom/filter-controls-behavior.js", _SESSION),
        ),
        Listener(
            "Escape closing an open menu",
            'ev.key !== "Escape" || ev.altKey || ev.ctrlKey || ev.metaKey',
            (_SESSION,),
        ),
    ),
    "static/overlay-layer.js": (
        Listener(
            "a modal's Tab focus trap, which keeps Option-Tab",
            'event.key !== "Tab" || event.ctrlKey || event.metaKey',
            ("tests/dom/overlay-layer-behavior.js", _SESSION),
        ),
    ),
    "static/source-ref-selector.js": (
        Listener(
            "the open list's Escape and Tab trap, which keeps Option-Tab",
            'event.ctrlKey || event.metaKey || (event.altKey && event.key !== "Tab")',
        ),
        Listener(
            "the list's arrows, Home, and End",
            "// Command-Up in the filter moves its caret, and Command-Left goes back.\n"
            "        if (event.altKey || event.ctrlKey || event.metaKey) {",
        ),
    ),
    "static/app.js": (
        Listener(
            "Escape closing the settings menu",
            'e.key === "Escape" && !(e.altKey || e.ctrlKey || e.metaKey) && isOpen()',
        ),
    ),
    "static/git-panel.js": (
        Listener(
            "a commit row's J, K, and arrows",
            "!event.altKey &&\n      !event.ctrlKey &&\n      !event.metaKey",
        ),
    ),
    "static/plugin-sdk-views.js": (
        Listener(
            "a source view's line gutter",
            "function handleGutterKey(view, event) {\n"
            "    if (event.altKey || event.ctrlKey || event.metaKey) {",
        ),
    ),
    "static/plugin-sdk.js": (
        Listener(
            "the idle-work input clock, passive",
            "global.addEventListener?.(type, () => (_lastInput = performance.now()), {\n"
            "        capture: true,\n"
            "        passive: true,",
        ),
    ),
    "static/perf.js": (
        Listener(
            "the interaction probe, which only counts inputs",
            'document.addEventListener("keydown", recordInteractionInput, true);',
        ),
    ),
    "builtin_plugins/agent_log/index.js": (
        Listener(
            "an event row's Enter and Space toggle",
            "const plain = !(event.altKey || event.ctrlKey || event.metaKey || event.shiftKey);",
        ),
    ),
    "builtin_plugins/folder/treemap.js": (
        Listener(
            "the tree map's cells",
            "if (e.altKey || e.ctrlKey || e.metaKey) {\n        return;\n      }\n      const key = e.key;",
            ("tests/dom/folder-plugin-behavior.js",),
        ),
    ),
    "builtin_plugins/diff/diff-view.js": (
        Listener(
            "a file jump's pin release, passive",
            "const options = { capture: true, passive: true, signal: listening.signal };",
        ),
    ),
    "builtin_plugins/github/pulls-panel.js": (
        Listener(
            "the reader's last input time",
            "        lastInputAt = Date.now();\n      },\n      { capture: true, signal },",
        ),
    ),
    "builtin_plugins/github/pull-page.js": (
        Listener(
            "the stack menu's trigger and rows",
            "reloads, Command-Left goes back, and Command-Down scrolls to the end.\n"
            "      if (event.altKey || event.ctrlKey || event.metaKey) {",
            ("tests/dom/github-pull-stack-mount-behavior.js",),
        ),
        Listener(
            "Escape closing the open stack menu",
            'root.open && event.key === "Escape" && !(event.altKey || event.ctrlKey || event.metaKey)',
            ("tests/dom/github-pull-stack-mount-behavior.js",),
        ),
        Listener(
            "the files pane's scroll keeper, which only notes a key",
            "if (keyMovesPane(event.key, target)) {\n        keeper.readerMoved();",
        ),
    ),
}


def _browser_sources() -> dict[str, str]:
    """Every first-party browser script, by its path under the package."""
    sources = {}
    for root in ("static", "builtin_plugins"):
        for path in sorted((_PACKAGE / root).rglob("*.js")):
            relative = path.relative_to(_PACKAGE).as_posix()
            if "/vendor/" not in f"/{relative}":
                sources[relative] = path.read_text(encoding="utf-8")
    return sources


def test_every_keydown_listener_is_listed() -> None:
    """A listener added, moved, or removed changes a file's count and fails here."""
    found = {
        path: count
        for path, text in _browser_sources().items()
        if (count := len(_KEYDOWN_LISTENER.findall(text))) > 0
    }
    listed = {path: len(listeners) for path, listeners in _LISTENERS.items()}
    unlisted = {
        path: f"{found.get(path, 0)} found, {listed.get(path, 0)} listed"
        for path in sorted(found.keys() | listed.keys())
        if found.get(path, 0) != listed.get(path, 0)
    }
    assert unlisted == {}, "each keydown listener needs a row saying what leaves chords alone"


def _squeezed(text: str) -> str:
    """``text`` without whitespace, so the formatter's line breaks do not matter."""
    return re.sub(r"\s+", "", text)


def test_each_listener_leaves_chords_to_the_browser_as_its_row_says() -> None:
    sources = {path: _squeezed(text) for path, text in _browser_sources().items()}
    missing = [
        f"{path}: {listener.what}"
        for path, listeners in _LISTENERS.items()
        for listener in listeners
        if _squeezed(listener.source) not in sources[path]
    ]
    assert missing == []


def test_the_named_checks_exist() -> None:
    checks = {
        check
        for listeners in _LISTENERS.values()
        for listener in listeners
        for check in listener.checks
    }
    assert [check for check in sorted(checks) if not (_REPO / check).is_file()] == []
    # The session part that presses every chord wherever the shell puts focus.
    assert "async modified() {" in (_REPO / _SESSION).read_text(encoding="utf-8")


def test_the_keyboard_shortcuts_reference_documents_command_r() -> None:
    """The design system's one keyboard reference says Command-R reloads, and why it can."""
    text = (_REPO / "docs" / "design-system.md").read_text(encoding="utf-8")
    start = text.index("\n## Keyboard Shortcuts\n")
    section = text[start : text.index("\n## ", start + 1)]
    browser_keys = section[section.index("\n### Browser and App Keys\n") :]
    assert "| Command-R (Control-R or F5 elsewhere) | Reload |" in browser_keys
    assert "`tests/test_modified_keys.py`" in browser_keys
    readme = (_REPO / "apps" / "macos" / "README.md").read_text(encoding="utf-8")
    assert "- **Reload:** Command-R, View > Reload Page, reloads in every state" in readme


def test_a_handler_that_cancels_a_chord_is_named() -> None:
    """The count check is red for an unlisted listener, and names its file."""
    text = 'el.addEventListener(\n  "keydown",\n  (e) => e.preventDefault(),\n);'
    assert len(_KEYDOWN_LISTENER.findall(text)) == 1
    assert len(_KEYDOWN_LISTENER.findall('for (const type of ["pointerdown", "keydown"]) {')) == 1
    assert _KEYDOWN_LISTENER.findall('el.removeEventListener("keydown", handler);') == []
