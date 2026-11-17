"""``devtools/run_goldens.py``: each golden's verdict, whole output, and time, several at a
time, and a failure for any golden that gave no verdict."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest

from devtools import run_goldens
from devtools.check_goldens import makefile_list, recipe
from devtools.run_goldens import FAIL, NO_VERDICT, PASS, PREFIX
from tests.required_tools import require_node

ROOT = Path(__file__).resolve().parents[1]
# A stand-in for tryscript: what it prints for a file is the file's first line.
FAKE = r"""
import pathlib, sys, time
path = pathlib.Path(sys.argv[2]).resolve()
how = path.read_text(encoding="utf-8").split()[0]
if how == "meet":
    # Wait until every "meet" file has started: they finish only if they run at once.
    pathlib.Path(f"{path}.started").touch()
    deadline = time.monotonic() + 20
    while len(list(path.parent.glob("*.started"))) < 3:
        if time.monotonic() > deadline:
            sys.exit(1)
        time.sleep(0.05)
    how = "pass"
if how == "pass":
    print(f"PASS {path}\n  first line\n  second line\n\n2 passed (5ms)")
elif how == "colored":
    print(f"\x1b[32m\x1b[1mPASS\x1b[22m\x1b[39m {path}\n\n\x1b[32m1 passed\x1b[39m (5ms)")
elif how == "fail":
    print(f"FAIL {path}\n  - expected\n  + actual\n\n1 passed, 1 failed (5ms)")
    sys.exit(1)
elif how == "pass-but-exit-1":
    print(f"PASS {path}\n\n1 passed (5ms)")
    sys.exit(1)
elif how == "another-file":
    print(f"PASS {path.parent / 'elsewhere.tryscript.md'}\n\n1 passed (5ms)")
# "silent" prints nothing and exits 0.
"""


@pytest.fixture
def tryscript(tmp_path: Path) -> list[str]:
    fake = tmp_path / "fake_tryscript.py"
    fake.write_text(FAKE, encoding="utf-8")
    return [sys.executable, str(fake)]


def _goldens(directory: Path, **files: str) -> str:
    directory.mkdir()
    for name, how in files.items():
        (directory / f"{name}.tryscript.md").write_text(f"{how}\n", encoding="utf-8")
    return str(directory / "*.tryscript.md")


def _lines(output: str) -> dict[str, tuple[str, str]]:
    """Each file's golden line: its verdict and its time."""

    found = re.findall(rf"^{PREFIX} (\S+) (\d+\.\d) s (\S+)$", output, re.MULTILINE)
    return {Path(path).name: (verdict, seconds) for verdict, seconds, path in found}


def test_a_file_passes_only_on_its_own_pass_verdict_and_exit_0(
    tmp_path: Path, tryscript: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    pattern = _goldens(
        tmp_path / "goldens",
        a="pass",
        b="colored",
        c="fail",
        d="pass-but-exit-1",
        e="silent",
        f="another-file",
    )

    assert run_goldens.main(["--jobs", "2", pattern, "--", *tryscript]) == 1

    output = capsys.readouterr().out
    verdicts = {name: verdict for name, (verdict, _) in _lines(output).items()}
    assert verdicts == {
        "a.tryscript.md": PASS,
        "b.tryscript.md": PASS,
        "c.tryscript.md": FAIL,
        "d.tryscript.md": FAIL,
        "e.tryscript.md": NO_VERDICT,
        "f.tryscript.md": NO_VERDICT,
    }
    # Each file's count is tryscript's last line for it: 2, 1, 2, 1, none, and 1.
    assert f"{PREFIX} 6 files and 7 commands in " in output
    assert ", 2 at a time (" in output and "): 2 passed, 4 failed" in output
    failed = re.findall(rf"^{PREFIX} failed: (\S+)$", output, re.MULTILINE)
    assert [Path(path).name for path in failed] == [f"{name}.tryscript.md" for name in "cdef"]


def test_each_files_output_is_printed_whole_before_its_line(
    tmp_path: Path, tryscript: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    pattern = _goldens(tmp_path / "goldens", **dict.fromkeys("abcd", "pass"))

    assert run_goldens.main(["--jobs", "4", pattern, "--", *tryscript]) == 0

    lines = capsys.readouterr().out.splitlines()
    for name in "abcd":
        golden = str(tmp_path / "goldens" / f"{name}.tryscript.md")
        start = lines.index(f"PASS {Path(golden).resolve()}")
        assert lines[start + 1 : start + 5] == [
            "  first line",
            "  second line",
            "",
            "2 passed (5ms)",
        ]
        assert re.fullmatch(rf"{PREFIX} {PASS} \d+\.\d s {re.escape(golden)}", lines[start + 5])
    assert "4 files and 8 commands" in lines[-1] and lines[-1].endswith("4 passed, 0 failed")


def test_files_run_side_by_side_up_to_the_jobs_asked_for(
    tmp_path: Path, tryscript: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    """Each of three files waits until all three have started."""

    pattern = _goldens(tmp_path / "goldens", a="meet", b="meet", c="meet")

    assert run_goldens.main(["--jobs", "3", pattern, "--", *tryscript]) == 0
    assert capsys.readouterr().out.splitlines()[-1].endswith("3 passed, 0 failed")


def test_patterns_that_match_no_file_fail(
    tmp_path: Path, tryscript: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    pattern = str(tmp_path / "*.tryscript.md")

    assert run_goldens.main([pattern, "--", *tryscript]) == 1
    assert f"{PREFIX} no file matches {pattern}" in capsys.readouterr().err


def test_a_command_that_cannot_start_leaves_its_file_without_a_verdict(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    pattern = _goldens(tmp_path / "goldens", a="pass")

    assert run_goldens.main([pattern, "--", str(tmp_path / "no-such-tryscript")]) == 1
    assert _lines(capsys.readouterr().out)["a.tryscript.md"][0] == NO_VERDICT


@pytest.mark.parametrize(
    "arguments", [["tests/golden/*.tryscript.md"], ["tests/golden/*.tryscript.md", "--"]]
)
def test_a_run_without_a_command_is_refused(
    arguments: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    assert run_goldens.main(arguments) == 2
    assert "usage:" in capsys.readouterr().err


def test_make_test_runs_every_golden_through_the_runner_with_the_makefiles_tryscript(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The recipe's words, and ``TRYSCRIPT``'s words as the command, on two real goldens."""

    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    line = (
        "\t$(UV_RUN) python -m devtools.run_goldens --jobs $(GOLDEN_JOBS) '$(GOLDENS)' "
        "-- $(TRYSCRIPT)"
    )
    assert line in recipe(makefile, "test").split("\n")
    assert makefile_list(makefile, "GOLDENS") == ["tests/golden/*.tryscript.md"]
    require_node()
    command = [
        word.replace("$(CURDIR)", str(ROOT)).replace("$$PATH", os.environ["PATH"]).strip('"')
        for word in makefile_list(makefile, "TRYSCRIPT")
    ]
    assert command[0] == "env"
    goldens = [
        "tests/golden/cli-ui-treemap-not-indexed.tryscript.md",
        "tests/golden/cli-ui-tree-summary-line.tryscript.md",
    ]
    monkeypatch.chdir(ROOT)

    assert run_goldens.main(["--jobs", "2", *goldens, "--", *command]) == 0

    output = capsys.readouterr().out
    assert {name: verdict for name, (verdict, _) in _lines(output).items()} == {
        Path(golden).name: PASS for golden in goldens
    }
