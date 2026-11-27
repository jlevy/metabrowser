"""``devtools/run_goldens.py``: each golden's verdict, whole output, and time, several at a
time, and a failure for any golden that gave no verdict."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from devtools import run_goldens
from devtools.check_goldens import makefile_list, recipe
from devtools.run_goldens import FAIL, NO_VERDICT, PASS, PREFIX
from devtools.shard_weights import GOLDENS, load
from tests.required_tools import require_node

ROOT = Path(__file__).resolve().parents[1]
# A stand-in for tryscript: what it prints for a file is the file's first line. The file's
# path is its last argument, after `run` and any option.
FAKE = r"""
import pathlib, sys, time
assert sys.argv[1] == "run", sys.argv
path = pathlib.Path(sys.argv[-1]).resolve()
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
    return [sys.executable, str(fake), "run"]


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


def test_every_pattern_must_match_before_sharding(
    tmp_path: Path, tryscript: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    pattern = _goldens(tmp_path / "goldens", present="pass")
    missing = str(tmp_path / "missing.tryscript.md")

    assert run_goldens.main(["--shard", "2/2", pattern, missing, "--", *tryscript]) == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert output.err.strip() == f"{PREFIX} no file matches {missing}"

    # The match is real even though the second shard has nothing to run.
    assert run_goldens.main(["--shard", "2/2", pattern, "--", *tryscript]) == 0
    assert "0 files and 0 commands" in capsys.readouterr().out


def test_a_command_that_cannot_start_leaves_its_file_without_a_verdict(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    pattern = _goldens(tmp_path / "goldens", a="pass")

    assert run_goldens.main([pattern, "--", str(tmp_path / "no-such-tryscript")]) == 1
    assert _lines(capsys.readouterr().out)["a.tryscript.md"][0] == NO_VERDICT


def test_the_parts_of_a_shard_hold_every_file_once_and_balance_by_time(tmp_path: Path) -> None:
    directory = tmp_path / "goldens"
    directory.mkdir()
    seconds: dict[str, float] = {}
    for name, time in {"a": 90, "b": 50, "c": 40, "d": 30, "e": 10}.items():
        path = directory / f"{name}.tryscript.md"
        # A file's size says nothing of its time: the slowest is the smallest.
        path.write_text("pass" + "x" * (100 - time), encoding="utf-8")
        seconds[str(path)] = float(time)
    paths = run_goldens.matched([str(directory / "*.tryscript.md")])

    parts = [run_goldens.dealt(paths, index, 2, seconds) for index in (1, 2)]

    assert sorted(parts[0] + parts[1]) == paths
    assert [[Path(path).stem.split(".")[0] for path in part] for part in parts] == [
        ["a", "d"],
        ["b", "c", "e"],
    ]
    assert run_goldens.dealt(paths, 1, 1, seconds) == paths
    # With no time measured for any, as for these, the parts hold the same number of files.
    assert [len(run_goldens.dealt(paths, index, 2)) for index in (1, 2)] == [3, 2]


def test_the_goldens_are_dealt_by_their_measured_seconds_wherever_they_are_named_from(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The committed weights name a golden from the repository's root, as CI's logs do."""

    measured = load(GOLDENS)
    paths = run_goldens.matched([str(ROOT / "tests/golden/*.tryscript.md")])
    assert len(measured.keys() & {Path(path).relative_to(ROOT).as_posix() for path in paths}) > 9
    parts = [run_goldens.dealt(paths, index, 2) for index in (1, 2)]
    assert sorted(parts[0] + parts[1]) == paths

    monkeypatch.chdir(ROOT / "tests")
    relative = run_goldens.matched(["golden/*.tryscript.md"])

    assert [Path(path).name for path in run_goldens.dealt(relative, 1, 2)] == [
        Path(path).name for path in parts[0]
    ]
    seconds = [
        sum(measured.get(Path(path).relative_to(ROOT).as_posix(), 0.0) for path in part)
        for part in parts
    ]
    assert max(seconds) <= sum(seconds) / 2 + max(measured.values())


def test_a_shard_runs_only_its_part_and_a_bad_shard_is_refused(
    tmp_path: Path, tryscript: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    pattern = _goldens(tmp_path / "goldens", big="pass", small="pass")

    assert run_goldens.main(["--shard", "2/2", pattern, "--", *tryscript]) == 0

    assert list(_lines(capsys.readouterr().out)) == ["small.tryscript.md"]
    for bad in ("0/2", "3/2", "1", "a/b"):
        with pytest.raises(SystemExit):
            run_goldens.main(["--shard", bad, pattern, "--", *tryscript])


@pytest.mark.parametrize(
    "arguments", [["tests/golden/*.tryscript.md"], ["tests/golden/*.tryscript.md", "--"]]
)
def test_a_run_without_a_command_is_refused(
    arguments: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    assert run_goldens.main(arguments) == 2
    assert "usage:" in capsys.readouterr().err


@pytest.mark.parametrize("only", ["", "   "])
def test_explicit_empty_only_refuses_to_update(only: str) -> None:
    result = subprocess.run(
        ["make", "--no-print-directory", "-n", "golden-update", f"ONLY={only}"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "ONLY needs at least one transcript pattern or module" in result.stderr
    assert result.stdout == ""


def test_omitting_only_updates_all_goldens(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ONLY", raising=False)
    monkeypatch.delenv("MAKEFLAGS", raising=False)
    result = subprocess.run(
        ["make", "-n", "golden-update"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "run --update" in result.stdout
    assert "tests/golden/*.tryscript.md" in result.stdout


def test_only_limits_updates_even_when_goldens_has_a_command_line_value() -> None:
    result = subprocess.run(
        [
            "make",
            "-n",
            "golden-update",
            "GOLDENS=tests/golden/*.tryscript.md",
            "ONLY=tests/golden/cli-doctor.tryscript.md",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "run --update" in result.stdout
    assert "tests/golden/cli-doctor.tryscript.md" in result.stdout
    assert "tests/golden/*.tryscript.md" not in result.stdout


def test_only_refuses_unmatched_patterns_before_running_recorders(tmp_path: Path) -> None:
    (tmp_path / "devtools").symlink_to(ROOT / "devtools", target_is_directory=True)
    (tmp_path / "real.tryscript.md").touch()
    env = {
        **os.environ,
        "PATH": os.pathsep.join([str(Path(sys.executable).parent), os.environ["PATH"]]),
    }
    result = subprocess.run(
        [
            "make",
            "-f",
            str(ROOT / "Makefile"),
            "golden-update",
            "UV_RUN=env",
            "ONLY=real*.tryscript.md missing.tryscript.md tests/test_inert_toc.py",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "no file matches missing.tryscript.md" in result.stderr
    assert "devtools.golden_update" not in result.stdout
    assert "run --update" not in result.stdout


def test_make_test_goldens_runs_every_golden_through_the_runner_with_the_makefiles_tryscript(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The recipe's words, and ``TRYSCRIPT``'s words as the command, on two real goldens."""

    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    line = "\t$(RUN_GOLDENS) $(if $(SHARD),--shard $(SHARD)) $(QUOTED_GOLDENS) -- $(TRYSCRIPT) run"
    assert recipe(makefile, "test-goldens") == line
    assert makefile_list(makefile, "GOLDENS") == ["tests/golden/*.tryscript.md"]
    require_node()
    command = [
        word.replace("$(CURDIR)", str(ROOT)) for word in makefile_list(makefile, "TRYSCRIPT")
    ]
    assert command == [str(ROOT / "devtools" / "tryscript.sh")]
    command.append("run")
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
