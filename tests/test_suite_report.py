"""``devtools/suite_report.py``: what it counts in a tree, and what it reads from a log."""

from __future__ import annotations

from devtools import suite_report
from devtools.suite_report import ADMITTED_GIT, NO_TIER, Size
from tests.required_tools import require_git

_MARKED = b"""import pytest


def darwin_only(test):
    return pytest.mark.macos_tier(test)


@pytest.mark.macos_tier
def test_marked_itself():
    pytest.skip("the file system is case-sensitive")


@darwin_only
def test_marked_by_a_decorator_the_module_defines():
    assert True


class TestGroup:
    def test_method(self):
        assert "def test_in_a_string(): is not a test"
"""
TREE: dict[str, bytes] = {
    "Makefile": b"ADMITTED_GIT_TESTS := \\\n\ttests/test_git_floor.py\n\ntest:\n\tpytest\n",
    "tests/conftest.py": (
        b'config.addinivalue_line(\n    "markers", "live_github: opt-in")\n'
        b'config.addinivalue_line("markers", "macos_tier: only on macOS")\n'
    ),
    "tests/suite_gates.py": b'ADMITTED_GIT_SKIP = "needs a Git the acquisition floor admits"\n',
    "tests/test_cache_marked.py": _MARKED,
    "tests/test_cache_plain.py": b"def test_one():\n    pass\n",
    "tests/test_git_floor.py": b"def test_a():\n    pass\n\n\nasync def test_b():\n    pass\n",
    "tests/test_live.py": b"pytestmark = [pytest.mark.live_github]\n\n\ndef test_live():\n    pass\n",
    "tests/dom/behavior.js": b"one\ntwo\n",
    "tests/golden/cli.tryscript.md": b"# Golden\n\n```console\n$ metab --version\n1.0\n```\n",
    "tests/golden/serve.txt": b"first\nlast line without a newline",
    "tests/fixtures/image.png": b"\x89PNG\r\n\0\0binary\n",
    "tests/fixtures/data.json": b"{}\n",
    "tests/manual-fixtures/readme.md": b"# Manual\n",
    "src/metabrowser/app.py": b"def test_not_under_tests():\n    pass\n",
}
LOG = "\n".join(
    [
        "lint\tRun gates\t2026-10-01T09:00:00.0000000Z tests/test_cache_plain.py is fine",
        "test (3.13)\tRun tests\t2026-10-01T09:46:06.5000000Z collected 9 items",
        "test (3.13)\tRun tests\t2026-10-01T09:46:06.5000000Z ",
        "test (3.13)\tRun tests\t2026-10-01T09:46:07.0000000Z tests/test_cache_marked.py s..    [ 33%]",
        "test (3.13)\tRun tests\t2026-10-01T09:46:09.0000000Z tests/test_git_floor.py .........",
        "test (3.13)\tRun tests\t2026-10-01T09:46:10.5000000Z ss                                [ 88%]",
        "test (3.13)\tRun tests\t2026-10-01T09:46:10.7500000Z tests/test_live.py s              [100%]",
        "test (3.13)\tRun tests\t2026-10-01T09:46:10.8Z ===== slowest 25 durations =====",
        "test (3.13)\tRun tests\t2026-10-01T09:46:10.8Z 1.50s call     tests/test_git_floor.py::test_a",
        "test (3.13)\tRun tests\t2026-10-01T09:46:10.8Z 0.25s setup    tests/test_git_floor.py::test_a[x::y]",
        "test (3.13)\tRun tests\t2026-10-01T09:46:10.8Z 0.40s call     tests/test_cache_plain.py::test_one",
        "test (3.13)\tRun tests\t2026-10-01T09:46:10.8Z SKIPPED [1] tests/test_cache_marked.py:10: "
        "the file system is case-sensitive",
        "test (3.13)\tRun tests\t2026-10-01T09:46:10.8Z SKIPPED [2] tests/admitted_git.py:70: "
        "needs a Git the acquisition floor admits; found 'git version 2.39.5'",
        "test (3.13)\tRun tests\t2026-10-01T09:46:10.8Z SKIPPED [1] tests/test_live.py:4: set "
        "METABROWSER_LIVE_GITHUB=1 to run",
        "test (3.13)\tRun tests\t2026-10-01T09:46:10.8Z SKIPPED [1] tests/test_cache_plain.py:1: "
        "symlinks are unavailable",
        "test (3.13)\tRun tests\t2026-10-01T09:46:10.9Z ===== 4 passed, 5 skipped in 4.40s =====",
        "test (3.13)\tRun tests\t2026-10-01T09:46:11.0Z npx --no-install tryscript run 'tests/golden/*'",
        "test (3.13)\tRun tests\t2026-10-01T09:46:14.0Z ^[[32m^[[1mPASS^[[22m^[[39m "
        "/work/metabrowser/tests/golden/cli.tryscript.md",
        "test (3.13)\tRun tests\t2026-10-01T09:46:14.0Z   ^[[32m✓^[[39m prints the version",
        "test (3.13)\tRun tests\t2026-10-01T09:46:14.5Z \x1b[31mFAIL\x1b[39m /x/tests/golden/other.tryscript.md",
    ]
)


def test_a_tree_is_measured_by_what_each_file_is() -> None:
    suite = suite_report.measure(TREE)

    assert suite.areas == {"cache": Size(2, 22, 4), "git": Size(1, 6, 2), "live": Size(1, 5, 1)}
    assert suite.python == Size(4, 33, 7)
    assert suite.helpers == Size(2, 4)
    assert suite.dom == Size(1, 2)
    # A last line with no newline is a line, and an image has none.
    assert suite.goldens == Size(2, 8)
    assert suite.fixtures == Size(2, 1)
    assert suite.other == Size(1, 1)
    assert suite.tryscript_commands == 1
    assert suite.tiers == {"the `live_github` tier": 1, "the `macos_tier` tier": 2, ADMITTED_GIT: 2}


def test_trees_side_by_side_show_the_change_from_the_first_to_the_last() -> None:
    smaller = {path: data for path, data in TREE.items() if path != "tests/test_cache_plain.py"}

    report = suite_report.render(
        ["before", "after"], [suite_report.measure(TREE), suite_report.measure(smaller)], areas=1
    )

    assert "| Measure | before | after | Change |" in report
    assert "| `tests/test_*.py` lines | 33 | 31 | -2 |" in report
    assert "| `def test_` functions | 7 | 6 | -1 |" in report
    assert "| `tests/dom` lines | 2 | 2 | 0 |" in report
    # Only the areas that changed are listed side by side.
    assert "| cache | 22 | 20 | -2 |" in report and "| git |" not in report


def test_a_ci_log_gives_each_file_the_time_between_its_progress_lines() -> None:
    run = suite_report.parse_log(LOG)

    assert (run.job, run.other_jobs) == ("test (3.13)", ["lint"])
    assert run.summary == "4 passed, 5 skipped in 4.40s"
    assert run.files == {
        "tests/test_cache_marked.py": 0.5,
        "tests/test_git_floor.py": 3.5,
        "tests/test_live.py": 0.25,
    }
    assert run.goldens == {
        "tests/golden/cli.tryscript.md": 3.0,
        "tests/golden/other.tryscript.md": 0.5,
    }
    assert suite_report.skip_tiers(run.skips, TREE) == {
        "the `live_github` tier": 1,
        "the `macos_tier` tier": 1,
        NO_TIER: 1,
        ADMITTED_GIT: 2,
    }
    assert suite_report.parse_log(LOG, job="lint").files == {}


def test_a_pytest_output_without_timestamps_gives_the_durations_it_listed() -> None:
    plain = "\n".join(
        line.split("Z ", 1)[1] for line in LOG.splitlines() if "\tRun tests\t" in line
    )

    run = suite_report.parse_log(plain)

    assert (run.job, run.files) == ("", {})
    assert run.listed == {"tests/test_git_floor.py": 1.75, "tests/test_cache_plain.py": 0.4}
    report = suite_report.render_run(run, TREE, top=1)
    assert "| tests/test_git_floor.py | 1.8 |" in report and "test_cache_plain" not in report
    assert "5 skips listed by -rs" in report


def test_the_working_tree_and_a_commit_are_read_the_same_way() -> None:
    require_git()

    tree = suite_report.read_tree(suite_report.WORKING_TREE)
    commit = suite_report.read_tree("HEAD")

    this = "tests/test_suite_report.py"
    assert tree[this] == (suite_report.REPO_ROOT / this).read_bytes()
    assert {"Makefile", "tests/conftest.py"} <= tree.keys() & commit.keys()
    assert all(path == "Makefile" or path.startswith("tests/") for path in tree | commit)
