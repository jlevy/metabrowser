"""Golden console-output tests for serve mode, with uvicorn mocked.

The CLI's console surface is pinned by the tryscript goldens in
``tests/golden/*.tryscript.md`` (run through ``make test``, regenerated
with ``make golden-update``). Serve mode cannot run as a tryscript
subprocess without binding a port and blocking on uvicorn, so its two
banner scenarios stay here, where the uvicorn server and the port
search are mockable in-process.

Regenerate after an intended change with:

    GOLDEN_UPDATE=1 uv --config-file uv.toml run --frozen pytest tests/test_cli_golden.py

Normalization keeps only stable fields: ANSI styling and Rich's
end-of-line padding are stripped, the terminal width is pinned, and
temporary roots are replaced with placeholders. The walk fixture gets
fixed mtimes so any sizes in output are deterministic.
"""

from __future__ import annotations

import difflib
import os
import re
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest
import typer.rich_utils
from click import unstyle
from typer.testing import CliRunner

from metabrowser.cli.main import _app

GOLDEN_DIR = Path(__file__).parent / "golden"
FIXED_MTIME = 1_700_000_000
# Logger output ("HH:MM:SS name | message") depends on timing and on which
# tests configured logging first; it is not part of the CLI's console
# contract, so those lines are removed rather than pinned.
_LOG_LINE = re.compile(r"^\d{2}:\d{2}:\d{2} \S+ \| .*\n?", re.MULTILINE)

runner = CliRunner()


@pytest.fixture(autouse=True)
def _stable_console(  # pyright: ignore[reportUnusedFunction]
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[None]:
    """Pin the rendering environment so goldens are terminal-independent.

    Typer reads FORCE_TERMINAL and MAX_WIDTH from the environment at import
    (GitHub Actions forces terminal mode, which makes Rich ignore COLUMNS and
    render 80 wide), so the module globals are pinned rather than the env vars.
    """
    monkeypatch.setattr(typer.rich_utils, "FORCE_TERMINAL", None)
    monkeypatch.setattr(typer.rich_utils, "MAX_WIDTH", 100)
    monkeypatch.setenv("COLUMNS", "100")
    monkeypatch.setenv("TERM", "dumb")
    monkeypatch.delenv("METABROWSER_PLUGINS_DIRS", raising=False)
    monkeypatch.delenv("METABROWSER_LOG_LEVEL", raising=False)
    yield


_BUILD_STATE = re.compile(r"  \[dev build: [^\]]*\]")


def _normalize(text: str, root: Path) -> str:
    out = unstyle(text)
    out = out.replace(str(root), "<ROOT>")
    out = _LOG_LINE.sub("", out)
    # A checkout annotates its build with how far past the tag it is and
    # whether the tree is dirty, which changes on every commit and every edit.
    # That is the point of the marker and the opposite of what a golden can
    # record, so the shape is kept and the contents are not — the same reason
    # <ROOT> is substituted above. See metabrowser.build_version.
    out = _BUILD_STATE.sub("  [dev build: <STATE>]", out)
    # Rich pads rendered lines to the console width; the padding is not part
    # of the CLI contract and trips `git diff --check` on the goldens.
    return re.sub(r"[ \t]+$", "", out, flags=re.MULTILINE)


def check_golden(name: str, actual: str) -> None:
    """Compare ``actual`` to the checked-in golden; GOLDEN_UPDATE=1 rewrites it."""
    path = GOLDEN_DIR / name
    if os.environ.get("GOLDEN_UPDATE") == "1":
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(actual)
        return
    if not path.is_file():
        pytest.fail(f"missing golden {path.name}; regenerate with GOLDEN_UPDATE=1")
    expected = path.read_text()
    if actual != expected:
        diff = "".join(
            difflib.unified_diff(
                expected.splitlines(keepends=True),
                actual.splitlines(keepends=True),
                fromfile=f"golden/{name}",
                tofile="actual",
            )
        )
        pytest.fail(f"golden mismatch for {name}:\n{diff}")


def _make_walk_fixture(tmp_path: Path) -> Path:
    """A tiny tree with pinned mtimes so sizes in output are deterministic."""
    root = tmp_path / "walkroot"
    logs = root / "logs"
    logs.mkdir(parents=True)
    (root / "README.md").write_text("# Sample\n\nHello.\n")
    (root / "data.jsonl").write_text('{"event": "start"}\n{"event": "stop"}\n')
    (logs / "run.log").write_text("line one\nline two\n")
    for entry in (root / "README.md", root / "data.jsonl", logs / "run.log", logs, root):
        os.utime(entry, (FIXED_MTIME, FIXED_MTIME))
    return root


def test_golden_serve_banner(tmp_path: Path) -> None:
    root = _make_walk_fixture(tmp_path)
    with (
        patch("metabrowser.cli.serve._QuietForceExitServer"),
        patch("metabrowser.cli.serve.find_available_local_port", return_value=8411),
    ):
        result = runner.invoke(_app, [str(root), "--no-open"])
    rendered = (
        "# metab <ROOT>/walkroot --no-open\n"
        f"exit: {result.exit_code}\n"
        f"--- stdout ---\n{_normalize(result.stdout, tmp_path)}"
        f"--- stderr ---\n{_normalize(result.stderr, tmp_path)}"
    )
    check_golden("serve-banner.txt", rendered)


def test_golden_serve_file_root_deep_link(tmp_path: Path) -> None:
    root = _make_walk_fixture(tmp_path)
    with (
        patch("metabrowser.cli.serve._QuietForceExitServer"),
        patch("metabrowser.cli.serve.find_available_local_port", return_value=8411),
    ):
        result = runner.invoke(_app, [str(root / "data.jsonl"), "--no-open"])
    rendered = (
        "# metab <ROOT>/walkroot/data.jsonl --no-open\n"
        f"exit: {result.exit_code}\n"
        f"--- stdout ---\n{_normalize(result.stdout, tmp_path)}"
        f"--- stderr ---\n{_normalize(result.stderr, tmp_path)}"
    )
    check_golden("serve-file-root.txt", rendered)
