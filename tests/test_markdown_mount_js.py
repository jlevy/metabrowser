"""Instance-lifecycle checks for rendered Markdown mounts."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parent.parent
TEST_JS = Path(__file__).resolve().parent / "dom" / "markdown-mount-behavior.js"
RESOLVER_JS = Path(__file__).resolve().parent / "dom" / "markdown-link-resolver-behavior.js"
ENHANCER_JS = Path(__file__).resolve().parent / "dom" / "markdown-link-enhancer-behavior.js"
WIKI_PARSER_JS = Path(__file__).resolve().parent / "dom" / "markdown-wiki-parser-behavior.js"
WIKI_RESOLVER_JS = Path(__file__).resolve().parent / "dom" / "markdown-wiki-resolver-behavior.js"
WIKI_ENHANCER_JS = Path(__file__).resolve().parent / "dom" / "markdown-wiki-enhancer-behavior.js"
RECONCILIATION_COORDINATOR_JS = (
    Path(__file__).resolve().parent / "dom" / "markdown-reconciliation-coordinator-behavior.js"
)
PROJECT_ADAPTER_JS = (
    Path(__file__).resolve().parent / "dom" / "markdown-project-adapter-behavior.js"
)
GITHUB_LOCALIZER_JS = (
    Path(__file__).resolve().parent / "dom" / "markdown-github-localizer-behavior.js"
)
TRANSCLUSION_JS = Path(__file__).resolve().parent / "dom" / "markdown-transclusion-behavior.js"
MARKDOWN_WORKER_JS = Path(__file__).resolve().parent / "dom" / "markdown-worker-behavior.js"
DOM_TRAVERSAL_JS = Path(__file__).resolve().parent / "dom" / "markdown-dom-traversal-behavior.js"
MEMO_WORK_JS = Path(__file__).resolve().parent / "dom" / "wiki-resolver-memo-work-session.js"
FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures"

# Breaks a hung session; it is not a speed budget. These sessions need a
# fraction of a second of CPU, but on a loaded host they wait for it: the link
# enhancer took 11-23 s of wall time at load average ~170 against a 30 s bound,
# and failed the suite there. A deadlock never finishes, so a generous bound
# loses nothing.
_SESSION_DEADLOCK_TIMEOUT_S = 300


def test_markdown_mount_lifecycle() -> None:
    if shutil.which("node") is None:
        pytest.skip("node not available")
    result = subprocess.run(
        ["node", str(TEST_JS), str(REPO_ROOT)],
        capture_output=True,
        text=True,
        timeout=_SESSION_DEADLOCK_TIMEOUT_S,
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
        timeout=_SESSION_DEADLOCK_TIMEOUT_S,
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
        timeout=_SESSION_DEADLOCK_TIMEOUT_S,
        check=False,
    )
    assert result.returncode == 0, (
        f"Markdown link enhancer failed:\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    assert "markdown link enhancer OK" in result.stdout


def test_wiki_resolver_memo_work_stays_constant_per_target() -> None:
    if shutil.which("node") is None:
        pytest.skip("node not available")
    result = subprocess.run(
        ["node", str(MEMO_WORK_JS)],
        capture_output=True,
        text=True,
        timeout=_SESSION_DEADLOCK_TIMEOUT_S,
        check=False,
    )
    assert result.returncode == 0, (
        f"wiki resolver memo work failed:\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    assert "wiki resolver memo work OK" in result.stdout


def test_source_aware_obsidian_wiki_parser() -> None:
    if shutil.which("node") is None:
        pytest.skip("node not available")
    result = subprocess.run(
        ["node", str(WIKI_PARSER_JS), str(REPO_ROOT)],
        capture_output=True,
        text=True,
        timeout=_SESSION_DEADLOCK_TIMEOUT_S,
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
        timeout=_SESSION_DEADLOCK_TIMEOUT_S,
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
        timeout=_SESSION_DEADLOCK_TIMEOUT_S,
        check=False,
    )
    assert result.returncode == 0, (
        f"Markdown wiki enhancer failed:\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    assert "markdown wiki enhancer OK" in result.stdout


def test_root_scoped_markdown_reconciliation_coordinator() -> None:
    if shutil.which("node") is None:
        pytest.skip("node not available")
    result = subprocess.run(
        ["node", str(RECONCILIATION_COORDINATOR_JS), str(REPO_ROOT)],
        capture_output=True,
        text=True,
        timeout=_SESSION_DEADLOCK_TIMEOUT_S,
        check=False,
    )
    assert result.returncode == 0, (
        "Markdown reconciliation coordinator failed:\n"
        f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    assert "markdown reconciliation coordinator OK" in result.stdout


def test_configured_markdown_project_adapters() -> None:
    if shutil.which("node") is None:
        pytest.skip("node not available")
    result = subprocess.run(
        ["node", str(PROJECT_ADAPTER_JS), str(REPO_ROOT)],
        capture_output=True,
        text=True,
        timeout=_SESSION_DEADLOCK_TIMEOUT_S,
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
        timeout=_SESSION_DEADLOCK_TIMEOUT_S,
        check=False,
    )
    assert result.returncode == 0, (
        f"Markdown GitHub localizer failed:\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    assert "markdown GitHub localizer OK" in result.stdout


def test_bounded_markdown_transclusion() -> None:
    if shutil.which("node") is None:
        pytest.skip("node not available")
    result = subprocess.run(
        ["node", str(TRANSCLUSION_JS), str(REPO_ROOT)],
        capture_output=True,
        text=True,
        timeout=_SESSION_DEADLOCK_TIMEOUT_S,
        check=False,
    )
    assert result.returncode == 0, (
        f"Markdown transclusion failed:\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    assert "markdown transclusion OK" in result.stdout


def test_generic_lazy_markdown_worker() -> None:
    if shutil.which("node") is None:
        pytest.skip("node not available")
    result = subprocess.run(
        ["node", str(MARKDOWN_WORKER_JS), str(REPO_ROOT)],
        capture_output=True,
        text=True,
        timeout=_SESSION_DEADLOCK_TIMEOUT_S,
        check=False,
    )
    assert result.returncode == 0, (
        f"Markdown worker behavior failed:\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    assert "markdown worker OK" in result.stdout


def test_bounded_markdown_dom_traversal() -> None:
    if shutil.which("node") is None:
        pytest.skip("node not available")
    result = subprocess.run(
        ["node", str(DOM_TRAVERSAL_JS), str(REPO_ROOT)],
        capture_output=True,
        text=True,
        timeout=_SESSION_DEADLOCK_TIMEOUT_S,
        check=False,
    )
    assert result.returncode == 0, (
        f"Markdown DOM traversal failed:\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    assert "markdown DOM traversal OK" in result.stdout


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
