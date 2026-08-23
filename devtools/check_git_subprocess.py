"""Every ``git`` spawned by this project must say which environment it gets.

``GIT_DIR`` and its siblings override ``cwd`` and ``-C``, and git exports them
into every hook it runs. A git command that inherits the ambient environment
therefore targets whatever repository started the process, not the one its
arguments name.

This is not hypothetical and it is not once. ``metabrowser.git.process`` was
already scrubbing these variables, with a comment recording that a fixture
``git init`` from a pre-push hook had re-initialized the served repository as
bare. Later, a new module's tests spawned git without knowing that, and wrote a
``v1.0.0`` tag and a stray commit onto a real branch — after which the next
build read the tag and reported itself as version 1.0.0.

Both times the knowledge existed and neither time did it reach the new caller.
So the rule is enforced rather than written down:

**Any subprocess spawning ``git`` passes an explicit ``env=``.**

Use :func:`metabrowser.git.env.scrubbed_environ`, which owns the variable list
and the reasons. Passing ``env=os.environ.copy()`` satisfies the parser and not
the intent, which is a limitation worth knowing: this check makes the decision
visible at the call site, it cannot make it correct.

**Exempt, narrowly.** ``git --version`` and ``git rev-parse --local-env-vars``
resolve no repository — the second is how a caller *discovers* what to strip and
so cannot be scrubbed by an answer it does not have yet. A call may also carry
``# git-env-ok: <reason>`` on the spawning line, which is for the cases nobody
has met yet and requires saying why.

**What it cannot see.** A vector built at runtime (``[*command, "log"]``) is not
literal, so this check does not classify it as git. It reads the call sites that
name git directly, which is all of them today and the shape a new one takes.
"""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCANNED = ("src", "tests", "devtools")

SPAWNERS = {
    ("subprocess", "run"),
    ("subprocess", "Popen"),
    ("subprocess", "call"),
    ("subprocess", "check_call"),
    ("subprocess", "check_output"),
    ("asyncio", "create_subprocess_exec"),
}

# Subcommands that resolve no repository, so no pin can redirect them.
REPOSITORY_FREE = ("--version", "--local-env-vars", "--exec-path", "--html-path")

ALLOW_COMMENT = "git-env-ok:"


@dataclass(frozen=True)
class Finding:
    path: Path
    line: int
    text: str


def _dotted(node: ast.AST) -> tuple[str, ...]:
    """``subprocess.run`` as ``("subprocess", "run")``; ``()`` for anything else."""
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return tuple(reversed(parts))
    return ()


def _literal_words(node: ast.AST | None) -> list[str]:
    """The string constants of a literal argument vector, in order."""
    if isinstance(node, (ast.List, ast.Tuple)):
        return [
            e.value for e in node.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)
        ]
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    return []


def _spawns_git(call: ast.Call) -> bool:
    words = _literal_words(call.args[0] if call.args else None)
    if not words:
        return False
    if Path(words[0]).name != "git":
        return False
    return not any(word in REPOSITORY_FREE for word in words)


def scan(path: Path) -> list[Finding]:
    source = path.read_text(encoding="utf8", errors="replace")
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    lines = source.splitlines()
    findings: list[Finding] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or _dotted(node.func) not in SPAWNERS:
            continue
        if not _spawns_git(node):
            continue
        if any(keyword.arg == "env" for keyword in node.keywords):
            continue
        # An opt-out has to be on one of the call's own lines and give a reason.
        span = lines[node.lineno - 1 : (node.end_lineno or node.lineno)]
        if any(ALLOW_COMMENT in line for line in span):
            continue
        findings.append(Finding(path, node.lineno, lines[node.lineno - 1].strip()))
    return findings


def main() -> int:
    findings: list[Finding] = []
    for directory in SCANNED:
        for path in sorted((ROOT / directory).rglob("*.py")):
            findings.extend(scan(path))

    if not findings:
        return 0

    print(
        "git subprocess: GIT_DIR and its siblings override -C, so every git spawn\n"
        "must name the environment it gets.",
        file=sys.stderr,
    )
    for finding in findings:
        print(
            f"  {finding.path.relative_to(ROOT)}:{finding.line}: {finding.text[:96]}",
            file=sys.stderr,
        )
    print(
        "\nPass env=scrubbed_environ() from metabrowser.git.env. Git exports these\n"
        "variables to every hook it runs, so a command inheriting them targets the\n"
        "repository that started the process -- which has twice been this one.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
