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
    RESERVED_SHELL_KEYS,
    check_view_keys,
    live_view_keys,
    reserved_keys_for,
)
from metabrowser.plugin_loader.manifest import merge_views


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
    """One view draws no tab, so its key would name a shortcut with nothing to select."""
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
