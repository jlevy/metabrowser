"""View keys stay clear of each other and of the shell's reserved keys.

A view of a multi-view kind declares a one-letter ``key`` in its manifest, and the
file envelope serves it as ``views[].key``. The shell reserves some letters in every
context and others only for some kinds; ``keymap.check_view_keys()`` applies the rule
to one kind's merged view list, and the server and ``metab --doctor`` both call it.

The keymap check below is the build-time gate the Shift key reveal plan asks for: it
reads every kind's views as the server merges them and fails on a duplicate letter or a
reserved one, rather than letting the server drop a key quietly at run time.

The design system's "Keyboard Shortcuts" section is the one reference for the scheme, and
the last checks here hold its table to what the registry, the manifests, and the
built-in plugins bind, so the documentation cannot drift from the keys.
"""

from __future__ import annotations

import json
import re
import string
from collections import Counter
from pathlib import Path

import pytest

from metabrowser import keymap, server
from metabrowser.file_kinds import VIEW_REGISTRY
from metabrowser.keymap import (
    RESERVED_SHELL_KEYS,
    ReservedKey,
    check_view_keys,
    live_view_keys,
    reserved_keys_for,
    serialize_reserved_shell_keys,
)
from metabrowser.plugin_loader.manifest import merge_views
from metabrowser.settings import client_settings_dict


def _served_kinds() -> list[str]:
    return sorted(set(VIEW_REGISTRY) | set(server._PLUGIN_VIEWS_BY_KIND))


def _declared_views(kind: str) -> list[dict[str, object]]:
    """A kind's merged views before the key rule runs, as the server merges them."""
    return merge_views(
        VIEW_REGISTRY.get(kind, []),
        server._PLUGIN_VIEWS_BY_KIND.get(kind, []),
    )


def test_every_kind_keeps_its_view_keys_clear_of_each_other_and_the_shell() -> None:
    for kind in _served_kinds():
        declared = [str(view["key"]) for view in _declared_views(kind) if "key" in view]
        taken = Counter([*reserved_keys_for(kind), *(key.lower() for key in declared)])
        assert [key for key, count in taken.items() if count > 1] == [], kind
        assert check_view_keys(kind, _declared_views(kind)).problems == [], kind

        served = [view.get("key") for view in server._views_for_kind(kind)]
        assert [key for key in served if key is not None] == declared, kind


def test_every_view_of_a_multi_view_kind_declares_a_key() -> None:
    for kind in _served_kinds():
        views = server._views_for_kind(kind)
        if len(views) > 1:
            assert [view["id"] for view in views if not view.get("key")] == [], kind


def test_a_duplicate_view_key_keeps_the_first_view_and_reports_the_second() -> None:
    check = check_view_keys("myk", [{"id": "main", "key": "m"}, {"id": "alt", "key": "M"}])

    assert check.views == [{"id": "main", "key": "m"}, {"id": "alt"}]
    assert [(problem.view_id, problem.key) for problem in check.problems] == [("alt", "M")]
    assert check.problems[0].holder == "main"
    assert "but view 'main' already holds it" in str(check.problems[0])
    assert "but view 'main' (plugin 'alpha') already holds it" in check.problems[0].describe(
        "alpha"
    )


def test_a_key_dropped_for_itself_names_no_holder() -> None:
    [problem] = check_view_keys("text", [{"id": "a", "key": "t"}]).problems

    assert problem.holder is None
    assert problem.describe("alpha") == str(problem)
    assert "plugin" not in str(problem)


def test_a_lone_view_is_served_without_a_key() -> None:
    """A lone view's tab has no other view to switch to, so its key would do nothing."""
    pair = [{"id": "overview", "key": "o"}, {"id": "treemap", "key": "m"}]

    assert live_view_keys(pair) == pair
    assert live_view_keys(pair[:1]) == [{"id": "overview"}]
    assert pair[0] == {"id": "overview", "key": "o"}
    assert live_view_keys([]) == []


def test_next_and_previous_are_reserved_in_every_kind() -> None:
    """``N`` and ``P`` mean next and previous wherever they apply, so no view takes them."""
    for kind in ("html", "pull-request", "markdown"):
        check = check_view_keys(kind, [{"id": "page", "key": "p"}, {"id": "next", "key": "N"}])
        assert check.views == [{"id": "page"}, {"id": "next"}], kind
        assert all("reserved" in str(problem) for problem in check.problems), kind


def test_a_contextual_shell_key_is_reserved_only_for_its_kinds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The table can still reserve a key for some kinds only; none of the shell's is, now."""
    assert all(reserved.kinds is None for reserved in RESERVED_SHELL_KEYS.values())
    table = {"q": ReservedKey("a stand-in", frozenset({"pull-request"}))}
    monkeypatch.setattr(keymap, "RESERVED_SHELL_KEYS", table)

    assert check_view_keys("html", [{"id": "preview", "key": "q"}]).problems == []
    check = check_view_keys("pull-request", [{"id": "page", "key": "q"}])
    assert check.views == [{"id": "page"}]
    assert "reserved" in str(check.problems[0])
    assert keymap.serialize_reserved_shell_keys() == {"q": ["pull-request"]}


def test_a_reserved_or_malformed_key_is_dropped_in_every_kind() -> None:
    views = [{"id": "a", "key": "t"}, {"id": "b", "key": "1"}, {"id": "c", "key": "ab"}]

    check = check_view_keys("text", views)

    assert check.views == [{"id": "a"}, {"id": "b"}, {"id": "c"}]
    assert [problem.view_id for problem in check.problems] == ["a", "b", "c"]


def _golden_shell_keys() -> set[str]:
    """The shell keys the reveal session's transcript prints, across its parts."""
    golden = Path(__file__).parent / "golden" / "cli-ui-key-reveal.tryscript.md"
    printed = re.findall(r'^\s*"shellKeys": (\[[^\]]*\])', golden.read_text(), re.MULTILINE)
    assert len(printed) == 3, "every part of the session prints its shell keys"
    return {key for keys in printed for key in json.loads(keys)}


def test_the_reserved_table_is_the_shell_keys_the_registry_registers() -> None:
    """The table the manifest loader and this check reserve is what the shell really binds.

    ``tests/dom/key-reveal-session.js`` runs the production shell keymap, main tabs, Pulls
    keys, tree keys, and Quick Search, and its golden prints every letter and digit they
    registered outside the view tabs and the modal scopes. Its letters are exactly the
    table's, so a shell key added or dropped on one side fails here; its digits are the
    situational numbers, ``1`` to ``9`` and no more, which the registry hands out by place.
    """
    shell_keys = _golden_shell_keys()
    letters = set(string.ascii_lowercase)
    reserved = set(RESERVED_SHELL_KEYS)
    assert shell_keys & letters == reserved & letters
    assert shell_keys - letters == set("123456789")
    assert shell_keys - letters == reserved - letters


def test_the_shell_serves_the_reserved_table_to_the_browser() -> None:
    """``METABROWSER_SETTINGS`` carries the table, so the plugin facade refuses its letters.

    ``static/plugin-shortcuts.js`` reads ``RESERVED_SHELL_KEYS`` from the settings the
    shell writes before any script runs. Every reserved key is served, each with the kinds
    it is reserved for or None for every kind; every shell key is reserved for every kind.
    """
    served = client_settings_dict()["RESERVED_SHELL_KEYS"]
    assert served == serialize_reserved_shell_keys()
    assert set(served) == set(RESERVED_SHELL_KEYS)
    assert served["n"] is served["p"] is served["t"] is None


def _plugin_session_list(name: str) -> list[str]:
    """One list the plugin shortcut session's transcript prints, by its field name."""
    golden = Path(__file__).parent / "golden" / "cli-ui-plugin-shortcuts.tryscript.md"
    printed = re.findall(rf'^\s*"{name}": (\[[^\]]*\])', golden.read_text(), re.MULTILINE)
    assert len(printed) == 1, f"the transcript prints {name} once"
    return json.loads(printed[0])


def test_the_plugin_facade_refuses_exactly_the_reserved_letters() -> None:
    """The facade refuses the letters this table reserves, contextual ones included.

    ``tests/dom/plugin-shortcuts-session.js`` serves its page a copy of the table and
    prints it, then attaches every letter through the production facade and prints the
    ones it refused. The copy must be the table the server serves, and the refused
    letters must be all of its letters: a plugin view can appear in any kind, so the
    facade cannot leave ``n`` and ``p`` to a pull request page alone.
    """
    printed = _plugin_session_list("reservedKeys")
    served = serialize_reserved_shell_keys()
    assert printed == sorted(
        f"{key}: {'every kind' if kinds is None else ' '.join(kinds)}"
        for key, kinds in served.items()
    )
    letters = set(string.ascii_lowercase)
    assert set(_plugin_session_list("refused")) == set(RESERVED_SHELL_KEYS) & letters


_BUILTIN_PLUGINS = Path(server.__file__).parent / "builtin_plugins"


def _builtin_plugin_letters() -> dict[str, str]:
    """Each letter a built-in plugin gives a control through ``shortcuts.attach()``.

    The pull request page attaches its tabs' letters from ``PULL_TABS`` in
    ``github/pull-page.js``, and the diff view its layout key in ``renderDiffToolbar`` in
    ``diff/diff-view.js``. Each letter maps to where it is declared.
    """
    pull_page = (_BUILTIN_PLUGINS / "github" / "pull-page.js").read_text(encoding="utf-8")
    tabs = re.search(r"\nconst PULL_TABS = Object\.freeze\(\[(.*?)\n\]\);", pull_page, re.S)
    assert tabs, "github/pull-page.js declares PULL_TABS"
    letters = dict.fromkeys(re.findall(r'key: "([^"]*)"', tabs[1]), "github/pull-page.js PULL_TABS")
    diff_view = (_BUILTIN_PLUGINS / "diff" / "diff-view.js").read_text(encoding="utf-8")
    toolbar = diff_view[diff_view.index("\nfunction renderDiffToolbar(") :]
    layout = re.search(r'\n      id: "diff\.layout",\n      key: "([^"]*)",', toolbar)
    assert layout, "diff/diff-view.js renderDiffToolbar attaches diff.layout"
    letters[layout[1]] = "diff/diff-view.js renderDiffToolbar"
    return letters


def test_the_built_in_plugins_keys_are_not_reserved() -> None:
    """The letters the built-in plugins attach are clear of the shell's reserved table.

    The plugin shortcut facade refuses every key in the table it is served, so reserving
    one of these letters later would leave the pull request page's tab key or the diff's
    layout toggle with no key and a console warning, while the browserless sessions,
    which serve a copy of the table, would keep passing. Every ``shortcuts.attach()``
    call in a built-in plugin is one of the two read here, so a new one must join them.
    """
    calls = sorted(
        str(path.relative_to(_BUILTIN_PLUGINS))
        for path in _BUILTIN_PLUGINS.rglob("*.js")
        for _ in re.finditer(r"\bshortcuts\.attach\(", path.read_text(encoding="utf-8"))
    )
    # The pull request page attaches its tabs' letters and numbers its header's controls.
    assert calls == ["diff/diff-view.js", "github/pull-page.js", "github/pull-page.js"]
    letters = _builtin_plugin_letters()
    assert set(letters) == {"c", "g", "e", "l"}
    served = serialize_reserved_shell_keys()
    assert {key: source for key, source in letters.items() if key in served} == {}
    assert not set(letters) & reserved_keys_for("pull-request")


def test_letters_never_collide_on_one_screen() -> None:
    """Within one screen a letter reaches one control.

    A file's tab bar shares the screen with the shell's letters, and a pull request page
    shares it with its own tab letters, the diff's layout key on its Changes tab, and the
    shell's letters. Two keys on one screen never share a letter; screens never shown
    together may, as Charts and Conversation share ``C``.
    """
    shell = {key for key in RESERVED_SHELL_KEYS if key.isalpha()}
    for kind in _served_kinds():
        tabs = [str(view["key"]) for view in server._views_for_kind(kind) if "key" in view]
        on_screen = [*shell, *tabs]
        assert len(on_screen) == len(set(on_screen)), kind
    letters = _builtin_plugin_letters()
    page = [*shell, *letters]
    assert len(page) == len(set(page)), sorted(page)


_DESIGN_SYSTEM = Path(__file__).parents[1] / "docs" / "design-system.md"


def _documented_keymap(text: str | None = None) -> list[tuple[list[str], str]]:
    """The design system's keymap table: each row's keys, lowercase, and its meaning."""
    if text is None:
        text = _DESIGN_SYSTEM.read_text(encoding="utf-8")
    start = text.index("\n## Keyboard Shortcuts\n")
    section = text[start : text.index("\n## ", start + 1)]
    table = section[section.index("### The Keymap") :]
    table = table[: table.index("\n\n", table.index("| Key |"))]
    rows = []
    for line in table.splitlines()[2:]:
        if not line.startswith("| `"):
            continue
        key_cell, meaning = [cell.strip() for cell in line.strip("|").split("|")][:2]
        run = re.fullmatch(r"`(\d)`–`(\d)`", key_cell)
        keys = [f"{run[1]}–{run[2]}"] if run else re.findall(r"`([^`]+)`", key_cell)
        rows.append(([key.lower() for key in keys], meaning))
    return rows


def _manifest_views() -> list[tuple[str, str, str]]:
    """Every built-in manifest view that declares a key, as (kind, label, key)."""
    views = []
    for kind in _served_kinds():
        for view in server._views_for_kind(kind):
            if "key" in view:
                views.append((kind, str(view["label"]), str(view["key"])))
    return views


def test_the_design_system_keymap_is_the_keys_the_app_binds() -> None:
    """The documented table and the bound keys are one set, and each row names its targets.

    Every reserved shell letter, every manifest view key, and every letter a built-in plugin
    attaches has a row; every row's letter is one of those, ``?``, or ``/``; a view's or a
    plugin control's row names its label; and the numbers are one row, ``1`` to ``9``,
    never a fixed digit.
    """
    rows = _documented_keymap()
    documented = {key for keys, _meaning in rows for key in keys if len(key) == 1}
    shell = {key for key in RESERVED_SHELL_KEYS if key.isalpha()}
    views = _manifest_views()
    plugins = _builtin_plugin_letters()
    bound = shell | {key for _kind, _label, key in views} | set(plugins)
    assert documented - {"?", "/"} == bound
    for _kind, label, key in views:
        assert any(key in keys and label in meaning for keys, meaning in rows), (key, label)
    pull_page = (_BUILTIN_PLUGINS / "github" / "pull-page.js").read_text(encoding="utf-8")
    for label, key in re.findall(r'label: "([^"]+)", key: "([a-z])"', pull_page):
        assert any(key in keys and label in meaning for keys, meaning in rows), (key, label)
    assert any("l" in keys and "Diff layout" in meaning for keys, meaning in rows)
    numbered = [keys for keys, _meaning in rows if any(re.search(r"\d", key) for key in keys)]
    assert numbered == [["1–9"]], "the numbers are one positional row"


def _golden_shell_commands() -> list[tuple[str, str, str]]:
    """Each shell letter the reveal session's registry bound, as (key, command, action).

    The session prints the command each shell letter is bound to and that command's own
    Help action, read from the production registry's presentation, so the commands keep
    their identity and their meaning (``shellCommands`` in cli-ui-key-reveal).
    """
    golden = Path(__file__).parent / "golden" / "cli-ui-key-reveal.tryscript.md"
    printed = re.findall(r'^\s*"shellCommands": (\[[^\]]*\])', golden.read_text(), re.MULTILINE)
    assert len(printed) == 3, "every part of the session prints its shell commands"
    entries = {entry for part in printed for entry in json.loads(part)}
    commands = []
    for entry in sorted(entries):
        key, rest = entry.split(" ", 1)
        command, action = rest.split(": ", 1)
        commands.append((key, command, action))
    return commands


def _shell_meaning_problems(
    rows: list[tuple[list[str], str]], commands: list[tuple[str, str, str]]
) -> list[str]:
    """Where the documented meaning of a shell letter is not its bound command's.

    A row with one letter names what its command opens: the command's Help action less a
    leading "Open", so ``F``, bound to ``main-tabs.files`` ("Open Files"), must say
    "Files". A row of two letters is a reusable pair, written "Down or up" or "Next or
    previous": its first letter's commands go to the next item and its second's to the
    previous one, as their actions say.
    """
    problems = []
    for key, command, action in commands:
        held = [(keys, meaning) for keys, meaning in rows if key in keys]
        if len(held) != 1:
            problems.append(f"{key.upper()} ({command}) is in {len(held)} rows, not one")
            continue
        keys, meaning = held[0]
        letters = [letter for letter in keys if letter.isalpha() and len(letter) == 1]
        if len(letters) == 2:
            expected = "Next" if letters.index(key) == 0 else "Previous"
            if not action.startswith(expected):
                problems.append(
                    f"{key.upper()} is {command} ({action}), but its row lists it as the "
                    f"{expected.lower()} key: {meaning!r}"
                )
            if not re.match(r"(Down or up|Next or previous)\b", meaning):
                problems.append(f"{key.upper()}'s pair row is not a direction pair: {meaning!r}")
            continue
        noun = action.removeprefix("Open ")
        if noun.lower() not in meaning.lower():
            problems.append(f"{key.upper()} is {command} ({action}), but its row says {meaning!r}")
    return problems


def test_the_documented_shell_letters_mean_their_commands() -> None:
    """Each shell letter's documented meaning is its bound command's, not only its letter.

    The set check above passes with two meanings swapped, so this one reads which command
    each letter is bound to, from the session that runs the production registry, and holds
    the row to that command's own action.
    """
    commands = _golden_shell_commands()
    assert {key for key, _command, _action in commands} == {
        key for key in RESERVED_SHELL_KEYS if key.isalpha()
    }
    assert _shell_meaning_problems(_documented_keymap(), commands) == []


def test_swapping_two_documented_shell_letters_fails_the_meaning_check() -> None:
    """The check is red for a table that swaps Files and Pulls, or J and K, or N and P."""
    text = _DESIGN_SYSTEM.read_text(encoding="utf-8")
    commands = _golden_shell_commands()
    files_row = "| `F` | The Files tab |"
    pulls_row = "| `R` | The Pulls tab: pull Requests |"
    assert files_row in text and pulls_row in text
    swapped = (
        text.replace(files_row, "\0")
        .replace(pulls_row, "| `F` | The Pulls tab: pull Requests |")
        .replace("\0", "| `R` | The Files tab |")
    )
    problems = _shell_meaning_problems(_documented_keymap(swapped), commands)
    assert any(problem.startswith("F is main-tabs.files") for problem in problems), problems
    assert any(problem.startswith("R is main-tabs.pulls") for problem in problems), problems
    for pair, reversed_pair in (
        ("| `J` or `K` |", "| `K` or `J` |"),
        ("| `N` or `P` |", "| `P` or `N` |"),
    ):
        assert pair in text
        reversed_rows = _documented_keymap(text.replace(pair, reversed_pair))
        assert _shell_meaning_problems(reversed_rows, commands), reversed_pair


def test_the_numbers_stop_at_nine() -> None:
    """The registry's numbering hands out ``1`` to ``9`` and no more: no ``0``, no tenth."""
    registry = (Path(server.__file__).parent / "static" / "keyboard-shortcuts.js").read_text(
        encoding="utf-8"
    )
    assert "const NUMBERED_LIMIT = 9;" in registry
    assert set(RESERVED_SHELL_KEYS) - set(string.ascii_lowercase) == set("123456789")
