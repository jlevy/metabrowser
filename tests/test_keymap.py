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

from collections import Counter

from metabrowser import server
from metabrowser.file_kinds import VIEW_REGISTRY
from metabrowser.keymap import check_view_keys, reserved_keys_for
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
    assert "view 'main'" in str(check.problems[0])


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
