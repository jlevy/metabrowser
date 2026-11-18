"""Changelog fragments: what `devtools/changelog.py` accepts, how `assemble` folds fragments
into CHANGELOG.md, and the guard that keeps new entries out of its Unreleased section."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from devtools import changelog
from devtools.changelog import ChangelogError, Fragment
from metabrowser.git.process import _REPO_PINNING_GIT_VARS
from tests.required_tools import require_git

ROOT = Path(__file__).resolve().parents[1]

# Two existing Unreleased entries, the second over two lines, between the note and the
# last release; the bytes `assemble` must leave exactly where they are.
CHANGELOG = """\
# Changelog

All notable changes are documented here.

## Unreleased

New entries live in [`changelog.d/`](changelog.d/README.md) until a release adds them.

- An existing entry.

- A second existing entry,
  over two lines.

## 0.12.0

- A released entry.

<!-- footer -->
"""


def _write(root: Path, files: dict[str, str]) -> None:
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def _git(root: Path, *args: str, when: int = 1_700_000_000) -> str:
    """Run git in the fixture repository *root*, committing at the Unix time *when*."""

    require_git()
    env = {key: value for key, value in os.environ.items() if key not in _REPO_PINNING_GIT_VARS}
    env.update(
        {
            "GIT_AUTHOR_NAME": "Fixture Author",
            "GIT_AUTHOR_EMAIL": "author@example.invalid",
            "GIT_COMMITTER_NAME": "Fixture Author",
            "GIT_COMMITTER_EMAIL": "author@example.invalid",
            "GIT_AUTHOR_DATE": f"@{when} +0000",
            "GIT_COMMITTER_DATE": f"@{when} +0000",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
        }
    )
    return subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True, text=True, env=env
    ).stdout


def _commit(root: Path, files: dict[str, str], message: str, when: int) -> None:
    _write(root, files)
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", message, when=when)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A repository whose `main` holds CHANGELOG and an empty `changelog.d/`, with a
    `pr` branch checked out from it."""

    _git(tmp_path, "init", "-q", "-b", "main")
    _commit(
        tmp_path,
        {"CHANGELOG.md": CHANGELOG, "changelog.d/README.md": "# Fragments\n"},
        "start",
        1_700_000_000,
    )
    _git(tmp_path, "checkout", "-q", "-b", "pr")
    return tmp_path


def _unreleased_body(text: str) -> str:
    return text.split("## Unreleased\n", 1)[1].split("## 0.12.0", 1)[0]


# ---- Fragments ----


def test_a_fragment_holds_top_level_bullets_with_their_continuations() -> None:
    text = "- One entry,\n  continued.\n\n- Another, with a list:\n\n  - nested\n"
    assert changelog.parse_fragment("mb-abcd.md", text) == Fragment(
        "mb-abcd.md",
        ("- One entry,\n  continued.", "- Another, with a list:\n\n  - nested"),
    )


@pytest.mark.parametrize(
    ("name", "text", "problem"),
    [
        ("mb-abcd.md", "", "changelog.d/mb-abcd.md: is empty"),
        ("mb-abcd.md", "\n\n", "changelog.d/mb-abcd.md: is empty"),
        ("mb-abcd.md", "A note.\n\n- An entry.\n", "changelog.d/mb-abcd.md:1: a fragment holds"),
        ("mb-abcd.md", "## Added\n\n- An entry.\n", "changelog.d/mb-abcd.md:1: a fragment holds"),
        ("mb-abcd.md", "- An entry.\n\nA note.\n", "changelog.d/mb-abcd.md:3: this line is"),
        ("mb-abcd.md", "- An entry.\n<!-- footer -->\n", "changelog.d/mb-abcd.md:2: this line"),
        ("mb-abcd.md", "* An entry.\n", "changelog.d/mb-abcd.md:1: write bullets with `- `"),
        ("mb-abcd.md", "-  \n", "changelog.d/mb-abcd.md:1: an empty bullet"),
        ("Fix_Thing.md", "- An entry.\n", "changelog.d/Fix_Thing.md: name a fragment"),
        ("mb-abcd.txt", "- An entry.\n", "changelog.d/mb-abcd.txt: name a fragment"),
    ],
)
def test_a_fragment_that_is_not_only_bullets_is_refused(name: str, text: str, problem: str) -> None:
    with pytest.raises(ChangelogError) as raised:
        changelog.parse_fragment(name, text)
    assert str(raised.value).startswith(problem)


def test_the_readme_is_not_a_fragment() -> None:
    assert changelog.is_fragment("changelog.d/mb-abcd.md")
    assert not changelog.is_fragment("changelog.d/README.md")
    assert not changelog.is_fragment("CHANGELOG.md")
    assert not changelog.is_fragment("docs/changelog.d/mb-abcd.md")


# ---- Assembly ----


def test_assembly_puts_fragments_above_the_existing_entries_and_moves_nothing() -> None:
    fragments = [
        Fragment("b.md", ("- Newest, first.", "- Its second bullet.")),
        Fragment("a.md", ("- Older,\n  second.",)),
    ]
    result = changelog.assembled(CHANGELOG, fragments)
    added = "- Newest, first.\n\n- Its second bullet.\n\n- Older,\n  second.\n\n"
    # The note stays above the new entries.
    note = "New entries live in [`changelog.d/`](changelog.d/README.md) until a release adds them."
    assert result == CHANGELOG.replace(f"{note}\n\n", f"{note}\n\n{added}")
    # Everything that was there is still there, byte for byte and in order.
    assert result.replace(added, "") == CHANGELOG


def test_assembly_after_a_release_fills_an_empty_unreleased_section() -> None:
    released = CHANGELOG.replace(
        "\n\n- An existing entry.", "\n\n## 0.13.0\n\n- An existing entry.", 1
    )
    result = changelog.assembled(released, [Fragment("a.md", ("- New.",))])
    assert changelog.unreleased_text(result) == (
        "## Unreleased\n\nNew entries live in [`changelog.d/`](changelog.d/README.md) until a "
        "release adds them.\n\n- New.\n"
    )
    assert result.replace("- New.\n\n", "", 1) == released


def test_assembly_without_a_note_goes_right_under_the_heading() -> None:
    bare = "# Changelog\n\n## Unreleased\n\n## 0.12.0\n\n- Old.\n"
    result = changelog.assembled(bare, [Fragment("a.md", ("- New.",))])
    assert result == "# Changelog\n\n## Unreleased\n\n- New.\n\n## 0.12.0\n\n- Old.\n"


def test_assembly_with_no_fragments_changes_nothing() -> None:
    assert changelog.assembled(CHANGELOG, []) == CHANGELOG


@pytest.mark.parametrize(
    ("text", "problem"),
    [
        ("# Changelog\n\n## 0.12.0\n", "CHANGELOG.md: needs exactly one `## Unreleased`"),
        ("## Unreleased\n\n## Unreleased\n", "CHANGELOG.md: needs exactly one `## Unreleased`"),
        ("## Unreleased\n\n- An entry.\nA note.\n", "CHANGELOG.md:4: this line is outside"),
    ],
)
def test_a_changelog_assembly_cannot_read_is_refused(text: str, problem: str) -> None:
    with pytest.raises(ChangelogError) as raised:
        changelog.read_unreleased(text)
    assert str(raised.value).startswith(problem)


def test_assemble_orders_by_landing_newest_first_and_deletes_the_fragments(repo: Path) -> None:
    # `old` lands through a merge, `late` is committed on main afterwards, and `pending`
    # is not committed at all. `old`'s own commit is the newest commit of the three, so
    # a merge's time, not its branch commit's, must decide the order.
    _git(repo, "checkout", "-q", "-b", "feature", "main")
    _commit(repo, {"changelog.d/old.md": "- Landed first.\n"}, "old", 1_700_000_900)
    _git(repo, "checkout", "-q", "main")
    _git(repo, "merge", "-q", "--no-ff", "-m", "merge old", "feature", when=1_700_000_100)
    _commit(repo, {"changelog.d/late.md": "- Landed second.\n"}, "late", 1_700_000_200)
    _commit(repo, {"changelog.d/also.md": "- Landed with late.\n"}, "also", 1_700_000_200)
    _write(repo, {"changelog.d/pending.md": "- Not committed.\n"})

    assert [f.name for f in changelog.read_fragments(repo)] == [
        "pending.md",
        "also.md",
        "late.md",
        "old.md",
    ]
    folded = changelog.assemble(repo)

    assert [f.name for f in folded] == ["pending.md", "also.md", "late.md", "old.md"]
    assert sorted(p.name for p in (repo / "changelog.d").iterdir()) == ["README.md"]
    body = _unreleased_body((repo / "CHANGELOG.md").read_text(encoding="utf-8"))
    assert body.index("Not committed") < body.index("Landed with late")
    assert body.index("Landed with late") < body.index("Landed second")
    assert body.index("Landed second") < body.index("Landed first")
    assert body.index("Landed first") < body.index("An existing entry")


def test_assemble_refuses_a_bad_fragment_and_writes_nothing(repo: Path) -> None:
    _write(repo, {"changelog.d/good.md": "- Good.\n", "changelog.d/bad.md": "# Bad\n"})
    with pytest.raises(ChangelogError, match="changelog.d/bad.md"):
        changelog.assemble(repo)
    assert (repo / "CHANGELOG.md").read_text(encoding="utf-8") == CHANGELOG
    assert (repo / "changelog.d/good.md").exists()


def test_show_prints_unreleased_as_assembly_would_leave_it(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(repo, {"changelog.d/mb-abcd.md": "- Pending.\n"})
    assert changelog.main(["show"], root=repo) == 0
    assert capsys.readouterr().out == (
        "## Unreleased\n\nNew entries live in [`changelog.d/`](changelog.d/README.md) until a "
        "release adds them.\n\n- Pending.\n\n- An existing entry.\n\n- A second existing "
        "entry,\n  over two lines.\n"
    )
    # Showing changes nothing.
    assert (repo / "changelog.d/mb-abcd.md").exists()
    assert (repo / "CHANGELOG.md").read_text(encoding="utf-8") == CHANGELOG


# ---- check, and the guard against new Unreleased entries ----


def test_check_passes_fragments_and_reports_each_bad_one(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(repo, {"changelog.d/mb-abcd.md": "- Fine.\n", "changelog.d/.DS_Store": "x"})
    assert changelog.main(["check"], root=repo) == 0
    assert capsys.readouterr().out == "Changelog checks passed.\n"

    _write(repo, {"changelog.d/empty.md": "", "changelog.d/Bad Name.md": "- Fine.\n"})
    assert changelog.main(["check"], root=repo) == 1
    out = capsys.readouterr().out
    assert "changelog.d/Bad Name.md: name a fragment" in out
    assert "changelog.d/empty.md: is empty" in out


def _guard(repo: Path) -> list[str]:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "--allow-empty", "-m", "change", when=1_700_000_500)
    return changelog.check(repo, "main")


def test_the_guard_fails_a_branch_that_adds_an_unreleased_entry(repo: Path) -> None:
    added = CHANGELOG.replace("- An existing entry.", "- A new entry.\n\n- An existing entry.")
    _write(repo, {"CHANGELOG.md": added})
    problems = _guard(repo)
    assert len(problems) == 1
    assert problems[0].startswith("CHANGELOG.md: adds 1 entry to the Unreleased section")
    assert "changelog.d/<bead>.md" in problems[0]
    assert problems[0].endswith("\n    - A new entry.")


def test_the_guard_passes_a_branch_that_writes_a_fragment(repo: Path) -> None:
    _write(repo, {"changelog.d/mb-abcd.md": "- A new entry.\n"})
    assert _guard(repo) == []


def test_the_guard_passes_a_branch_that_corrects_or_rewraps_an_existing_entry(
    repo: Path,
) -> None:
    edited = CHANGELOG.replace("- An existing entry.", "- An existing entry, corrected.")
    rewrapped = edited.replace("entry,\n  over two lines.", "entry, over two lines.")
    _write(repo, {"CHANGELOG.md": rewrapped})
    assert _guard(repo) == []


def test_the_guard_counts_an_addition_beside_an_edit(repo: Path) -> None:
    edited = CHANGELOG.replace("- An existing entry.", "- New.\n\n- An existing entry, edited.")
    _write(repo, {"CHANGELOG.md": edited})
    problems = _guard(repo)
    assert len(problems) == 1
    assert problems[0].startswith("CHANGELOG.md: adds 1 entry")
    assert problems[0].endswith("\n    - New.\n    - An existing entry, edited.")


def test_the_guard_passes_a_release_that_assembles_the_fragments(repo: Path) -> None:
    _git(repo, "checkout", "-q", "main")
    _commit(repo, {"changelog.d/mb-abcd.md": "- Pending.\n"}, "fragment", 1_700_000_100)
    _git(repo, "checkout", "-q", "-b", "release")
    changelog.assemble(repo)
    assert _guard(repo) == []

    # ... and the version heading under the note that the release adds next.
    text = (repo / "CHANGELOG.md").read_text(encoding="utf-8")
    note = "until a release adds them.\n\n"
    _write(repo, {"CHANGELOG.md": text.replace(note, f"{note}## 0.13.0\n\n", 1)})
    assert _guard(repo) == []
    assert (
        changelog.read_unreleased((repo / "CHANGELOG.md").read_text(encoding="utf-8")).entries == ()
    )


def test_the_guard_compares_with_the_merge_base_not_the_tip(repo: Path) -> None:
    # main moves on after the branch left it: a release folds an entry in. The branch,
    # which never touched CHANGELOG.md, adds nothing.
    _git(repo, "checkout", "-q", "main")
    moved = CHANGELOG.replace("- An existing entry.", "- Landed later.\n\n- An existing entry.")
    _commit(repo, {"CHANGELOG.md": moved}, "main moves", 1_700_000_300)
    _git(repo, "checkout", "-q", "pr")
    _write(repo, {"changelog.d/mb-abcd.md": "- Mine.\n"})
    assert _guard(repo) == []


def test_the_guard_passes_a_merge_of_main_in_progress(repo: Path) -> None:
    # main gains an entry after the branch left it, and the branch merges main in. Until
    # the merge is committed HEAD is the branch's own commit, so the merge base is the
    # older main, and only main's tip shows the entry is not the branch's.
    _write(repo, {"changelog.d/mb-abcd.md": "- Mine.\n"})
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "fragment", when=1_700_000_100)
    _git(repo, "checkout", "-q", "main")
    moved = CHANGELOG.replace("- An existing entry.", "- Landed later.\n\n- An existing entry.")
    _commit(repo, {"CHANGELOG.md": moved}, "main moves", 1_700_000_300)
    _git(repo, "checkout", "-q", "pr")
    _git(repo, "merge", "-q", "--no-commit", "--no-ff", "main", when=1_700_000_400)
    assert (repo / "CHANGELOG.md").read_text(encoding="utf-8") == moved
    assert changelog.check(repo, "main") == []

    # The same entry written by the branch itself, not merged from main, still fails.
    _git(repo, "merge", "--abort")
    _write(repo, {"CHANGELOG.md": moved.replace("Landed later", "Mine, in the changelog")})
    assert changelog.check(repo, "main")[0].startswith("CHANGELOG.md: adds 1 entry")


def test_the_guard_says_to_fetch_a_ref_it_cannot_find(repo: Path) -> None:
    problems = changelog.check(repo, "upstream/trunk")
    assert len(problems) == 1
    assert "git merge-base upstream/trunk HEAD failed" in problems[0]
    assert "(git fetch upstream trunk)" in problems[0]


def test_this_repository_passes_its_own_check() -> None:
    require_git()
    assert changelog.check(ROOT, None) == []
