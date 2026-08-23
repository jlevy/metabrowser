"""A build that is not exactly a released one has to say so.

The failure these guard against is quiet: `importlib.metadata` reports the
version recorded when the package was installed, so a checkout keeps reporting
its last tag however far the working tree has moved. Two builds under
comparison both claimed the same version once, and nothing on screen
contradicted it.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from metabrowser import build_version


def _git(repository: Path, *arguments: str) -> None:
    subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    """A real repository with one tagged commit."""

    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "test@example.invalid")
    _git(tmp_path, "config", "user.name", "Test")
    (tmp_path / "file.txt").write_text("one\n")
    _git(tmp_path, "add", "file.txt")
    _git(tmp_path, "commit", "-qm", "first")
    _git(tmp_path, "tag", "v1.0.0")
    return tmp_path


@pytest.fixture(autouse=True)
def fresh_caches() -> object:
    """Both answers are cached for the life of a process, so clear them around
    every test rather than leaving one test's repository to answer the next."""

    build_version.source_checkout.cache_clear()
    build_version.build_state.cache_clear()
    yield
    build_version.source_checkout.cache_clear()
    build_version.build_state.cache_clear()


def _state(monkeypatch: pytest.MonkeyPatch, repository: Path | None) -> str:
    """build_state() as it would read *repository*.

    Only ``source_checkout`` is replaced; ``build_state`` stays the real cached
    function, so its cache is what needs clearing and the fixture does that.
    """

    monkeypatch.setattr(build_version, "source_checkout", lambda: repository)
    build_version.build_state.cache_clear()
    return build_version.build_state()


def test_an_installed_release_is_reported_exactly_as_installed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The common case, and the one where the recorded version is the truth.

    An installed package is not a checkout, so there is nothing to add and
    nothing to get wrong.
    """

    assert _state(monkeypatch, None) == ""
    monkeypatch.setattr(build_version, "build_state", lambda: "")
    assert build_version.display_version("0.6.0") == "0.6.0"


def test_a_clean_checkout_on_the_tag_adds_no_distance(
    monkeypatch: pytest.MonkeyPatch, repository: Path
) -> None:
    """Sitting exactly on a tag with nothing modified is a release build."""

    state = _state(monkeypatch, repository)
    assert "commits" not in state
    assert "dirty" not in state


def test_commits_past_the_tag_are_counted(
    monkeypatch: pytest.MonkeyPatch, repository: Path
) -> None:
    """The case that produced two builds claiming one version.

    The package version cannot move without a reinstall, so the distance is
    the only thing that can say the code is not the tag.
    """

    (repository / "file.txt").write_text("two\n")
    _git(repository, "commit", "-qam", "second")
    (repository / "file.txt").write_text("three\n")
    _git(repository, "commit", "-qam", "third")

    state = _state(monkeypatch, repository)
    assert "+2 commits" in state
    assert "dirty" not in state


def test_uncommitted_changes_are_called_dirty(
    monkeypatch: pytest.MonkeyPatch, repository: Path
) -> None:
    """The state no version string can otherwise describe."""

    (repository / "file.txt").write_text("edited but not committed\n")
    assert "dirty" in _state(monkeypatch, repository)


def test_an_untracked_file_also_counts_as_dirty(
    monkeypatch: pytest.MonkeyPatch, repository: Path
) -> None:
    """A new file changes the build as much as an edited one does."""

    (repository / "extra.txt").write_text("new\n")
    assert "dirty" in _state(monkeypatch, repository)


def test_a_repository_with_no_tags_still_names_its_commit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """describe fails without a tag, and a commit is still worth reporting."""

    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "test@example.invalid")
    _git(tmp_path, "config", "user.name", "Test")
    (tmp_path / "file.txt").write_text("one\n")
    _git(tmp_path, "add", "file.txt")
    _git(tmp_path, "commit", "-qm", "first")

    state = _state(monkeypatch, tmp_path)
    assert state, "an untagged checkout should still identify itself"


def test_a_broken_git_never_fails_the_command(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """No git binary, no repository, a slow disk: all fall through silently.

    This runs before anything useful happens, and a version string is not
    worth an error.
    """

    def explode(*_args: object, **_kwargs: object) -> None:
        raise OSError("git is not here")

    monkeypatch.setattr(build_version.subprocess, "run", explode)
    assert build_version.source_checkout() is None
    assert build_version.build_state() == ""
    assert build_version.display_version("0.6.0") == "0.6.0"


def test_the_package_version_itself_is_never_annotated() -> None:
    """The publish workflow compares __version__ against the release tag.

    A marker there would fail that check for the wrong reason, so the
    annotation is display-only and this is the line that keeps it that way.
    """

    from metabrowser import __version__

    for marker in ("dirty", "commits", "(", ")"):
        assert marker not in __version__
