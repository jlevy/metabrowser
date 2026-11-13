"""View keys stay clear of each other and of the shell's reserved keys.

A view of a multi-view kind declares a one-letter ``key`` in its manifest, and the
file envelope serves it as ``views[].key``. The shell reserves some letters in every
context and others only for some kinds; ``keymap.check_view_keys()`` applies the rule
to one kind's merged view list, and the server and ``metab --doctor`` both call it.

The keymap check below is the build-time gate the Shift key reveal plan asks for: it
reads every kind's views as the server merges them and fails on a duplicate letter or a
reserved one, rather than letting the server drop a key quietly at run time.
"""

from __future__ import annotations

import json
import re
import string
from collections import Counter
from pathlib import Path

from metabrowser import server
from metabrowser.file_kinds import VIEW_REGISTRY
from metabrowser.keymap import (
    PULL_REQUEST_KIND,
    RESERVED_SHELL_KEYS,
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


def test_a_contextual_shell_key_is_reserved_only_for_its_kinds() -> None:
    assert check_view_keys("html", [{"id": "preview", "key": "p"}]).problems == []

    check = check_view_keys("pull-request", [{"id": "page", "key": "p"}])

    assert check.views == [{"id": "page"}]
    assert [problem.view_id for problem in check.problems] == ["page"]
    assert "reserved" in str(check.problems[0])


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
    navigation tabs' fixed digits, which the table reserves with the gaps a future tab
    takes.
    """
    shell_keys = _golden_shell_keys()
    letters = set(string.ascii_lowercase)
    reserved = set(RESERVED_SHELL_KEYS)
    assert shell_keys & letters == reserved & letters
    assert shell_keys - letters == {"1", "2", "3"}
    assert shell_keys - letters <= reserved - letters


def test_the_shell_serves_the_reserved_table_to_the_browser() -> None:
    """``METABROWSER_SETTINGS`` carries the table, so the plugin facade refuses its letters.

    ``static/plugin-shortcuts.js`` reads ``RESERVED_SHELL_KEYS`` from the settings the
    shell writes before any script runs. Every reserved key is served, each with the kinds
    it is reserved for or None for every kind, so the contextual ``n`` and ``p`` arrive
    with their kind although the facade refuses them everywhere.
    """
    served = client_settings_dict()["RESERVED_SHELL_KEYS"]
    assert served == serialize_reserved_shell_keys()
    assert set(served) == set(RESERVED_SHELL_KEYS)
    assert served["n"] == served["p"] == [PULL_REQUEST_KIND]
    assert served["t"] is None


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
    assert calls == ["diff/diff-view.js", "github/pull-page.js"]
    letters = _builtin_plugin_letters()
    assert set(letters) == {"c", "g", "h", "l"}
    served = serialize_reserved_shell_keys()
    assert {key: source for key, source in letters.items() if key in served} == {}
    assert not set(letters) & reserved_keys_for(PULL_REQUEST_KIND)
