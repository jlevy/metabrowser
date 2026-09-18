"""CLI --no-serve and file:// --api cache inspection. No serving."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from metabrowser.cache.paths import SOURCES, STAGING, source_record
from metabrowser.cli.main import _app
from metabrowser.errors import CLIError
from tests.test_cache_acquire import _allow_installed_git, _origin

posix_only = pytest.mark.skipif(os.name != "posix", reason="owner-only cache is POSIX-only")

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git executable is required")

runner = CliRunner()


def _isolate_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    monkeypatch.setenv("METABROWSER_HOME", str(home))
    _allow_installed_git(monkeypatch)
    return home


def _file_url(origin: Path) -> str:
    return f"file://{origin.resolve()}"


@posix_only
def test_no_serve_acquires_a_file_source_and_prints_logical_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = _isolate_home(tmp_path, monkeypatch)
    url = _file_url(_origin(tmp_path, allow_filter=False))
    result = runner.invoke(_app, [url, "--no-serve"])
    assert result.exit_code == 0, result.output
    assert "Serving" not in result.output
    assert "acquired: " in result.output
    assert "slug: " in result.output
    assert "store: sha256:" in result.output
    assert "strategy: full" in result.output
    assert "revision: " in result.output
    assert list((home / STAGING).iterdir()) == []
    assert any((home / SOURCES).iterdir())
    assert "repository.git" not in result.output
    assert str(home) not in result.output


@posix_only
def test_a_second_no_serve_reuses_the_published_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _isolate_home(tmp_path, monkeypatch)
    url = _file_url(_origin(tmp_path, allow_filter=False))
    first = runner.invoke(_app, [url, "--no-serve"])
    second = runner.invoke(_app, [url, "--no-serve"])
    assert first.exit_code == 0, first.output
    assert second.exit_code == 0, second.output
    assert first.output == second.output


@posix_only
def test_file_url_api_cache_layout_acquires_then_inspects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = _isolate_home(tmp_path, monkeypatch)
    url = _file_url(_origin(tmp_path, allow_filter=False))
    result = runner.invoke(_app, [url, "--api", "/api/cache/layout"])
    assert result.exit_code == 0, result.output
    assert "api: /api/cache/layout" in result.output
    assert '"home": "present"' in result.output
    assert '"state": "current"' in result.output
    slug = next(path.name for path in (home / SOURCES).iterdir() if path.is_dir())
    listed = runner.invoke(_app, [url, "--api", "/api/cache/sources"])
    assert listed.exit_code == 0, listed.output
    assert slug in listed.output
    assert '"publication": "published"' in listed.output


@posix_only
def test_file_url_api_tree_is_refused_without_acquiring(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = _isolate_home(tmp_path, monkeypatch)
    url = _file_url(_origin(tmp_path, allow_filter=False))
    result = runner.invoke(_app, [url, "--api", "/api/tree"])
    assert isinstance(result.exception, CLIError)
    message = str(result.exception)
    assert "file Git sources are not served yet" in message
    assert "--api /api/cache/" in message
    assert not home.exists()


@posix_only
def test_serve_file_url_does_not_create_the_application_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("METABROWSER_HOME", str(home))
    result = runner.invoke(_app, ["file:///srv/git/repo.git", "--no-open"])
    assert isinstance(result.exception, CLIError)
    assert "file Git sources are not served yet" in str(result.exception)
    assert not home.exists()


@posix_only
def test_api_on_a_local_root_sees_a_prior_no_serve_acquire(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = _isolate_home(tmp_path, monkeypatch)
    url = _file_url(_origin(tmp_path, allow_filter=False))
    acquired = runner.invoke(_app, [url, "--no-serve"])
    assert acquired.exit_code == 0, acquired.output
    slug = next(
        line.split(": ", 1)[1] for line in acquired.output.splitlines() if line.startswith("slug: ")
    )
    assert (home / source_record(slug, "source.yml")).is_file()
    empty = tmp_path / "empty"
    empty.mkdir()
    listed = runner.invoke(_app, [str(empty), "--api", "/api/cache/source/" + slug])
    assert listed.exit_code == 0, listed.output
    assert slug in listed.output
    assert '"publication": "published"' in listed.output
