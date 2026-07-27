"""Golden console-output tests for the metab CLI.

Console-capture golden tests per `tbd guidelines golden-testing-guidelines`:
each scenario's exit code, stdout, and stderr are captured, normalized, and
diffed against a checked-in golden file under ``tests/golden/``. Any change
to the CLI surface — help layout, error wording, mode output — shows up as
a reviewable golden diff.

Regenerate after an intended change with:

    GOLDEN_UPDATE=1 uv --config-file uv.toml run --frozen pytest tests/test_cli_golden.py

Normalization keeps only stable fields: ANSI styling is stripped, the
terminal width is pinned, and the package version, temporary roots, the
repository checkout path, and log timestamps are replaced with
placeholders. Walk fixtures get fixed mtimes so sizes and timestamps in
walker output are deterministic.
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

from metabrowser import __version__
from metabrowser.cli.main import _app

GOLDEN_DIR = Path(__file__).parent / "golden"
REPO_ROOT = Path(__file__).parent.parent
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


def _normalize(text: str, root: Path | None = None) -> str:
    out = unstyle(text)
    if root is not None:
        out = out.replace(str(root), "<ROOT>")
    out = out.replace(str(REPO_ROOT), "<REPO>")
    out = out.replace(__version__, "<VERSION>")
    return _LOG_LINE.sub("", out)


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


def _run_and_check(name: str, args: list[str], root: Path | None = None) -> None:
    result = runner.invoke(_app, args)
    rendered = (
        f"# metab {_normalize(' '.join(args), root)}\n"
        f"exit: {result.exit_code}\n"
        f"--- stdout ---\n{_normalize(result.stdout, root)}"
        f"--- stderr ---\n{_normalize(result.stderr, root)}"
    )
    check_golden(name, rendered)


def _make_walk_fixture(tmp_path: Path) -> Path:
    """A tiny tree with pinned mtimes so walker output is deterministic."""
    root = tmp_path / "walkroot"
    logs = root / "logs"
    logs.mkdir(parents=True)
    (root / "README.md").write_text("# Sample\n\nHello.\n")
    (root / "data.jsonl").write_text('{"event": "start"}\n{"event": "stop"}\n')
    (logs / "run.log").write_text("line one\nline two\n")
    for entry in (root / "README.md", root / "data.jsonl", logs / "run.log", logs, root):
        os.utime(entry, (FIXED_MTIME, FIXED_MTIME))
    return root


# ── Top-level surface ──────────────────────────────────────────


def test_golden_help() -> None:
    _run_and_check("help.txt", ["--help"])


def test_golden_bare_invocation_shows_help() -> None:
    _run_and_check("bare.txt", [])


def test_golden_version() -> None:
    _run_and_check("version.txt", ["--version"])


# ── Usage errors ───────────────────────────────────────────────


@pytest.mark.parametrize(
    ("name", "args"),
    [
        ("error-mode-conflict.txt", [".", "--walk", "--plugins"]),
        ("error-option-wrong-mode.txt", [".", "--walk", "--port", "9000", "--no-open"]),
        ("error-serve-option-json.txt", [".", "--json"]),
        ("error-missing-root.txt", ["--no-open"]),
        ("error-walk-missing-root.txt", ["--walk"]),
        ("error-root-with-plugins.txt", [".", "--plugins"]),
        ("error-root-with-remote.txt", [".", "--remote", "vm", "--path", "/runs"]),
        ("error-remote-missing-path.txt", ["--remote", "vm"]),
        ("error-old-subcommand.txt", ["serve", "."]),
        ("error-bad-format.txt", [".", "--walk", "--format", "xml"]),
        ("error-bad-port.txt", [".", "--port", "0"]),
    ],
)
def test_golden_usage_errors(name: str, args: list[str]) -> None:
    _run_and_check(name, args)


def test_golden_serve_nonexistent_root(tmp_path: Path) -> None:
    missing = tmp_path / "missing"
    result = runner.invoke(_app, [str(missing), "--no-open"])
    rendered = (
        "# metab <ROOT>/missing --no-open\n"
        f"exit: {1 if result.exception else result.exit_code}\n"
        f"exception: {_normalize(str(result.exception), tmp_path)}\n"
    )
    check_golden("error-nonexistent-root.txt", rendered)


# ── Plugin modes ───────────────────────────────────────────────


def test_golden_plugins_list() -> None:
    _run_and_check("plugins-list.txt", ["--plugins"])


def test_golden_plugins_list_json() -> None:
    _run_and_check("plugins-list-json.txt", ["--plugins", "--json"])


def test_golden_plugin_show() -> None:
    _run_and_check("plugin-show.txt", ["--plugin", "markdown"])


def test_golden_plugin_show_json() -> None:
    _run_and_check("plugin-show-json.txt", ["--plugin", "markdown", "--json"])


def test_golden_doctor() -> None:
    _run_and_check("doctor.txt", ["--doctor"])


def test_golden_doctor_json() -> None:
    _run_and_check("doctor-json.txt", ["--doctor", "--json"])


# ── Walk mode ──────────────────────────────────────────────────


def test_golden_walk_text(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _make_walk_fixture(tmp_path)
    monkeypatch.chdir(tmp_path)
    _run_and_check("walk-text.txt", [str(root), "--walk"], root=tmp_path)


def test_golden_walk_text_summary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _make_walk_fixture(tmp_path)
    monkeypatch.chdir(tmp_path)
    _run_and_check(
        "walk-text-summary.txt",
        [str(root), "--walk", "--detail", "summary"],
        root=tmp_path,
    )


def test_golden_walk_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _make_walk_fixture(tmp_path)
    monkeypatch.chdir(tmp_path)
    _run_and_check("walk-json.txt", [str(root), "--walk", "--format", "json"], root=tmp_path)


def test_golden_walk_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _make_walk_fixture(tmp_path)
    monkeypatch.chdir(tmp_path)
    _run_and_check("walk-yaml.txt", [str(root), "--walk", "--format", "yaml"], root=tmp_path)


def test_golden_walk_json_stream(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _make_walk_fixture(tmp_path)
    monkeypatch.chdir(tmp_path)
    _run_and_check(
        "walk-json-stream.txt",
        [str(root), "--walk", "--format", "json", "--stream"],
        root=tmp_path,
    )


def test_golden_walk_json_subtree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _make_walk_fixture(tmp_path)
    monkeypatch.chdir(tmp_path)
    _run_and_check(
        "walk-json-subtree.txt",
        [str(root), "--walk", "--format", "json", "--path", "logs"],
        root=tmp_path,
    )


# ── Serve mode (uvicorn mocked) ────────────────────────────────


def test_golden_serve_banner(tmp_path: Path) -> None:
    root = _make_walk_fixture(tmp_path)
    with (
        patch("uvicorn.run"),
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
        patch("uvicorn.run"),
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
