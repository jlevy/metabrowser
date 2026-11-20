"""The views/models/routes map is checked against the code it describes.

``docs/project/architecture/arch-views-models-routes.md`` is the index of
what the browser shows, from what, and at what address. A table there
that no longer matches the manifests or the route table is worse than no
table, so this test fails the build instead of letting it drift. The parity
tables are a separate document, which ``devtools/check_parity.py`` reads.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import Any

from devtools import check_parity

REPO_ROOT = Path(__file__).resolve().parent.parent
MAP_DOC = REPO_ROOT / "docs/project/architecture/arch-views-models-routes.md"
BUILTIN_PLUGINS = REPO_ROOT / "src/metabrowser/builtin_plugins"
SHOW_CLI = REPO_ROOT / "src/metabrowser/cli/show_cli.py"


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


def test_every_route_backed_kind_show_reports_is_in_the_map() -> None:
    """``--show`` names a kind for a route no manifest matches, such as a commit's comparison.

    Those kinds are assigned in ``cli/show_cli.py`` rather than declared in a manifest,
    so the manifest check above cannot see them.
    """
    doc = _doc()
    kinds = set(re.findall(r'\bkind = "([a-z0-9-]+)"', SHOW_CLI.read_text(encoding="utf-8")))
    assert "comparison" in kinds, "the scan of show_cli.py no longer finds its kinds"
    for kind in kinds:
        assert f"| `{kind}` |" in doc, f"--show reports kind {kind!r}, which the map omits"


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
    section = doc.split("kinds are also **containers**", 1)
    assert len(section) == 2, "the map lost its container paragraph"
    for kind in containers:
        assert f"`{kind}`" in section[1][:400], f"container kind {kind!r} missing from the map"


def test_browser_and_data_routes_match_the_route_table() -> None:
    """The map names every route ``check_parity`` counts, so the two agree on what one is.

    That is each ``/api/``, browser-address, ``/raw``, and ``/_debug`` route anywhere in
    the package, plus the plugin hooks, with placeholders cut off. The root redirect and
    the two static-asset mounts are not selections, and neither check counts them. A
    plugin hook is named in the hook list as ``<plugin>/<route>``, under the
    ``/api/plugin/<plugin>/<route>`` row.
    """

    doc = _doc()
    hooks = _hook_list(doc)
    registered = check_parity.registered_surfaces()
    assert {"/api/cache/source", "/api/events", "/api/plugin/diff/document"} <= registered
    for surface in registered:
        hook = surface.removeprefix("/api/plugin/")
        named = f"`{hook}`" in hooks if hook != surface else surface in doc
        assert named, f"route {surface!r} is served but missing from the map"


def _hook_list(doc: str) -> str:
    """The paragraph that lists the registered plugin hooks."""
    listed = doc.split("Plugin hooks currently registered:", 1)
    assert len(listed) == 2, "the map lost its hook list"
    return listed[1].split("\n\n", 1)[0]


def _registered_hooks() -> set[str]:
    return {
        f"{manifest['plugin']['name']}/{hook['route']}"
        for manifest in _manifests()
        for hook in manifest.get("data_hook", [])
    }


def test_documented_plugin_hooks_exist() -> None:
    listed = _hook_list(_doc())
    for hook in _registered_hooks():
        assert f"`{hook}`" in listed, f"data hook {hook!r} is registered but missing from the map"


def test_every_listed_plugin_hook_is_registered() -> None:
    """The hook list names no hook the manifests lack, so a wildcard or a stale name fails."""
    hooks = _registered_hooks()
    for name in re.findall(r"`([^`]+)`", _hook_list(_doc())):
        assert name in hooks, f"the map lists hook {name!r}, which no manifest registers"
