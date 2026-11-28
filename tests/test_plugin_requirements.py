"""Declared plugin dependencies: ``[plugin] requires`` and ``mb.plugins.load``.

The loader check that replaced the render-time-only ``mb.builtins`` rule. A manifest
names the plugins whose exports its browser code loads; discovery refuses a plugin whose
requirements cannot be met; and every built-in plugin loads exactly the providers it
declares. ``tests/golden/cli-plugins-requires.tryscript.md`` shows the CLI's report, and
``tests/dom/kpress-plugin-sdk-behavior.js`` the browser half, ``plugins.load``.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from metabrowser.cli.plugins import requirement_details
from metabrowser.plugin_loader.discovery import LoadedPlugin, discover_plugins, resolve_requirements
from metabrowser.plugin_loader.manifest import (
    PLUGIN_SDK_VERSION,
    TABLE_PLUGIN,
    PluginInfo,
    PluginManifest,
    load_manifest,
)

SOURCE = Path(__file__).resolve().parents[1] / "src" / "metabrowser"
BUILTIN = SOURCE / "builtin_plugins"

# A call that loads a provider's exports, however the SDK is reached: `mb.plugins.load`,
# `api?.plugins?.load`, or a chain broken across lines.
_LOAD_CALL = re.compile(r"\bplugins\??\s*\.\s*load\(\s*\"([a-z][a-z0-9_-]*)\"")


def _plugin(name: str, *requires: str) -> LoadedPlugin:
    manifest = PluginManifest(
        plugin=PluginInfo(name=name, sdk_version=PLUGIN_SDK_VERSION, requires=list(requires))
    )
    return LoadedPlugin(name=name, static_root=Path("/nonexistent"), manifest=manifest, source="t")


def _write_plugin(root: Path, name: str, requires: str) -> None:
    directory = root / name
    directory.mkdir(parents=True)
    directory.joinpath("manifest.toml").write_text(
        f'[plugin]\nname = "{name}"\nsdk_version = "{PLUGIN_SDK_VERSION}"\nrequires = {requires}\n',
        encoding="utf-8",
    )
    directory.joinpath("index.js").write_text("// stub\n", encoding="utf-8")


# ── The manifest ─────────────────────────────────────────────


def test_requires_defaults_to_none() -> None:
    assert PluginInfo(name="p", sdk_version=PLUGIN_SDK_VERSION).requires == []


@pytest.mark.parametrize(
    ("requires", "message"),
    [
        (["Markdown"], "is not a plugin name"),
        (["../markdown"], "is not a plugin name"),
        (["markdown", "markdown"], "more than once"),
    ],
)
def test_requires_names_each_plugin_once(requires: list[str], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        PluginInfo(name="p", sdk_version=PLUGIN_SDK_VERSION, requires=requires)


def test_a_plugin_that_requires_itself_is_refused(tmp_path: Path) -> None:
    _write_plugin(tmp_path, "selfish", '["selfish"]')
    with pytest.raises(ValueError, match="plugin 'selfish' requires itself"):
        load_manifest(tmp_path / "selfish" / "manifest.toml")


# ── Discovery ────────────────────────────────────────────────


def test_met_requirements_keep_every_plugin_in_its_order() -> None:
    plugins = [_plugin("folder", "markdown"), _plugin("markdown"), _plugin("diff", "markdown")]
    kept, refused = resolve_requirements(plugins)
    assert kept == plugins
    assert refused == []


def test_a_missing_provider_refuses_its_dependents_directly_or_not() -> None:
    plugins = [_plugin("a", "absent"), _plugin("b", "a"), _plugin("c", "b"), _plugin("d")]
    kept, refused = resolve_requirements(plugins)
    assert [plugin.name for plugin in kept] == ["d"]
    assert refused == [
        "plugin 'a' is refused: it requires 'absent', which was not discovered",
        "plugin 'b' is refused: it requires 'a', which was refused",
        "plugin 'c' is refused: it requires 'b', which was refused",
    ]


def test_a_refusal_reaches_a_dependent_discovered_before_its_provider() -> None:
    """The refusals are listed causes first, whatever the discovery order."""
    plugins = [_plugin("c", "b"), _plugin("b", "a"), _plugin("a", "absent")]
    kept, refused = resolve_requirements(plugins)
    assert kept == []
    assert refused == [
        "plugin 'a' is refused: it requires 'absent', which was not discovered",
        "plugin 'b' is refused: it requires 'a', which was refused",
        "plugin 'c' is refused: it requires 'b', which was refused",
    ]


def test_a_cycle_is_refused_with_its_shortest_path() -> None:
    plugins = [
        _plugin("a", "b"),
        _plugin("b", "markdown", "c"),
        _plugin("c", "a"),
        _plugin("on-cycle", "c"),
        _plugin("markdown"),
    ]
    kept, refused = resolve_requirements(plugins)
    assert [plugin.name for plugin in kept] == ["markdown"]
    assert refused == [
        "plugin 'a' is refused: its requirements form a cycle, a -> b -> c -> a",
        "plugin 'b' is refused: its requirements form a cycle, b -> c -> a -> b",
        "plugin 'c' is refused: its requirements form a cycle, c -> a -> b -> c",
        "plugin 'on-cycle' is refused: it requires 'c', which was refused",
    ]


def test_discovery_refuses_an_operator_plugin_whose_requirement_is_missing(
    tmp_path: Path,
) -> None:
    _write_plugin(tmp_path, "needs-markdown", '["markdown"]')
    _write_plugin(tmp_path, "needs-absent", '["absent"]')
    result = discover_plugins(extra_dirs=[tmp_path])
    names = [plugin.name for plugin in result.plugins]
    assert "needs-markdown" in names
    assert "needs-absent" not in names
    assert result.errors == [
        "plugin 'needs-absent' is refused: it requires 'absent', which was not discovered"
    ]


def test_a_refused_override_keeps_the_plugin_it_would_replace(tmp_path: Path) -> None:
    """An operator plugin that replaces a provider by name and requires something
    missing is refused like an invalid one: the built-in it shadowed stays, and so do the
    built-ins that require it."""
    builtin = {plugin.name: plugin for plugin in discover_plugins().plugins}
    _write_plugin(tmp_path, "markdown", '["absent"]')
    result = discover_plugins(extra_dirs=[tmp_path])
    assert result.errors == [
        "plugin 'markdown' is refused: it requires 'absent', which was not discovered; "
        "the plugin it overrides (builtin) is kept"
    ]
    assert [plugin.name for plugin in result.plugins] == list(builtin)
    assert {plugin.name: plugin.source for plugin in result.plugins}["markdown"] == "builtin"


def test_a_refused_override_on_a_cycle_restores_the_plugin_it_would_replace(
    tmp_path: Path,
) -> None:
    """Restoring a provider resolves again, so a dependent the override's refusal reached
    loads, and a refusal that still holds is reported once."""
    _write_plugin(tmp_path, "markdown", '["loop"]')
    _write_plugin(tmp_path, "loop", '["markdown"]')
    _write_plugin(tmp_path, "needs-loop", '["loop"]')
    result = discover_plugins(extra_dirs=[tmp_path])
    names = {plugin.name: plugin.source for plugin in result.plugins}
    assert names["markdown"] == "builtin"
    assert "folder" in names
    assert "loop" in names
    assert "needs-loop" in names
    assert result.errors == [
        "plugin 'markdown' is refused: its requirements form a cycle, "
        "markdown -> loop -> markdown; the plugin it overrides (builtin) is kept"
    ]


# ── The built-in plugins ─────────────────────────────────────


def _builtin_manifests() -> dict[str, tuple[Path, PluginManifest]]:
    return {
        directory.name: (directory, load_manifest(directory / "manifest.toml"))
        for directory in sorted(BUILTIN.iterdir())
        if (directory / "manifest.toml").is_file()
    }


def test_every_builtin_loads_exactly_the_providers_it_declares() -> None:
    """A provider a plugin loads but does not declare is unchecked by discovery and
    unreported by the doctor; one it declares but never loads refuses it for nothing.
    A plugin with a ``[[table_source]]`` requires the table plugin, whose routes serve
    it, whether or not its browser code loads it."""
    used: dict[str, set[str]] = {}
    declared: dict[str, set[str]] = {}
    for name, (directory, manifest) in _builtin_manifests().items():
        sources = "\n".join(
            path.read_text(encoding="utf-8") for path in sorted(directory.rglob("*.js"))
        )
        # A provider's own comments name the call its dependents make.
        used[name] = set(_LOAD_CALL.findall(sources)) - {manifest.plugin.name}
        if manifest.table_source:
            used[name].add(TABLE_PLUGIN)
        declared[name] = set(manifest.plugin.requires)
    assert used == declared
    assert declared == {
        "agents": {"structured"},
        "binary": set(),
        "delimited": {"table"},
        "diff": {"pdf", "structured"},
        "event_log": {"agents"},
        "folder": {"markdown"},
        "fsqlite": {"sqlite", "table"},
        "github": {"markdown", "diff"},
        "html": set(),
        "image": set(),
        "markdown": {"pdf"},
        "pdf": set(),
        "softschema": {"structured", "table"},
        "sqlite": {"table"},
        "structured": {"table"},
        "table": set(),
        "text": set(),
        "unknown_jsonl": {"agents"},
    }


def test_no_browser_code_reads_the_retired_builtins_namespace() -> None:
    """``mb.builtins`` was the informal, render-time-only way to share a plugin's helpers;
    a provider's exports now come from ``mb.plugins.load``."""
    sessions = Path(__file__).resolve().parent / "dom"
    readers = [
        path.name
        for root in (SOURCE / "static", BUILTIN, sessions)
        for path in sorted([*root.rglob("*.js"), *root.rglob("*.mjs")])
        if "vendor" not in path.parts
        and re.search(r"\.builtins\b", path.read_text(encoding="utf-8"))
    ]
    assert readers == []


def test_every_builtin_provider_exports_from_its_module() -> None:
    for provider in ("agents", "github", "markdown", "pdf", "structured"):
        source = (BUILTIN / provider / "index.js").read_text(encoding="utf-8")
        assert re.search(r"^export ", source, re.MULTILINE), provider


def test_the_doctor_reports_each_declared_requirement() -> None:
    plugins = [_plugin("folder", "markdown"), _plugin("markdown"), _plugin("x", "a", "b")]
    assert requirement_details(plugins) == (
        ("folder", "requires markdown"),
        ("x", "requires a, b"),
    )
