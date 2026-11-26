"""No page key handler takes a key held with Command, Control, or Option (mb-i1wy).

Command-R reloads, in a browser and in the macOS app. A browser lets a page's ``keydown``
handler cancel most chords, and the app's web view hands each key to the page before
its menu, so a handler that calls ``preventDefault()`` on a chord keeps that chord from
the browser and from View > Reload Page alike. The shortcut registry matches no chord
but the two a binding declares, Control-N and Control-P, which walk a pull request's
stack and are bound only on macOS and iOS, where no browser and no menu of the app uses
them (mb-lnqj; ``CONTROL_CHORD_KEYS``, ``controlReachesPage``, and
``DISQUALIFYING_MODIFIERS`` in ``static/keyboard-shortcuts.js``). Every other listener leaves chords alone: the tree
map, the filter bar's groups and menus, the branch switcher, and the pull request page's
stack menu each moved on Command-Up or Command-Left as on the plain arrow, and the
overlay's focus trap took Command-Tab and Control-Tab.

The other exception is Option-Tab in a modal's or a menu's focus trap: Safari moves focus
with it, so a trap that let it pass would let focus leave the dialog.

Every ``keydown`` listener in the browser code is listed below, by file and in source
order, with the guard that leaves chords alone, found in that listener's own source or in
the functions it hands the event to, and the browserless checks that press chords through
it. A listener with no guard must never cancel a key: no ``preventDefault`` in its source
or theirs. ``tests/dom/key-reveal-session.js modified`` presses every key with each chord
wherever the shell puts focus, through the production registry, Quick Search, Help, the
tree, and the filter bar, and on a pull request in a stack, where Control-N and
Control-P are the only chords taken and Quick Search's field keeps them. A listener added
without a row fails here, naming its file.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from metabrowser import server

_PACKAGE = Path(server.__file__).parent
_REPO = Path(__file__).resolve().parents[1]
_SESSION = "tests/dom/key-reveal-session.js"
# A listener registered by name, or through a list of event types it loops over.
_KEYDOWN_LISTENER = re.compile(
    r'addEventListener(?:\?\.)?\(\s*"keydown"|\[[^\]\[]*"keydown"[^\]\[]*\]'
)
_ADD_LISTENER = re.compile(r"addEventListener(?:\?\.)?\(")
_GUARD = "if (event.altKey || event.ctrlKey || event.metaKey) { return; }"


@dataclass(frozen=True)
class Listener:
    """One ``keydown`` listener, and what leaves chords alone in it."""

    what: str
    # Code that leaves chords to the browser, compared without whitespace, in the
    # listener's own source or, with `via`, in the last function it hands the event to.
    # None for a listener that never cancels a key.
    guard: str | None
    # The functions the listener hands the event to, in order: each is named in the
    # source before it.
    via: tuple[str, ...] = ()
    # The browserless checks that press chords through it; none where no check mounts it.
    checks: tuple[str, ...] = ()
    # Why its source is its only check, where no browserless check mounts it.
    unmounted: str = ""
    # Whether it may cancel a key; one that never does is checked for `preventDefault`.
    cancels: bool = True


_LISTENERS: dict[str, tuple[Listener, ...]] = {
    "static/keyboard-shortcuts.js": (
        Listener(
            "the registry's one document listener, which takes Control-N and Control-P alone",
            "if (DISQUALIFYING_MODIFIERS.some((field) => event[field])) { return false; }",
            via=("handleKeydown", "dispatch", "eventMatchesBinding"),
            checks=("tests/dom/keyboard-shortcuts-behavior.js", _SESSION),
        ),
    ),
    "static/filter-controls.js": (
        Listener(
            "a segmented group's arrows and a menu's rows",
            'typeof target.closest !== "function" || ev.altKey || ev.ctrlKey || ev.metaKey',
            via=("onKeyDown",),
            checks=("tests/dom/filter-controls-behavior.js", _SESSION),
        ),
    ),
    "static/menus.js": (
        Listener(
            "Escape closing the menu opened last, every menu's",
            "!(key.defaultPrevented || key.altKey || key.ctrlKey || key.metaKey)",
            via=("onKey",),
            checks=("tests/dom/menu-dismissal-session.js", _SESSION),
        ),
    ),
    "static/overlay-layer.js": (
        Listener(
            "a modal's Tab focus trap, which keeps Option-Tab",
            'event.key !== "Tab" || event.ctrlKey || event.metaKey',
            via=("handleDialogKeydown",),
            checks=("tests/dom/overlay-layer-behavior.js", _SESSION),
        ),
    ),
    "static/source-ref-selector.js": (
        Listener(
            "the open list's Tab trap, which keeps Option-Tab",
            'parts.panel.hidden || event.ctrlKey || event.metaKey || (event.altKey && event.key !== "Tab")',
            checks=("tests/dom/source-ref-selector-keys-session.js",),
        ),
        Listener(
            "the list's arrows, Home, and End",
            _GUARD,
            checks=("tests/dom/source-ref-selector-keys-session.js",),
        ),
    ),
    "static/app.js": (
        Listener(
            "the reader's key ending a tooltip's focus repair, which only notes it",
            None,
            via=("endTooltipFocusRepair",),
        ),
    ),
    "static/git-panel.js": (
        Listener(
            "a commit row's J, K, and arrows",
            "!event.altKey && !event.ctrlKey && !event.metaKey",
            via=("handleCommitRowKeydown",),
            unmounted="the commit row's own guard, which this PR did not change",
        ),
    ),
    "static/plugin-sdk-views.js": (
        Listener(
            "a source view's line gutter",
            _GUARD,
            via=("handleGutterKey",),
            unmounted="the gutter's own guard, which this PR did not change",
        ),
        Listener(
            "the ref menu's navigation; Tab and Option-Tab leave it",
            _GUARD,
            checks=("tests/dom/checkout-ref-selector-chrome.mjs",),
        ),
        Listener(
            "ArrowDown and ArrowUp opening a ref's action menu",
            _GUARD,
            checks=("tests/dom/checkout-ref-selector-chrome.mjs",),
        ),
        Listener(
            "the View on GitHub chevron's ArrowDown and ArrowUp, which open its menu",
            _GUARD,
            checks=("tests/dom/counterpart-session.js",),
        ),
        Listener(
            "the View on GitHub menu's arrows, Home, and End, and Tab and Option-Tab "
            "closing it, which cancel nothing",
            _GUARD,
            checks=("tests/dom/counterpart-session.js",),
        ),
    ),
    "static/plugin-sdk.js": (Listener("the idle-work input clock", None),),
    "static/perf.js": (
        Listener(
            "the interaction probe, which only counts inputs", None, via=("recordInteractionInput",)
        ),
    ),
    "builtin_plugins/agents/agent-log.js": (
        Listener(
            "an event row's Enter and Space toggle",
            "const plain = !(event.altKey || event.ctrlKey || event.metaKey || event.shiftKey);",
            via=("toggleFromKey",),
            unmounted="the row's own guard, which this PR did not change",
        ),
    ),
    "builtin_plugins/folder/treemap-map.js": (
        Listener(
            "the tree map's cells, in the Treemap view",
            "if (e.altKey || e.ctrlKey || e.metaKey) { return; }",
            via=("onKeyDown",),
            checks=("tests/dom/folder-plugin-behavior.js",),
        ),
    ),
    "builtin_plugins/diff/diff-view.js": (
        Listener("a Diff | Current choice's held row, released", None, via=("releaseHold",)),
        Listener("a file jump's pin release", None, via=("release",)),
    ),
    "builtin_plugins/diff/diff-summary.js": (
        Listener(
            "the Diff summary tree's arrows, Home, End, Enter, and Space",
            _GUARD,
            checks=("tests/dom/diff-view-behavior.js",),
        ),
    ),
    "builtin_plugins/github/pulls-panel.js": (Listener("the reader's last input time", None),),
    "builtin_plugins/table/table-view.js": (
        Listener(
            "a table's rows and cells, and Escape in a record",
            _GUARD,
            via=("onKeyDown",),
            checks=("tests/dom/table-view-session.js",),
        ),
        Listener("Enter in a table's Search, which asks at once", None, via=("onSearchKey",)),
    ),
    "builtin_plugins/github/pull-page.js": (
        Listener(
            "the stack menu's trigger and rows",
            _GUARD,
            checks=("tests/dom/github-pull-stack-mount-behavior.js",),
        ),
        Listener("the files pane's scroll keeper, which only notes a key", None),
    ),
    "builtin_plugins/github/stack-page.js": (
        Listener("a stack's page noting the reader's first key, which only notes it", None),
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


def _squeezed(text: str) -> str:
    """``text`` without whitespace, so the formatter's line breaks do not matter."""
    return re.sub(r"\s+", "", text)


_CLOSERS = {"(": ")", "{": "}", "[": "]"}


def _close(text: str, start: int) -> int:
    """The index of the bracket that closes the one at ``start``.

    Strings, template literals, and comments are skipped; the sources this reads keep
    no bracket in a regular expression literal inside a listener.
    """
    stack = []
    index = start
    while index < len(text):
        char = text[index]
        if char in "\"'`":
            index += 1
            while text[index] != char:
                index += 2 if text[index] == "\\" else 1
        elif text.startswith("//", index):
            index = text.index("\n", index)
        elif text.startswith("/*", index):
            index = text.index("*/", index) + 1
        elif char in _CLOSERS:
            stack.append(_CLOSERS[char])
        elif char in _CLOSERS.values():
            assert stack.pop() == char, f"unbalanced {char!r} at {index}"
            if not stack:
                return index
        index += 1
    raise AssertionError(f"no bracket closes the one at {start}")


def _listener_spans(text: str) -> list[str]:
    """Each ``keydown`` listener's own source, in order: its ``addEventListener`` call, and
    for a list of event types, the list and the call that follows it."""
    spans = []
    for match in _KEYDOWN_LISTENER.finditer(text):
        call = _ADD_LISTENER.search(text, match.start())
        assert call is not None, f"no addEventListener after {match.group()!r}"
        spans.append(text[match.start() : _close(text, call.end() - 1) + 1])
    return spans


def _definition(text: str, name: str) -> str:
    """The source of the one function ``name`` names: a declaration or an arrow."""
    found = list(re.finditer(rf"\bfunction {name}\(|\b(?:const|let|var) {name} = \(", text))
    assert len(found) == 1, f"{name} is defined {len(found)} times"
    parameters = found[0].end() - 1
    body = text.index("{", _close(text, parameters))
    return text[found[0].start() : _close(text, body) + 1]


def _chains() -> list[tuple[str, Listener, list[str]]]:
    """Each row with its listener's source, then the source of each function in ``via``."""
    sources = _browser_sources()
    chains = []
    for path, listeners in _LISTENERS.items():
        text = sources[path]
        for span, listener in zip(_listener_spans(text), listeners, strict=True):
            chain = [span, *(_definition(text, name) for name in listener.via)]
            chains.append((path, listener, chain))
    return chains


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


def test_each_listener_hands_the_event_to_the_functions_its_row_names() -> None:
    broken = [
        f"{path}: {listener.what}: {name} is not named before it"
        for path, listener, chain in _chains()
        for name, source in zip(listener.via, chain, strict=False)
        if not re.search(rf"\b{name}\b", source)
    ]
    assert broken == []


def test_each_listener_leaves_chords_to_the_browser_in_its_own_source() -> None:
    """The guard is in the listener the row names, or in the last function it hands the
    event to, and a listener without one cancels no key."""
    problems = []
    for path, listener, chain in _chains():
        if listener.guard is not None and _squeezed(listener.guard) not in _squeezed(chain[-1]):
            problems.append(f"{path}: {listener.what}: no guard")
        cancels = any("preventDefault" in source for source in chain)
        if (listener.guard is None or not listener.cancels) and cancels:
            problems.append(f"{path}: {listener.what}: cancels a key")
    assert problems == []


def test_a_guard_outside_its_listener_does_not_count() -> None:
    """The guard is read from the listener's own source: one elsewhere in the file fails."""
    text = (
        'el.addEventListener("keydown", (event) => event.preventDefault());\n'
        "function other(event) {\n"
        "  if (event.altKey || event.ctrlKey || event.metaKey) { return; }\n"
        "}\n"
    )
    [span] = _listener_spans(text)
    assert _squeezed(_GUARD) in _squeezed(text)
    assert _squeezed(_GUARD) not in _squeezed(span)
    loop = 'for (const type of ["pointerdown", "keydown"]) {\n  x.addEventListener?.(type, f, true);\n}'
    assert _listener_spans(loop) == [
        '["pointerdown", "keydown"]) {\n  x.addEventListener?.(type, f, true)'
    ]


def test_every_listener_has_a_check_or_says_why_its_source_is_enough() -> None:
    rows = [listener for listeners in _LISTENERS.values() for listener in listeners]
    assert [
        row.what for row in rows if row.guard is not None and not row.checks and not row.unmounted
    ] == []
    checks = {check for row in rows for check in row.checks}
    assert [check for check in sorted(checks) if not (_REPO / check).is_file()] == []
    # The session part that presses every chord wherever the shell puts focus.
    assert "async modified() {" in (_REPO / _SESSION).read_text(encoding="utf-8")


def test_the_registry_takes_control_only_with_n_or_p_and_never_from_a_text_field() -> None:
    """The registry's one chord is Control with N or P, and Control alone (mb-lnqj).

    AltGr reports Control and Alt, so a chord that let Alt through would take a character
    from the keyboards that type it with AltGr; Control-Command is another chord; and a
    text field keeps Control-N and Control-P, which move its caret on macOS. The behavior
    is pressed in ``tests/dom/keyboard-shortcuts-behavior.js`` and the sessions; this
    holds the guard to the matcher the registry's listener hands each key to.
    """
    text = _browser_sources()["static/keyboard-shortcuts.js"]
    matcher = _squeezed(_definition(text, "eventMatchesBinding"))
    for guard in (
        "event.ctrlKey && !event.altKey && !event.metaKey",
        "!matchOptions.physical",
        "!isEditableTarget(event.target)",
    ):
        assert _squeezed(guard) in matcher, guard


def test_the_app_menus_leave_control_n_and_control_p_to_the_page() -> None:
    """No macOS app menu item is Control with N or P, so the page's two chords are free.

    The design system says the app's menus give those chords no command; a menu item that
    took one would never fire, since the web view hands the page each key first.

    A key equivalent is Command unless its item's modifier mask says otherwise, and the app
    sets a mask in one place, ``MainMenu.item``, which the main menu and the folder
    chooser call, so every Control equivalent is a key passed with its modifiers beside it.
    Those pairs are read from every app source, with the source's whitespace removed, so an
    item written over several lines is read too, and in either case, since AppKit reads
    ``"N"`` as Shift-N and the page takes Control-Shift-N as Control-N.
    """
    sources = _REPO / "apps" / "macos" / "Sources"
    masks = [
        (path.name, line.strip())
        for path in sorted(sources.rglob("*.swift"))
        for line in path.read_text(encoding="utf-8").splitlines()
        if "keyEquivalentModifierMask" in line
    ]
    assert masks == [("MainMenu.swift", "menuItem.keyEquivalentModifierMask = modifiers")], (
        "a modifier mask set outside MainMenu.item is a Control equivalent this cannot read"
    )
    menu = "".join(
        _squeezed(path.read_text(encoding="utf-8")) for path in sorted(sources.rglob("*.swift"))
    )
    # Each one-character key with the modifiers after it: an `item(` call's arguments, or a
    # row of the Find menu's table.
    equivalents = re.findall(r'"([^"\\])",(\[[^\]]*\]|[\w.]+)', menu)
    with_control = [(key, modifiers) for key, modifiers in equivalents if ".control" in modifiers]
    assert with_control, "the menu still names Control somewhere, so this reads it"
    assert [pair for pair in with_control if pair[0].lower() in ("n", "p")] == []


def test_the_keyboard_shortcuts_reference_documents_command_r() -> None:
    """The user reference says Command-R reloads, and the design system says why it can."""
    text = (_REPO / "docs" / "design-system.md").read_text(encoding="utf-8")
    start = text.index("\n## Keyboard Shortcuts\n")
    section = text[start : text.index("\n## ", start + 1)]
    browser_keys = section[section.index("\n### Browser and App Keys\n") :]
    assert "Command-R always reloads, whatever has focus" in browser_keys
    assert "`tests/test_modified_keys.py`" in browser_keys
    guide = (_REPO / "docs" / "keyboard-shortcuts.md").read_text(encoding="utf-8")
    guide_keys = guide[guide.index("\n## Browser and App Keys\n") :]
    assert "Command-R (Control-R or F5 elsewhere) always reloads" in guide_keys
    app = (_REPO / "docs" / "project" / "architecture" / "arch-macos-app.md").read_text(
        encoding="utf-8"
    )
    assert "- **Reload.** Command-R reloads in every state a folder window can be in" in app


def test_a_handler_that_cancels_a_chord_is_named() -> None:
    """The count check is red for an unlisted listener, and names its file."""
    text = 'el.addEventListener(\n  "keydown",\n  (e) => e.preventDefault(),\n);'
    assert len(_KEYDOWN_LISTENER.findall(text)) == 1
    assert len(_KEYDOWN_LISTENER.findall('for (const type of ["pointerdown", "keydown"]) {')) == 1
    assert _KEYDOWN_LISTENER.findall('el.removeEventListener("keydown", handler);') == []
