"""``devtools/npm_audit.sh`` tolerates one reviewed advisory, exactly as reviewed.

The exception for GHSA-fc5q-39xc-vjpf (``devtools/npm_audit_exceptions.py``, bead
mb-p1o0) passes a failing audit only when that advisory, as reviewed and on the packages,
releases, edges, and lockfile nodes it was reviewed at, is everything at or above the
level. ``tests/fixtures/npm-audit-picomatch-redos.json`` is the report it was reviewed on,
as ``npm audit --json`` printed it on 2026-11-17. Each test below changes one thing a
different finding would change and expects the gate to fail, or changes something below
the level and expects the gate to behave as plain ``npm audit`` does; each fail-closed
branch of the check has its own case. The last tests run the wrapper itself against a
stand-in ``npm``: one JSON request decides, an outage is still NOT PERFORMED, and a
finding is never mistaken for one.
"""

from __future__ import annotations

import copy
import json
import os
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any, cast

import pytest

from devtools.npm_audit_exceptions import PICOMATCH_REDOS, SEVERITIES, check

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
# What `npm audit --json` printed, on stdout and stderr, when the endpoint was unreachable.
OUTAGE_REPORT = {
    "message": "request to https://registry.npmjs.org/-/npm/v1/security/advisories/bulk "
    "failed, reason: getaddrinfo ENOTFOUND registry.npmjs.org",
    "error": {"summary": "", "detail": ""},
}
OUTAGE_STDERR = "npm error audit endpoint returned an error\n"
# What npm prints for an error that is neither a report nor an outage.
NO_LOCK_REPORT = {
    "error": {"code": "ENOLOCK", "summary": "This command requires an existing lockfile."}
}


def _report() -> dict[str, Any]:
    return copy.deepcopy(cast(dict[str, Any], REPORT))


def _lock() -> dict[str, Any]:
    return copy.deepcopy(cast(dict[str, Any], LOCK))


def _recount(report: dict[str, Any]) -> dict[str, Any]:
    """*report* with its metadata counts matching its entries, as npm writes them."""

    counts = Counter(entry["severity"] for entry in report["vulnerabilities"].values())
    report["metadata"]["vulnerabilities"] = {
        **{severity: counts.get(severity, 0) for severity in SEVERITIES},
        "total": len(report["vulnerabilities"]),
    }
    return report


def _add(report: dict[str, Any], entry: dict[str, object]) -> dict[str, Any]:
    report["vulnerabilities"][entry["name"]] = entry
    return _recount(report)


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


# Other advisories.


def test_another_advisory_at_the_level_fails() -> None:
    report = _add(_report(), _entry("example-glob", "high", [OTHER_ADVISORY]))
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


def test_an_advisory_of_unknown_severity_is_checked_not_skipped() -> None:
    report = _report()
    unknown = {**OTHER_ADVISORY, "name": "picomatch", "severity": None}
    report["vulnerabilities"]["picomatch"]["via"].append(unknown)
    assert "GHSA-0000-0000-0000 (None, " in _problems(report)


def test_an_advisory_below_the_level_is_ignored_as_npm_ignores_it() -> None:
    moderate = {**OTHER_ADVISORY, "severity": "moderate"}
    report = _add(_report(), _entry("example-glob", "moderate", [moderate]))
    assert check(report, LOCK, "high").passes
    assert "example-glob" in _problems(report, level="moderate")


def test_a_dependency_below_the_level_is_not_another_path() -> None:
    low = {**OTHER_ADVISORY, "name": "zod", "severity": "low"}
    report = _add(_report(), _entry("zod", "low", [low]))
    report["vulnerabilities"]["tryscript"]["via"].append("zod")
    assert check(report, LOCK, "moderate").passes


# The advisory itself, as reviewed (A1) and while no fix exists (A3).


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("severity", "critical", "now has severity 'critical', not the reviewed 'high'"),
        ("range", "<4.0.9", "now has range '<4.0.9', not the reviewed '<=4.0.7'"),
        ("cwe", ["CWE-400"], "now has cwe ['CWE-400'], not the reviewed ['CWE-1333']"),
        (
            "cvss",
            {"score": 9.8, "vectorString": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"},
            "now has CVSS vector 'CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H'",
        ),
    ],
)
def test_a_revised_advisory_fails(field: str, value: object, message: str) -> None:
    report = _report()
    report["vulnerabilities"]["picomatch"]["via"][0][field] = value
    assert message in _problems(report)


def test_a_rescored_path_package_fails() -> None:
    report = _report()
    report["vulnerabilities"]["tinyglobby"]["severity"] = "critical"
    assert "tinyglobby: critical, not the reviewed high" in _problems(_recount(report))


def test_a_published_fix_ends_the_exception() -> None:
    report = _report()
    report["vulnerabilities"]["picomatch"]["fixAvailable"] = True
    assert "picomatch: npm now offers fixAvailable True" in _problems(report)


# The reviewed path: packages, edges, nodes, releases, and direct dependencies (A2, A4).


def test_the_advisory_through_another_package_fails() -> None:
    report = _add(_report(), _entry("example-glob", "high", ["picomatch"]))
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


def test_the_advisory_reported_on_another_entry_fails() -> None:
    report = _report()
    advisory = report["vulnerabilities"]["picomatch"]["via"][0]
    report["vulnerabilities"]["tinyglobby"]["via"].append(copy.deepcopy(advisory))
    assert "is reported on tinyglobby, not picomatch" in _problems(report)


def test_the_advisory_naming_another_package_fails() -> None:
    report = _report()
    report["vulnerabilities"]["picomatch"]["via"][0]["name"] = "example-glob"
    assert "names 'example-glob', not picomatch" in _problems(report)


@pytest.mark.parametrize(("name", "is_direct"), [("picomatch", True), ("tryscript", False)])
def test_a_changed_direct_dependency_fails(name: str, is_direct: bool) -> None:
    report = _report()
    report["vulnerabilities"][name]["isDirect"] = is_direct
    assert f"{name}: isDirect is {is_direct!r}, not the reviewed {not is_direct!r}" in (
        _problems(report)
    )


@pytest.mark.parametrize("name", ["picomatch", "fdir", "tinyglobby"])
def test_a_root_dependency_on_a_path_package_fails(name: str) -> None:
    lock = _lock()
    lock["packages"][""]["devDependencies"][name] = "1.0.0"
    assert f"package-lock.json's root depends on {name} directly" in _problems(REPORT, lock)


@pytest.mark.parametrize(
    ("name", "moved"),
    [("picomatch", "4.0.8"), ("fdir", "6.5.1"), ("tinyglobby", "0.2.18"), ("tryscript", "0.3.2")],
)
def test_a_moved_path_package_fails(name: str, moved: str) -> None:
    lock = _lock()
    lock["packages"][f"node_modules/{name}"]["version"] = moved
    assert f"is '{moved}' in package-lock.json, not the reviewed" in _problems(REPORT, lock)


def test_a_node_that_is_not_a_dev_dependency_fails() -> None:
    lock = _lock()
    del lock["packages"]["node_modules/tinyglobby"]["dev"]
    assert "node_modules/tinyglobby is not a dev dependency" in _problems(REPORT, lock)


@pytest.mark.parametrize("name", ["picomatch", "tryscript"])
def test_a_finding_the_path_does_not_explain_fails(name: str) -> None:
    report = _report()
    report["vulnerabilities"][name]["via"] = []
    assert f"{name}: high, but nothing on the reviewed path is why" in _problems(report)


def test_a_path_package_missing_from_the_report_explains_nothing() -> None:
    report = _report()
    for name in ("fdir", "tinyglobby"):
        del report["vulnerabilities"][name]
    assert "tryscript: vulnerable through tinyglobby, which the report does not list" in (
        _problems(_recount(report))
    )


def test_a_dependent_alone_fails() -> None:
    report = _report()
    report["vulnerabilities"] = {"fdir": report["vulnerabilities"]["fdir"]}
    assert "fdir: vulnerable through picomatch, which the report does not list" in (
        _problems(_recount(report))
    )


# Each fail-closed branch (A6).


def test_no_node_named_fails() -> None:
    report = _report()
    report["vulnerabilities"]["picomatch"]["nodes"] = []
    assert "picomatch: npm names no lockfile node for it" in _problems(report)


def test_a_node_missing_from_the_lock_fails() -> None:
    lock = _lock()
    del lock["packages"]["node_modules/fdir"]
    assert "fdir: node_modules/fdir is not in package-lock.json" in _problems(REPORT, lock)


def test_an_unknown_level_fails() -> None:
    assert "unknown audit level 'severe'" in _problems(REPORT, level="severe")


def test_a_lock_without_packages_fails() -> None:
    assert "package-lock.json has no packages map" in _problems(REPORT, {"lockfileVersion": 3})


def test_an_unreadable_entry_fails() -> None:
    report = _report()
    report["vulnerabilities"]["example-glob"] = "high"
    assert "example-glob: unreadable report entry" in _problems(report)


def test_an_unknown_severity_fails() -> None:
    report = _report()
    report["vulnerabilities"]["fdir"]["severity"] = "severe"
    assert "fdir: unknown severity 'severe'" in _problems(report)


def test_an_unreadable_via_fails() -> None:
    report = _report()
    report["vulnerabilities"]["fdir"]["via"] = "picomatch"
    assert "fdir: unreadable via 'picomatch'" in _problems(report)


def test_an_unreadable_via_entry_fails() -> None:
    report = _report()
    report["vulnerabilities"]["fdir"]["via"].append(42)
    assert "fdir: unreadable via entry 42" in _problems(report)


def test_unreadable_nodes_fail() -> None:
    report = _report()
    report["vulnerabilities"]["fdir"]["nodes"] = "node_modules/fdir"
    assert "fdir: unreadable nodes 'node_modules/fdir'" in _problems(report)


def test_counts_that_disagree_with_the_entries_fail() -> None:
    report = _report()
    report["metadata"]["vulnerabilities"].update(critical=1, total=5)
    problems = _problems(report)
    assert "the report's metadata counts 1 critical, but it lists 0" in problems
    assert "the report's metadata counts 5 total, but it lists 4" in problems


def test_a_report_without_counts_fails() -> None:
    report = _report()
    del report["metadata"]
    assert "the report has no metadata.vulnerabilities counts" in _problems(report)


@pytest.mark.parametrize(
    "report",
    [OUTAGE_REPORT, NO_LOCK_REPORT, None, [], {"auditReportVersion": 1, "vulnerabilities": {}}],
    ids=["endpoint-error", "npm-error", "not-json", "not-an-object", "old-format"],
)
def test_an_answer_that_is_not_a_report_applies_nothing(report: object) -> None:
    verdict = check(report, LOCK, "moderate")
    assert not verdict.passes
    assert not verdict.report
    assert "not an audit report" in verdict.problems[0]


def test_a_report_with_nothing_to_tolerate_fails() -> None:
    report = _report()
    report["vulnerabilities"] = {}
    assert "nothing from GHSA-fc5q-39xc-vjpf at or above moderate" in _problems(_recount(report))


def test_the_exception_cites_its_bead_where_it_is_applied_and_reviewed() -> None:
    for path in (SCRIPT, ROOT / "SUPPLY-CHAIN-SECURITY.md"):
        text = path.read_text(encoding="utf-8")
        assert PICOMATCH_REDOS.ghsa in text, path
        assert PICOMATCH_REDOS.bead in text, path


# The wrapper. A stand-in for `npm audit` logs each request; with --json it prints the
# JSON answer and its stderr, and otherwise npm's text report, both with one status.
FAKE_NPM = """#!/usr/bin/env bash
echo "$*" >> "$FAKE_NPM_DIR/calls"
case " $* " in
  *" --json "*)
    cat "$FAKE_NPM_DIR/answer"
    cat "$FAKE_NPM_DIR/stderr" >&2
    exit "$FAKE_NPM_STATUS" ;;
esac
cat "$FAKE_NPM_DIR/text"
exit "$FAKE_NPM_STATUS"
"""
JSON_REQUEST = "audit --json --audit-level=moderate"
TEXT_REQUEST = "audit --audit-level=moderate"


def _run_wrapper(
    tmp_path: Path,
    status: int,
    answer: object = REPORT,
    stderr: str = "",
    text: str = "4 high severity vulnerabilities\n",
) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    """``npm_audit.sh`` at one attempt, run where ``make audit`` runs it, and npm's calls."""

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    npm = bin_dir / "npm"
    npm.write_text(FAKE_NPM, encoding="utf-8")
    npm.chmod(0o755)
    (tmp_path / "answer").write_text(json.dumps(answer), encoding="utf-8")
    (tmp_path / "stderr").write_text(stderr, encoding="utf-8")
    (tmp_path / "text").write_text(text, encoding="utf-8")
    env = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "FAKE_NPM_DIR": str(tmp_path),
        "FAKE_NPM_STATUS": str(status),
        "NPM_AUDIT_ATTEMPTS": "1",
        "NPM_AUDIT_LEVEL": "moderate",
    }
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=50,
        check=False,
    )
    calls = (tmp_path / "calls").read_text(encoding="utf-8").splitlines()
    return result, calls


def test_the_wrapper_passes_a_clean_audit(tmp_path: Path) -> None:
    result, calls = _run_wrapper(tmp_path, 0, text="found 0 vulnerabilities\n")
    assert result.returncode == 0
    assert "found 0 vulnerabilities" in result.stdout
    assert "npm audit: no advisories at or above moderate." in result.stdout
    assert "EXCEPTION" not in result.stderr
    assert calls == [JSON_REQUEST, TEXT_REQUEST]


def test_the_wrapper_applies_the_exception_loudly(tmp_path: Path) -> None:
    result, calls = _run_wrapper(tmp_path, 1)
    assert result.returncode == 0, result.stderr
    assert "4 high severity vulnerabilities" in result.stdout
    assert "npm audit EXCEPTION APPLIED: GHSA-fc5q-39xc-vjpf tolerated until bead mb-p1o0" in (
        result.stderr
    )
    # The JSON request decides; the text one only shows the report.
    assert calls == [JSON_REQUEST, TEXT_REQUEST]


def test_the_wrapper_decides_on_the_json_answer_not_the_text(tmp_path: Path) -> None:
    report = _add(_report(), _entry("example-glob", "high", [OTHER_ADVISORY]))
    result, _ = _run_wrapper(tmp_path, 1, report, text="found 0 vulnerabilities\n")
    assert result.returncode == 1
    assert "example-glob" in result.stderr
    assert "npm audit: advisories found at or above moderate; failing." in result.stderr
    assert "EXCEPTION APPLIED" not in result.stderr


def test_a_finding_that_names_an_outage_is_still_a_finding(tmp_path: Path) -> None:
    titled = {**OTHER_ADVISORY, "title": "ECONNRESET and network timeout in example-glob"}
    report = _add(_report(), _entry("example-glob", "high", [titled]))
    result, _ = _run_wrapper(tmp_path, 1, report, text="ECONNRESET network timeout\n")
    assert result.returncode == 1
    assert "NOT PERFORMED" not in result.stderr
    assert "advisory endpoint unreachable" not in result.stdout


def test_the_wrapper_still_reports_an_outage_as_not_performed(tmp_path: Path) -> None:
    result, calls = _run_wrapper(tmp_path, 1, OUTAGE_REPORT, OUTAGE_STDERR)
    assert result.returncode == 0
    assert "npm audit: advisory endpoint unreachable (attempt 1/1)." in result.stdout
    assert "npm audit was NOT PERFORMED." in result.stderr
    assert "EXCEPTION" not in result.stderr
    assert calls == [JSON_REQUEST]


def test_an_npm_error_that_is_not_an_outage_fails(tmp_path: Path) -> None:
    result, calls = _run_wrapper(tmp_path, 1, NO_LOCK_REPORT, "npm error code ENOLOCK\n")
    assert result.returncode == 1
    assert "npm audit: npm returned an error, not an audit report; failing." in result.stderr
    assert "NOT PERFORMED" not in result.stderr
    assert calls == [JSON_REQUEST]
