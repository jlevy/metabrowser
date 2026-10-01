"""``devtools/golden_update.py`` fails when a module it ran skipped a test.

``make golden-update`` says it regenerates everything. A skipped recorder regenerates
nothing, so a skip there has to be a failure and not a line in a summary.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from devtools.check_goldens import UPDATE_ENV

REPO_ROOT = Path(__file__).resolve().parent.parent

WRITES = """\
import os
from pathlib import Path

def test_writes_when_updating():
    assert os.environ["GOLDEN_UPDATE"] == "1"
    (Path(__file__).parent / "written.txt").write_text("regenerated\\n")
"""
SKIPS = """\
import pytest

@pytest.mark.skipif(True, reason="node not available")
def test_skipped_by_mark():
    raise AssertionError("not run")

def test_skipped_in_its_body():
    pytest.skip("git is below the acquisition floor")

@pytest.mark.xfail(reason="a known failure is not a skip")
def test_expected_failure():
    raise AssertionError("expected")
"""
MODULE_SKIP = 'import pytest\n\npytest.skip("POSIX only", allow_module_level=True)\n'


def _run(tmp_path: Path, **modules: str) -> subprocess.CompletedProcess[str]:
    paths: list[str] = []
    for name, source in modules.items():
        path = tmp_path / f"test_{name}.py"
        path.write_text(source, encoding="utf-8")
        paths.append(str(path))
    env = {name: value for name, value in os.environ.items() if name != UPDATE_ENV}
    return subprocess.run(
        [sys.executable, "-m", "devtools.golden_update", *paths],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=env,
        timeout=50,
        check=False,
    )


def test_a_run_with_no_skip_updates_and_passes(tmp_path: Path) -> None:
    result = _run(tmp_path, writes=WRITES)
    assert result.returncode == 0, result.stdout + result.stderr
    assert (tmp_path / "written.txt").read_text(encoding="utf-8") == "regenerated\n"


@pytest.mark.parametrize(
    ("source", "reasons"),
    [
        (
            SKIPS,
            [
                "::test_skipped_by_mark: node not available",
                "::test_skipped_in_its_body: git is below the acquisition floor",
            ],
        ),
        (MODULE_SKIP, ["test_skipping.py: POSIX only"]),
    ],
    ids=["tests", "module"],
)
def test_a_skip_fails_the_run_and_is_named(source: str, reasons: list[str], tmp_path: Path) -> None:
    result = _run(tmp_path, writes=WRITES, skipping=source)
    assert result.returncode == 1, result.stdout + result.stderr
    assert f"{len(reasons)} test(s) were skipped" in result.stderr
    for reason in reasons:
        assert reason in result.stderr
    assert "test_expected_failure" not in result.stderr
    # What could be regenerated was: the failure is about what was not.
    assert (tmp_path / "written.txt").is_file()


def test_no_module_is_a_usage_error() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "devtools.golden_update"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=50,
        check=False,
    )
    assert result.returncode == 2 and "usage:" in result.stderr
