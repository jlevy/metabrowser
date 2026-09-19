"""Golden CLI transcripts for a leased file:// Git pin.

Successful ``metab file:// --show`` / ``--api`` cannot run as a tryscript
subprocess on ubuntu-latest: Git 2.43.0 is below the acquisition floor.
These goldens invoke the production CLI in-process with
``require_acquisition_git`` monkeypatched — the same boundary as
``tests/test_cli_cache_acquire_golden.py``. Nothing binds a port.

Regenerate after an intended change with:

    GOLDEN_UPDATE=1 uv --config-file uv.toml run --frozen pytest tests/test_cli_git_pin_golden.py
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from metabrowser.cli.main import _app
from metabrowser.git.tree_source import GitPath
from tests.test_cli_cache_acquire_golden import (
    _block,
    _deterministic_origin,
    _file_url,
    _isolate,
)
from tests.test_cli_golden import check_golden

posix_only = pytest.mark.skipif(os.name != "posix", reason="owner-only cache is POSIX-only")

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git executable is required")

runner = CliRunner()

README_WIRE = GitPath.from_segments(b"README").to_wire()


def _invoke(args: list[str]) -> object:
    result = runner.invoke(_app, args)
    assert result.exit_code == 0, result.output
    return result


@posix_only
def test_golden_file_url_show_and_api_on_the_default_pin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = _isolate(tmp_path, monkeypatch)
    url = _file_url(_deterministic_origin(tmp_path))

    shown = _invoke([url, "--show", "README"])
    progress = _invoke([url, "--api", "/api/index/progress"])
    blob = _invoke([url, "--api", f"/api/file?path={README_WIRE}"])
    tree = _invoke([url, "--api", "/api/tree?depth=0"])

    assert "Serving" not in shown.stdout
    assert "show: README" in shown.stdout
    assert f"route: /view/{README_WIRE}" in shown.stdout
    assert str(home) not in shown.stdout
    assert '"subject": "git_revision"' in tree.stdout
    assert '"provider": "git"' in progress.stdout
    assert '"status": "done"' in progress.stdout

    rendered = "".join(
        [
            _block("file://<ORIGIN> --show README", shown, origin_url=url, api=False),
            _block(
                "file://<ORIGIN> --api /api/index/progress",
                progress,
                origin_url=url,
                api=False,
            ),
            _block(
                f"file://<ORIGIN> --api /api/file?path={README_WIRE}",
                blob,
                origin_url=url,
                api=False,
            ),
            _block(
                "file://<ORIGIN> --api /api/tree?depth=0",
                tree,
                origin_url=url,
                api=False,
            ),
        ]
    )
    assert str(tmp_path) not in rendered
    assert str(home) not in rendered
    check_golden("cli-git-pin.txt", rendered)
