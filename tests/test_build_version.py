"""A build that is not exactly a released one has to say so.

The failure these guard against is quiet: `importlib.metadata` reports the
version recorded when the package was installed, so a checkout keeps reporting
its last tag however far the working tree has moved. Two builds under
comparison both claimed the same version once, and nothing on screen
contradicted it.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
from pathlib import Path
from types import ModuleType

import pytest

from metabrowser import build_version


def _git(repository: Path, *arguments: str) -> str:
    """Run git against *repository* and nothing else, and return its output.

    GIT_DIR and its siblings override -C, and git exports them to every hook it
    runs. Without stripping them these tests commit and tag in whatever
    repository invoked them — which, run from a pre-push hook, is this one.
    That happened: a fixture's "first" commit and its `v1.0.0` tag landed on a
    real branch.

    The developer's global and system configuration are shut out too, and the
    identity is pinned: a global ``commit.gpgsign`` or ``core.hooksPath`` would
    otherwise sign or hook every fixture commit, or fail it.
    """

    environment = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    environment.update(
        {
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "test@example.invalid",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "test@example.invalid",
        }
    )
    return subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    ).stdout.strip()


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    """A real repository with one tagged commit."""

    _git(tmp_path, "init", "-q")
    (tmp_path / "file.txt").write_text("one\n")
    _git(tmp_path, "add", "file.txt")
    _git(tmp_path, "commit", "-qm", "first")
    _git(tmp_path, "tag", "v1.0.0")
    return tmp_path


def test_fixture_commits_ignore_the_developers_git_configuration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """These fixtures commit, and a developer's global configuration must not reach them.

    A global ``commit.gpgsign`` signs every fixture commit, and fails it where
    signing is unavailable; stripping ``GIT_*`` alone keeps that configuration,
    because it is found through ``HOME`` and ``XDG_CONFIG_HOME``.
    """

    configuration = tmp_path / "xdg" / "git" / "config"
    configuration.parent.mkdir(parents=True)
    configuration.write_text("[commit]\n\tgpgsign = true\n[gpg]\n\tprogram = false\n")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    fixture = tmp_path / "fixture"
    fixture.mkdir()

    _git(fixture, "init", "-q")
    _git(fixture, "commit", "--allow-empty", "-qm", "unsigned")

    assert _git(fixture, "log", "--format=%an <%ae>") == "Test <test@example.invalid>"


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
    (tmp_path / "file.txt").write_text("one\n")
    _git(tmp_path, "add", "file.txt")
    _git(tmp_path, "commit", "-qm", "first")

    state = _state(monkeypatch, tmp_path)
    assert state, "an untagged checkout should still identify itself"


def _place_copy(destination: Path) -> Path:
    """Copy this module's own source to *destination*, as an installer would."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    (destination.parent / "__init__.py").touch()
    shutil.copyfile(build_version.__file__, destination)
    return destination


def _import_copy(path: Path) -> ModuleType:
    """Import the copy at *path* under a private name.

    ``source_checkout()`` asks git about the directory holding its own file, so
    the faithful way to learn what a copy somewhere else reports is to import
    that copy. It carries its own caches, so nothing it answers leaks into the
    module under test.
    """

    spec = importlib.util.spec_from_file_location("_build_version_copy", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("ignored", [False, True], ids=["untracked", "gitignored"])
def test_an_environment_inside_a_repository_is_still_an_installed_release(
    repository: Path, ignored: bool
) -> None:
    """A virtualenv inside a project's repository is not that project's source.

    A project-local ``.venv/``, or a performance-loop environment under
    ``.bench/``, sits inside a work tree while containing none of its tracked
    code. Asking only whether a work tree enclosed the package labeled a
    released wheel with the enclosing repository's commit —
    ``metab 0.9.1 (+153 commits, 8d111f4a)`` — and the performance harness
    then refused it as the wrong build. Ignoring the directory did not help.
    """

    if ignored:
        (repository / ".gitignore").write_text(".venv/\n")
        _git(repository, "add", ".gitignore")
        _git(repository, "commit", "-qm", "ignore the environment")

    site_packages = repository / ".venv" / "lib" / "python3.13" / "site-packages"
    installed = _import_copy(_place_copy(site_packages / "metabrowser" / "build_version.py"))

    assert installed.source_checkout() is None
    assert installed.build_state() == ""
    assert installed.display_version("0.9.1") == "0.9.1"


@pytest.fixture
def source_copy(repository: Path) -> Path:
    """This module committed at its place in a Metabrowser checkout."""

    module = _place_copy(repository / "src" / "metabrowser" / "build_version.py")
    (repository / ".gitignore").write_text("__pycache__/\n")
    _git(repository, "add", ".gitignore", "src")
    _git(repository, "commit", "-qm", "add the package")
    return module


def test_a_tracked_source_tree_still_reports_its_repository(
    repository: Path, source_copy: Path
) -> None:
    """The case the annotation exists for keeps it.

    An editable install puts the checkout's ``src/`` on the import path, so the
    running file is one the repository tracks, and the repository's state
    describes this build.
    """

    source = _import_copy(source_copy)

    assert source.source_checkout() == repository.resolve()
    state = source.build_state()
    assert "+1 commits" in state
    assert _git(repository, "rev-parse", "--short", "HEAD") in state
    assert "dirty" not in state


def test_an_edited_source_tree_is_still_a_checkout_and_is_dirty(
    repository: Path, source_copy: Path
) -> None:
    """Editing the running file keeps it tracked, and the annotation says so."""

    with source_copy.open("a") as module:
        module.write("# a local edit\n")
    source = _import_copy(source_copy)

    assert source.source_checkout() == repository.resolve()
    assert "dirty" in source.build_state()


def test_a_linked_worktree_reports_itself(
    repository: Path, source_copy: Path, tmp_path_factory: pytest.TempPathFactory
) -> None:
    """A second worktree of the checkout is its own source tree, not the primary one."""

    worktree = tmp_path_factory.mktemp("linked") / "worktree"
    _git(repository, "worktree", "add", "-q", "-b", "side", str(worktree))
    (worktree / "side.txt").write_text("side\n")
    _git(worktree, "add", "side.txt")
    _git(worktree, "commit", "-qm", "side")
    source = _import_copy(worktree / source_copy.relative_to(repository))

    assert source.source_checkout() == worktree.resolve()
    state = source.build_state()
    assert "+2 commits" in state
    assert _git(worktree, "rev-parse", "--short", "HEAD") in state
    assert "dirty" not in state


def test_a_copy_committed_into_another_project_is_not_that_projects_build(
    repository: Path,
) -> None:
    """Tracked is not enough: the file must be tracked where Metabrowser keeps it.

    ``pip install --target vendor/`` followed by a commit, or a subtree merge,
    puts this file under version control in someone else's repository. That
    repository's tags and commits say nothing about which Metabrowser is
    running.
    """

    vendored = _place_copy(repository / "vendor" / "metabrowser" / "build_version.py")
    _git(repository, "add", "vendor")
    _git(repository, "commit", "-qm", "vendor metabrowser")
    copy = _import_copy(vendored)

    assert copy.source_checkout() is None
    assert copy.build_state() == ""
    assert copy.display_version("0.9.1") == "0.9.1"


def test_a_hook_exported_repository_does_not_redirect_the_answer(
    repository: Path,
    source_copy: Path,
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``metab`` run from inside a githook still describes the checkout it runs from.

    Git exports ``GIT_DIR`` to hooks, and it outranks ``-C``. Unstripped, every
    question here would be asked of the hook's repository.
    """

    decoy = tmp_path_factory.mktemp("decoy")
    _git(decoy, "init", "-q")
    (decoy / "decoy.txt").write_text("decoy\n")
    _git(decoy, "add", "decoy.txt")
    _git(decoy, "commit", "-qm", "decoy")
    monkeypatch.setenv("GIT_DIR", str(decoy / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(decoy))
    monkeypatch.setenv("GIT_INDEX_FILE", str(decoy / ".git" / "index"))
    source = _import_copy(source_copy)

    assert source.source_checkout() == repository.resolve()
    state = source.build_state()
    assert _git(repository, "rev-parse", "--short", "HEAD") in state
    assert _git(decoy, "rev-parse", "--short", "HEAD") not in state


def test_an_undecodable_tag_does_not_fail_the_command(repository: Path, source_copy: Path) -> None:
    """Git output is bytes, and a tag or path need not be UTF-8.

    Strict decoding raised ``UnicodeDecodeError`` out of ``metab --version`` and
    the server's startup, the two places this module promises never to fail.
    """

    head = _git(repository, "rev-parse", "HEAD")
    with (repository / ".git" / "packed-refs").open("ab") as refs:
        refs.write(head.encode() + b" refs/tags/v1\xff\n")
    source = _import_copy(source_copy)

    shown = source.display_version("0.9.1")
    assert shown.startswith("0.9.1 (")
    assert head[:7] in shown


def test_reading_the_state_never_rewrites_the_index(repository: Path, source_copy: Path) -> None:
    """A version string must not take ``index.lock`` from a concurrent ``git commit``.

    ``git status`` and ``git describe --dirty`` both refresh stale stat data
    and write the index back under its lock. A file whose timestamp moved
    without a content change is the ordinary way to leave that data stale.
    """

    tracked = repository / "file.txt"
    later = tracked.stat().st_mtime + 3600
    os.utime(tracked, (later, later))
    index = repository / ".git" / "index"
    before = index.read_bytes()
    source = _import_copy(source_copy)

    assert "dirty" not in source.build_state()
    assert index.read_bytes() == before


def test_the_checkout_path_is_where_this_module_lives() -> None:
    """Every source run is recognized by this one path, so it must stay true.

    Moving the package without updating it would silently drop the annotation
    from every checkout.
    """

    root = Path(__file__).resolve().parents[1]
    module = Path(build_version.__file__).resolve()
    assert module.relative_to(root).as_posix() == build_version._CHECKOUT_PATH


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
