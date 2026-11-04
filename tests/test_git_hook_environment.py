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

import ast
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

from metabrowser.git.process import _REPO_PINNING_GIT_VARS
from tests.required_tools import require_git
from tests.test_gitignore_hierarchical import _git_verdicts, _init_fixture_repository

ROOT = Path(__file__).resolve().parents[1]


def _git_outside_any_hook(cwd: Path, *args: str) -> str:
    """Run git in *cwd* with no inherited repository and no developer configuration."""

    require_git()
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
        hook_environment={
            "GIT_DIR": str(primary / ".git" / "worktrees" / "decoy-worktree"),
            "GIT_WORK_TREE": str(tmp_path / "decoy-worktree"),
        },
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


_GIT_GLOBAL_OPTION = r"(?:\s+-[Cc]\s+\S+|\s+--(?:git-dir|work-tree|namespace)[=\s]\S+|\s+--[\w-]+)"
_GIT_WRITE = re.compile(
    rf"\bgit{_GIT_GLOBAL_OPTION}*\s+"
    r"(?:init|add|commit|tag|mv|checkout|switch|branch|merge|rebase|reset|worktree|config|update-ref)\b"
)
_UNSET = re.compile(r"\bunset((?:\s+GIT_[A-Z_]+)+)")


@pytest.mark.parametrize(
    ("command", "writes"),
    [
        ("git init -q repo", True),
        ("git -C repo commit -qm one", True),
        ("git -c init.defaultBranch=main init -q", True),
        ("git -C repo -c user.name=x commit -qm one", True),
        ("git --git-dir=repo/.git update-ref HEAD abc", True),
        ("git --git-dir repo/.git --no-pager tag v1", True),
        ("git -C repo log --oneline", False),
        ("cat repo/.git/config", False),
    ],
)
def test_the_golden_check_sees_a_write_behind_any_global_option(command: str, writes: bool) -> None:
    assert bool(_GIT_WRITE.search(command)) is writes


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


def _runs_git_init(node: ast.AST) -> bool:
    """Whether *node* spawns ``git init``, as an argument vector or through a git helper."""

    if not isinstance(node, ast.Call):
        return False
    func = node.func
    name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
    for argument in node.args[:2]:
        if isinstance(argument, ast.List | ast.Tuple):
            words = [e.value for e in argument.elts if isinstance(e, ast.Constant)]
            if words[:1] == ["git"] and "init" in words:
                return True
            if words[:1] == ["init"] and "git" in name:
                return True
        elif "git" in name and isinstance(argument, ast.Constant) and argument.value == "init":
            return True
    return False


def _sets_a_pinning_variable(call: ast.Call) -> bool:
    return any(
        keyword.arg == "env"
        and isinstance(keyword.value, ast.Dict)
        and any(
            isinstance(key, ast.Constant) and key.value in _REPO_PINNING_GIT_VARS
            for key in keyword.value.keys
        )
        for keyword in call.keywords
    )


def _reads_the_whole_environment(statement: ast.stmt) -> bool:
    """Whether *statement* copies ``os.environ``, as against naming one variable in it."""

    named = {
        id(parent.value)
        for parent in ast.walk(statement)
        if isinstance(parent, ast.Subscript)
        or (isinstance(parent, ast.Attribute) and parent.attr in {"get", "pop", "setdefault"})
    }
    return any(
        isinstance(node, ast.Attribute)
        and node.attr == "environ"
        and isinstance(node.value, ast.Name)
        and node.value.id == "os"
        and id(node) not in named
        for node in ast.walk(statement)
    )


def _unscrubbed_git_init(source: str) -> list[str]:
    """What in a test module's *source* escapes the session scrub for a ``git init``."""

    found: list[str] = []
    tree = ast.parse(source)
    for statement in tree.body:
        if isinstance(statement, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            continue
        if any(_runs_git_init(node) for node in ast.walk(statement)):
            found.append(f"line {statement.lineno}: runs git init at import")
        if _reads_the_whole_environment(statement):
            found.append(f"line {statement.lineno}: copies os.environ at import")
    found.extend(
        f"line {node.lineno}: gives git init a pinning variable"
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and _runs_git_init(node) and _sets_a_pinning_variable(node)
    )
    return found


@pytest.mark.parametrize(
    ("source", "found"),
    [
        ('subprocess.run(["git", "init"])', ["line 1: runs git init at import"]),
        ('_git(ROOT, "init", "-q")', ["line 1: runs git init at import"]),
        ('run_git(["init", "-q"], cwd=ROOT)', ["line 1: runs git init at import"]),
        ("ENV = dict(os.environ)", ["line 1: copies os.environ at import"]),
        ("ENV = {**os.environ}", ["line 1: copies os.environ at import"]),
        ("ENV = os.environ.copy()", ["line 1: copies os.environ at import"]),
        (
            'def f():\n    subprocess.run(["git", "init"], env={"GIT_DIR": "x"})',
            ["line 2: gives git init a pinning variable"],
        ),
        ('def f():\n    subprocess.run(["git", "init"], env=dict(os.environ))', []),
        ('def f():\n    _git(root, "init", "-q")', []),
        ('os.environ["A"] = "1"\nos.environ.pop("B", None)\nC = os.environ.get("C")', []),
        ('subprocess.run(["git", "status"])', []),
        ('print("git init")', []),
    ],
)
def test_the_fixture_check_finds_what_escapes_the_scrub(source: str, found: list[str]) -> None:
    assert _unscrubbed_git_init(source) == found


def test_every_python_fixture_that_runs_git_init_reads_the_environment_after_the_scrub() -> None:
    """``tests/conftest.py`` protects a fixture only if the fixture runs after it.

    The session scrub empties the pinning variables from ``os.environ``, so a fixture
    that inherits it, or builds its own environment from it, cannot reach the hook's
    repository. Three shapes escape that, and conftest's own imports run before its
    scrub: spawning ``git init`` at import, copying ``os.environ`` at import, and naming
    a pinning variable to the spawn itself.
    """

    tests = ROOT / "tests"
    offenders: dict[str, list[str]] = {}
    spawns = 0
    for path in sorted(tests.rglob("*.py")):
        if path.parent.name in {"manual-fixtures", "fixtures"}:
            continue
        source = path.read_text(encoding="utf-8")
        spawns += sum(_runs_git_init(node) for node in ast.walk(ast.parse(source)))
        found = _unscrubbed_git_init(source)
        if found:
            offenders[str(path.relative_to(ROOT))] = found
    assert offenders == {}
    assert spawns, "no fixture runs git init any more, so this check has no subject"


def _script_starts_git(text: str) -> bool:
    return bool(_GIT_WRITE.search(text)) or (
        "child_process" in text and re.search(r"\bgit\b", text) is not None
    )


@pytest.mark.parametrize(
    ("text", "starts"),
    [
        ("git init -q repo", True),
        ('require("child_process").execFileSync("git", ["status"])', True),
        ('const spawn = require("child_process").spawn; // every digit counts', False),
        ('require("child_process"); // a legitimate spawn', False),
        ('require("child_process"); readFileSync(".gitignore")', False),
        ('console.log("git status")', False),
    ],
)
def test_the_script_check_reads_git_as_a_word(text: str, starts: bool) -> None:
    assert _script_starts_git(text) is starts


def test_no_script_a_golden_can_run_starts_git() -> None:
    """A golden runs ``node`` and shell scripts in a shell nothing in Python scrubbed.

    Those scripts drive production modules and have no reason to build a repository, so
    this holds them to none rather than to clearing the list by hand.
    """

    scripts = [
        path
        for path in (ROOT / "tests").rglob("*")
        if path.is_file()
        and path.suffix in {".js", ".mjs", ".cjs", ".sh", ""}
        and "manual-fixtures" not in path.parts
        and "fixtures" not in path.parts
    ]
    assert scripts, "no script is left under tests/, so this check has no subject"

    assert [
        str(path.relative_to(ROOT))
        for path in scripts
        if _script_starts_git(path.read_text(encoding="utf-8", errors="replace"))
    ] == []


def test_the_pre_push_gate_unsets_the_pinning_variables() -> None:
    """The gate clears them once for everything it runs, Python or not."""

    configuration = (ROOT / "lefthook.yml").read_text()
    pre_push = configuration[configuration.index("pre-push:") :]
    missing = set(_REPO_PINNING_GIT_VARS) - _unset_names(pre_push[pre_push.index("run:") :])
    assert not missing, f"lefthook.yml pre-push leaves {sorted(missing)}"
