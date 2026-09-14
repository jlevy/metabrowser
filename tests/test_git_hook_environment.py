"""The test suite runs inside a githook and must not write through its environment.

Lefthook's pre-push gate runs pytest inside a githook. From a linked worktree git
exports ``GIT_DIR=<common>/.git/worktrees/<name>`` there, and ``GIT_DIR`` outranks both
the working directory and ``git -C``. A fixture that spawns ``git init`` with that
environment does not create its repository: it re-initializes the hook's repository
and writes ``core.bare = true`` into the configuration every worktree shares, after
which ``git status`` in the primary checkout fails with "this operation must be run
in a work tree". The test that did it still passed.

These tests stand a scratch repository with a linked worktree in for the developer's
checkout, export what the hook exports, and require that repository's configuration
to come through unchanged. Nothing here touches the repository the suite runs from.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

from metabrowser.git.process import _REPO_PINNING_GIT_VARS
from tests.test_gitignore_hierarchical import _git_verdicts, _init_fixture_repository

ROOT = Path(__file__).resolve().parents[1]


def _git_outside_any_hook(cwd: Path, *args: str) -> str:
    """Run git in *cwd* with no inherited repository and no developer configuration."""

    env = {key: value for key, value in os.environ.items() if key not in _REPO_PINNING_GIT_VARS}
    env.update(
        {
            "GIT_AUTHOR_NAME": "Fixture Author",
            "GIT_AUTHOR_EMAIL": "author@example.invalid",
            "GIT_COMMITTER_NAME": "Fixture Author",
            "GIT_COMMITTER_EMAIL": "author@example.invalid",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
        }
    )
    return subprocess.run(
        ["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True, env=env
    ).stdout.strip()


@dataclass(frozen=True)
class Decoy:
    """A checkout with a linked worktree, and the environment its pre-push hook sees."""

    primary: Path
    hook_environment: dict[str, str]
    shared_config: bytes

    def assert_unchanged(self) -> None:
        assert (self.primary / ".git" / "config").read_bytes() == self.shared_config
        assert _git_outside_any_hook(self.primary, "config", "--get", "core.bare") == "false"
        _git_outside_any_hook(self.primary, "status", "--porcelain")


@pytest.fixture
def decoy(tmp_path: Path) -> Decoy:
    primary = tmp_path / "decoy"
    primary.mkdir()
    _git_outside_any_hook(primary, "init", "-q", "-b", "main")
    (primary / "file.txt").write_text("one\n")
    _git_outside_any_hook(primary, "add", "file.txt")
    _git_outside_any_hook(primary, "commit", "-qm", "first")
    _git_outside_any_hook(primary, "worktree", "add", "-q", str(tmp_path / "decoy-worktree"))
    return Decoy(
        primary=primary,
        # What `git push` exports to a pre-push hook run from that linked worktree.
        hook_environment={"GIT_DIR": str(primary / ".git" / "worktrees" / "decoy-worktree")},
        shared_config=(primary / ".git" / "config").read_bytes(),
    )


def probe_an_unscrubbed_git_init(tmp_path: Path) -> None:
    """A fixture written the naive way, collected only by the session test below.

    It inherits the whole process environment, as the fixture that set
    ``core.bare`` did. The session scrub in ``tests/conftest.py`` is the only thing
    between it and the hook's repository.
    """

    fixture = tmp_path / "fixture"
    subprocess.run(["git", "init", "-q", str(fixture)], check=True, capture_output=True)
    assert (fixture / ".git").is_dir()


def test_the_session_scrubs_a_hook_exported_git_dir(decoy: Decoy, tmp_path: Path) -> None:
    """Every test inherits the scrub, including one that forgets to scrub itself.

    Runs a nested session under the hook's environment, so the scrub is exercised
    where it has to work: before any test module is imported.
    """

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "-o",
            "python_functions=probe_*",
            f"--basetemp={tmp_path / 'nested'}",
            f"{Path(__file__).relative_to(ROOT)}::probe_an_unscrubbed_git_init",
        ],
        cwd=ROOT,
        env={**os.environ, **decoy.hook_environment},
        capture_output=True,
        text=True,
        check=False,
    )

    decoy.assert_unchanged()
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_gitignore_fixture_git_calls_scrub_a_hook_exported_git_dir(
    decoy: Decoy, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The gitignore cross-check's own git calls scrub, independent of the session.

    This fixture set ``core.bare = true`` in a developer's real repository from a
    linked worktree's pre-push gate.
    """

    for name, value in decoy.hook_environment.items():
        monkeypatch.setenv(name, value)

    root = tmp_path / "repo"
    _init_fixture_repository(root)
    (root / ".gitignore").write_text("*.log\n")
    verdicts = _git_verdicts(root, [("app.log", False), ("app.py", False)])

    decoy.assert_unchanged()
    assert (root / ".git").is_dir()
    assert verdicts == {("app.log", False): True, ("app.py", False): False}


_GIT_WRITE = re.compile(
    r"\bgit(?:\s+-C\s+\S+)*\s+"
    r"(?:init|add|commit|tag|mv|checkout|switch|branch|merge|rebase|reset|worktree|config|update-ref)\b"
)
_UNSET = re.compile(r"\bunset((?:\s+GIT_[A-Z_]+)+)")


def _unset_names(script: str) -> set[str]:
    unset = _UNSET.search(script.replace("\\\n>", " "))
    return set(unset.group(1).split()) if unset else set()


def _golden_shell_commands(golden: str) -> list[str]:
    """The frontmatter ``before:`` script and each ``$`` command with its continuations."""

    before = re.search(r"^before:\s*[>|]-?\n((?:[ \t]+.*\n)+)", golden, re.MULTILINE)
    commands = [before.group(1)] if before else []
    commands.extend(re.findall(r"^\$ .*(?:\n>.*)*", golden, re.MULTILINE))
    return commands


def test_every_golden_that_writes_git_state_unsets_the_pinning_variables() -> None:
    """A console golden builds its repositories in a shell the test runner started.

    That shell inherits the hook's environment and nothing in Python scrubs it, so
    each command that creates or changes a repository clears the same list
    ``metabrowser.git.process`` does.
    """

    writers = 0
    for golden in sorted((ROOT / "tests" / "golden").glob("*.tryscript.md")):
        for command in _golden_shell_commands(golden.read_text()):
            if not _GIT_WRITE.search(command):
                continue
            writers += 1
            missing = set(_REPO_PINNING_GIT_VARS) - _unset_names(command)
            assert not missing, (
                f"{golden.name}: {command.splitlines()[0]!r} leaves {sorted(missing)}"
            )
    assert writers, "no golden writes git state any more, so this check has no subject"


def test_the_pre_push_gate_unsets_the_pinning_variables() -> None:
    """The gate clears them once for everything it runs, Python or not."""

    configuration = (ROOT / "lefthook.yml").read_text()
    pre_push = configuration[configuration.index("pre-push:") :]
    missing = set(_REPO_PINNING_GIT_VARS) - _unset_names(pre_push[pre_push.index("run:") :])
    assert not missing, f"lefthook.yml pre-push leaves {sorted(missing)}"
