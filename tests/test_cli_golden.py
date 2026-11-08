"""Golden console-output tests for serving and Unicode rollup requests.

The CLI's console surface is pinned by the tryscript goldens in
``tests/golden/*.tryscript.md`` (run through ``make test``, regenerated
with ``make golden-update``). Serve mode cannot run as a tryscript
subprocess without binding a port and blocking on uvicorn, so its two
banner scenarios stay here, where the uvicorn server and the port
search are mockable in-process.
Unicode rollup requests use the real CLI entry point to pin successful root and
subfolder responses without binding a server.

Normalization keeps only stable fields: ANSI styling and Rich's
end-of-line padding are stripped, the terminal width is pinned, and
temporary roots are replaced with placeholders. The walk fixture gets
fixed mtimes so any sizes in output are deterministic.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest
import typer.rich_utils
from typer.testing import CliRunner

from metabrowser.cli.main import _app
from tests.golden_harness import block, check_golden, normalize_console, run_metab
from tests.required_tools import needs_git

FIXED_MTIME = 1_700_000_000

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


def test_golden_rollup_in_a_unicode_root_and_subfolder(tmp_path: Path) -> None:
    root = tmp_path / "资料"
    child = root / "子目录"
    child.mkdir(parents=True)
    (root / "README.md").write_text("root\n")
    (child / "雪.txt").write_text("nested\n")
    for entry in (root / "README.md", child / "雪.txt", child, root):
        os.utime(entry, (FIXED_MTIME, FIXED_MTIME))
    blocks: list[str] = []
    for path, files, size in (("", 2, 12), ("子目录", 1, 7)):
        route = f"/api/rollup?path={path}&depth=0"
        result = run_metab([str(root), "--api", route, "--format", "json"])
        assert result.exit_code == 0, result.stdout + result.stderr
        body = json.loads(result.stdout)
        assert body["path"] == path
        assert body["node"]["total_files"] == files
        assert body["node"]["total_size"] == size
        blocks.append(
            block(
                f"metab <ROOT>/资料 --api '{route}' --format json",
                result.exit_code,
                normalize_console(result.stdout, tmp_path),
                normalize_console(result.stderr, tmp_path),
            )
        )
    check_golden("cli-rollup-unicode.txt", "\n".join(blocks))


@needs_git
@pytest.mark.parametrize(
    ("golden", "selection"),
    [("serve-banner.txt", ""), ("serve-file-root.txt", "/data.jsonl")],
    ids=["folder", "file-deep-link"],
)
def test_golden_serve_banner(golden: str, selection: str, tmp_path: Path) -> None:
    root = _make_walk_fixture(tmp_path)
    with (
        patch("metabrowser.cli.serve._QuietForceExitServer"),
        patch("metabrowser.cli.serve.find_available_local_port", return_value=8411),
    ):
        result = runner.invoke(_app, [f"{root}{selection}", "--no-open"])
    rendered = block(
        f"metab <ROOT>/walkroot{selection} --no-open",
        result.exit_code,
        normalize_console(result.stdout, tmp_path),
        normalize_console(result.stderr, tmp_path),
    )
    check_golden(golden, rendered)
