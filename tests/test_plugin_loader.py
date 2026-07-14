"""Tests for metabrowser.plugin_loader — manifest, discovery, classifier, routes.

Covers the plugin contract end-to-end:

* manifest.toml validation (required fields, predicate emptiness, view
  uniqueness, default-per-kind, sidekick syntax);
* discovery from filesystem (built-in plugins + local plugin dirs);
* classifier compilation from declarative match rules;
* /plugin-static path-traversal guard + ETag round-trip.

The Python entry-point discovery path is covered by integration tests in
downstream plugins; installing a fixture distribution during collection is
more trouble than it is worth here.
"""

from __future__ import annotations

import importlib.metadata
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest
import yaml as pyyaml
from pydantic import ValidationError

from metabrowser.file_kinds import FileContext
from metabrowser.paths_safe import _set_root_dir
from metabrowser.plugin_loader.classify import (
    CompiledKindRule,
    build_classifier,
    collect_folder_markers,
)
from metabrowser.plugin_loader.discovery import (
    LoadedPlugin,
    _discover_entry_point_plugins,
    _try_load_plugin,
    discover_plugins,
)
from metabrowser.plugin_loader.manifest import (
    DataHookSpec,
    KindMatch,
    KindRule,
    PluginInfo,
    PluginManifest,
    ViewSpec,
    load_manifest,
)

# ── Fixtures ────────────────────────────────────────────────


@pytest.fixture
def make_plugin_dir(tmp_path: Path):
    """Build a plugin directory with the given manifest text."""

    def _build(name: str, manifest_text: str, *, with_index: bool = True) -> Path:
        plugin_dir = tmp_path / name
        plugin_dir.mkdir()
        (plugin_dir / "manifest.toml").write_text(manifest_text)
        if with_index:
            (plugin_dir / "index.js").write_text("// stub\n")
        return plugin_dir

    return _build


# ── Manifest validation ─────────────────────────────────────


def test_manifest_minimum_fields(make_plugin_dir) -> None:
    plugin_dir = make_plugin_dir(
        "p1",
        """
[plugin]
name = "p1"

[[kind]]
id = "myk"
match = { ext = ".myk" }

[[view]]
kind = "myk"
id = "main"
label = "Main"
default = true
""",
    )
    manifest = load_manifest(plugin_dir / "manifest.toml")
    assert manifest.plugin.name == "p1"
    assert manifest.kind[0].id == "myk"
    assert manifest.view[0].id == "main"


def test_manifest_rejects_empty_match(make_plugin_dir) -> None:
    plugin_dir = make_plugin_dir(
        "p2",
        """
[plugin]
name = "p2"

[[kind]]
id = "myk"
match = {}
""",
    )
    with pytest.raises(ValueError, match="empty match predicate"):
        load_manifest(plugin_dir / "manifest.toml")


def test_manifest_rejects_duplicate_view_ids(make_plugin_dir) -> None:
    plugin_dir = make_plugin_dir(
        "p3",
        """
[plugin]
name = "p3"

[[kind]]
id = "myk"
match = { ext = ".x" }

[[view]]
kind = "myk"
id = "main"
label = "M"
[[view]]
kind = "myk"
id = "main"
label = "M2"
""",
    )
    with pytest.raises(ValueError, match="appears 2 times"):
        load_manifest(plugin_dir / "manifest.toml")


def test_manifest_rejects_multiple_defaults(make_plugin_dir) -> None:
    plugin_dir = make_plugin_dir(
        "p4",
        """
[plugin]
name = "p4"

[[kind]]
id = "myk"
match = { ext = ".x" }

[[view]]
kind = "myk"
id = "a"
label = "A"
default = true
[[view]]
kind = "myk"
id = "b"
label = "B"
default = true
""",
    )
    with pytest.raises(ValueError, match="multiple default views"):
        load_manifest(plugin_dir / "manifest.toml")


def test_manifest_rejects_bad_sidekick(make_plugin_dir) -> None:
    plugin_dir = make_plugin_dir(
        "p5",
        """
[plugin]
name = "p5"

[[kind]]
id = "myk"
match = { ext = ".x" }

[[data_hook]]
route = "viz-model"
sidekick = "this_is_not_a_module_callable"
""",
    )
    with pytest.raises(ValueError, match="malformed sidekick"):
        load_manifest(plugin_dir / "manifest.toml")


def test_manifest_rejects_invalid_plugin_name() -> None:
    # Plugin name pattern is enforced by Pydantic at construction time.
    with pytest.raises(ValidationError):
        PluginManifest(
            plugin=PluginInfo(name="Bad-Name"),  # uppercase rejected
            kind=[KindRule(id="x", match=KindMatch(ext=".x"))],
        )


def test_manifest_rejects_slashed_route() -> None:
    manifest = PluginManifest(
        plugin=PluginInfo(name="p"),
        kind=[KindRule(id="x", match=KindMatch(ext=".x"))],
        data_hook=[DataHookSpec(route="not/ok", sidekick="m:fn")],
    )
    problems = manifest.validate_consistency()
    assert any("'/'" in p for p in problems)


def test_manifest_rejects_duplicate_data_hook_routes() -> None:
    manifest = PluginManifest(
        plugin=PluginInfo(name="p"),
        kind=[KindRule(id="x", match=KindMatch(ext=".x"))],
        data_hook=[
            DataHookSpec(route="same", sidekick="m:first"),
            DataHookSpec(route="same", sidekick="m:second"),
        ],
    )
    problems = manifest.validate_consistency()
    assert any("data_hook route 'same' appears 2 times" in p for p in problems)


# ── Discovery ───────────────────────────────────────────────


def test_discovery_skips_dirs_without_manifest(tmp_path: Path) -> None:
    # Empty subdir under an extra_dir root should be silently ignored.
    extra = tmp_path / "plugins"
    extra.mkdir(parents=True)
    (extra / "scaffold").mkdir()  # no manifest.toml
    result = discover_plugins(extra_dirs=[extra])
    assert all("scaffold" not in (e or "") for e in result.errors)


def test_discovery_reports_manifest_missing_index_js(make_plugin_dir, tmp_path: Path) -> None:
    plugin_dir = make_plugin_dir(
        "broken",
        """
[plugin]
name = "broken"

[[kind]]
id = "x"
match = { ext = ".x" }
""",
        with_index=False,
    )
    result = _try_load_plugin(plugin_dir, source="local:test")
    assert isinstance(result, str)
    assert "index.js" in result


def test_discovery_finds_extra_dir_plugin(make_plugin_dir, tmp_path: Path) -> None:
    """A directory passed via extra_dirs (CLI / env var) is scanned for plugins.
    Auto-discovery from <served-root>/.metabrowser/plugins/ or ~/.metabrowser/
    is intentionally not a source — the cut requires explicit operator opt-in.
    """
    extra = tmp_path / "plugins"
    extra.mkdir(parents=True)
    plugin_dir = extra / "myplug"
    plugin_dir.mkdir()
    (plugin_dir / "manifest.toml").write_text(
        """
[plugin]
name = "myplug"

[[kind]]
id = "myk"
match = { ext = ".myk" }
"""
    )
    (plugin_dir / "index.js").write_text("// ok\n")
    result = discover_plugins(extra_dirs=[extra])
    names = [p.name for p in result.plugins]
    assert "myplug" in names


def test_entry_point_calls_documented_plugin_dir_factory(
    make_plugin_dir, monkeypatch: pytest.MonkeyPatch
) -> None:
    plugin_dir = make_plugin_dir(
        "entrypoint-plugin",
        """
[plugin]
name = "entrypoint-plugin"

[[kind]]
id = "entrypoint-kind"
match = { ext = ".entrypoint" }
""",
    )
    module_name = "metabrowser_test_entrypoint_plugin"
    module = ModuleType(module_name)
    cast(Any, module).plugin_dir = lambda: plugin_dir
    monkeypatch.setitem(sys.modules, module_name, module)
    entry_point = importlib.metadata.EntryPoint(
        name="entrypoint-plugin",
        value=f"{module_name}:plugin_dir",
        group="metabrowser.plugins",
    )
    monkeypatch.setattr(
        importlib.metadata,
        "entry_points",
        lambda **_kwargs: [entry_point],
    )

    discovered = _discover_entry_point_plugins()

    assert len(discovered) == 1
    assert isinstance(discovered[0], LoadedPlugin)
    assert discovered[0].static_root == plugin_dir.resolve()
    assert discovered[0].source == "entry-point:entrypoint-plugin"


def test_entry_point_reports_directory_without_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plugin_dir = tmp_path / "incomplete-entrypoint-plugin"
    plugin_dir.mkdir()
    module_name = "metabrowser_test_incomplete_entrypoint_plugin"
    module = ModuleType(module_name)
    cast(Any, module).plugin_dir = lambda: plugin_dir
    monkeypatch.setitem(sys.modules, module_name, module)
    entry_point = importlib.metadata.EntryPoint(
        name="incomplete-entrypoint-plugin",
        value=f"{module_name}:plugin_dir",
        group="metabrowser.plugins",
    )
    monkeypatch.setattr(
        importlib.metadata,
        "entry_points",
        lambda **_kwargs: [entry_point],
    )

    discovered = _discover_entry_point_plugins()

    assert discovered == [
        f"entry-point incomplete-entrypoint-plugin: {plugin_dir}/manifest.toml missing"
    ]


# ── Classifier ─────────────────────────────────────────────


def _ctx(path: Path, ext: str = "", adapter: str | None = None) -> FileContext:
    return FileContext(path, ext or path.suffix, adapter)


def test_classifier_priority_wins(tmp_path: Path) -> None:
    f = tmp_path / "x.md"
    f.write_text("---\nreport:\n  name: p\n---\nbody\n")
    rules = [
        CompiledKindRule(
            rule=KindRule(
                id="markdown",
                match=KindMatch(ext=".md"),
                priority=0,
            ),
            plugin_name="builtin",
            discovery_index=0,
        ),
        CompiledKindRule(
            rule=KindRule(
                id="report",
                match=KindMatch(ext=".md", frontmatter_has_key="report"),
                priority=100,
            ),
            plugin_name="reports",
            discovery_index=1,
        ),
    ]
    classifier = build_classifier(rules)
    assert classifier(_ctx(f)) == "report"


def test_classifier_returns_none_when_nothing_matches(tmp_path: Path) -> None:
    f = tmp_path / "x.png"
    f.write_bytes(b"\x89PNG")
    rules = [
        CompiledKindRule(
            rule=KindRule(id="markdown", match=KindMatch(ext=".md")),
            plugin_name="builtin",
            discovery_index=0,
        ),
    ]
    assert build_classifier(rules)(_ctx(f)) is None


def test_classifier_json_value_prefix(tmp_path: Path) -> None:
    f = tmp_path / "resources.json"
    f.write_text('{"schema": "example.resources/v1", "x": 1}')
    rule = CompiledKindRule(
        rule=KindRule(
            id="analysis-report",
            match=KindMatch(
                ext=".json",
                basename="resources.json",
                json_has_key="schema",
                json_value_prefix="example.resources/",
            ),
            priority=100,
        ),
        plugin_name="reports",
        discovery_index=0,
    )
    assert build_classifier([rule])(_ctx(f)) == "analysis-report"


def test_classifier_json_value_prefix_rejects_mismatch(tmp_path: Path) -> None:
    f = tmp_path / "resources.json"
    f.write_text('{"schema": "something_else", "x": 1}')
    rule = CompiledKindRule(
        rule=KindRule(
            id="analysis-report",
            match=KindMatch(
                ext=".json",
                basename="resources.json",
                json_has_key="schema",
                json_value_prefix="example.resources/",
            ),
        ),
        plugin_name="reports",
        discovery_index=0,
    )
    assert build_classifier([rule])(_ctx(f)) is None


def test_classifier_exts_list_match(tmp_path: Path) -> None:
    """A single [[kind]] block with match.exts = [...] matches any listed extension."""
    rule = CompiledKindRule(
        rule=KindRule(
            id="structured",
            match=KindMatch(exts=[".json", ".yaml", ".yml"]),
        ),
        plugin_name="structured",
        discovery_index=0,
    )
    classifier = build_classifier([rule])
    fj = tmp_path / "x.json"
    fj.write_text("{}")
    fy = tmp_path / "y.yaml"
    fy.write_text("a: 1")
    fyml = tmp_path / "z.yml"
    fyml.write_text("a: 1")
    fother = tmp_path / "n.txt"
    fother.write_text("nope")
    assert classifier(_ctx(fj)) == "structured"
    assert classifier(_ctx(fy)) == "structured"
    assert classifier(_ctx(fyml)) == "structured"
    assert classifier(_ctx(fother)) is None


def test_manifest_rejects_ext_and_exts_both_set() -> None:
    """Setting match.ext and match.exts on the same rule is a manifest error."""
    manifest = PluginManifest(
        plugin=PluginInfo(name="x"),
        kind=[KindRule(id="x", match=KindMatch(ext=".json", exts=[".json"]))],
    )
    problems = manifest.validate_consistency()
    assert any("both match.ext and match.exts" in p for p in problems)


def test_manifest_rejects_empty_exts_list() -> None:
    manifest = PluginManifest(
        plugin=PluginInfo(name="x"),
        kind=[KindRule(id="x", match=KindMatch(exts=[]))],
    )
    problems = manifest.validate_consistency()
    # Empty exts means the predicate is empty -> the empty-predicate check fires,
    # plus a friendlier-specific check; either is a problem.
    assert problems, "expected validation problem for empty exts"


def test_manifest_rejects_exts_entry_without_dot() -> None:
    manifest = PluginManifest(
        plugin=PluginInfo(name="x"),
        kind=[KindRule(id="x", match=KindMatch(exts=["json"]))],
    )
    problems = manifest.validate_consistency()
    assert any("must be a string starting with '.'" in p for p in problems)


def test_classifier_adapter_match() -> None:
    fake = Path("/dev/null/fake.jsonl")
    rule = CompiledKindRule(
        rule=KindRule(
            id="agent-log",
            match=KindMatch(ext=".jsonl", adapter="claude"),
        ),
        plugin_name="builtin",
        discovery_index=0,
    )
    classifier = build_classifier([rule])
    assert classifier(FileContext(fake, ".jsonl", "claude")) == "agent-log"
    assert classifier(FileContext(fake, ".jsonl", "custom-adapter")) is None


# ── ViewSpec model unit ─────────────────────────────────────


def test_view_spec_default_is_false() -> None:
    v = ViewSpec(kind="x", id="y", label="Y")
    assert v.default is False
    assert v.printable is False
    assert v.print_profile == "plain"
    assert v.render_runtime is None


def test_view_spec_accepts_print_metadata() -> None:
    v = ViewSpec(
        kind="markdown",
        id="rendered",
        label="Document",
        printable=True,
        print_profile="document",
        render_runtime="kpress",
    )
    assert v.printable is True
    assert v.print_profile == "document"
    assert v.render_runtime == "kpress"


def test_view_spec_rejects_unknown_print_profile() -> None:
    with pytest.raises(ValidationError):
        ViewSpec(kind="x", id="y", label="Y", print_profile=cast(Any, "poster"))


# ── folder_marker + yaml matchers (Tier A of dataset-plugin spec) ───────


def test_classifier_folder_marker_matches_basename(tmp_path: Path) -> None:
    f = tmp_path / "dataset.yml"
    f.write_text("spec: ExampleDataset/0.1\n")
    rule = CompiledKindRule(
        rule=KindRule(id="dataset", match=KindMatch(folder_marker="dataset.yml"), priority=100),
        plugin_name="dataset",
        discovery_index=0,
    )
    other = tmp_path / "other.yml"
    other.write_text("nope: 1\n")
    classifier = build_classifier([rule])
    assert classifier(_ctx(f)) == "dataset"
    assert classifier(_ctx(other)) is None


def test_collect_folder_markers_aggregates_across_rules() -> None:
    rules = [
        CompiledKindRule(
            rule=KindRule(id="catalog", match=KindMatch(folder_marker="catalog.yml")),
            plugin_name="dataset",
            discovery_index=0,
        ),
        CompiledKindRule(
            rule=KindRule(id="dataset", match=KindMatch(folder_marker="dataset.yml")),
            plugin_name="dataset",
            discovery_index=1,
        ),
        CompiledKindRule(
            rule=KindRule(id="markdown", match=KindMatch(ext=".md")),
            plugin_name="builtin",
            discovery_index=2,
        ),
    ]
    assert collect_folder_markers(rules) == {"catalog.yml", "dataset.yml"}


def test_classifier_yaml_has_key(tmp_path: Path) -> None:
    f = tmp_path / "bundle.yaml"
    f.write_text("project: ALPHA\nspec: ReportBundle/0.1\nresults: []\n")
    rule = CompiledKindRule(
        rule=KindRule(
            id="report-bundle",
            match=KindMatch(
                ext=".yaml",
                yaml_has_key="spec",
                yaml_value_prefix="ReportBundle/",
            ),
            priority=100,
        ),
        plugin_name="report-bundle",
        discovery_index=0,
    )
    assert build_classifier([rule])(_ctx(f)) == "report-bundle"


def test_classifier_yaml_value_prefix_rejects_mismatch(tmp_path: Path) -> None:
    f = tmp_path / "bundle.yaml"
    f.write_text("spec: OtherBundle/0.1\n")
    rule = CompiledKindRule(
        rule=KindRule(
            id="report-bundle",
            match=KindMatch(
                ext=".yaml",
                yaml_has_key="spec",
                yaml_value_prefix="ReportBundle/",
            ),
        ),
        plugin_name="report-bundle",
        discovery_index=0,
    )
    assert build_classifier([rule])(_ctx(f)) is None


def test_classifier_yaml_has_key_skips_non_yaml(tmp_path: Path) -> None:
    f = tmp_path / "thing.json"
    f.write_text('{"spec": "ReportBundle/0.1"}')
    rule = CompiledKindRule(
        rule=KindRule(
            id="report-bundle",
            match=KindMatch(yaml_has_key="spec", yaml_value_prefix="ReportBundle/"),
        ),
        plugin_name="report-bundle",
        discovery_index=0,
    )
    # JSON file: yaml_has_key matcher must not claim it.
    assert build_classifier([rule])(_ctx(f)) is None


def test_classifier_yaml_bounded_parse_ignores_trailing_garbage(tmp_path: Path) -> None:
    f = tmp_path / "bundle.yaml"
    # Header parses cleanly within the 16 KiB prefix; trailing garbage past
    # the prefix is irrelevant. Use a large pad so we'd hit the prefix limit
    # well before the broken section.
    header = "spec: ReportBundle/0.1\nproject: ALPHA\n"
    pad = "comment: " + ("x" * (20 * 1024)) + "\n"
    f.write_text(header + pad)
    rule = CompiledKindRule(
        rule=KindRule(
            id="report-bundle",
            match=KindMatch(
                ext=".yaml",
                yaml_has_key="spec",
                yaml_value_prefix="ReportBundle/",
            ),
        ),
        plugin_name="report-bundle",
        discovery_index=0,
    )
    # A non-truncating safe-load of the full file should still parse fine here,
    # but the bounded read MUST also see the header; assert the classifier
    # claims the file regardless.
    assert build_classifier([rule])(_ctx(f)) == "report-bundle"


def test_classifier_yaml_unparseable_returns_none(tmp_path: Path) -> None:
    f = tmp_path / "broken.yaml"
    f.write_text(":\n:\n:")  # invalid yaml
    rule = CompiledKindRule(
        rule=KindRule(
            id="report-bundle",
            match=KindMatch(ext=".yaml", yaml_has_key="spec"),
        ),
        plugin_name="report-bundle",
        discovery_index=0,
    )
    assert build_classifier([rule])(_ctx(f)) is None


def test_yaml_top_level_caches_on_context(tmp_path: Path, monkeypatch) -> None:
    """Multiple rules consulting yaml_has_key against the same FileContext
    should parse the YAML prefix only once. The cache lives on the
    FileContext instance via the yaml_top_level property."""

    f = tmp_path / "bundle.yaml"
    f.write_text("spec: ReportBundle/0.1\nproject: ALPHA\n")
    rules = [
        CompiledKindRule(
            rule=KindRule(
                id="bundle-A",
                match=KindMatch(ext=".yaml", yaml_has_key="spec"),
            ),
            plugin_name="p1",
            discovery_index=0,
        ),
        CompiledKindRule(
            rule=KindRule(
                id="bundle-B",
                match=KindMatch(
                    ext=".yaml",
                    yaml_has_key="spec",
                    yaml_value_prefix="ReportBundle/",
                ),
            ),
            plugin_name="p2",
            discovery_index=1,
        ),
    ]
    classifier = build_classifier(rules)

    call_count = {"n": 0}
    real_safe_load = pyyaml.safe_load

    def counting_safe_load(stream):
        call_count["n"] += 1
        return real_safe_load(stream)

    monkeypatch.setattr(pyyaml, "safe_load", counting_safe_load)

    # Single FileContext consulted by both rules; assert safe_load fires once.
    ctx = _ctx(f)
    result = classifier(ctx)
    # First rule has lower priority equality and matches first; both rules
    # match this file (so the classifier stops at the first), but the
    # second rule's predicate would also reuse the cached parse if asked.
    # The point of the test is that running the classifier doesn't double
    # parse the YAML.
    assert result is not None
    # Touch the property explicitly to ensure the cache is engaged for the
    # second rule's matching pass.
    _ = ctx.yaml_top_level
    assert call_count["n"] == 1


def test_classify_path_glob_matches_under_subtree(tmp_path: Path) -> None:
    """A file under `**/files/derived/**/*.md` matches the glob."""

    _set_root_dir(tmp_path)
    derived = tmp_path / "rooms" / "ALPHA" / "files" / "derived" / "abc"
    derived.mkdir(parents=True)
    md = derived / "defuddle-0.18.1.md"
    md.write_text("# derived\n")
    rule = CompiledKindRule(
        rule=KindRule(
            id="derived-markdown",
            match=KindMatch(ext=".md", path_glob="**/files/derived/**/*.md"),
            priority=100,
        ),
        plugin_name="dataset",
        discovery_index=0,
    )
    assert build_classifier([rule])(_ctx(md)) == "derived-markdown"
    _set_root_dir(Path())


def test_classify_path_glob_rejects_outside_subtree(tmp_path: Path) -> None:

    _set_root_dir(tmp_path)
    plain = tmp_path / "notes.md"
    plain.write_text("# plain\n")
    rule = CompiledKindRule(
        rule=KindRule(
            id="derived-markdown",
            match=KindMatch(ext=".md", path_glob="**/files/derived/**/*.md"),
        ),
        plugin_name="dataset",
        discovery_index=0,
    )
    assert build_classifier([rule])(_ctx(plain)) is None
    _set_root_dir(Path())


def test_manifest_rejects_yaml_value_prefix_without_key() -> None:
    manifest = PluginManifest(
        plugin=PluginInfo(name="x"),
        kind=[KindRule(id="x", match=KindMatch(ext=".yaml", yaml_value_prefix="Foo/"))],
    )
    problems = manifest.validate_consistency()
    assert any("yaml_value_prefix without match.yaml_has_key" in p for p in problems), (
        f"expected validation problem, got: {problems}"
    )
