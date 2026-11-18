"""Changelog fragments: each change adds its own file under ``changelog.d/``, and a release
folds them into ``CHANGELOG.md``.

**Why.** Every pull request used to add its entry at the top of ``CHANGELOG.md``'s
Unreleased section, so each merge to main left every other open pull request with a
conflict there, and each conflict cost a merge-up and a full CI run. Git's ``union`` merge
driver would resolve those, but GitHub's server-side merge ignores it: with
``CHANGELOG.md merge=union`` in ``.gitattributes`` on both sides, a merge of two such
branches through the API returned 409 on 2026-11-18. A file per change is a file no other
pull request touches.

**A fragment** is ``changelog.d/<name>.md``, named for its bead or a short slug, holding
one or more top-level ``- `` bullets written exactly as they would read under Unreleased,
links included: they are relative to the repository root, as in ``CHANGELOG.md``.
``changelog.d/README.md`` has the rules for contributors and is not a fragment.

Commands, run as ``python -m devtools.changelog <command>``:

- ``check`` validates every fragment, and that ``CHANGELOG.md`` has one Unreleased section
  that assembly can read. With ``--against REF`` it also compares the working tree's
  Unreleased section with the one at the merge base of REF and ``HEAD``, and fails when
  it gained more entries than it lost: a new entry belongs in a fragment, while an edit
  to an existing one replaces it and passes. An entry that came from a fragment the
  branch deletes is not new, which is what ``assemble`` produces, so a release passes,
  as does one that moves the entries under a version heading; nor is one REF already
  has, which a merge of REF in progress brings. ``make lint-check`` runs it
  against ``origin/main``.
- ``show`` prints the Unreleased section as ``assemble`` would leave it: everything on
  ``main`` that the last release lacks.
- ``assemble`` writes every fragment's entries at the top of the Unreleased section, above
  the entries already there, and deletes the fragments. The release checklist in
  ``docs/publishing.md`` runs it before tagging.

Assembly orders fragments newest first. A fragment's time is that of the newest commit on
``HEAD``'s first-parent history that added it, which on ``main`` is the merge that landed
it; a fragment no commit has added yet counts as newest, and the name breaks ties.
"""

from __future__ import annotations

import argparse
import math
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHANGELOG = "CHANGELOG.md"
FRAGMENTS = "changelog.d"
FRAGMENTS_README = "README.md"
UNRELEASED = "## Unreleased"
# A bead ID such as `mb-a4fa`, or a short slug: lowercase words joined by hyphens.
FRAGMENT_NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\.md")
# The end of a section: the next heading of level one or two.
_SECTION_END = re.compile(r"#{1,2} ")
# A local `git log` of the fragments directory takes well under a second.
GIT_TIMEOUT_SECONDS = 30
# How much of an entry an error message quotes.
_QUOTE_CHARS = 100


class ChangelogError(Exception):
    """Something assembly cannot read, with what to change in its message."""


@dataclass(frozen=True)
class Fragment:
    name: str
    entries: tuple[str, ...]


@dataclass(frozen=True)
class Unreleased:
    """``CHANGELOG.md``'s lines, the bounds of its Unreleased section, where new entries
    go in it, and the entries it holds."""

    lines: tuple[str, ...]
    start: int
    end: int
    insert_at: int
    entries: tuple[str, ...]


def is_fragment(path: str) -> bool:
    """Whether the repository-relative POSIX *path* names a changelog fragment."""

    parent, _, name = path.rpartition("/")
    return parent == FRAGMENTS and name.endswith(".md") and name != FRAGMENTS_README


def _split_entries(lines: list[str], where: str, first_line: int) -> tuple[int, list[str]]:
    """The index of the first top-level bullet in *lines* (``len(lines)`` when there is
    none) and each bullet's text, without trailing blank lines.

    A bullet is a line starting ``- `` and the blank or indented lines after it. Any other
    line after the first bullet is outside every bullet, and an error."""

    first_bullet = len(lines)
    entries: list[list[str]] = []
    for index, line in enumerate(lines):
        number = first_line + index
        if line.startswith(("* ", "+ ")):
            raise ChangelogError(f"{where}:{number}: write bullets with `- `, as {CHANGELOG} does")
        if line.startswith("- "):
            if not line[2:].strip():
                raise ChangelogError(f"{where}:{number}: an empty bullet")
            if not entries:
                first_bullet = index
            entries.append([line])
        elif entries:
            if line.strip() and not line.startswith((" ", "\t")):
                raise ChangelogError(
                    f"{where}:{number}: this line is outside every `- ` bullet; indent a "
                    "continuation line two spaces, and keep headings and notes out"
                )
            entries[-1].append(line)
    texts: list[str] = []
    for entry in entries:
        while not entry[-1].strip():
            entry.pop()
        texts.append("\n".join(entry))
    return first_bullet, texts


def parse_fragment(name: str, text: str) -> Fragment:
    """The entries of the fragment file *name*, whose content is *text*."""

    where = f"{FRAGMENTS}/{name}"
    if not FRAGMENT_NAME.fullmatch(name):
        raise ChangelogError(
            f"{where}: name a fragment for its bead or a short slug, in lowercase letters, "
            "digits, and hyphens, ending in .md"
        )
    lines = text.split("\n")
    first_bullet, entries = _split_entries(lines, where, 1)
    if not entries:
        raise ChangelogError(f"{where}: is empty; write the change as one or more `- ` bullets")
    leading = next((i for i, line in enumerate(lines[:first_bullet]) if line.strip()), None)
    if leading is not None:
        raise ChangelogError(
            f"{where}:{leading + 1}: a fragment holds only top-level `- ` bullets, and this "
            "line comes before the first one"
        )
    return Fragment(name, tuple(entries))


def read_unreleased(text: str) -> Unreleased:
    """Find the Unreleased section of ``CHANGELOG.md``'s *text* and its entries."""

    lines = text.split("\n")
    headings = [i for i, line in enumerate(lines) if line.rstrip() == UNRELEASED]
    if len(headings) != 1:
        raise ChangelogError(
            f"{CHANGELOG}: needs exactly one `{UNRELEASED}` heading, and has {len(headings)}"
        )
    start = headings[0]
    end = next(
        (i for i in range(start + 1, len(lines)) if _SECTION_END.match(lines[i])), len(lines)
    )
    body = lines[start + 1 : end]
    first_bullet, entries = _split_entries(body, CHANGELOG, start + 2)
    if entries:
        insert_at = start + 1 + first_bullet
    else:
        # After the section's note, or right under the heading when it has none.
        written = [i for i, line in enumerate(body) if line.strip()]
        insert_at = start + 1 + (written[-1] + 1 if written else 0)
    return Unreleased(tuple(lines), start, end, insert_at, tuple(entries))


def _git(root: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            text=True,
            check=False,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ChangelogError(f"git {' '.join(args)}: {error}") from error
    if result.returncode != 0:
        raise ChangelogError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def _fragment_paths(root: Path) -> list[Path]:
    """Every file in ``changelog.d/`` but its README and hidden files, such as an editor's."""

    directory = root / FRAGMENTS
    if not directory.is_dir():
        return []
    return sorted(
        path
        for path in directory.iterdir()
        if path.name != FRAGMENTS_README and not path.name.startswith(".")
    )


def _load(path: Path) -> Fragment:
    if not path.is_file():
        raise ChangelogError(f"{FRAGMENTS}/{path.name}: is not a file; fragments are files")
    return parse_fragment(path.name, path.read_text(encoding="utf-8"))


def read_fragments(root: Path) -> list[Fragment]:
    """The fragments under *root*, newest first, or the first one that does not parse."""

    fragments = [_load(path) for path in _fragment_paths(root)]
    if not fragments:
        return []
    added = landing_times(root)

    def newest_first(fragment: Fragment) -> tuple[float, str]:
        return (-added.get(f"{FRAGMENTS}/{fragment.name}", math.inf), fragment.name)

    return sorted(fragments, key=newest_first)


def landing_times(root: Path) -> dict[str, int]:
    """For each path under ``changelog.d/`` a commit on ``HEAD``'s first-parent history
    added, the commit time of the newest such commit.

    Following first parents makes a merge into ``main`` the commit that added a fragment
    its pull request wrote, so the time is when it landed. ``--no-renames`` counts a
    renamed fragment as added under its new name."""

    log = _git(
        root,
        "log",
        "--first-parent",
        "--diff-merges=first-parent",
        "--no-renames",
        "--diff-filter=A",
        "--name-only",
        "--format=%x00%ct",
        "--",
        f"{FRAGMENTS}/",
    )
    times: dict[str, int] = {}
    for commit in log.split("\0")[1:]:
        stamp, *names = commit.strip().split("\n")
        for name in names:
            if name:
                times.setdefault(name, int(stamp))
    return times


def assembled(changelog: str, fragments: list[Fragment]) -> str:
    """*changelog* with every entry of *fragments* at the top of its Unreleased section."""

    section = read_unreleased(changelog)
    new = [entry for fragment in fragments for entry in fragment.entries]
    if not new:
        return changelog
    before = list(section.lines[: section.insert_at])
    after = list(section.lines[section.insert_at :])
    block = "\n\n".join(new).split("\n")
    if before and before[-1].strip():
        block = ["", *block]
    if not after or after[0].strip():
        block = [*block, ""]
    return "\n".join([*before, *block, *after])


def unreleased_text(changelog: str) -> str:
    """The Unreleased section of *changelog*, from its heading to the last line it holds."""

    section = read_unreleased(changelog)
    lines = list(section.lines[section.start : section.end])
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines) + "\n"


def _normalized(entry: str) -> str:
    """An entry's words, so that rewrapping it does not make it a different entry."""

    return " ".join(entry.split())


def _quote(entry: str) -> str:
    words = _normalized(entry)
    return words if len(words) <= _QUOTE_CHARS else words[: _QUOTE_CHARS - 1] + "…"


def new_entry_problems(root: Path, against: str) -> list[str]:
    """Why the working tree's Unreleased section must not be merged: it gained more
    entries than it lost since the merge base of *against* and ``HEAD``.

    An entry is not new when it came from a fragment the working tree no longer has, which
    is what ``assemble`` does, or when *against* already has it: in the middle of merging
    *against* in, ``HEAD`` is still the commit before the merge, so the merge base is the
    older one and the entries the merge brings would otherwise count as this branch's."""

    try:
        base = _git(root, "merge-base", against, "HEAD").strip()
    except ChangelogError as error:
        remote, _, branch = against.partition("/")
        fetch = f"git fetch {remote} {branch}" if branch else "git fetch"
        raise ChangelogError(
            f"{error}\nThe check compares with the merge base of {against}; fetch it first "
            f"({fetch})."
        ) from error
    base_entries = read_unreleased(_git(root, "show", f"{base}:{CHANGELOG}")).entries
    tip_entries = read_unreleased(_git(root, "show", f"{against}:{CHANGELOG}")).entries
    head_entries = read_unreleased((root / CHANGELOG).read_text(encoding="utf-8")).entries
    moved: list[str] = []
    for path in _git(root, "ls-tree", "--name-only", base, f"{FRAGMENTS}/").splitlines():
        if is_fragment(path) and not (root / path).exists():
            name = path.rpartition("/")[2]
            moved += parse_fragment(name, _git(root, "show", f"{base}:{path}")).entries
    known = {_normalized(entry) for entry in (*base_entries, *tip_entries, *moved)}
    kept = {_normalized(entry) for entry in head_entries}
    added = [entry for entry in head_entries if _normalized(entry) not in known]
    removed = [entry for entry in base_entries if _normalized(entry) not in kept]
    if len(added) <= len(removed):
        return []
    count = len(added) - len(removed)
    message = (
        f"{CHANGELOG}: adds {count} {'entry' if count == 1 else 'entries'} to the Unreleased "
        f"section since the merge base with {against} ({base[:12]}). Write each change's "
        f"entry in its own file, {FRAGMENTS}/<bead>.md, and take it out of {CHANGELOG}: an "
        "addition there conflicts with every other open pull request "
        f"({FRAGMENTS}/{FRAGMENTS_README} has the rules). New or changed entries:"
    )
    return ["\n".join([message, *(f"    {_quote(entry)}" for entry in added)])]


def check(root: Path, against: str | None) -> list[str]:
    """Every problem with the fragments, ``CHANGELOG.md``, and, given *against*, the
    entries the working tree adds to Unreleased."""

    problems: list[str] = []
    try:
        read_unreleased((root / CHANGELOG).read_text(encoding="utf-8"))
    except ChangelogError as error:
        problems.append(str(error))
    for path in _fragment_paths(root):
        try:
            _load(path)
        except ChangelogError as error:
            problems.append(str(error))
    if against is not None and not problems:
        try:
            problems += new_entry_problems(root, against)
        except ChangelogError as error:
            problems.append(str(error))
    return problems


def assemble(root: Path) -> list[Fragment]:
    """Fold the fragments into ``CHANGELOG.md`` and delete them; return what was folded."""

    fragments = read_fragments(root)
    if not fragments:
        return []
    path = root / CHANGELOG
    path.write_text(assembled(path.read_text(encoding="utf-8"), fragments), encoding="utf-8")
    for fragment in fragments:
        (root / FRAGMENTS / fragment.name).unlink()
    return fragments


def main(argv: list[str] | None = None, root: Path = ROOT) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m devtools.changelog",
        description="Check, show, or assemble the changelog fragments in changelog.d/.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    check_parser = commands.add_parser(
        "check", help="validate the fragments and the Unreleased section"
    )
    check_parser.add_argument(
        "--against",
        metavar="REF",
        help="also fail when Unreleased gained entries since the merge base with REF",
    )
    commands.add_parser("show", help="print the Unreleased section as assembly would leave it")
    commands.add_parser("assemble", help="fold the fragments into CHANGELOG.md, deleting them")
    args = parser.parse_args(argv)

    try:
        if args.command == "check":
            problems = check(root, args.against)
            if problems:
                print("Changelog checks failed:")
                print("\n".join(f"- {problem}" for problem in problems))
                return 1
            print("Changelog checks passed.")
        elif args.command == "show":
            changelog = (root / CHANGELOG).read_text(encoding="utf-8")
            print(unreleased_text(assembled(changelog, read_fragments(root))), end="")
        else:
            folded = assemble(root)
            names = ", ".join(fragment.name for fragment in folded) or "none"
            print(f"Assembled {len(folded)} fragments into {CHANGELOG}: {names}")
    except ChangelogError as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
