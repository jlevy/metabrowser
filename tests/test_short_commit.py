"""One short commit ID wherever a line names a commit (docs/design-system.md, "Short
Commit IDs").

The owner, 2026-11-18: "let's make all short commits 7 chars, just like github. Make this
part of the design system and apply it consistently. In the branch chooser, it's many more
characters. They should always be monospace, always the same gray, and always 7
characters."

The server and the CLI shorten a commit with ``short_commit`` in ``commit_ids.py``; the
page and its plugins with ``shortCommit`` in ``static/formatters.js``, which the SDK hands
plugins as ``metabrowser.shortCommit``. Each holds its own copy of the length, and this
keeps the two equal and at GitHub's seven. It also fails a display that shortens a commit
any other way: a fixed slice of a commit-like value, Git's own abbreviation, or the
``short_id`` the history routes carry for a caller that hands it back to Git. The look,
the commit-ID face and one gray, is ``.git-commit-sha``, and only its own rule gives it a
color. ``tests/test_checkout_ref_selector_chrome.py`` and
``tests/test_github_pull_timeline_chrome.py`` measure the look in Chrome. A development
version's label cuts its commit to the same length (``commit-length`` in
``pyproject.toml``), and the macOS app's About box with its own copy, which
``tests/test_macos_app_pins.py`` holds to this one.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

from metabrowser.commit_ids import SHORT_COMMIT_CHARS, short_commit

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src" / "metabrowser"
FORMATTERS = PACKAGE / "static" / "formatters.js"
COMMIT_IDS = PACKAGE / "commit_ids.py"
# Every script the page runs that is ours: the shell's and every built-in plugin's.
SCRIPTS = sorted(
    path
    for path in (*PACKAGE.glob("static/*.js"), *PACKAGE.glob("builtin_plugins/**/*.js"))
    if "vendor" not in path.parts
)
STYLESHEETS = (PACKAGE / "static" / "styles.css", *sorted(PACKAGE.glob("builtin_plugins/*/*.css")))
# The Python that runs in the server and the CLI.
MODULES = sorted(path for path in PACKAGE.rglob("*.py") if path != COMMIT_IDS)
# Everything that asks Git for a commit: the package, the tests, the developer tools, and
# the macOS app's sources and scripts.
_APP = ROOT / "apps" / "macos"
GIT_CALLERS = sorted(
    {
        *SCRIPTS,
        *MODULES,
        *(ROOT / "tests").rglob("*.py"),
        *(ROOT / "tests" / "dom").rglob("*.js"),
        *(ROOT / "tests" / "dom").rglob("*.mjs"),
        *(ROOT / "devtools").rglob("*.py"),
        *(_APP / "scripts").glob("*.sh"),
        *(_APP / "Sources").rglob("*.swift"),
        *(_APP / "Tests").rglob("*.swift"),
        *(_APP / "webkit-gate").glob("*.mjs"),
    }
    - {Path(__file__).resolve()}
)

# A value that names a commit, cut to a length an abbreviation has. The value is the last
# name before the cut, `commit.slice(0, 12)`, `event.oid.slice(0, 7)`, `resolved.commit[:12]`,
# and it names a commit when one of its words, split at underscores and capitals, is one of
# these: `headOid`, `pin_sha`, `comparison.right`, `latest`, `base`. A word elsewhere in a
# name does not count, so `preview.slice(0, 40)` is no revision; a loose object's
# directory, `oid[:2]`, and a pack's magic, `header[:4]`, are too short for an ID. An `id`
# is a commit's only alone, as in `commit.id`: `session_id` names a log's session.
_COMMIT_NAMES = frozenset({"id"})
_COMMIT_WORDS = frozenset(
    {
        "base",
        "commit",
        "hash",
        "head",
        "latest",
        "left",
        "oid",
        "parent",
        "pin",
        "rev",
        "revision",
        "right",
        "sha",
        "target",
    }
)
_ID_LENGTH = r"(?P<length>[5-9]|[1-6]\d)"
_NAME = r"(?P<name>[A-Za-z_$][\w$]*)(?:\(\))?"
JS_CUT = re.compile(rf"{_NAME}\??\.(?:slice|substring|substr)\(\s*0\s*,\s*{_ID_LENGTH}\s*\)")
PY_CUT = re.compile(rf"""{_NAME}(?:\[["'](?P<key>\w+)["']\])?\[\s*:\s*{_ID_LENGTH}\s*\]""")
# Git's own abbreviation, which grows with the repository: `--short` on a commit, an
# `--abbrev` shorter than an ID, and `%h` in any format string.
GIT_ABBREVIATION = re.compile(
    r"--short\b(?!-)|--abbrev-commit|--abbrev=(?!40\b|64\b)\d+|objectname:short|(?<!%)%h\b"
)
# `--short` that names no commit: a status in short format, or a ref's short name.
_SHORT_NOT_A_COMMIT = re.compile(r"\b(?:status|symbolic-ref)\b.*--short\b")
# The history routes' `short_id` is Git's abbreviation, kept for a caller that hands it
# back to Git; git/log.py and git/detail.py ask Git for it, and nothing shows it.
GIT_SHORT_ID_PRODUCERS = {PACKAGE / "git" / "log.py", PACKAGE / "git" / "detail.py"}
# Each other place that may cut or abbreviate a commit, and why it is not a line that
# names one: (file, text on the line, reason).
ALLOWED: tuple[tuple[str, str, str], ...] = (
    (
        "apps/macos/webkit-gate/run.mjs",
        '"--short=12"',
        "a measurement record names its commit as the earlier records it is compared with do",
    ),
)

CSS_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
CSS_RULE = re.compile(r"(?P<selectors>[^{}]+)\{(?P<body>[^{}]*)\}")


def _relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _names_a_commit(*names: str | None) -> bool:
    return any(
        name in _COMMIT_NAMES
        or any(
            word.lower() in _COMMIT_WORDS
            for word in re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])", name)
        )
        for name in names
        if name
    )


def _allowed(path: Path, line: str) -> bool:
    return any(_relative(path) == where and text in line for where, text, _ in ALLOWED)


def _cuts(pattern: re.Pattern[str], line: str) -> bool:
    return any(
        _names_a_commit(match["name"], match.groupdict().get("key"))
        for match in pattern.finditer(line)
    )


def _abbreviates(path: Path, line: str) -> bool:
    if path in GIT_SHORT_ID_PRODUCERS:
        return False
    return any(
        not (match[0].startswith("--short") and _SHORT_NOT_A_COMMIT.search(line))
        for match in GIT_ABBREVIATION.finditer(line)
    )


def _found(paths: list[Path], offends: object) -> list[str]:
    check = offends  # (path, line) -> bool
    return [
        f"{_relative(path)}:{number}: {line.strip()}"
        for path in paths
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)
        if check(path, line) and not _allowed(path, line)  # type: ignore[operator]
    ]


def test_a_short_commit_is_seven_characters_as_github_shows_them() -> None:
    assert SHORT_COMMIT_CHARS == 7
    commit = "c7ae2a331f546e6a2431ed7093e9e430a9d1269b"
    assert short_commit(commit) == "c7ae2a3"
    # A SHA-256 repository's ID is cut to the same length.
    assert short_commit("ab" * 32) == "abababa"


def test_the_page_and_the_server_shorten_a_commit_to_one_length() -> None:
    found = re.findall(r"^\s*const SHORT_COMMIT_CHARS = (\d+);$", FORMATTERS.read_text(), re.M)
    assert found == [str(SHORT_COMMIT_CHARS)]
    assert "return String(commit).slice(0, SHORT_COMMIT_CHARS);" in FORMATTERS.read_text()


def test_a_development_versions_label_cuts_its_commit_to_the_same_length() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert project["tool"]["uv-dynamic-versioning"]["commit-length"] == SHORT_COMMIT_CHARS


def test_plugins_reach_the_one_formatter_through_the_sdk() -> None:
    sdk = (PACKAGE / "static" / "plugin-sdk.js").read_text()
    assert "return global.MetabrowserFormatters.shortCommit(commit);" in sdk
    assert "    shortCommit: shortCommit,\n" in sdk


def test_no_script_shortens_a_commit_any_other_way() -> None:
    found = _found(SCRIPTS, lambda path, line: _cuts(JS_CUT, line) or "short_id" in line)
    assert found == [], "shorten a commit with shortCommit:\n" + "\n".join(found)


def test_no_module_shortens_a_commit_any_other_way() -> None:
    found = _found(MODULES, lambda path, line: _cuts(PY_CUT, line))
    assert found == [], "shorten a commit with short_commit:\n" + "\n".join(found)


def test_nothing_asks_git_for_its_abbreviation() -> None:
    found = _found(GIT_CALLERS, _abbreviates)
    assert found == [], "ask Git for the full ID and cut it with short_commit:\n" + "\n".join(found)


def test_the_guards_tell_a_commit_from_other_values() -> None:
    def js(line: str) -> bool:
        return _cuts(JS_CUT, line)

    def py(line: str) -> bool:
        return _cuts(PY_CUT, line)

    def git(line: str) -> bool:
        return _abbreviates(ROOT / "anywhere.py", line)

    for line in (
        "commit.slice(0, 12)",
        "event.oid.slice(0, 7)",
        "comparison.right.slice(0, 12)",
        "latest.slice(0, 7)",
        "row.id.slice(0, 7)",
        "base.slice(0, 12)",
        "headOid.substring(0, 8)",
        "parent?.slice(0, 7)",
    ):
        assert js(line), line
    for line in ("preview.slice(0, 40)", "rows.slice(0, 12)", "c.slice(0, 7)", "name.slice(0, 2)"):
        assert not js(line), line
    for line in ("resolved.commit[:12]", 'entry["target"][:7]', "pin_sha[:9]"):
        assert py(line), line
    for line in ("oid[:2]", "header[:4]", "preview[:40]", "rows[:12]", "session_id[:8]"):
        assert not py(line), line
    for line in (
        '["git", "rev-parse", "--short", "HEAD"]',
        "git rev-parse --short=7 HEAD",
        '"--format=%h %s"',
        '"%(objectname:short)"',
        "git log --abbrev-commit",
        "describe --abbrev=12",
    ):
        assert git(line), line
    for line in (
        '["git", "status", "--short"]',
        "git symbolic-ref --short HEAD",
        '"--format=%H %s"',
        "describe --tags --long --abbrev=40",
        "rev-parse --abbrev-ref HEAD",
    ):
        assert not git(line), line


def test_the_commit_id_face_is_one_face_and_one_gray() -> None:
    colors: list[tuple[str, str]] = []
    faces: list[tuple[str, str]] = []
    for path in STYLESHEETS:
        for rule in CSS_RULE.finditer(CSS_COMMENT.sub("", path.read_text())):
            for selector in (part.strip() for part in rule["selectors"].split(",")):
                if not re.search(r"\.git-commit-sha(?::[\w-]+)?$", selector):
                    continue
                body = rule["body"]
                if color := re.search(r"(?:^|;)\s*color\s*:\s*([^;]+)", body):
                    colors.append((f"{_relative(path)} {selector}", color[1].strip()))
                if face := re.search(r"(?:^|;)\s*font-family\s*:\s*([^;]+)", body):
                    faces.append((f"{_relative(path)} {selector}", face[1].strip()))
    styles = "src/metabrowser/static/styles.css .git-commit-sha"
    assert colors == [(styles, "var(--muted)")]
    assert faces == [(styles, "var(--font-mono)")]
