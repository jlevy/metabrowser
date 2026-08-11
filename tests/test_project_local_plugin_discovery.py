"""Served-root and user-home plugins are never discovered implicitly.

Implicit discovery from ``<served-root>/.metabrowser/plugins/`` or
``~/.metabrowser/plugins/`` would let viewed data opt itself into running JavaScript in
the Metabrowser page. The only operator-supplied source is therefore the
``--plugins-dir`` CLI flag merged with ``METABROWSER_PLUGINS_DIRS`` (loaded
from ``.env`` / ``.env.local``).

These tests guard that trust boundary: a plugin under ``<served-root>/.metabrowser/plugins/``
or ``~/.metabrowser/plugins/`` is NOT loaded by default. The same plugin IS
loaded when its parent directory is explicitly named via ``extra_dirs``.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from metabrowser.plugin_loader.discovery import discover_plugins


def _make_plugin(parent: Path, name: str = "local-demo") -> Path:
    plug = parent / name
    plug.mkdir(parents=True)
    (plug / "manifest.toml").write_text(
        f'[plugin]\nname = "{name}"\n[[kind]]\nid = "demo"\nmatch = {{ ext = ".demo" }}\n'
    )
    (plug / "index.js").write_text("// stub\n")
    return plug


def test_project_local_plugins_dir_is_not_auto_discovered(tmp_path: Path) -> None:
    """A plugin in <served-root>/.metabrowser/plugins/ must not load by default."""
    project_local = tmp_path / ".metabrowser" / "plugins"
    project_local.mkdir(parents=True)
    _make_plugin(project_local, "auto-demo")

    # No extra_dirs — auto-demo must NOT be picked up.
    result = discover_plugins()
    names = [p.name for p in result.plugins]
    assert "auto-demo" not in names, (
        "project-local plugins must NOT auto-discover; the trust boundary requires "
        f"operator opt-in via --plugins-dir / METABROWSER_PLUGINS_DIRS. Loaded: {names!r}"
    )


def test_extra_dirs_loads_plugin(tmp_path: Path) -> None:
    """Same plugin, explicitly named via extra_dirs, IS discovered."""
    parent = tmp_path / "plugins"
    parent.mkdir(parents=True)
    _make_plugin(parent, "explicit-demo")

    result = discover_plugins(extra_dirs=[parent])
    names = [p.name for p in result.plugins]
    assert "explicit-demo" in names


def test_metabrowser_plugins_dirs_env_var_drives_discovery(tmp_path: Path) -> None:
    """METABROWSER_PLUGINS_DIRS in the environment loads plugins via server.py."""
    parent = tmp_path / "plugins"
    parent.mkdir(parents=True)
    _make_plugin(parent, "env-demo")

    env = os.environ.copy()
    env["METABROWSER_PLUGINS_DIRS"] = str(parent)

    code = (
        "import json, metabrowser.server as s; "
        "print(json.dumps([p.name for p in s._LOADED_PLUGINS]))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, (
        f"subprocess failed: stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    last_line = result.stdout.strip().splitlines()[-1]
    names = json.loads(last_line)
    assert "env-demo" in names, (
        f"server.py must read METABROWSER_PLUGINS_DIRS at module load; loaded plugins: {names}"
    )


def test_server_import_expands_env_plugin_paths(tmp_path: Path) -> None:
    """Direct server imports canonicalize env paths without requiring the CLI."""
    home = tmp_path / "home"
    parent = home / "plugins"
    parent.mkdir(parents=True)
    _make_plugin(parent, "expanded-env-demo")

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["METABROWSER_PLUGINS_DIRS"] = "~/plugins"

    code = (
        "import json, metabrowser.server as s; "
        "print(json.dumps([p.name for p in s._LOADED_PLUGINS]))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, (
        f"subprocess failed: stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    names = json.loads(result.stdout.strip().splitlines()[-1])
    assert "expanded-env-demo" in names


def test_server_import_rejects_missing_env_plugin_path(tmp_path: Path) -> None:
    """Direct server imports fail loudly for invalid operator configuration."""
    env = os.environ.copy()
    env["METABROWSER_PLUGINS_DIRS"] = str(tmp_path / "missing-plugins")

    result = subprocess.run(
        [sys.executable, "-c", "import metabrowser.server"],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode != 0
    assert "plugin directory not a directory" in result.stderr


def test_pytest_collection_ignores_operator_plugin_env(tmp_path: Path) -> None:
    """Repository tests must not inherit an operator's plugin configuration."""
    env = os.environ.copy()
    env["METABROWSER_PLUGINS_DIRS"] = str(tmp_path / "missing-plugins")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "tests/test_api_file_frontmatter.py",
        ],
        cwd=Path(__file__).parents[1],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, (
        f"pytest collection failed: stdout={result.stdout!r} stderr={result.stderr!r}"
    )


def test_user_home_plugins_dir_is_not_auto_discovered(tmp_path: Path, monkeypatch) -> None:
    """A plugin in ~/.metabrowser/plugins/ must not load by default either.

    Uses HOME monkey-patch so the test doesn't depend on / mutate the real
    user's home directory.
    """
    fake_home = tmp_path / "fake-home"
    fake_home.mkdir(parents=True)
    user_local = fake_home / ".metabrowser" / "plugins"
    user_local.mkdir(parents=True)
    _make_plugin(user_local, "user-home-demo")

    monkeypatch.setenv("HOME", str(fake_home))

    result = discover_plugins()
    names = [p.name for p in result.plugins]
    assert "user-home-demo" not in names, (
        f"user-home plugins must NOT auto-discover; loaded: {names!r}"
    )
