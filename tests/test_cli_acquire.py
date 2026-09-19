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
from metabrowser.git.process import (
    UnsupportedGitVersionError,
    acquisition_allowed,
    detect_git_version,
)
from tests.test_cache_acquire import (
    _allow_installed_git,
    _origin,
    _remove_owner_write,
    _restore_owner_write,
)

posix_only = pytest.mark.skipif(os.name != "posix", reason="owner-only cache is POSIX-only")
skip_as_root = pytest.mark.skipif(
    os.geteuid() == 0, reason="root is never denied by modes, so a denial cannot be staged"
)

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
def test_file_url_api_tree_attaches_the_default_pin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = _isolate_home(tmp_path, monkeypatch)
    url = _file_url(_origin(tmp_path, allow_filter=False))
    result = runner.invoke(_app, [url, "--api", "/api/tree"])
    assert result.exit_code == 0, result.output
    assert "Serving" not in result.output
    assert '"subject": "git_revision"' in result.output
    assert '"kind": "tree"' in result.output
    assert "README" in result.output
    assert str(home) not in result.output
    assert "repository.git" not in result.output


@posix_only
def test_file_url_show_reports_the_pin_blob(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _isolate_home(tmp_path, monkeypatch)
    url = _file_url(_origin(tmp_path, allow_filter=False))
    result = runner.invoke(_app, [url, "--show", "README"])
    assert result.exit_code == 0, result.output
    assert "Serving" not in result.output
    assert "show: README" in result.output
    assert "route: /view/" in result.output
    assert "kind: text" in result.output
    assert "model: text envelope" in result.output


@posix_only
def test_https_show_stays_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = _isolate_home(tmp_path, monkeypatch)
    result = runner.invoke(_app, ["https://example.com/owner/repo.git", "--show", "README"])
    assert isinstance(result.exception, CLIError)
    assert "https Git sources are not opened yet" in str(result.exception)
    assert not home.exists()


@posix_only
def test_https_api_tree_stays_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = _isolate_home(tmp_path, monkeypatch)
    result = runner.invoke(_app, ["https://example.com/owner/repo.git", "--api", "/api/tree"])
    assert isinstance(result.exception, CLIError)
    assert "https Git sources are not served yet" in str(result.exception)
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


@posix_only
def test_no_serve_refuses_below_floor_git_without_creating_the_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("METABROWSER_HOME", str(home))

    def refuse() -> tuple[int, int, int]:
        raise UnsupportedGitVersionError("git version 2.39.5", "2.43.7")

    monkeypatch.setattr("metabrowser.cache.acquire.require_acquisition_git", refuse)
    url = _file_url(_origin(tmp_path, allow_filter=False))
    result = runner.invoke(_app, [url, "--no-serve"])
    assert isinstance(result.exception, CLIError)
    assert "unsupported Git version" in str(result.exception)
    assert not home.exists()


@posix_only
def test_no_serve_refuses_below_floor_git_without_writing_an_empty_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("METABROWSER_HOME", str(home))

    def refuse() -> tuple[int, int, int]:
        raise UnsupportedGitVersionError("git version 2.39.5", "2.43.7")

    monkeypatch.setattr("metabrowser.cache.acquire.require_acquisition_git", refuse)
    url = _file_url(_origin(tmp_path, allow_filter=False))
    result = runner.invoke(_app, [url, "--no-serve"])
    assert isinstance(result.exception, CLIError)
    assert "unsupported Git version" in str(result.exception)
    assert list(home.iterdir()) == []


@posix_only
def test_installed_git_below_the_floor_is_refused_by_no_serve(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    version, _raw = detect_git_version()
    if acquisition_allowed(version):
        pytest.skip("installed git meets the acquisition floor")
    home = tmp_path / "home"
    monkeypatch.setenv("METABROWSER_HOME", str(home))
    url = _file_url(_origin(tmp_path, allow_filter=False))
    result = runner.invoke(_app, [url, "--no-serve"])
    assert isinstance(result.exception, CLIError)
    assert "unsupported Git version" in str(result.exception)
    assert not home.exists()


@posix_only
@skip_as_root
def test_no_serve_reuses_a_cache_hit_when_the_home_has_no_owner_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = _isolate_home(tmp_path, monkeypatch)
    url = _file_url(_origin(tmp_path, allow_filter=False))
    first = runner.invoke(_app, [url, "--no-serve"])
    assert first.exit_code == 0, first.output
    _remove_owner_write(home)
    try:
        second = runner.invoke(_app, [url, "--no-serve"])
        assert second.exit_code == 0, second.output
        assert second.output == first.output
        assert list((home / STAGING).iterdir()) == []
    finally:
        _restore_owner_write(home)


@posix_only
@skip_as_root
def test_no_serve_miss_against_a_home_without_owner_write_does_not_fetch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = _isolate_home(tmp_path, monkeypatch)
    first_url = _file_url(_origin(tmp_path, allow_filter=False))
    first = runner.invoke(_app, [first_url, "--no-serve"])
    assert first.exit_code == 0, first.output
    other = tmp_path / "other"
    other.mkdir()
    other_url = _file_url(_origin(other, allow_filter=False))
    sources_before = {path.name for path in (home / SOURCES).iterdir() if path.is_dir()}
    _remove_owner_write(home)
    try:
        result = runner.invoke(_app, [other_url, "--no-serve"])
        assert isinstance(result.exception, CLIError)
        assert list((home / STAGING).iterdir()) == []
        assert {path.name for path in (home / SOURCES).iterdir() if path.is_dir()} == sources_before
    finally:
        _restore_owner_write(home)
