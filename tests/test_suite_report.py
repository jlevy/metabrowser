"""``devtools/suite_report.py``: what it counts in a tree, and what it reads from a log."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from devtools import suite_report
from devtools.check_goldens import recipe
from devtools.run_goldens import PREFIX
from devtools.suite_report import REPO_ROOT, Size
from metabrowser.commit_ids import short_commit
from tests.required_tools import require_git
from tests.suite_timing import TITLE

_GROUPED = b'''SOURCE = """
def test_at_the_start_of_a_line_in_a_string():
    pass
"""


def test_at_module_level():
    def test_nested_in_a_test():
        pass


class TestGroup:
    def test_method(self):
        pass

    async def test_async_method(self):
        pass


class Helper:
    def test_in_a_class_pytest_does_not_collect(self):
        pass
'''
TREE: dict[str, bytes] = {
    "tests/conftest.py": b"import pytest\n",
    "tests/test_cache_grouped.py": _GROUPED,
    "tests/test_cache_plain.py": b"def test_one():\n    pass\n",
    "tests/test_git_floor.py": b"def test_a():\n    pass\n\n\nasync def test_b():\n    pass\n",
    "tests/dom/behavior.js": b"one\ntwo\n",
    "tests/golden/cli.tryscript.md": b"# Golden\n\n```console\n$ metab --version\n1.0\n```\n",
    "tests/golden/serve.txt": b"first\nlast line without a newline",
    "tests/fixtures/image.png": b"\x89PNG\r\n\0\0binary\n",
    "tests/fixtures/data.json": b"{}\n",
    "tests/manual-fixtures/readme.md": b"# Manual\n",
    "src/metabrowser/app.py": b"def test_not_under_tests():\n    pass\n",
}
_STAMP = "test (3.13)\tRun tests\t2026-10-01T09:46:"
LOG = "\n".join(
    [
        "lint\tRun gates\t2026-10-01T09:00:00.0000000Z tests/test_cache_plain.py is fine",
        f"{_STAMP}06.5000000Z collected 9 items",
        f"{_STAMP}06.5000000Z ",
        f"{_STAMP}07.0000000Z tests/test_cache_grouped.py s..                    [ 33%]",
        f"{_STAMP}09.0000000Z tests/test_git_floor.py .........",
        f"{_STAMP}10.5000000Z ss                                                [ 88%]",
        f"{_STAMP}10.7500000Z tests/test_cache_plain.py s                        [100%]",
        f"{_STAMP}10.8Z ===== slowest 25 durations =====",
        f"{_STAMP}10.8Z 1.50s call     tests/test_git_floor.py::test_a",
        f"{_STAMP}10.8Z SKIPPED [1] tests/test_cache_grouped.py:7: the file system is case-sensitive",
        f"{_STAMP}10.8Z SKIPPED [2] tests/admitted_git.py:70: needs a Git the floor admits",
        f"{_STAMP}10.8Z SKIPPED [1] tests/test_cache_plain.py:1: the file system is case-sensitive",
        f"{_STAMP}10.9Z ===== 5 passed, 4 skipped in 4.40s =====",
        f"{_STAMP}11.0Z npx --no-install tryscript run 'tests/golden/*'",
        f"{_STAMP}14.0Z ^[[32m^[[1mPASS^[[22m^[[39m /work/metabrowser/tests/golden/cli.tryscript.md",
        f"{_STAMP}14.0Z   ^[[32m✓^[[39m prints the version",
        f"{_STAMP}14.5Z \x1b[31mFAIL\x1b[39m /x/tests/golden/other.tryscript.md",
    ]
)


def test_a_tree_is_measured_by_what_each_file_is() -> None:
    suite = suite_report.measure(TREE)

    # Tests are the functions pytest collects: not one in a string, nested in a test, or
    # in a class whose name does not start with Test.
    assert suite.areas == {"cache": Size(2, 24, 4), "git": Size(1, 6, 2)}
    assert suite.python == Size(3, 30, 6)
    assert suite.helpers == Size(1, 1)
    assert suite.dom == Size(1, 2)
    # A last line with no newline is a line, and an image has none.
    assert suite.goldens == Size(2, 8)
    assert suite.fixtures == Size(2, 1)
    assert suite.other == Size(1, 1)
    assert suite.tryscript_commands == 1


def test_one_tree_lists_its_largest_areas_and_folds_the_rest() -> None:
    report = suite_report.render_tree("the tree", suite_report.measure(TREE), areas=1).splitlines()

    assert report[:5] == [
        "| Area | Files | Lines | Test functions |",
        "| --- | ---: | ---: | ---: |",
        "| cache | 2 | 24 | 4 |",
        "| 1 smaller areas | 1 | 6 | 2 |",
        "| all Python tests | 3 | 30 | 6 |",
    ]
    assert report[6:10] == [
        "| Measure | the tree |",
        "| --- | ---: |",
        "| `tests/test_*.py` files | 3 |",
        "| `tests/test_*.py` lines | 30 |",
    ]


def test_trees_side_by_side_show_the_change_from_the_first_to_the_last() -> None:
    without_plain = {path: data for path, data in TREE.items() if "plain" not in path}
    without_git = {path: data for path, data in TREE.items() if "git" not in path}
    suites = [suite_report.measure(tree) for tree in (TREE, without_plain, without_git)]

    report = suite_report.render_trees(["first", "middle", "last"], suites, areas=1)

    assert "| Measure | first | middle | last | Change |" in report
    assert "| `tests/test_*.py` lines | 30 | 28 | 24 | -6 |" in report
    assert "| test functions | 6 | 5 | 4 | -2 |" in report
    assert "| `tests/dom` lines | 2 | 2 | 2 | 0 |" in report
    # Only areas that differ between the first and the last are listed, largest change
    # first, and `areas` bounds how many.
    assert report.splitlines()[-3:] == [
        "| Lines of Python tests, 1 of 1 changed areas | first | middle | last | Change |",
        "| --- | ---: | ---: | ---: | ---: |",
        "| git | 6 | 6 | 0 | -6 |",
    ]


def test_a_ci_log_gives_each_file_the_time_between_its_progress_lines() -> None:
    run = suite_report.parse_log(LOG)

    assert (run.job, run.other_jobs) == ("test (3.13)", ["lint"])
    assert run.summaries == ["5 passed, 4 skipped in 4.40s"]
    assert run.files == {
        "tests/test_cache_grouped.py": 0.5,
        "tests/test_git_floor.py": 3.5,
        "tests/test_cache_plain.py": 0.25,
    }
    assert run.goldens == {
        "tests/golden/cli.tryscript.md": 3.0,
        "tests/golden/other.tryscript.md": 0.5,
    }
    assert run.skips == {
        "the file system is case-sensitive": 2,
        "needs a Git the floor admits": 2,
    }
    assert suite_report.parse_log(LOG, job="lint").files == {}
    report = suite_report.render_run(run, top=1)
    assert "| tests/test_git_floor.py | 3.5 |" in report and "test_cache_plain" not in report
    assert "4 skips listed by -rs" in report


def test_a_pytest_output_without_timestamps_gives_the_summary_and_no_times() -> None:
    plain = "\n".join(line.split("Z ", 1)[1] for line in LOG.splitlines() if _STAMP in line)

    run = suite_report.parse_log(plain)

    assert (run.job, run.files, run.goldens) == ("", {}, {})
    assert run.summaries == ["5 passed, 4 skipped in 4.40s"]
    assert run.skips.total() == 4
    assert "No time per file in this log" in suite_report.render_run(run, top=1)


# A job that runs a session under pytest-xdist, whose progress lines name no file, then a
# session in one process, then the goldens several at a time: each session lists its files'
# times, and each golden has its own line.
_LISTED = "\n".join(
    [
        f"{_STAMP}06.0Z 3 workers [3 items]",
        f"{_STAMP}07.0Z ...                                              [100%]",
        f"{_STAMP}07.1Z ===== {TITLE.format(shown='all', files=2, seconds=5.25)} =====",
        f"{_STAMP}07.1Z 4.00s tests/test_cache_grouped.py",
        f"{_STAMP}07.1Z 1.25s tests/test_git_floor.py",
        f"{_STAMP}07.2Z ===== 3 passed in 2.10s =====",
        f"{_STAMP}08.0Z collected 2 items",
        f"{_STAMP}09.0Z tests/test_cache_plain.py ..                       [100%]",
        f"{_STAMP}09.1Z ===== {TITLE.format(shown='slowest 1', files=1, seconds=0.5)} =====",
        f"{_STAMP}09.1Z 0.50s tests/test_cache_plain.py",
        f"{_STAMP}09.2Z ===== 2 passed in 0.60s =====",
        f"{_STAMP}20.0Z ^[[32mPASS^[[39m /work/metabrowser/tests/golden/cli.tryscript.md",
        f"{_STAMP}20.0Z {PREFIX} PASS 3.2 s tests/golden/cli.tryscript.md",
        f"{_STAMP}20.5Z {PREFIX} FAIL 9.0 s tests/golden/other.tryscript.md",
        f"{_STAMP}21.0Z {PREFIX} 2 files and 4 commands in 9.1 s, 4 at a time (12.2 s of files)",
    ]
)


def test_a_log_reads_the_times_each_session_and_golden_listed() -> None:
    run = suite_report.parse_log(_LISTED)

    assert run.job == "test (3.13)"
    assert run.summaries == ["3 passed in 2.10s", "2 passed in 0.60s"]
    # The listed times, not the gaps between the second session's progress lines.
    assert run.files == {
        "tests/test_cache_grouped.py": 4.0,
        "tests/test_git_floor.py": 1.25,
        "tests/test_cache_plain.py": 0.5,
    }
    assert run.listed == [(2, 5.25), (1, 0.5)]
    assert run.goldens == {
        "tests/golden/cli.tryscript.md": 3.2,
        "tests/golden/other.tryscript.md": 9.0,
    }
    report = suite_report.render_run(run, top=1)
    assert "pytest: 3 passed in 2.10s\npytest: 2 passed in 0.60s" in report
    assert "3 test files, 5.8 s of test time, as 2 session(s) listed them" in report
    assert "| tests/test_cache_grouped.py | 4.0 |" in report
    assert "2 tryscript goldens, 12.2 s of files" in report


def test_a_real_session_lists_its_files_as_the_report_reads_them(tmp_path: Path) -> None:
    """``tests/suite_timing.py`` prints the section that ``parse_log`` reads."""

    modules = ["tests/test_run_goldens.py", "tests/test_suite_tiers.py"]
    session = [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-p", "no:sugar"]
    completed = subprocess.run(
        [*session, f"--basetemp={tmp_path}", "--file-durations=0", "-k", "refused", *modules],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=50,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    run = suite_report.parse_log(completed.stdout)
    assert sorted(run.files) == modules
    assert [files for files, _ in run.listed] == [2]
    assert len(run.summaries) == 1 and " passed, " in run.summaries[0]


def _head() -> str:
    require_git()
    return short_commit(
        subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    )


def test_the_working_tree_and_a_commit_are_read_and_named() -> None:
    head = _head()

    tree = suite_report.read_tree(suite_report.WORKING_TREE)
    commit = suite_report.read_tree("HEAD")

    this = "tests/test_suite_report.py"
    assert tree[this] == (REPO_ROOT / this).read_bytes()
    assert "tests/conftest.py" in tree.keys() & commit.keys()
    assert all(path.startswith("tests/") for path in tree | commit)
    assert suite_report.describe(suite_report.WORKING_TREE) == f"working tree on {head}"
    assert suite_report.describe("HEAD") == f"HEAD ({head})"
    assert suite_report.describe(head) == head


def test_the_make_target_runs_the_report_on_commits_and_a_log(tmp_path: Path) -> None:
    """Run the recipe of ``make test-report`` with ``REFS`` and ``LOG`` filled in."""

    head = _head()
    log = tmp_path / "run.log"
    log.write_text(LOG, encoding="utf-8")
    (line,) = recipe((REPO_ROOT / "Makefile").read_text(encoding="utf-8"), "test-report").split(
        "\n"
    )
    assert line == "\t$(UV_RUN) python -m devtools.suite_report $(REFS) $(if $(LOG),--log $(LOG))"
    command = line.split("python ", 1)[1].replace("$(REFS)", "HEAD . --areas 2")
    command = command.replace("$(if $(LOG),--log $(LOG))", f"--log {log}")

    completed = subprocess.run(
        [sys.executable, *command.split()],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=50,
    )

    assert completed.returncode == 0, completed.stderr
    report = completed.stdout
    assert f"| Measure | HEAD ({head}) | working tree on {head} | Change |" in report
    assert "job: test (3.13)" in report and "pytest: 5 passed, 4 skipped in 4.40s" in report


def test_one_tree_is_reported_by_area_with_the_number_of_areas_asked_for(
    capsys: pytest.CaptureFixture[str],
) -> None:
    require_git()

    assert suite_report.main(["HEAD", "--areas", "2"]) == 0

    report = capsys.readouterr().out.splitlines()
    assert report[0] == "| Area | Files | Lines | Test functions |"
    assert " smaller areas | " in report[4] and report[5].startswith("| all Python tests | ")
