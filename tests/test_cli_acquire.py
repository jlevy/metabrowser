"""CLI --no-serve, file:// cache inspection, and the pin modes. Nothing binds a port."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from metabrowser.cache import acquire as acquire_module
from metabrowser.cache.paths import SOURCES, STAGING, source_record
from metabrowser.cli.main import _app
from metabrowser.errors import CLIError
from metabrowser.git.process import (
    GitCommandError,
    GitError,
    GitOutputTooLargeError,
    GitTimeoutError,
    GitUnavailableError,
    UnsupportedGitVersionError,
    acquisition_allowed,
    detect_git_version,
)
from metabrowser.git.tree_source import GitPath
from tests.test_cache_acquire import (
    _allow_installed_git,
    _git,
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
    url = _file_url(_origin(tmp_path))
    result = runner.invoke(_app, [url, "--no-serve"])
    assert result.exit_code == 0, result.output
    assert "Serving" not in result.output
    assert "acquired: " in result.output
    assert "slug: " in result.output
    assert "store: sha256:" in result.output
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
    url = _file_url(_origin(tmp_path))
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
    url = _file_url(_origin(tmp_path))
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
def test_file_url_api_applies_the_content_trust_flags(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``--untrusted`` reaches the capability block on the acquire path too.

    ``--api`` accepts the content-trust flags, so accepting them and then not
    applying them on a ``file://`` source would drop the operator's decision
    silently.
    """
    from metabrowser.capabilities import get_capabilities

    _isolate_home(tmp_path, monkeypatch)
    url = _file_url(_origin(tmp_path))
    result = runner.invoke(_app, [url, "--api", "/api/cache/layout", "--untrusted"])
    assert result.exit_code == 0, result.output
    assert get_capabilities().active_content is False
    assert get_capabilities().mutations is False


@posix_only
@pytest.mark.parametrize(
    ("flags", "env"),
    [
        ([], {}),
        (["--untrusted"], {}),
        ([], {"METAB_ACTIVE_CONTENT": "1", "METAB_ALLOW_EDITS": "1"}),
        ([], {"METAB_UNTRUSTED": "0"}),
    ],
    ids=["default", "explicit", "env-enables", "env-trusted"],
)
def test_pin_api_always_runs_under_the_untrusted_profile(
    flags: list[str],
    env: dict[str, str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Acquired content is third-party, so no flag or variable lifts the profile.

    ``/api/capabilities`` is the wire form, so this reads the answer the
    browser would read rather than a process global.
    """
    _isolate_home(tmp_path, monkeypatch)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    url = _file_url(_origin(tmp_path))
    result = runner.invoke(_app, [url, "--api", "/api/capabilities", *flags])
    assert result.exit_code == 0, result.output
    assert '"active_content": false' in result.output
    assert '"mutations": false' in result.output


@posix_only
@pytest.mark.parametrize("mode", [["--api", "/api/capabilities"], ["--show", "README"]])
def test_pin_refuses_allow_edits_instead_of_dropping_it(
    mode: list[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = _isolate_home(tmp_path, monkeypatch)
    url = _file_url(_origin(tmp_path))
    result = runner.invoke(_app, [url, *mode, "--allow-edits"])
    assert isinstance(result.exception, CLIError)
    assert "--allow-edits is not available on an acquired Git source" in str(result.exception)
    assert not home.exists()


@posix_only
def test_pin_show_runs_under_the_untrusted_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from metabrowser.capabilities import get_capabilities

    _isolate_home(tmp_path, monkeypatch)
    monkeypatch.setenv("METAB_ACTIVE_CONTENT", "1")
    url = _file_url(_origin(tmp_path))
    result = runner.invoke(_app, [url, "--show", "README"])
    assert result.exit_code == 0, result.output
    assert get_capabilities().active_content is False
    assert get_capabilities().mutations is False


@posix_only
def test_a_pin_in_a_populated_cache_sees_only_its_own_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Another cached source's objects are unreachable from a pin's content routes."""
    home = _isolate_home(tmp_path, monkeypatch)
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    first_url = _file_url(_origin(first))
    second_origin = _origin(second)
    work = second / "work"
    (work / "OTHER").write_text("other source\n", encoding="utf-8")
    _git(work, "add", "OTHER")
    _git(work, "commit", "-qm", "second")
    _git(work, "push", "-q", str(second_origin), "HEAD:topic")
    assert runner.invoke(_app, [_file_url(second_origin), "--no-serve"]).exit_code == 0
    assert len([p for p in (home / SOURCES).iterdir() if p.is_dir()]) == 1

    tree = runner.invoke(_app, [first_url, "--api", "/api/tree?depth=1"])
    assert tree.exit_code == 0, tree.output
    assert "README" in tree.output
    assert "OTHER" not in tree.output
    other_wire = GitPath.from_segments(b"OTHER").to_wire()
    missing = runner.invoke(_app, [first_url, "--api", f"/api/file?path={other_wire}"])
    assert "other source" not in missing.output
    assert len([p for p in (home / SOURCES).iterdir() if p.is_dir()]) == 2


@posix_only
def test_file_url_api_tree_attaches_the_default_pin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = _isolate_home(tmp_path, monkeypatch)
    url = _file_url(_origin(tmp_path))
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
    url = _file_url(_origin(tmp_path))
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
@pytest.mark.parametrize(
    "url", ["https://example.com/owner/repo.git", "ssh://git@example.com/o/r.git"]
)
def test_serve_stays_closed_to_https_and_ssh_without_creating_the_home(
    url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("METABROWSER_HOME", str(home))
    result = runner.invoke(_app, [url, "--no-open"])
    assert isinstance(result.exception, CLIError)
    assert "Git sources are not served yet" in str(result.exception)
    assert "https and ssh stay closed" in str(result.exception)
    assert not home.exists()


@posix_only
@pytest.mark.parametrize("mode", [["--no-open"], ["--check-api"]])
def test_serve_and_check_api_refuse_allow_edits_before_acquiring(
    mode: list[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = _isolate_home(tmp_path, monkeypatch)
    url = _file_url(_origin(tmp_path))
    result = runner.invoke(_app, [url, *mode, "--allow-edits"])
    assert isinstance(result.exception, CLIError)
    assert "--allow-edits is not available on an acquired Git source" in str(result.exception)
    assert not home.exists()


@posix_only
def test_walk_refuses_a_git_source_and_names_the_tree_route(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The walker reads a filesystem; a pin's complete listing is ``/api/tree``."""

    home = _isolate_home(tmp_path, monkeypatch)
    url = _file_url(_origin(tmp_path))
    result = runner.invoke(_app, [url, "--walk"])
    assert isinstance(result.exception, CLIError)
    assert "--walk runs the filesystem inventory walker" in str(result.exception)
    assert "--api '/api/tree?depth=N'" in str(result.exception)
    assert not home.exists()


@posix_only
def test_check_api_runs_the_navigation_scenario_on_the_pin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The live filter's typed refusal is the pin's pass, not a failure."""

    from metabrowser.capabilities import get_capabilities

    _isolate_home(tmp_path, monkeypatch)
    monkeypatch.setenv("METAB_ACTIVE_CONTENT", "1")
    url = _file_url(_origin(tmp_path))
    result = runner.invoke(_app, [url, "--check-api"])
    assert result.exit_code == 0, result.output
    assert f"api check: {url}" in result.output
    assert "live filter: 409; unsupported_for_subject" in result.output
    assert "final nav: 200; rows=1; files=1; size=6; index=done" in result.output
    assert "result: pass" in result.output
    assert get_capabilities().active_content is False


@posix_only
def test_api_on_a_local_root_sees_a_prior_no_serve_acquire(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = _isolate_home(tmp_path, monkeypatch)
    url = _file_url(_origin(tmp_path))
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
    url = _file_url(_origin(tmp_path))
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
    url = _file_url(_origin(tmp_path))
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
    url = _file_url(_origin(tmp_path))
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
    url = _file_url(_origin(tmp_path))
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
    first_url = _file_url(_origin(tmp_path))
    first = runner.invoke(_app, [first_url, "--no-serve"])
    assert first.exit_code == 0, first.output
    other = tmp_path / "other"
    other.mkdir()
    other_url = _file_url(_origin(other))
    sources_before = {path.name for path in (home / SOURCES).iterdir() if path.is_dir()}
    _remove_owner_write(home)
    try:
        result = runner.invoke(_app, [other_url, "--no-serve"])
        assert isinstance(result.exception, CLIError)
        assert list((home / STAGING).iterdir()) == []
        assert {path.name for path in (home / SOURCES).iterdir() if path.is_dir()} == sources_before
    finally:
        _restore_owner_write(home)


def _git_failure(kind: str, args: list[str]) -> GitError:
    """The error ``run_git`` raises for *kind*, with its real path-bearing message."""
    command = " ".join(args)
    if kind == "timeout":
        return GitTimeoutError(f"git {command} exceeded 900s and was terminated")
    if kind == "too-large":
        return GitOutputTooLargeError(f"git {command} produced more than 1 bytes on stdout")
    if kind == "unavailable":
        return GitUnavailableError(f"could not run git: [Errno 2] No such file: {args[-1]!r}")
    return GitCommandError(args, 128, f"fatal: cannot mkdir {args[-1]}")


@posix_only
def test_git_failures_during_acquisition_are_distinct_path_free_cli_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = _isolate_home(tmp_path, monkeypatch)
    url = _file_url(_origin(tmp_path))
    real_run = acquire_module._run
    messages: dict[str, str] = {}
    for kind in ("timeout", "too-large", "unavailable", "command"):

        async def fail_init(
            args: list[str],
            *,
            cwd: Path | None = None,
            git_dir: Path | None = None,
            kind: str = kind,
        ) -> bytes:
            if args[0] == "init":
                raise _git_failure(kind, args)
            return await real_run(args, cwd=cwd, git_dir=git_dir)

        monkeypatch.setattr(acquire_module, "_run", fail_init)
        result = runner.invoke(_app, [url, "--no-serve"])
        assert isinstance(result.exception, CLIError), (kind, result.exception)
        assert isinstance(result.exception.__cause__, GitError)
        message = str(result.exception)
        assert str(tmp_path) not in message
        assert str(tmp_path.resolve()) not in message
        assert "repository.git" not in message
        assert list((home / STAGING).iterdir()) == []
        assert list((home / SOURCES).iterdir()) == []
        messages[kind] = message
    assert len(set(messages.values())) == len(messages)
    assert "900" in messages["timeout"]


@posix_only
def test_pin_html_offers_only_source_under_the_forced_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A pin never offers HTML preview, so it cannot 404 on a relative reference (mb-g5je)."""
    _isolate_home(tmp_path, monkeypatch)
    origin = _origin(tmp_path)
    work = tmp_path / "work"
    (work / "page.html").write_text('<img src="logo.png"><a href="b.html">b</a>\n')
    _git(work, "add", "page.html")
    _git(work, "commit", "-qm", "page")
    _git(work, "push", "-q", str(origin), "HEAD:topic")
    result = runner.invoke(_app, [_file_url(origin), "--show", "page.html"])
    assert result.exit_code == 0, result.output
    assert "kind: html" in result.output
    assert "views: source (default)" in result.output
    assert "preview" not in result.output
