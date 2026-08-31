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
    script = Path(__file__).parent / "dom" / "file-type-taxonomy-behavior.js"
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


def test_file_type_identity_is_one_taxonomy() -> None:
    """A family is one icon and one colour, in the tree and in the bars.

    The defect this guards was invisible to every other test in the suite: the
    tree's own table and the rollup registry were each internally consistent
    and disagreed with each other, so asking either one what it thought
    passed. Measured against the table this replaced, ``.js``/``.mjs``/``.cjs``/
    ``.jsx`` rendered two icons and three of them had no colour at all,
    ``.json``/``.toml``/``.yaml`` rendered as one colour rather than three, and
    Python and TypeScript were the same. What has to be pinned is the relation.
    """

    if shutil.which("node") is None:
        pytest.skip("node not available")
    script = Path(__file__).parent / "dom" / "file-type-identity-behavior.js"
    result = subprocess.run(
        ["node", str(script)],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    assert "OK file type identity" in result.stdout
