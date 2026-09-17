"""The application-home resolver, the ``f01`` skeleton, and its separation from browsing.

Every home here is temporary. The browsing tests point ``METABROWSER_HOME`` at a missing,
a permissive, and a symlinked directory, run ordinary local browsing both in process and
as a real ``metab`` subprocess, and prove the application home was never resolved,
validated, or created.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from metabrowser import home as home_module
from metabrowser.cli.main import _app
from metabrowser.home import (
    CACHEDIR_TAG_CONTENT,
    CACHEDIR_TAG_SIGNATURE,
    DEFAULT_HOME_NAME,
    F01_DIRECTORIES,
    METABROWSER_HOME_ENV,
    ApplicationHomeError,
    PrivateStorageError,
    PrivateStorageViolation,
    application_home,
    ensure_home,
    write_private_file_atomic,
)

posix_only = pytest.mark.skipif(os.name != "posix", reason="owner-only storage is POSIX-only")
CHILD_TIMEOUT = 120


def _mode(path: Path) -> int:
    return stat.S_IMODE(os.lstat(path).st_mode)


def _snapshot(root: Path) -> dict[str, tuple[int, int]]:
    """Every entry below *root* (links not followed) with its mode and inode."""

    entries = {".": (os.lstat(root).st_mode, os.lstat(root).st_ino)}
    for path in sorted(root.rglob("*")):
        status = os.lstat(path)
        entries[str(path.relative_to(root))] = (status.st_mode, status.st_ino)
    return entries


# ── Resolution ─────────────────────────────────────────────────────


def test_the_default_home_is_dot_metabrowser_in_the_user_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))

    assert application_home({}) == tmp_path / DEFAULT_HOME_NAME
    assert not (tmp_path / DEFAULT_HOME_NAME).exists()


def test_metabrowser_home_overrides_the_default_without_touching_it(tmp_path: Path) -> None:
    chosen = tmp_path / "missing" / "home"

    assert application_home({METABROWSER_HOME_ENV: str(chosen)}) == chosen
    assert not (tmp_path / "missing").exists()


def test_the_process_environment_is_the_default_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(METABROWSER_HOME_ENV, str(tmp_path / "home"))

    assert application_home() == tmp_path / "home"


@pytest.mark.parametrize("value", ["", "relative/home", "~/home", "/tmp/../home"])
def test_an_unusable_metabrowser_home_is_refused_rather_than_ignored(value: str) -> None:
    with pytest.raises(ApplicationHomeError, match="METABROWSER_HOME"):
        application_home({METABROWSER_HOME_ENV: value})


# ── Skeleton ───────────────────────────────────────────────────────


@posix_only
def test_ensure_home_creates_the_private_f01_skeleton_and_cachedir_tag(tmp_path: Path) -> None:
    home = tmp_path / "home"

    cache_root = ensure_home(home)

    assert cache_root == home / "cache"
    assert _mode(home) == 0o700
    for directory in F01_DIRECTORIES:
        assert (home / directory).is_dir(), directory
        assert _mode(home / directory) == 0o700, directory
    tag = home / "cache/CACHEDIR.TAG"
    assert tag.read_bytes() == CACHEDIR_TAG_CONTENT
    assert tag.read_bytes().startswith(CACHEDIR_TAG_SIGNATURE)
    assert _mode(tag) == 0o600
    assert not (home / "config.yml").exists()
    assert not (home / "cache/layout.yml").exists()


@posix_only
def test_ensure_home_is_idempotent_and_keeps_a_valid_tag(tmp_path: Path) -> None:
    home = tmp_path / "home"
    ensure_home(home)
    tag = home / "cache/CACHEDIR.TAG"
    write_private_file_atomic(home, "cache/CACHEDIR.TAG", CACHEDIR_TAG_SIGNATURE + b"\n# mine\n")
    before = _snapshot(home)

    ensure_home(home)

    assert _snapshot(home) == before
    assert tag.read_bytes().endswith(b"# mine\n")


@posix_only
@pytest.mark.parametrize("content", [b"", b"Signature: 00000000\n"], ids=["torn", "foreign"])
def test_ensure_home_replaces_a_tag_without_the_signature(tmp_path: Path, content: bytes) -> None:
    home = tmp_path / "home"
    ensure_home(home)
    write_private_file_atomic(home, "cache/CACHEDIR.TAG", content)

    ensure_home(home)

    assert (home / "cache/CACHEDIR.TAG").read_bytes() == CACHEDIR_TAG_CONTENT


@posix_only
def test_ensure_home_refuses_a_permissive_home_without_repairing_it(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    home.chmod(0o755)

    with pytest.raises(PrivateStorageError) as refused:
        ensure_home(home)

    assert refused.value.violation is PrivateStorageViolation.PERMISSIVE
    assert _mode(home) == 0o755
    assert list(home.iterdir()) == []


# ── Local browsing never touches the application home ──────────────


def _browsing_root(tmp_path: Path) -> Path:
    root = tmp_path / "browse"
    root.mkdir()
    (root / "README.md").write_text("# Local\n")
    return root


def _home_variants(tmp_path: Path) -> dict[str, Path]:
    permissive = tmp_path / "permissive-home"
    permissive.mkdir()
    permissive.chmod(0o777)
    target = tmp_path / "symlink-target"
    target.mkdir()
    target.chmod(0o755)
    link = tmp_path / "symlinked-home"
    link.symlink_to(target, target_is_directory=True)
    return {
        "missing": tmp_path / "missing-home",
        "permissive": permissive,
        "symlinked": link,
    }


_FORBIDDEN_CALLS = (
    "application_home",
    "ensure_home",
    "validate_private_home",
    "ensure_private_directory",
    "open_private_file",
    "write_private_file_atomic",
)


@pytest.mark.parametrize("variant", ["missing", "permissive", "symlinked"])
def test_local_browsing_in_process_never_calls_the_application_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, variant: str
) -> None:
    root = _browsing_root(tmp_path)
    chosen = _home_variants(tmp_path)[variant]
    monkeypatch.setenv(METABROWSER_HOME_ENV, str(chosen))
    before = _snapshot(tmp_path)
    calls: list[str] = []

    def forbid(name: str) -> Any:
        def refuse(*_args: object, **_kwargs: object) -> Any:
            calls.append(name)
            raise AssertionError(f"local browsing called metabrowser.home.{name}")

        return refuse

    for name in _FORBIDDEN_CALLS:
        monkeypatch.setattr(home_module, name, forbid(name))
    runner = CliRunner()

    with (
        patch("metabrowser.cli.serve._QuietForceExitServer"),
        patch("metabrowser.cli.serve.find_available_local_port", return_value=8411),
    ):
        served = runner.invoke(_app, [str(root), "--no-open"])
    api = runner.invoke(_app, [str(root), "--api", "/api/tree?depth=1"])
    shown = runner.invoke(_app, [str(root), "--show", "README.md"])

    assert served.exit_code == 0, served.output
    assert api.exit_code == 0, api.output
    assert shown.exit_code == 0, shown.output
    assert calls == []
    assert _snapshot(tmp_path) == before


@posix_only
@pytest.mark.parametrize("variant", ["missing", "permissive", "symlinked"])
def test_metab_browsing_a_local_directory_never_creates_or_imports_the_home(
    tmp_path: Path, variant: str
) -> None:
    root = _browsing_root(tmp_path)
    chosen = _home_variants(tmp_path)[variant]
    before = _snapshot(tmp_path)
    script = textwrap.dedent(
        """
        import atexit, json, sys
        def report():
            loaded = sorted(
                name for name in sys.modules
                if name == "metabrowser.home"
                or name in {
                    "metabrowser.cache.atomic",
                    "metabrowser.cache.layout",
                    "metabrowser.cache.locks",
                    "metabrowser.cache.probe",
                    "metabrowser.cache.reclaim",
                }
            )
            sys.stderr.write("\\nloaded-modules:" + json.dumps(loaded) + "\\n")
        atexit.register(report)
        sys.argv = ["metab", *sys.argv[1:]]
        from metabrowser.cli.entrypoint import main
        main()
        """
    )
    environment = {**os.environ, METABROWSER_HOME_ENV: str(chosen)}

    result = subprocess.run(
        [sys.executable, "-c", script, str(root), "--api", "/api/tree?depth=1"],
        capture_output=True,
        text=True,
        env=environment,
        timeout=CHILD_TIMEOUT,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert '"tree"' in result.stdout
    loaded = json.loads(result.stderr.rpartition("loaded-modules:")[2])
    assert loaded == []
    assert _snapshot(tmp_path) == before
