"""Run the browser taxonomy parity contract in a Node VM."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from metabrowser.file_type_filters import serialize_file_type_registry

CONFORMANCE = (
    Path(__file__).resolve().parents[1]
    / "src/metabrowser/data/file-rollup-format/file-rollup-conformance.json"
)


def test_file_type_taxonomy_js_assertions_pass(tmp_path: Path) -> None:
    if shutil.which("node") is None:
        pytest.skip("node not available")
    script = Path(__file__).parent / "dom" / "file_type_taxonomy_behavior.js"
    fixture = tmp_path / "file-type-registry.json"
    fixture.write_text(json.dumps(serialize_file_type_registry()), encoding="utf-8")
    result = subprocess.run(
        ["node", str(script), str(fixture), str(CONFORMANCE)],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, (
        f"taxonomy assertions failed:\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    assert result.stdout.startswith("OK file type taxonomy")
