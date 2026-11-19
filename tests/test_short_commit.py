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
color. ``tests/test_checkout_ref_selector_chrome.py`` measures the look in Chrome.
"""

from __future__ import annotations

import re
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

# A value that names a commit, cut to a length an abbreviation has: `commit.slice(0, 12)`,
# `envelope.pin.slice(0, 12)`, `resolved.commit[:12]`. Ordinary slices of other values do
# not name one: `c.slice(0, 7)` of a color, `rows.slice(0, 12)`, or a loose object's
# directory, `oid[:2]`, and a pack's magic, `header[:4]`, which are too short to be IDs.
_COMMITISH = r"(?:commit|sha|oid|pin|head|revision|rev|hash|right|left)\w*\)?"
_ID_LENGTH = r"(?:[5-9]|[1-6]\d)"
JS_ABBREVIATION = re.compile(
    rf"(?i)\b\w*{_COMMITISH}\??\.(?:slice|substring|substr)\(\s*0\s*,\s*{_ID_LENGTH}\s*\)"
)
PY_ABBREVIATION = re.compile(rf"(?i)\b\w*{_COMMITISH}\[\s*:\s*{_ID_LENGTH}\s*\]")
# Git's own abbreviation, which grows with the repository.
GIT_ABBREVIATION = re.compile(r'"--short\b|objectname:short|"%h"')
# The history routes' `short_id` is Git's abbreviation, kept for a caller that hands it
# back to Git; git/log.py and git/detail.py ask Git for it, and nothing shows it.
GIT_SHORT_ID_PRODUCERS = {PACKAGE / "git" / "log.py", PACKAGE / "git" / "detail.py"}

CSS_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
CSS_RULE = re.compile(r"(?P<selectors>[^{}]+)\{(?P<body>[^{}]*)\}")


def _relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


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


def test_plugins_reach_the_one_formatter_through_the_sdk() -> None:
    sdk = (PACKAGE / "static" / "plugin-sdk.js").read_text()
    assert "return global.MetabrowserFormatters.shortCommit(commit);" in sdk
    assert "    shortCommit: shortCommit,\n" in sdk


def test_no_script_shortens_a_commit_any_other_way() -> None:
    found = [
        f"{_relative(path)}:{number}: {line.strip()}"
        for path in SCRIPTS
        for number, line in enumerate(path.read_text().splitlines(), start=1)
        if JS_ABBREVIATION.search(line) or "short_id" in line
    ]
    assert found == [], "shorten a commit with shortCommit:\n" + "\n".join(found)


def test_no_module_shortens_a_commit_any_other_way() -> None:
    found = [
        f"{_relative(path)}:{number}: {line.strip()}"
        for path in MODULES
        for number, line in enumerate(path.read_text().splitlines(), start=1)
        if PY_ABBREVIATION.search(line)
        or (GIT_ABBREVIATION.search(line) and path not in GIT_SHORT_ID_PRODUCERS)
    ]
    assert found == [], "shorten a commit with short_commit:\n" + "\n".join(found)


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
