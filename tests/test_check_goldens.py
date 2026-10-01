"""The golden machinery check fails on each thing it exists to catch.

Every probe builds a small tree and asserts the one finding it should produce, so the
check cannot go quiet without a test noticing. The first test runs it on the repository.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from devtools import check_goldens

MAKEFILE = """\
GOLDEN_RECORDERS := \\
\ttests/test_recorder.py
GOLDEN_DRIVERS := \\
\ttests/test_driver.py

golden-update:
\tGOLDEN_UPDATE=1 pytest $(GOLDEN_RECORDERS)
\tGOLDEN_UPDATE=1 pytest $(GOLDEN_DRIVERS)
"""
RECORDER = 'check_recording("answers.json", {}, transcript="cli-ui.tryscript.md")\n'
DRIVER = 'check_golden("banner.txt", "text")\n'
TRANSCRIPT = "# A transcript\n\n```console\n$ metab root --walk\nwalked\n? 0\n```\n"


def _tree(tmp_path: Path, **files: str) -> Path:
    """A repository with one recorder, one driver, and what each of them writes."""

    layout = {
        "Makefile": MAKEFILE,
        "tests/golden_harness.py": 'UPDATE_ENV = "GOLDEN_UPDATE"\n',
        "tests/test_recorder.py": RECORDER,
        "tests/test_driver.py": DRIVER,
        "tests/fixtures/answers.json": "{}\n",
        "tests/golden/banner.txt": "text\n",
        "tests/golden/cli-ui.tryscript.md": TRANSCRIPT,
    } | {name.replace("__", "/"): text for name, text in files.items()}
    for name, text in layout.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return tmp_path


def _write(root: Path, name: str, text: str) -> None:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_the_repository_passes() -> None:
    assert check_goldens.find_findings() == []


def test_the_probe_tree_passes(tmp_path: Path) -> None:
    assert check_goldens.find_findings(_tree(tmp_path), over_budget={}) == []


# ── golden-update regenerates everything ────────────────────────────


@pytest.mark.parametrize(
    ("name", "source", "finding"),
    [
        (
            "tests/test_other_recorder.py",
            RECORDER,
            "tests/test_other_recorder.py: calls check_recording but is not in GOLDEN_RECORDERS",
        ),
        (
            "tests/test_other_driver.py",
            DRIVER,
            "tests/test_other_driver.py: calls check_golden but is not in GOLDEN_DRIVERS",
        ),
        (
            "tests/test_own_switch.py",
            'import os\nif os.environ.get("GOLDEN_UPDATE") == "1":\n    pass\n',
            "tests/test_own_switch.py: reads GOLDEN_UPDATE itself",
        ),
    ],
    ids=["unlisted-recorder", "unlisted-driver", "own-update-switch"],
)
def test_a_module_golden_update_would_miss_is_reported(
    name: str, source: str, finding: str, tmp_path: Path
) -> None:
    root = _tree(tmp_path)
    _write(root, name, source)
    findings = check_goldens.registration_findings(root)
    assert len(findings) == 1 and findings[0].startswith(finding), findings


def test_a_recorder_listed_among_the_drivers_is_reported(tmp_path: Path) -> None:
    """The lists are ordered: a recorder that ran after tryscript would record too late."""

    root = _tree(tmp_path)
    _write(root, "Makefile", MAKEFILE.replace("test_recorder.py", "test_driver.py", 1))
    findings = check_goldens.registration_findings(root)
    assert any("tests/test_recorder.py: calls check_recording" in item for item in findings)
    assert any("test_driver.py, which does not call check_recording" in item for item in findings)


def test_a_stale_makefile_entry_is_reported(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    _write(root, "Makefile", MAKEFILE.replace("test_driver.py\n", "test_gone.py\n", 1))
    findings = check_goldens.registration_findings(root)
    assert "Makefile: GOLDEN_DRIVERS names tests/test_gone.py, which does not exist" in findings


def test_a_list_golden_update_does_not_run_is_reported(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    _write(root, "Makefile", MAKEFILE.replace("\tGOLDEN_UPDATE=1 pytest $(GOLDEN_RECORDERS)\n", ""))
    assert "Makefile: golden-update does not run $(GOLDEN_RECORDERS)" in (
        check_goldens.registration_findings(root)
    )


def test_a_transcript_no_driver_writes_is_reported(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    _write(root, "tests/golden/orphan.txt", "left behind\n")
    findings = check_goldens.registration_findings(root)
    assert len(findings) == 1 and findings[0].startswith("tests/golden/orphan.txt: no module")


def test_a_recording_that_is_not_committed_is_reported(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    (root / "tests/fixtures/answers.json").unlink()
    assert check_goldens.registration_findings(root) == [
        "tests/test_recorder.py: records tests/fixtures/answers.json, which is missing"
    ]


def test_a_recording_named_through_a_constant_is_found(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    _write(
        root,
        "tests/test_recorder.py",
        'RECORDING = "answers.json"\ncheck_recording(RECORDING, {}, transcript="x")\n',
    )
    assert check_goldens.recorded_fixtures(root) == [root / "tests/fixtures/answers.json"]


# ── size ────────────────────────────────────────────────────────────


@pytest.mark.parametrize("name", ["tests/golden/banner.txt", "tests/fixtures/answers.json"])
def test_a_file_over_the_budget_is_reported(name: str, tmp_path: Path) -> None:
    root = _tree(tmp_path)
    _write(root, name, "line\n" * 11)
    findings = check_goldens.size_findings(root, limit=10, over_budget={})
    assert findings == [
        f"{name}: 11 lines is over the 10-line review budget; split it by scenario, "
        "or show a repeated payload once"
    ]
    assert check_goldens.size_findings(root, limit=11, over_budget={}) == []


def test_a_listed_exception_is_allowed_until_its_file_fits(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    name = "tests/golden/banner.txt"
    listed = {name: "a bead shards it"}
    _write(root, name, "line\n" * 11)
    assert check_goldens.size_findings(root, limit=10, over_budget=listed) == []
    _write(root, name, "line\n" * 10)
    assert check_goldens.size_findings(root, limit=10, over_budget=listed) == [
        f"{name}: 10 lines is inside the budget now; remove it from OVER_BUDGET"
    ]


def test_an_exception_for_a_file_that_is_gone_is_reported(tmp_path: Path) -> None:
    findings = check_goldens.size_findings(
        _tree(tmp_path), limit=10, over_budget={"tests/golden/gone.txt": "a bead"}
    )
    assert findings == [
        "tests/golden/gone.txt: listed in OVER_BUDGET but is not a golden or a recording"
    ]


def test_every_listed_exception_names_its_bead() -> None:
    for name, reason in check_goldens.OVER_BUDGET.items():
        assert reason.startswith("mb-"), name


# ── transcripts that are not evidence ───────────────────────────────


def _transcript_findings(tmp_path: Path, body: str) -> list[str]:
    root = _tree(tmp_path)
    _write(root, "tests/golden/cli-ui.tryscript.md", f"---\nsandbox: true\n---\n{body}")
    return check_goldens.tryscript_findings(root)


@pytest.mark.parametrize(
    "command",
    [
        "metab root --api /api/tree | grep status",
        "HOME=$PWD/home metab root --api /api/tree | grep -c x",
        "metab root --api /api/tree 2>&1 | head -3",
        "metab root > out.txt; node session.js | sort",
    ],
)
def test_a_piped_command_under_test_is_reported(command: str, tmp_path: Path) -> None:
    findings = _transcript_findings(tmp_path, f"```console\n$ {command}\n? 0\n```\n")
    assert len(findings) == 1
    assert findings[0].startswith(
        "tests/golden/cli-ui.tryscript.md:5: the command under test is piped"
    )


@pytest.mark.parametrize(
    "command",
    [
        "metab root --api /api/tree > out.txt",
        "grep -E 'status' out.txt | sort -u",
        "metab root > out.txt; grep x out.txt | sort",
        "metab root || echo failed",
        "metab root > a.txt && diff a.txt b.txt | head",
    ],
)
def test_a_filter_over_a_saved_file_is_not_reported(command: str, tmp_path: Path) -> None:
    assert _transcript_findings(tmp_path, f"```console\n$ {command}\n? 0\n```\n") == []


def test_a_pipe_on_a_continuation_line_is_reported(tmp_path: Path) -> None:
    body = "```console\n$ metab root --api /api/tree \\\n> | grep status\n? 0\n```\n"
    assert len(_transcript_findings(tmp_path, body)) == 1


def test_a_transcript_with_no_command_is_reported(tmp_path: Path) -> None:
    assert _transcript_findings(tmp_path, "# Only prose\n") == [
        "tests/golden/cli-ui.tryscript.md: no console block with a command, "
        "so tryscript runs nothing in it"
    ]


def test_a_command_in_a_block_tryscript_does_not_run_is_reported(tmp_path: Path) -> None:
    body = "```console\n$ metab root\n? 0\n```\n\n```bash\n$ metab root --walk\nwalked\n```\n"
    findings = _transcript_findings(tmp_path, body)
    assert len(findings) == 1 and "cli-ui.tryscript.md:10: a command in a block" in findings[0]


def test_output_that_quotes_a_command_is_not_reported(tmp_path: Path) -> None:
    body = "```console\n$ metab root --help\nUsage:\n  $ metab ROOT | less\n? 0\n```\n"
    assert _transcript_findings(tmp_path, body) == []


@pytest.mark.parametrize("annotation", ["skip", "only"])
def test_an_annotation_that_hides_tests_is_reported(annotation: str, tmp_path: Path) -> None:
    body = f"## A test <!-- {annotation} -->\n\n```console\n$ metab root\n? 0\n```\n"
    findings = _transcript_findings(tmp_path, body)
    assert len(findings) == 1 and f"a `{annotation}` annotation" in findings[0]


def test_the_report_states_the_distribution(tmp_path: Path) -> None:
    report = check_goldens.report(_tree(tmp_path))
    assert report.splitlines()[0] == f"3 files, 9 lines; limit {check_goldens.MAX_GOLDEN_LINES}"
    assert "1 tryscript files with 1 commands" in report
