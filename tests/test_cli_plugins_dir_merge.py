"""``--plugins-dir`` and ``METABROWSER_PLUGINS_DIRS`` are additive (3a).

Previously the CLI unconditionally
overwrote ``METABROWSER_PLUGINS_DIRS`` from the ``--plugins-dir`` flag,
silently dropping any pre-set env-var value. Operators who exported the
env var in their shell rc and ALSO passed ``--plugins-dir`` lost the
env-var dirs.

Fix: env-var dirs come first, CLI dirs are appended; duplicates dropped.
This test exercises the CLI path via subprocess so we get a clean process
+ clean module state + verify discovery actually picks up plugins from
both sources.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def _make_plugin(root: Path, name: str, ext: str = ".demo") -> None:
    plug = root / name
    plug.mkdir(parents=True)
    (plug / "manifest.toml").write_text(
        f'[plugin]\nname = "{name}"\n[[kind]]\nid = "demo-{name}"\nmatch = {{ ext = "{ext}" }}\n'
    )
    (plug / "index.js").write_text("// stub\n")


def _load_plugin_names(env: dict[str, str]) -> list[str]:
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
    return json.loads(last_line)


def test_env_var_alone_loads_plugin(tmp_path: Path) -> None:
    """Setting METABROWSER_PLUGINS_DIRS without any --plugins-dir works."""
    env_root = tmp_path / "env-dir"
    env_root.mkdir()
    _make_plugin(env_root, "from-env")

    env = os.environ.copy()
    env["METABROWSER_PLUGINS_DIRS"] = str(env_root)
    env.pop("METABROWSER_ROOT", None)

    names = _load_plugin_names(env)
    assert "from-env" in names


def test_serve_expands_env_plugin_paths_before_server_import(tmp_path: Path) -> None:
    """The serve path normalizes env-only directories just like plugins commands."""
    served_root = tmp_path / "served"
    served_root.mkdir()

    home = tmp_path / "home"
    env_root = home / "plugins"
    env_root.mkdir(parents=True)
    _make_plugin(env_root, "from-expanded-env")

    wrapper = (
        "import json, os\n"
        "from pathlib import Path\n"
        "from unittest.mock import patch\n"
        f"served_root = Path({str(served_root)!r})\n"
        "from metabrowser.cli.serve import run_serve\n"
        "with (\n"
        "    patch('metabrowser.cli.serve._QuietForceExitServer'),\n"
        "    patch('metabrowser.cli.serve.find_available_local_port', return_value=8411),\n"
        "    patch('threading.Thread'),\n"
        "):\n"
        "    run_serve(\n"
        "        root=served_root, path='', port=8411, host='127.0.0.1',\n"
        "        no_open=True, plugins_dir=None, log_level='',\n"
        "    )\n"
        "import metabrowser.server as server\n"
        "print(json.dumps({\n"
        "    'plugin_dirs': os.environ['METABROWSER_PLUGINS_DIRS'],\n"
        "    'plugin_names': [p.name for p in server._LOADED_PLUGINS],\n"
        "}))\n"
    )

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["METABROWSER_PLUGINS_DIRS"] = "~/plugins"

    result = subprocess.run(
        [sys.executable, "-c", wrapper],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, (
        f"subprocess failed: stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    observed = json.loads(result.stdout.strip().splitlines()[-1])
    assert observed["plugin_dirs"] == str(env_root.resolve())
    assert "from-expanded-env" in observed["plugin_names"]


def test_env_var_and_cli_configure_server_before_import(tmp_path: Path) -> None:
    """When both sources name distinct dirs, plugins from both load.

    This exercises serve's env-merge path: simulate ``metab <root>
    --plugins-dir <cli_root>`` with ``METABROWSER_PLUGINS_DIRS=<env_root>``
    pre-set in the env. After the CLI runs, the env var must contain
    BOTH dirs (env_root first, then cli_root).
    """
    served_root = tmp_path / "served"
    served_root.mkdir()

    env_root = tmp_path / "env-dir"
    env_root.mkdir()
    _make_plugin(env_root, "from-env")

    cli_root = tmp_path / "cli-dir"
    cli_root.mkdir()
    _make_plugin(cli_root, "from-cli")

    # Run the CLI as a subprocess so the env-merge logic in
    # cli/serve.py runs naturally (no monkeypatching). We use
    # ``--no-open`` and a wrapper script that runs the CLI and exits
    # before uvicorn starts — by importing the CLI's serve()
    # function directly and inspecting os.environ AFTER it ran the
    # merge. Cheaper than spinning up uvicorn + tearing it down.
    wrapper = (
        "import os, sys, json, logging\n"
        "from pathlib import Path\n"
        "from unittest.mock import patch\n"
        f"served_root = Path({str(served_root)!r})\n"
        f"cli_root = Path({str(cli_root)!r})\n"
        "from metabrowser.cli.serve import run_serve\n"
        "with (\n"
        "    patch('metabrowser.cli.serve._QuietForceExitServer'),\n"
        "    patch('metabrowser.cli.serve.find_available_local_port', return_value=8411),\n"
        "    patch('threading.Thread'),\n"
        "):\n"
        "    run_serve(\n"
        "        root=served_root,\n"
        "        path='',\n"
        "        port=8411,\n"
        "        host='127.0.0.1',\n"
        "        no_open=True,\n"
        "        plugins_dir=[cli_root],\n"
        "        log_level='DEBUG',\n"
        "    )\n"
        "import metabrowser.server as server\n"
        "print(json.dumps({\n"
        "    'plugin_dirs': os.environ['METABROWSER_PLUGINS_DIRS'],\n"
        "    'plugin_names': [p.name for p in server._LOADED_PLUGINS],\n"
        "    'log_level': logging.getLogger('metabrowser').level,\n"
        "}))\n"
    )

    env = os.environ.copy()
    env["METABROWSER_PLUGINS_DIRS"] = str(env_root)

    result = subprocess.run(
        [sys.executable, "-c", wrapper],
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
    observed = json.loads(last_line)
    merged = observed["plugin_dirs"]
    parts = merged.split(os.pathsep)
    assert str(env_root) in parts, f"env_root should appear: {merged!r}"
    assert str(cli_root.resolve()) in parts, f"cli_root should appear: {merged!r}"
    # Order: env first, CLI second.
    assert parts.index(str(env_root)) < parts.index(str(cli_root.resolve()))
    assert "from-env" in observed["plugin_names"]
    assert "from-cli" in observed["plugin_names"]
    assert observed["log_level"] == 10  # logging.DEBUG


def test_cli_dedupes_overlap_with_env(tmp_path: Path) -> None:
    """If the same dir appears in both env and CLI, it's listed once."""
    served_root = tmp_path / "served"
    served_root.mkdir()
    shared = tmp_path / "shared-dir"
    shared.mkdir()

    wrapper = (
        "import os, sys, json\n"
        "from pathlib import Path\n"
        "from unittest.mock import patch\n"
        f"served_root = Path({str(served_root)!r})\n"
        f"shared = Path({str(shared)!r})\n"
        "from metabrowser.cli.serve import run_serve\n"
        "with (\n"
        "    patch('metabrowser.cli.serve._QuietForceExitServer'),\n"
        "    patch('metabrowser.cli.serve.find_available_local_port', return_value=8411),\n"
        "    patch('threading.Thread'),\n"
        "):\n"
        "    run_serve(\n"
        "        root=served_root, path='', port=8411, host='127.0.0.1',\n"
        "        no_open=True, plugins_dir=[shared],\n"
        "    )\n"
        "print(json.dumps(os.environ['METABROWSER_PLUGINS_DIRS']))\n"
    )

    env = os.environ.copy()
    env["METABROWSER_PLUGINS_DIRS"] = str(shared.resolve())

    result = subprocess.run(
        [sys.executable, "-c", wrapper],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0
    last_line = result.stdout.strip().splitlines()[-1]
    merged = json.loads(last_line)
    parts = merged.split(os.pathsep)
    assert parts.count(str(shared.resolve())) == 1, f"shared dir should be deduped, got: {merged!r}"
