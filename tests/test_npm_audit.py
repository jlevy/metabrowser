"""``devtools/npm_audit.sh`` fails on a finding and tolerates only an outage.

Each test runs the wrapper where ``make audit`` runs it, against a stand-in ``npm`` that
prints a recorded stdout and stderr and exits with a chosen status. The texts follow
npm 11.17.0: a finding is a report on stdout that begins ``# npm audit report``; an
unreachable endpoint prints ``undefined`` on stdout and names the failure on stderr; a
missing lockfile prints only an ``ENOLOCK`` error on stderr.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "devtools" / "npm_audit.sh"

# The stand-in logs each request and answers with the files the test wrote.
FAKE_NPM = """#!/usr/bin/env bash
echo "$*" >> "$FAKE_NPM_DIR/calls"
cat "$FAKE_NPM_DIR/stdout"
cat "$FAKE_NPM_DIR/stderr" >&2
exit "$FAKE_NPM_STATUS"
"""
REQUEST = "audit --include=dev --audit-level=moderate"
CLEAN = "found 0 vulnerabilities\n"


def _report(title: str) -> str:
    """npm's text report for one high advisory with ``title``."""

    return (
        "# npm audit report\n"
        "\n"
        "example-glob  *\n"
        "Severity: high\n"
        f"{title} - https://github.com/advisories/GHSA-0000-0000-0000\n"
        "No fix available\n"
        "node_modules/example-glob\n"
        "\n"
        "1 high severity vulnerability\n"
    )


ADVISORY = _report("example-glob vulnerable to ReDoS through repeated extglobs")
OUTAGE_STDOUT = "undefined\n"
OUTAGE_STDERR = (
    "npm warn audit request to https://registry.npmjs.org/-/npm/v1/security/advisories/bulk"
    " failed, reason: getaddrinfo ENOTFOUND registry.npmjs.org\n"
    "npm error audit endpoint returned an error\n"
)
NO_LOCK_STDERR = (
    "npm error code ENOLOCK\nnpm error audit This command requires an existing lockfile.\n"
)


def _run_wrapper(
    tmp_path: Path,
    status: int,
    stdout: str,
    stderr: str = "",
    env: dict[str, str] | None = None,
) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    """``npm_audit.sh`` at one attempt against the stand-in, and the requests npm saw."""

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    npm = bin_dir / "npm"
    npm.write_text(FAKE_NPM, encoding="utf-8")
    npm.chmod(0o755)
    (tmp_path / "stdout").write_text(stdout, encoding="utf-8")
    (tmp_path / "stderr").write_text(stderr, encoding="utf-8")
    calls_file = tmp_path / "calls"
    calls_file.write_text("", encoding="utf-8")
    run_env = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "FAKE_NPM_DIR": str(tmp_path),
        "FAKE_NPM_STATUS": str(status),
        "NPM_AUDIT_ATTEMPTS": "1",
        "NPM_AUDIT_LEVEL": "moderate",
        **(env or {}),
    }
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=ROOT,
        env=run_env,
        capture_output=True,
        text=True,
        timeout=50,
        check=False,
    )
    return result, calls_file.read_text(encoding="utf-8").splitlines()


def test_a_clean_audit_passes(tmp_path: Path) -> None:
    result, calls = _run_wrapper(tmp_path, 0, CLEAN)
    assert result.returncode == 0, result.stderr
    assert "found 0 vulnerabilities" in result.stdout
    assert "npm audit: no advisories at or above moderate." in result.stdout
    assert "NOT PERFORMED" not in result.stderr
    assert calls == [REQUEST]


def test_an_advisory_fails(tmp_path: Path) -> None:
    result, calls = _run_wrapper(tmp_path, 1, ADVISORY)
    assert result.returncode == 1
    assert "1 high severity vulnerability" in result.stdout
    assert "npm audit: advisories found at or above moderate; failing." in result.stderr
    assert "NOT PERFORMED" not in result.stderr
    assert calls == [REQUEST]


def test_an_outage_is_reported_as_not_performed(tmp_path: Path) -> None:
    result, calls = _run_wrapper(tmp_path, 1, OUTAGE_STDOUT, OUTAGE_STDERR)
    assert result.returncode == 0, result.stderr
    assert "npm audit: advisory endpoint unreachable (attempt 1/1)." in result.stdout
    assert "npm audit was NOT PERFORMED." in result.stderr
    assert "audit endpoint returned an error" in result.stderr
    assert calls == [REQUEST]


def test_an_npm_error_that_is_not_an_outage_fails(tmp_path: Path) -> None:
    result, calls = _run_wrapper(tmp_path, 1, "", NO_LOCK_STDERR)
    assert result.returncode == 1
    assert "ENOLOCK" in result.stderr
    assert "NOT PERFORMED" not in result.stderr
    assert "advisory endpoint unreachable" not in result.stdout
    assert calls == [REQUEST]


@pytest.mark.parametrize(
    "title",
    [
        "example-http crashes with an uncaught ECONNRESET on a reset socket",
        "example-fetch ignores its network timeout option",
        "example-dns retries forever on EAI_AGAIN and ENOTFOUND",
        "example-proxy forwards a 503 Service Unavailable body unescaped",
    ],
)
def test_a_finding_whose_title_names_an_outage_is_still_a_finding(
    tmp_path: Path, title: str
) -> None:
    result, calls = _run_wrapper(tmp_path, 1, _report(title))
    assert result.returncode == 1
    assert title in result.stdout
    assert "npm audit: advisories found at or above moderate; failing." in result.stderr
    assert "NOT PERFORMED" not in result.stderr
    assert "advisory endpoint unreachable" not in result.stdout
    assert calls == [REQUEST]


def test_a_report_is_a_finding_even_when_npm_also_warns_of_an_outage(tmp_path: Path) -> None:
    result, _ = _run_wrapper(tmp_path, 1, ADVISORY, OUTAGE_STDERR)
    assert result.returncode == 1
    assert "npm audit: advisories found at or above moderate; failing." in result.stderr
    assert "NOT PERFORMED" not in result.stderr
    assert "advisory endpoint unreachable" not in result.stdout


@pytest.mark.parametrize("attempts", ["x", "0", "-1", "2x", "1.5", " "])
def test_an_attempt_count_that_is_not_a_positive_integer_fails(
    tmp_path: Path, attempts: str
) -> None:
    result, calls = _run_wrapper(tmp_path, 0, CLEAN, env={"NPM_AUDIT_ATTEMPTS": attempts})
    assert result.returncode != 0
    assert "NPM_AUDIT_ATTEMPTS must be a positive integer" in result.stderr
    assert "NOT PERFORMED" not in result.stderr
    assert calls == []


@pytest.mark.parametrize(
    "ambient",
    [{"NODE_ENV": "production"}, {"NPM_CONFIG_OMIT": "dev"}, {"npm_config_omit": "dev"}],
)
def test_the_audit_covers_dev_dependencies_whatever_the_environment_omits(
    tmp_path: Path, ambient: dict[str, str]
) -> None:
    # Every npm package here is a dev dependency, so an audit that honored an ambient
    # omission of dev dependencies would cover nothing. `--include=dev` overrides it.
    result, calls = _run_wrapper(tmp_path, 1, ADVISORY, env=ambient)
    assert result.returncode == 1
    assert calls == [REQUEST]
