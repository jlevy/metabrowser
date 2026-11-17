"""``devtools/npm_audit.sh`` tolerates one reviewed advisory, and only on its reviewed path.

The exception for GHSA-fc5q-39xc-vjpf (``devtools/npm_audit_exceptions.py``, bead
mb-p1o0) passes a failing audit only when that advisory, on the packages, edges, lockfile
nodes, affected range, and locked release it was reviewed at, is everything at or above
the level. ``tests/fixtures/npm-audit-picomatch-redos.json`` is the report it was reviewed
on, as ``npm audit --json`` printed it on 2026-11-17. Each test below changes one thing a
different finding would change and expects the gate to fail, or changes something below
the level and expects the gate to behave as plain ``npm audit`` does. The last tests run
the wrapper itself against a stand-in ``npm``, so its clean and outage paths are held to
what they were before the exception.
"""

from __future__ import annotations

import copy
import json
import os
import subprocess
from pathlib import Path
from typing import Any, cast

import pytest

from devtools.npm_audit_exceptions import PICOMATCH_REDOS, check

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "devtools" / "npm_audit.sh"
REPORT = json.loads(
    (ROOT / "tests" / "fixtures" / "npm-audit-picomatch-redos.json").read_text(encoding="utf-8")
)
# The lockfile nodes the reviewed report names, as package-lock.json records them.
LOCK = {
    "lockfileVersion": 3,
    "packages": {
        "": {"devDependencies": {"tryscript": "0.3.1"}},
        "node_modules/fdir": {"version": "6.5.0", "dev": True},
        "node_modules/picomatch": {"version": "4.0.7", "dev": True},
        "node_modules/tinyglobby": {"version": "0.2.17", "dev": True},
        "node_modules/tryscript": {"version": "0.3.1", "dev": True},
    },
}
# An advisory shaped like the reviewed one, on a package the repository does not have.
OTHER_ADVISORY = {
    "source": 1,
    "name": "example-glob",
    "dependency": "example-glob",
    "title": "example-glob vulnerable to something else",
    "url": "https://github.com/advisories/GHSA-0000-0000-0000",
    "severity": "high",
    "cwe": [],
    "cvss": {},
    "range": "<2.0.0",
}
# What `npm audit --json` printed when it could not reach the advisory endpoint.
OUTAGE_REPORT = {
    "message": "request to https://registry.npmjs.org/-/npm/v1/security/advisories/bulk "
    "failed, reason: getaddrinfo ENOTFOUND registry.npmjs.org",
    "error": {"summary": "", "detail": ""},
}


def _report() -> dict[str, Any]:
    return copy.deepcopy(cast(dict[str, Any], REPORT))


def _lock() -> dict[str, Any]:
    return copy.deepcopy(cast(dict[str, Any], LOCK))


def _entry(
    name: str, severity: str, via: list[object], nodes: list[str] | None = None
) -> dict[str, object]:
    return {
        "name": name,
        "severity": severity,
        "isDirect": False,
        "via": via,
        "effects": [],
        "range": "*",
        "nodes": nodes if nodes is not None else [f"node_modules/{name}"],
        "fixAvailable": False,
    }


def _problems(report: object, lock: object = LOCK, level: str = "moderate") -> str:
    verdict = check(report, lock, level)
    assert not verdict.passes
    return "\n".join(verdict.problems)


def test_the_reviewed_report_passes_against_the_repository_lock() -> None:
    lock = json.loads((ROOT / "package-lock.json").read_text(encoding="utf-8"))
    verdict = check(REPORT, lock, "moderate")
    assert verdict.problems == ()
    assert verdict.tolerated == ("fdir", "picomatch", "tinyglobby", "tryscript")


def test_another_advisory_at_the_level_fails() -> None:
    report = _report()
    report["vulnerabilities"]["example-glob"] = _entry("example-glob", "high", [OTHER_ADVISORY])
    assert (
        "example-glob: high through https://github.com/advisories/GHSA-0000-0000-0000 (high, "
        "'example-glob vulnerable to something else'), which is not GHSA-fc5q-39xc-vjpf"
        in _problems(report)
    )


def test_another_advisory_on_picomatch_fails() -> None:
    report = _report()
    report["vulnerabilities"]["picomatch"]["via"].append({**OTHER_ADVISORY, "name": "picomatch"})
    problems = _problems(report)
    assert "picomatch: https://github.com/advisories/GHSA-0000-0000-0000 (high," in problems
    assert "is not an excepted advisory" in problems


def test_an_advisory_below_the_level_is_ignored_as_npm_ignores_it() -> None:
    report = _report()
    moderate = {**OTHER_ADVISORY, "severity": "moderate"}
    report["vulnerabilities"]["example-glob"] = _entry("example-glob", "moderate", [moderate])
    assert check(report, LOCK, "high").passes
    assert "example-glob" in _problems(report, level="moderate")


def test_a_dependency_below_the_level_is_not_another_path() -> None:
    report = _report()
    low = {**OTHER_ADVISORY, "name": "zod", "severity": "low"}
    report["vulnerabilities"]["zod"] = _entry("zod", "low", [low])
    report["vulnerabilities"]["tryscript"]["via"].append("zod")
    assert check(report, LOCK, "moderate").passes


def test_the_advisory_through_another_package_fails() -> None:
    report = _report()
    report["vulnerabilities"]["example-glob"] = _entry("example-glob", "high", ["picomatch"])
    report["vulnerabilities"]["picomatch"]["effects"].append("example-glob")
    assert (
        "example-glob: high through picomatch, which is not GHSA-fc5q-39xc-vjpf on its reviewed "
        "path" in _problems(report)
    )


def test_the_advisory_through_another_edge_fails() -> None:
    report = _report()
    report["vulnerabilities"]["tryscript"]["via"].append("picomatch")
    assert "tryscript: vulnerable through picomatch, not a reviewed edge" in _problems(report)


def test_the_advisory_at_another_node_fails() -> None:
    report = _report()
    nested = "node_modules/example-glob/node_modules/picomatch"
    report["vulnerabilities"]["picomatch"]["nodes"].append(nested)
    lock = _lock()
    lock["packages"][nested] = {"version": "4.0.7", "dev": True}
    assert f"picomatch: installed at {nested}, outside the reviewed" in _problems(report, lock)


def test_the_advisory_on_another_package_fails() -> None:
    report = _report()
    advisory = report["vulnerabilities"]["picomatch"]["via"][0]
    report["vulnerabilities"]["tinyglobby"]["via"].append({**advisory, "name": "tinyglobby"})
    assert "reported on a package other than picomatch" in _problems(report)


@pytest.mark.parametrize("name", ["picomatch", "tryscript"])
def test_a_finding_the_path_does_not_explain_fails(name: str) -> None:
    report = _report()
    report["vulnerabilities"][name]["via"] = []
    assert f"{name}: high, but nothing on the reviewed path is why" in _problems(report)


def test_a_revised_affected_range_fails() -> None:
    report = _report()
    report["vulnerabilities"]["picomatch"]["via"][0]["range"] = "<4.0.9"
    assert "now affects '<4.0.9', not the reviewed '<=4.0.7'" in _problems(report)


def test_a_moved_picomatch_fails() -> None:
    lock = _lock()
    lock["packages"]["node_modules/picomatch"]["version"] = "4.0.8"
    assert "is '4.0.8' in package-lock.json, not the reviewed '4.0.7'" in _problems(REPORT, lock)


def test_a_node_that_is_not_dev_only_fails() -> None:
    lock = _lock()
    del lock["packages"]["node_modules/tinyglobby"]["dev"]
    assert "node_modules/tinyglobby is not a dev-only install" in _problems(REPORT, lock)


@pytest.mark.parametrize(
    "report",
    [OUTAGE_REPORT, None, [], {"auditReportVersion": 1, "vulnerabilities": {}}],
    ids=["endpoint-error", "not-json", "not-an-object", "old-format"],
)
def test_an_unreadable_report_applies_nothing(report: object) -> None:
    assert "unreadable" in _problems(report)


def test_a_report_with_nothing_to_tolerate_fails() -> None:
    report = _report()
    report["vulnerabilities"] = {}
    assert "nothing from GHSA-fc5q-39xc-vjpf at or above moderate" in _problems(report)


def test_the_exception_cites_its_bead_where_it_is_applied_and_reviewed() -> None:
    for path in (SCRIPT, ROOT / "SUPPLY-CHAIN-SECURITY.md"):
        text = path.read_text(encoding="utf-8")
        assert PICOMATCH_REDOS.ghsa in text, path
        assert PICOMATCH_REDOS.bead in text, path


# A stand-in for `npm audit`: the text report and its status, or with --json the JSON
# report, which npm prints with status 1 whenever it has a finding.
FAKE_NPM = """#!/usr/bin/env bash
case " $* " in
  *" --json "*) cat "$FAKE_NPM_DIR/report.json"; exit 1 ;;
esac
cat "$FAKE_NPM_DIR/text"
exit "$FAKE_NPM_STATUS"
"""


def _run_wrapper(
    tmp_path: Path, status: int, text: str, report: object = REPORT
) -> subprocess.CompletedProcess[str]:
    """``npm_audit.sh`` at one attempt, run where ``make audit`` runs it, with fake npm."""

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    npm = bin_dir / "npm"
    npm.write_text(FAKE_NPM, encoding="utf-8")
    npm.chmod(0o755)
    (tmp_path / "text").write_text(text, encoding="utf-8")
    (tmp_path / "report.json").write_text(json.dumps(report), encoding="utf-8")
    env = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "FAKE_NPM_DIR": str(tmp_path),
        "FAKE_NPM_STATUS": str(status),
        "NPM_AUDIT_ATTEMPTS": "1",
        "NPM_AUDIT_LEVEL": "moderate",
    }
    return subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def test_the_wrapper_passes_a_clean_audit(tmp_path: Path) -> None:
    result = _run_wrapper(tmp_path, 0, "found 0 vulnerabilities\n")
    assert result.returncode == 0
    assert "npm audit: no advisories at or above moderate." in result.stdout
    assert "EXCEPTION" not in result.stderr


def test_the_wrapper_applies_the_exception_loudly(tmp_path: Path) -> None:
    result = _run_wrapper(tmp_path, 1, "4 high severity vulnerabilities\n")
    assert result.returncode == 0, result.stderr
    assert "4 high severity vulnerabilities" in result.stdout
    assert "npm audit EXCEPTION APPLIED: GHSA-fc5q-39xc-vjpf tolerated until bead mb-p1o0" in (
        result.stderr
    )


def test_the_wrapper_fails_on_another_advisory(tmp_path: Path) -> None:
    report = _report()
    report["vulnerabilities"]["example-glob"] = _entry("example-glob", "high", [OTHER_ADVISORY])
    result = _run_wrapper(tmp_path, 1, "5 high severity vulnerabilities\n", report)
    assert result.returncode == 1
    assert "example-glob" in result.stderr
    assert "npm audit: advisories found at or above moderate; failing." in result.stderr
    assert "EXCEPTION APPLIED" not in result.stderr


def test_the_wrapper_fails_when_the_json_request_finds_an_outage(tmp_path: Path) -> None:
    result = _run_wrapper(tmp_path, 1, "4 high severity vulnerabilities\n", OUTAGE_REPORT)
    assert result.returncode == 1
    assert "unreadable" in result.stderr
    assert "EXCEPTION APPLIED" not in result.stderr


def test_the_wrapper_still_reports_an_outage_as_not_performed(tmp_path: Path) -> None:
    result = _run_wrapper(tmp_path, 1, "npm error audit endpoint returned an error\n")
    assert result.returncode == 0
    assert "npm audit: advisory endpoint unreachable (attempt 1/1)." in result.stdout
    assert "npm audit was NOT PERFORMED." in result.stderr
    assert "EXCEPTION" not in result.stderr
