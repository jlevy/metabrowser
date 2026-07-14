"""Tests for the metabrowser plugins diagnostic CLI.

Drives ``metabrowser plugins list / show / doctor`` via Typer's CliRunner.
Confirms the discovered set, the JSON output shape, and the doctor's
exit-code contract on broken / valid plugins.
"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from metabrowser.cli.plugins import plugins_app

_runner = CliRunner()


def test_plugins_list_table_includes_builtin_plugins() -> None:
    result = _runner.invoke(plugins_app, ["list"])
    assert result.exit_code == 0
    assert "markdown" in result.stdout
    assert "builtin" in result.stdout
    # Table header
    assert "NAME" in result.stdout
    assert "KINDS" in result.stdout


def test_plugins_list_json_emits_structured_output() -> None:
    result = _runner.invoke(plugins_app, ["list", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "plugins" in data
    assert "errors" in data
    names = {p["name"] for p in data["plugins"]}
    assert "markdown" in names
    markdown = next(p for p in data["plugins"] if p["name"] == "markdown")
    assert "markdown" in markdown["kinds"]
    assert "rendered" in markdown["views"]


def test_plugins_show_builtin_dumps_manifest() -> None:
    result = _runner.invoke(plugins_app, ["show", "markdown"])
    assert result.exit_code == 0
    assert "name:         markdown" in result.stdout
    assert "markdown/rendered" in result.stdout
    assert "static_root:" in result.stdout


def test_plugins_show_unknown_plugin_errors() -> None:
    result = _runner.invoke(plugins_app, ["show", "no-such-plugin"])
    assert result.exit_code != 0
    # The CLIError from cmd_show propagates through Typer; the runner records
    # it as result.exception.
    assert "no-such-plugin" in str(result.exception)


def test_plugins_doctor_exits_zero_on_clean_install() -> None:
    result = _runner.invoke(plugins_app, ["doctor"])
    assert result.exit_code == 0
    assert "OK" in result.stdout


def test_plugins_doctor_flags_broken_plugin(tmp_path: Path) -> None:
    """A plugin under --plugins-dir with a broken sidekick reference flags."""
    pdir = tmp_path / "broken"
    pdir.mkdir()
    (pdir / "manifest.toml").write_text(
        """
[plugin]
name = "broken"

[[kind]]
id = "x"
match = { ext = ".x" }

[[data_hook]]
route = "boom"
sidekick = "nonexistent.module:nope"
"""
    )
    (pdir / "index.js").write_text("// stub\n")

    result = _runner.invoke(plugins_app, ["doctor", "--plugins-dir", str(tmp_path)])
    assert result.exit_code != 0
    assert "broken" in result.stdout
    assert "nonexistent.module" in result.stdout
