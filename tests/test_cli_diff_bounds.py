"""`metab --diff` on a comparison past what one run hydrates answers as the page does.

The page asks for the files within the bound in one run and each file past it alone when
the reader reaches it; the command line has no reader to wait for, so it asks for each at
once (review of #284, Qodo on the layer above: it answered `diff error: file 'f5' not
found in the produced diff` to a comparison of 10.9 MB whose largest file was 3.5 MB). A
file too large alone is said to be, as the page says it, and `--diff-check` refuses such a
comparison by name rather than failing in the oracle.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import typer

from metabrowser.cli import diff_cli
from metabrowser.diff.adapters import git as adapter
from tests.diff_fixture_repo import git
from tests.required_tools import needs_git

pytestmark = needs_git


def _sized(tmp_path: Path) -> Path:
    """`a`, `b` and `c` within a small bound; `big` past it; and a binary, so the run is
    path-limited as the page's is."""
    root = tmp_path / "sized"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    (root / "keep.txt").write_text("keep\n")
    (root / "logo.bin").write_bytes(b"\x00\x01old\x00")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "base")
    (root / "a.txt").write_text("a\n" * 30)
    (root / "b.txt").write_text("b\n" * 30)
    (root / "big.txt").write_text("big line\n" * 1000)
    (root / "c.txt").write_text("c\n" * 30)
    (root / "logo.bin").write_bytes(b"\x00\x01new\x00")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "target")
    return root


def _run(root: Path, capsys: Any, **options: Any) -> str:
    diff_cli.run_diff(
        root,
        spec="HEAD^..HEAD",
        fmt=options.get("fmt", "text"),
        patch_path=options.get("patch_path"),
        check=options.get("check", False),
    )
    return capsys.readouterr().out


def _by_path(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {(c.get("new") or c["old"])["path"]: c for c in document["manifest"]["files"]}


def test_every_file_is_hydrated_and_one_too_large_alone_is_said(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    root = _sized(tmp_path)
    whole = json.loads(_run(root, capsys, fmt="json"))
    assert all(c["availability"] == "ready" for p, c in _by_path(whole).items() if p != "logo.bin")

    monkeypatch.setattr(adapter, "MAX_FILE_PATCH_BYTES", 400)
    bounded = json.loads(_run(root, capsys, fmt="json"))
    files = _by_path(bounded)
    assert files["big.txt"]["availability"] == "too_large"
    assert files["big.txt"]["id"] not in bounded["patches"]
    within = ("a.txt", "b.txt", "c.txt")
    assert all(files[path]["availability"] == "ready" for path in within)
    assert {files[path]["id"] for path in within} <= set(bounded["patches"])
    for path in within:
        assert bounded["patches"][files[path]["id"]] == whole["patches"][files[path]["id"]], (
            f"{path}: not the unrestricted run's bytes"
        )
    assert bounded["resolved"]["warnings"] == []

    text = _run(root, capsys)
    assert "A    big.txt  [too_large]" in text
    assert "A    c.txt  [+30 -0]" in text
    assert "M    logo.bin  [binary]" in text

    with pytest.raises(typer.Exit) as refused:
        _run(root, capsys, patch_path="big.txt")
    assert refused.value.exit_code == 2
    assert "carries no textual patch (too_large)" in capsys.readouterr().err


def test_diff_check_refuses_a_comparison_it_cannot_apply_whole_by_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    root = _sized(tmp_path)
    assert "apply: clean" in _run(root, capsys, check=True)
    monkeypatch.setattr(adapter, "MAX_FILE_PATCH_BYTES", 400)
    with pytest.raises(typer.Exit) as refused:
        _run(root, capsys, check=True)
    assert refused.value.exit_code == 2
    err = capsys.readouterr().err
    assert "--diff-check" in err and "big.txt" in err and "too_large" in err
