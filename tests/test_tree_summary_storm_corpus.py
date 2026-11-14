"""The storm corpus builder writes only the repository it creates.

``explorations/tree-summary-storm/make-corpus.sh`` initializes a repository, commits to
it, fast-imports its history, and runs ``git reset --hard main``. A git hook exports
``GIT_DIR`` and ``GIT_WORK_TREE``, and either outranks the working directory, so a run
that inherited them wrote all of that into the hook's checkout instead (review A1 on
#413). These tests export them, pointed at a decoy repository with a linked worktree,
and require the decoy's refs, configuration, index, and files to come through unchanged.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

from metabrowser.git.process import _REPO_PINNING_GIT_VARS
from tests.required_tools import require_git
from tests.test_git_hook_environment import _git_outside_any_hook

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "explorations" / "tree-summary-storm" / "make-corpus.sh"
# A corpus small enough to build in a second: 4 tracked files, 6 ignored, 7 commits.
SMALL = {
    "COMMITS": "6",
    "REFS": "2",
    "TRACKED_DIRS": "2",
    "TRACKED_PER_DIR": "2",
    "IGNORED_DIRS": "2",
    "IGNORED_PER_DIR": "3",
}


def _repository_state(repository: Path) -> dict[str, object]:
    """Everything the builder could have written: refs, HEAD, config, index, files."""

    git = repository / ".git"
    return {
        "refs": _git_outside_any_hook(
            repository, "for-each-ref", "--format=%(refname) %(objectname)"
        ),
        "head": _git_outside_any_hook(repository, "rev-parse", "HEAD"),
        "config": (git / "config").read_bytes(),
        "index": (git / "index").read_bytes(),
        "files": {
            path.relative_to(repository).as_posix(): path.read_bytes()
            for path in sorted(repository.rglob("*"))
            if path.is_file() and ".git" not in path.relative_to(repository).parts
        },
    }


@pytest.mark.parametrize(
    "pinned",
    [
        # Before the fix this added every corpus commit to the decoy's main.
        ("GIT_DIR",),
        ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR", "GIT_OBJECT_DIRECTORY"),
    ],
    ids=["git-dir-only", "work-tree-and-index"],
)
def test_the_builder_leaves_an_inherited_repository_untouched(
    tmp_path: Path, pinned: tuple[str, ...]
) -> None:
    require_git()
    decoy = tmp_path / "decoy"
    decoy.mkdir()
    _git_outside_any_hook(decoy, "init", "-q", "-b", "main")
    (decoy / "file.txt").write_text("one\n")
    _git_outside_any_hook(decoy, "add", "file.txt")
    _git_outside_any_hook(decoy, "commit", "-qm", "first")
    _git_outside_any_hook(decoy, "worktree", "add", "-q", str(tmp_path / "decoy-worktree"))
    before = _repository_state(decoy)

    corpus = tmp_path / "corpus"
    # What a hook run from the decoy exports, and more of the pinning list.
    pinning = {
        "GIT_DIR": str(decoy / ".git"),
        "GIT_WORK_TREE": str(decoy),
        "GIT_INDEX_FILE": str(decoy / ".git" / "index"),
        "GIT_COMMON_DIR": str(decoy / ".git"),
        "GIT_OBJECT_DIRECTORY": str(decoy / ".git" / "objects"),
    }
    environment = {
        **{key: value for key, value in os.environ.items() if key not in _REPO_PINNING_GIT_VARS},
        **{name: pinning[name] for name in pinned},
        # No developer configuration: signing or hooks must not decide the outcome.
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        **SMALL,
    }
    completed = subprocess.run(
        ["bash", str(SCRIPT), str(corpus)],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        # The build took 0.7 s at a load average near 170, so this only catches a hang,
        # under the suite's 50 s ceiling for inner bounds (pyproject.toml).
        timeout=30,
        check=False,
    )

    assert _repository_state(decoy) == before, "the builder wrote into the inherited repository"
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert (corpus / ".git").is_dir(), "the corpus is not its own repository"
    assert _git_outside_any_hook(corpus, "rev-list", "--count", "main") == "7"
    assert len(list((corpus / "node_modules").rglob("*.js"))) == 6


def test_the_builder_unsets_every_repository_pinning_variable() -> None:
    """The builder's list is the one ``metabrowser.git.process`` scrubs, and stays so."""

    script = SCRIPT.read_text().replace("\\\n", " ")
    unset = re.search(r"^unset((?:[ \t]+GIT_[A-Z_]+)+)", script, re.MULTILINE)
    assert unset is not None, "the builder unsets no repository-pinning variable"
    first_git = script.index("\ngit ")
    assert unset.start() < first_git, "the builder runs git before it unsets the variables"
    assert set(unset.group(1).split()) == set(_REPO_PINNING_GIT_VARS)
