"""Instance-lifecycle checks for rendered Markdown mounts."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parent.parent
TEST_JS = Path(__file__).resolve().parent / "dom" / "markdown_mount_behavior.js"
RESOLVER_JS = Path(__file__).resolve().parent / "dom" / "markdown_link_resolver_behavior.js"
ENHANCER_JS = Path(__file__).resolve().parent / "dom" / "markdown_link_enhancer_behavior.js"
FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures"


def test_markdown_mount_lifecycle() -> None:
    if shutil.which("node") is None:
        pytest.skip("node not available")
    result = subprocess.run(
        ["node", str(TEST_JS), str(REPO_ROOT)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, (
        f"Markdown mount behavior failed:\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    assert "markdown mount OK" in result.stdout


def test_standard_markdown_link_resolver() -> None:
    if shutil.which("node") is None:
        pytest.skip("node not available")
    result = subprocess.run(
        ["node", str(RESOLVER_JS), str(REPO_ROOT)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, (
        f"Markdown link resolver failed:\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    assert "markdown link resolver OK" in result.stdout


def test_rendered_markdown_link_enhancer() -> None:
    if shutil.which("node") is None:
        pytest.skip("node not available")
    result = subprocess.run(
        ["node", str(ENHANCER_JS), str(REPO_ROOT)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, (
        f"Markdown link enhancer failed:\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    assert "markdown link enhancer OK" in result.stdout


def test_standard_markdown_link_fixture_matches_its_schema() -> None:
    schema = json.loads((FIXTURE_ROOT / "markdown_link_targets.schema.json").read_text())
    fixture = json.loads((FIXTURE_ROOT / "markdown_link_targets.json").read_text())

    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(fixture)
    case_ids = [case["id"] for case in fixture["cases"]]
    assert len(case_ids) == len(set(case_ids))
