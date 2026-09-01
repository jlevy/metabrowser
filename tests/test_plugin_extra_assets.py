"""Manifest-driven plugin asset emission.

The shell previously hardcoded optional plugin assets in the index template.
Plugins now declare extra JS or CSS files in their
manifest's ``[plugin].extra_scripts`` / ``extra_styles`` lists, and
the loader emits ``<link>`` / ``<script>`` tags for each. This module
exercises:

1. The manifest schema accepts the new fields.
2. The loader rejects malformed entries (slashes, traversal).
3. The shell configures assets by kind without fetching them eagerly.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

import pytest

from metabrowser import server
from metabrowser.plugin_loader.discovery import LoadedPlugin
from metabrowser.plugin_loader.manifest import PLUGIN_SDK_VERSION, PluginManifest


def _build_manifest(
    extra_scripts: list[str] | None = None,
    extra_styles: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "plugin": {
            "name": "fixture",
            "sdk_version": PLUGIN_SDK_VERSION,
            "extra_scripts": extra_scripts or [],
            "extra_styles": extra_styles or [],
        },
    }


def test_manifest_accepts_extra_scripts_and_styles() -> None:
    m = PluginManifest.model_validate(
        _build_manifest(extra_scripts=["lib.js", "helpers.js"], extra_styles=["theme.css"])
    )
    assert m.plugin.extra_scripts == ["lib.js", "helpers.js"]
    assert m.plugin.extra_styles == ["theme.css"]
    assert m.validate_consistency() == []


def test_manifest_rejects_slashed_extra_script() -> None:
    m = PluginManifest.model_validate(_build_manifest(extra_scripts=["sub/lib.js"]))
    problems = m.validate_consistency()
    assert any("extra_scripts" in p and "sub/lib.js" in p for p in problems), problems


def test_manifest_rejects_traversal_in_extra_script() -> None:
    m = PluginManifest.model_validate(_build_manifest(extra_scripts=["../escape.js"]))
    problems = m.validate_consistency()
    assert any("extra_scripts" in p for p in problems), problems


def test_manifest_rejects_dotfile_in_extra_script() -> None:
    m = PluginManifest.model_validate(_build_manifest(extra_scripts=[".hidden.js"]))
    problems = m.validate_consistency()
    assert any("extra_scripts" in p for p in problems), problems


def test_manifest_rejects_slashed_extra_style() -> None:
    m = PluginManifest.model_validate(_build_manifest(extra_styles=["theme/dark.css"]))
    problems = m.validate_consistency()
    assert any("extra_styles" in p for p in problems), problems


def test_index_configures_plugin_assets_for_on_demand_loading(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    fake_manifest = PluginManifest.model_validate(
        {
            "plugin": {
                "name": "fixture",
                "sdk_version": PLUGIN_SDK_VERSION,
                "extra_scripts": ["alpha.js", "beta.js"],
                "extra_styles": ["palette.css"],
            },
            "kind": [{"id": "fixture-kind", "match": {"ext": ".fixture"}}],
            "view": [{"kind": "fixture-kind", "id": "source", "label": "Source"}],
        }
    )
    fake = LoadedPlugin(
        name="fixture",
        static_root=tmp_path,
        manifest=fake_manifest,
        source="builtin",
    )

    with patch.object(server, "_LOADED_PLUGINS", [fake]):
        response = asyncio.run(server.index(Mock()))
    body = bytes(response.body).decode("utf-8")

    config_idx = body.index("MetabrowserPluginHost.configureAssets")
    app_idx = body.index('<script src="/static/app.js')
    assert config_idx < app_idx
    assert body.index("/plugin-static/fixture/alpha.js") < body.index(
        "/plugin-static/fixture/beta.js"
    )
    assert '"fixture-kind"' in body
    assert '<script src="/plugin-static/fixture/' not in body
    assert '<script type="module" src="/plugin-static/fixture/' not in body
    assert '<link rel="stylesheet" href="/plugin-static/fixture/' not in body


def test_asset_config_deduplicates_the_default_stylesheet(tmp_path: Path) -> None:
    tmp_path.joinpath("styles.css").write_text("", encoding="utf-8")
    fake_manifest = PluginManifest.model_validate(
        {
            "plugin": {
                "name": "fixture",
                "sdk_version": PLUGIN_SDK_VERSION,
                "extra_styles": ["styles.css", "theme.css"],
            },
            "kind": [{"id": "fixture-kind", "match": {"ext": ".fixture"}}],
        }
    )
    fake = LoadedPlugin(
        name="fixture",
        static_root=tmp_path,
        manifest=fake_manifest,
        source="builtin",
    )

    with patch.object(server, "_LOADED_PLUGINS", [fake]):
        config = server._build_plugin_asset_config_block()

    assert config.count("/plugin-static/fixture/styles.css") == 1
    assert config.count("/plugin-static/fixture/theme.css") == 1


def test_file_render_waits_for_the_selected_kind_plugin() -> None:
    app = (server.STATIC_DIR / "app.js").read_text(encoding="utf-8")
    helper = app[
        app.index("async function renderFileWithPlugins") : app.index(
            "/** @returns {Promise<QuickFileOpenOutcome>} */"
        )
    ]

    assert "ensureKindAssets(data.kind)" in helper
    assert "MetabrowserPluginHost" not in helper
    assert "await _perf.measureAsync" in helper
    assert "return renderFile(data, preferredViewId, previewClaim)" in helper


def test_server_no_hardcoded_optional_asset_paths() -> None:
    """metabrowser core emits NO plugin-asset paths by name.

    Optional assets should only appear through plugin manifests, never as
    literals in ``server.py``.
    """
    src = Path(server.__file__).read_text(encoding="utf-8")
    # The historical block contained the literal "viz.css" and "viz.js" strings.
    assert "viz.css" not in src, "server.py should not name plugin assets directly"
    assert "viz.js" not in src, "server.py should not name plugin assets directly"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
