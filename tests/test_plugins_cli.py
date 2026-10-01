"""Tests for the plugin diagnostic modes of the metab CLI.

Drives ``metab --plugins / --plugin NAME / --doctor`` via Typer's
CliRunner. Confirms the discovered set, the JSON output shape, and the
doctor's exit-code contract on broken / valid plugins.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from metabrowser.cache import contracts as cache_contracts
from metabrowser.cache.records import CACHE_LAYOUT_CONTRACT_ID
from metabrowser.cli.main import _app

_runner = CliRunner()


def test_plugins_list_table_includes_builtin_plugins() -> None:
    result = _runner.invoke(_app, ["--plugins"])
    assert result.exit_code == 0
    assert "markdown" in result.stdout
    assert "builtin" in result.stdout
    # Table header
    assert "NAME" in result.stdout
    assert "KINDS" in result.stdout


def test_plugins_list_json_emits_structured_output() -> None:
    result = _runner.invoke(_app, ["--plugins", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "plugins" in data
    assert "errors" in data
    names = {p["name"] for p in data["plugins"]}
    assert "markdown" in names
    markdown = next(p for p in data["plugins"] if p["name"] == "markdown")
    assert "markdown" in markdown["kinds"]
    assert "rendered" in markdown["views"]


def test_plugins_list_reports_partial_discovery_as_failure(tmp_path: Path) -> None:
    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / "manifest.toml").write_text('[plugin]\nname = "broken"\nsdk_version = "0.7"\n')

    table_result = _runner.invoke(
        _app,
        ["--plugins", "--plugins-dir", str(tmp_path)],
    )
    assert table_result.exit_code == 1
    assert "markdown" in table_result.stdout
    assert "Discovery errors:" in table_result.stderr
    assert "index.js missing" in table_result.stderr

    json_result = _runner.invoke(
        _app,
        ["--plugins", "--json", "--plugins-dir", str(tmp_path)],
    )
    assert json_result.exit_code == 1
    payload = json.loads(json_result.stdout)
    assert any("index.js missing" in error for error in payload["errors"])
    assert "Logging error" not in json_result.stderr


def test_plugins_show_builtin_dumps_manifest() -> None:
    result = _runner.invoke(_app, ["--plugin", "markdown"])
    assert result.exit_code == 0
    assert "name:         markdown" in result.stdout
    assert "markdown/rendered" in result.stdout
    assert "static_root:" in result.stdout


def test_plugins_show_json_emits_resolved_plugin() -> None:
    result = _runner.invoke(_app, ["--plugin", "markdown", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    plugin = payload["plugin"]
    assert plugin["name"] == "markdown"
    assert plugin["source"] == "builtin"
    assert any(kind["id"] == "markdown" for kind in plugin["kinds"])
    assert any(view["id"] == "rendered" for view in plugin["views"])
    assert "index.js" in plugin["assets"]
    assert payload["errors"] == []


def test_plugins_show_unknown_plugin_errors() -> None:
    result = _runner.invoke(_app, ["--plugin", "no-such-plugin"])
    assert result.exit_code != 0
    # The CLIError from show_plugin propagates through Typer; the runner
    # records it as result.exception.
    assert "no-such-plugin" in str(result.exception)


def test_plugins_show_unknown_plugin_json_emits_structured_error() -> None:
    result = _runner.invoke(_app, ["--plugin", "no-such-plugin", "--json"])
    assert result.exit_code == 1
    assert result.stdout == ""
    payload = json.loads(result.stderr)
    assert "no-such-plugin" in payload["error"]


def test_plugins_doctor_exits_zero_on_clean_install() -> None:
    result = _runner.invoke(_app, ["--doctor"])
    assert result.exit_code == 0
    assert "11 plugin(s) OK" in result.stdout


def test_plugins_doctor_json_emits_structured_result() -> None:
    result = _runner.invoke(_app, ["--doctor", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert set(payload) == {"ok", "plugin_count", "problems"}
    assert payload["ok"] is True
    assert payload["plugin_count"] > 0
    assert payload["problems"] == []


@pytest.fixture
def damaged_cache_schemas(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """Serve the packaged cache schemas from a copy in which one no longer fits its model.

    The registry and its declarations are cached for the process, so they are dropped on
    the way in, to read the copy, and on the way out, so no other test sees the damage.
    """

    damaged = cache_contracts.CACHE_CONTRACT_BY_ID[CACHE_LAYOUT_CONTRACT_ID]
    schemas = tmp_path / "schemas"
    shutil.copytree(cache_contracts.SCHEMA_ROOT, schemas)
    path = schemas / damaged.schema_name
    path.write_text(
        path.read_text(encoding="utf-8").replace("created_by", "created_with"), encoding="utf-8"
    )
    monkeypatch.setattr(cache_contracts, "SCHEMA_ROOT", schemas)

    def forget() -> None:
        cache_contracts.cache_contract_registry.cache_clear()
        cache_contracts._artifact_contracts.cache_clear()  # pyright: ignore[reportPrivateUsage]

    forget()
    try:
        yield damaged.schema_name
    finally:
        monkeypatch.undo()
        forget()


def test_plugins_doctor_reports_a_damaged_cache_contract(damaged_cache_schemas: str) -> None:
    result = _runner.invoke(_app, ["--doctor"])

    assert result.exit_code == 1
    assert "OK" not in result.stdout
    assert "cache record contracts:" in result.stderr
    assert CACHE_LAYOUT_CONTRACT_ID in result.stderr
    assert f"cache record schema '{damaged_cache_schemas}'" in result.stderr


def test_plugins_doctor_json_reports_a_damaged_cache_contract(damaged_cache_schemas: str) -> None:
    result = _runner.invoke(_app, ["--doctor", "--json"])

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert set(payload) == {"ok", "plugin_count", "problems"}
    assert payload["ok"] is False
    assert any(problem.startswith("cache record contracts:") for problem in payload["problems"])
    assert any(damaged_cache_schemas in problem for problem in payload["problems"])


def test_plugins_doctor_rejects_local_python_data_hook(tmp_path: Path) -> None:
    """Operator-directory plugins are JavaScript-only."""
    pdir = tmp_path / "broken"
    pdir.mkdir()
    (pdir / "manifest.toml").write_text(
        """
[plugin]
name = "broken"
sdk_version = "0.7"

[[kind]]
id = "x"
match = { ext = ".x" }

[[data_hook]]
route = "boom"
sidekick = "nonexistent.module:nope"
"""
    )
    (pdir / "index.js").write_text("// stub\n")

    result = _runner.invoke(_app, ["--doctor", "--plugins-dir", str(tmp_path)])
    assert result.exit_code != 0
    assert result.stdout == ""
    assert "broken" in result.stderr
    assert "JavaScript-only" in result.stderr

    json_result = _runner.invoke(
        _app,
        ["--doctor", "--json", "--plugins-dir", str(tmp_path)],
    )
    assert json_result.exit_code == 1
    payload = json.loads(json_result.stdout)
    assert payload["ok"] is False
    assert any("JavaScript-only" in problem for problem in payload["problems"])
    assert "Logging error" not in json_result.stderr


def test_plugins_diagnostics_do_not_advertise_disabled_local_hooks(tmp_path: Path) -> None:
    pdir = tmp_path / "local-demo"
    pdir.mkdir()
    (pdir / "manifest.toml").write_text(
        """
[plugin]
name = "local-demo"
sdk_version = "0.7"

[[kind]]
id = "x"
match = { ext = ".x" }

[[data_hook]]
route = "boom"
sidekick = "nonexistent.module:nope"
"""
    )
    (pdir / "index.js").write_text("// stub\n")

    json_result = _runner.invoke(
        _app,
        ["--plugins", "--json", "--plugins-dir", str(tmp_path)],
    )
    assert json_result.exit_code == 0
    data = json.loads(json_result.stdout)
    local = next(plugin for plugin in data["plugins"] if plugin["name"] == "local-demo")
    assert local["data_hooks"] == []
    assert local["disabled_data_hooks"] == ["boom"]

    table_result = _runner.invoke(_app, ["--plugins", "--plugins-dir", str(tmp_path)])
    assert table_result.exit_code == 0
    assert "boom" not in table_result.stdout

    show_result = _runner.invoke(
        _app,
        ["--plugin", "local-demo", "--plugins-dir", str(tmp_path)],
    )
    assert show_result.exit_code == 0
    assert "disabled for operator-directory plugins" in show_result.stdout
    assert "nonexistent.module:nope" not in show_result.stdout
