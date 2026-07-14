"""``.env`` / ``.env.local`` files are honored by metabrowser CLI bootstrap.

Phase 4: the trust cut moved metabrowser plugin discovery to opt-in.
Operators name plugin parents via ``--plugins-dir`` flags or set
``METABROWSER_PLUGINS_DIRS`` in ``.env`` / ``.env.local``.

These tests exercise the dotenv loader and the CLI's interaction with
it. We use python-dotenv under the hood; the wrapper in
``metabrowser.dotenv`` only adds the .env-then-.env.local search order
+ the ``override=False`` semantics (shell-set values win over file
values).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from metabrowser.dotenv import load_dotenv_chain


def test_load_dotenv_chain_picks_up_env_var(tmp_path: Path, monkeypatch) -> None:
    """A `.env` in the cwd's ancestors is loaded into os.environ."""
    (tmp_path / ".env").write_text("METABROWSER_TEST_VAR=hello\n")

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("METABROWSER_TEST_VAR", raising=False)

    applied = load_dotenv_chain()
    assert any(p.name == ".env" for p in applied)
    assert os.environ.get("METABROWSER_TEST_VAR") == "hello"


def test_dotenv_local_overlays_dotenv(tmp_path: Path, monkeypatch) -> None:
    """`.env.local` runs after `.env`; both contribute via setdefault, so
    the first non-empty value wins. Local fills gaps left by `.env`."""
    (tmp_path / ".env").write_text("ONLY_IN_ENV=base\n")
    (tmp_path / ".env.local").write_text("ONLY_IN_LOCAL=overlay\n")

    monkeypatch.chdir(tmp_path)
    for k in ("ONLY_IN_ENV", "ONLY_IN_LOCAL"):
        monkeypatch.delenv(k, raising=False)

    load_dotenv_chain()
    assert os.environ.get("ONLY_IN_ENV") == "base"
    assert os.environ.get("ONLY_IN_LOCAL") == "overlay"


def test_shell_export_wins_over_dotenv(tmp_path: Path, monkeypatch) -> None:
    """`override=False`: a value already in os.environ beats both .env
    and .env.local."""
    (tmp_path / ".env").write_text("SHELL_WINS=from_env\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SHELL_WINS", "from_shell")

    load_dotenv_chain()
    assert os.environ.get("SHELL_WINS") == "from_shell"


def test_dotenv_drives_plugin_discovery(tmp_path: Path) -> None:
    """End-to-end: a `.env` setting METABROWSER_PLUGINS_DIRS makes that
    directory's plugins load through the regular metabrowser bootstrap.

    Uses subprocess so the python-dotenv side effects don't leak into
    other tests in the suite.
    """
    plugins_parent = tmp_path / "plugins"
    plugins_parent.mkdir()
    plugin = plugins_parent / "envloaded"
    plugin.mkdir()
    (plugin / "manifest.toml").write_text(
        '[plugin]\nname = "envloaded"\n[[kind]]\nid = "envk"\nmatch = { ext = ".envk" }\n'
    )
    (plugin / "index.js").write_text("// stub\n")

    cwd = tmp_path / "workdir"
    cwd.mkdir()
    (cwd / ".env").write_text(f"METABROWSER_PLUGINS_DIRS={plugins_parent}\n")

    env = os.environ.copy()
    env.pop("METABROWSER_PLUGINS_DIRS", None)

    code = (
        "from metabrowser.dotenv import load_dotenv_chain; "
        "load_dotenv_chain(); "
        "import metabrowser.server as s; "
        "import json; print(json.dumps([p.name for p in s._LOADED_PLUGINS]))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        env=env,
        cwd=cwd,
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
    assert "envloaded" in names, f"`.env` should drive plugin discovery; loaded plugins: {names}"
