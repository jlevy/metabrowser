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
WIKI_PARSER_JS = Path(__file__).resolve().parent / "dom" / "markdown_wiki_parser_behavior.js"
WIKI_RESOLVER_JS = Path(__file__).resolve().parent / "dom" / "markdown_wiki_resolver_behavior.js"
WIKI_ENHANCER_JS = Path(__file__).resolve().parent / "dom" / "markdown_wiki_enhancer_behavior.js"
PROJECT_ADAPTER_JS = (
    Path(__file__).resolve().parent / "dom" / "markdown_project_adapter_behavior.js"
)
GITHUB_LOCALIZER_JS = (
    Path(__file__).resolve().parent / "dom" / "markdown_github_localizer_behavior.js"
)
GRAPH_ANALYSIS_JS = Path(__file__).resolve().parent / "dom" / "markdown_graph_analysis_behavior.js"
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


def test_source_aware_obsidian_wiki_parser() -> None:
    if shutil.which("node") is None:
        pytest.skip("node not available")
    result = subprocess.run(
        ["node", str(WIKI_PARSER_JS), str(REPO_ROOT)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, (
        f"Markdown wiki parser failed:\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    assert "markdown wiki parser OK" in result.stdout


def test_deterministic_obsidian_wiki_resolver() -> None:
    if shutil.which("node") is None:
        pytest.skip("node not available")
    result = subprocess.run(
        ["node", str(WIKI_RESOLVER_JS), str(REPO_ROOT)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, (
        f"Markdown wiki resolver failed:\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    assert "markdown wiki resolver OK" in result.stdout


def test_obsidian_wiki_dom_enhancer() -> None:
    if shutil.which("node") is None:
        pytest.skip("node not available")
    result = subprocess.run(
        ["node", str(WIKI_ENHANCER_JS), str(REPO_ROOT)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, (
        f"Markdown wiki enhancer failed:\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    assert "markdown wiki enhancer OK" in result.stdout


def test_configured_markdown_project_adapters() -> None:
    if shutil.which("node") is None:
        pytest.skip("node not available")
    result = subprocess.run(
        ["node", str(PROJECT_ADAPTER_JS), str(REPO_ROOT)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, (
        f"Markdown project adapter failed:\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    assert "markdown project adapter OK" in result.stdout


def test_verified_github_url_localization() -> None:
    if shutil.which("node") is None:
        pytest.skip("node not available")
    result = subprocess.run(
        ["node", str(GITHUB_LOCALIZER_JS), str(REPO_ROOT)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, (
        f"Markdown GitHub localizer failed:\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    assert "markdown GitHub localizer OK" in result.stdout


def test_bounded_markdown_graph_analysis() -> None:
    if shutil.which("node") is None:
        pytest.skip("node not available")
    result = subprocess.run(
        ["node", str(GRAPH_ANALYSIS_JS), str(REPO_ROOT)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, (
        f"Markdown graph analysis failed:\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    assert "markdown graph analysis OK" in result.stdout


def test_standard_markdown_link_fixture_matches_its_schema() -> None:
    schema = json.loads((FIXTURE_ROOT / "markdown_link_resolution.schema.json").read_text())
    fixture = json.loads((FIXTURE_ROOT / "markdown_link_resolution.json").read_text())

    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(fixture)
    case_ids = [case["id"] for case in fixture["cases"]]
    assert len(case_ids) == len(set(case_ids))


def test_obsidian_wiki_fixture_matches_its_schema() -> None:
    fixture = json.loads((FIXTURE_ROOT / "obsidian_wiki_resolution.json").read_text())
    schema = json.loads((FIXTURE_ROOT / "obsidian_wiki_resolution.schema.json").read_text())
    Draft202012Validator(schema).validate(fixture)
    case_ids = [case["id"] for case in fixture["cases"]]
    assert len(case_ids) == len(set(case_ids))
