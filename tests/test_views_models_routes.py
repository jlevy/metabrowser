"""The views/models/routes map is checked against the code it describes.

``docs/project/architecture/arch-views-models-routes.md`` is the index of
what the browser shows, from what, and at what address. A table there
that no longer matches the manifests or the route table is worse than no
table, so this test fails the build instead of letting it drift.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from devtools import check_parity

REPO_ROOT = Path(__file__).resolve().parent.parent
MAP_DOC = REPO_ROOT / "docs/project/architecture/arch-views-models-routes.md"
BUILTIN_PLUGINS = REPO_ROOT / "src/metabrowser/builtin_plugins"


def _doc() -> str:
    return MAP_DOC.read_text(encoding="utf-8")


def _manifests() -> list[dict[str, Any]]:
    return [
        tomllib.loads(path.read_text(encoding="utf-8"))
        for path in sorted(BUILTIN_PLUGINS.glob("*/manifest.toml"))
    ]


def _cell(doc: str, row_key: str, column: int) -> str:
    """One cell from the markdown row whose first cell is *row_key*."""
    for line in doc.splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if cells and cells[0].strip("`") == row_key:
            return cells[column]
    raise AssertionError(f"no row for {row_key!r} in the map")


def test_every_registered_kind_is_in_the_map() -> None:
    doc = _doc()
    registered = {rule["id"] for manifest in _manifests() for rule in manifest.get("kind", [])}
    # Kinds without a match predicate of their own (folder, text, binary)
    # are claimed by the classifier, so read them off the view blocks too.
    registered |= {view["kind"] for manifest in _manifests() for view in manifest.get("view", [])}
    for kind in registered:
        assert f"| `{kind}` |" in doc, f"kind {kind!r} is registered but missing from the map"


def test_every_kinds_views_are_listed_with_the_default_first() -> None:
    doc = _doc()
    by_kind: dict[str, list[dict[str, Any]]] = {}
    for manifest in _manifests():
        for view in manifest.get("view", []):
            by_kind.setdefault(view["kind"], []).append(view)
    for kind, views in by_kind.items():
        listed = _cell(doc, kind, 2)
        for view in views:
            assert view["label"] in listed, f"{kind}: view {view['label']!r} missing from the map"
        default = next((view for view in views if view.get("default")), None)
        if default is not None:
            assert listed.startswith(default["label"]), (
                f"{kind}: the map must list the default view {default['label']!r} first"
            )


def test_container_kinds_match_the_map() -> None:
    doc = _doc()
    containers = {
        rule["id"]
        for manifest in _manifests()
        for rule in manifest.get("kind", [])
        if "container" in rule
    }
    # `folder` is a container by construction, not by manifest.
    containers.add("folder")
    section = doc.split("Two kinds are also **containers**", 1)
    assert len(section) == 2, "the map lost its container paragraph"
    for kind in containers:
        assert f"`{kind}`" in section[1][:400], f"container kind {kind!r} missing from the map"


def test_browser_and_data_routes_match_the_route_table() -> None:
    """The map names every route ``check_parity`` counts, so the two agree on what one is.

    That is each ``/api/``, browser-address, ``/raw``, and ``/_debug`` route anywhere in
    the package, plus the plugin hooks, with placeholders cut off. The root redirect and
    the two static-asset mounts are not selections, and neither check counts them.
    """

    doc = _doc()
    registered = check_parity.registered_surfaces()
    assert {"/api/cache/source", "/api/events", "/api/plugin/diff/document"} <= registered
    for surface in registered:
        assert surface in doc, f"route {surface!r} is served but missing from the map"


def test_documented_plugin_hooks_exist() -> None:
    doc = _doc()
    hooks = {
        f"{manifest['plugin']['name']}/{hook['route']}"
        for manifest in _manifests()
        for hook in manifest.get("data_hook", [])
    }
    listed = doc.split("Plugin hooks currently registered:", 1)
    assert len(listed) == 2, "the map lost its hook list"
    for hook in hooks:
        plugin = hook.split("/", 1)[0]
        assert f"`{hook}`" in listed[1][:400] or f"`{plugin}/*`" in listed[1][:400], (
            f"data hook {hook!r} is registered but missing from the map"
        )
