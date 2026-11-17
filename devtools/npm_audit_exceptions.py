"""The one npm advisory ``devtools/npm_audit.sh`` tolerates, and the check that applies it.

``npm audit`` exits 1 for any advisory at or above the audit level, so its status cannot
tell a reviewed advisory from a new one. When the audit fails, the wrapper hands this
module the JSON answer of that same request, and the gate passes only if every package
reported at or above the level is explained by the exception below. Everything the review
rested on is pinned: the advisory's identity, severity, weakness, CVSS vector, and affected
range; that npm still knows no fix but the reviewed one; and the path, as packages,
releases, lockfile nodes, dependency edges, and which package the project depends on
directly.

Anything else fails the gate: another advisory at or above the level; the same advisory
re-scored, re-scoped, or fixable; the same advisory reaching us through another package,
release, edge, or node, or with the project depending on a path package directly; or a
report this module cannot read or whose counts disagree with its entries. So the
exception can lapse, which fails the gate and asks for a new review, but it cannot widen.

An answer that is not an audit report at all gets its own exit status, ``NOT_A_REPORT``,
because only such an answer can be an outage; the wrapper decides whether it is one.

Why the advisory is not exploitable here, the owner's approval, and when the exception is
removed: "Picomatch ReDoS Audit Exception" in SUPPLY-CHAIN-SECURITY.md, and bead mb-p1o0.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

# npm's severities, lowest first: the order `npm audit --audit-level` compares them in.
SEVERITIES = ("info", "low", "moderate", "high", "critical")
# The `npm audit --json` format this check reads; another version is unreadable here.
AUDIT_REPORT_VERSION = 2
ADVISORY_URL_PREFIX = "https://github.com/advisories/"
# The lockfile root's dependency maps: what the project itself depends on.
ROOT_DEPENDENCY_FIELDS = (
    "dependencies",
    "devDependencies",
    "optionalDependencies",
    "peerDependencies",
)
# Exit status for an answer that is not an audit report (an endpoint or npm error).
# Distinct from 1 (the exception does not cover the report) and from 2, which argparse
# and uv use for their own errors; `devtools/npm_audit.sh` reads it.
NOT_A_REPORT = 3


@dataclass(frozen=True)
class Hop:
    """One package npm may report as vulnerable through the advisory.

    ``version`` is the locked release it was reviewed at, ``nodes`` the lockfile nodes it
    may name, ``direct`` whether the project depends on it itself, and ``via`` the
    packages it may be vulnerable through. A report may name fewer nodes or edges, which
    only narrows the path; a node or a package not listed here is another path.
    """

    version: str
    nodes: tuple[str, ...]
    direct: bool
    via: tuple[str, ...] = ()


@dataclass(frozen=True)
class AuditException:
    """A reviewed advisory, and the only path on which the audit tolerates it."""

    ghsa: str
    package: str
    # The advisory as npm reported it when it was reviewed. A change to any of these is a
    # reason to review it again, so it lapses the exception rather than following it.
    severity: str
    cwe: tuple[str, ...]
    cvss_vector: str
    affected_range: str
    # What npm offered as a fix on the vulnerable package's entry. A published fix, or a
    # tryscript release that drops the path, changes it, which ends the exception.
    fix_available: Mapping[str, object]
    path: Mapping[str, Hop]
    bead: str

    @property
    def url(self) -> str:
        return ADVISORY_URL_PREFIX + self.ghsa


# "picomatch vulnerable to ReDoS through single-branch repeated extglobs". It affected
# picomatch <= 4.0.7 and had no patched release when the owner approved this exception on
# 2026-11-17, so npm's only offered fix was a breaking downgrade of tryscript. picomatch
# reaches the lock only through the dev dependency tryscript, whose test discovery globs
# the repository's own committed patterns.
PICOMATCH_REDOS = AuditException(
    ghsa="GHSA-fc5q-39xc-vjpf",
    package="picomatch",
    severity="high",
    cwe=("CWE-1333",),
    cvss_vector="CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H",
    affected_range="<=4.0.7",
    fix_available={"name": "tryscript", "version": "0.2.1", "isSemVerMajor": True},
    path={
        "picomatch": Hop("4.0.7", ("node_modules/picomatch",), direct=False),
        "fdir": Hop("6.5.0", ("node_modules/fdir",), direct=False, via=("picomatch",)),
        "tinyglobby": Hop(
            "0.2.17", ("node_modules/tinyglobby",), direct=False, via=("fdir", "picomatch")
        ),
        "tryscript": Hop("0.3.1", ("node_modules/tryscript",), direct=True, via=("tinyglobby",)),
    },
    bead="mb-p1o0",
)


@dataclass(frozen=True)
class Verdict:
    """What the report still has against the gate once the exception is applied.

    ``report`` is false when the answer was not an audit report at all.
    """

    problems: tuple[str, ...]
    tolerated: tuple[str, ...]
    report: bool = True

    @property
    def passes(self) -> bool:
        return not self.problems


def _object(value: object) -> dict[str, object] | None:
    return cast(dict[str, object], value) if isinstance(value, dict) else None


def _strings(value: object) -> list[str] | None:
    if not isinstance(value, list):
        return None
    items = cast(list[object], value)
    if not all(isinstance(item, str) for item in items):
        return None
    return cast(list[str], items)


def _rank(severity: object) -> int | None:
    return (
        SEVERITIES.index(severity) if isinstance(severity, str) and severity in SEVERITIES else None
    )


def _describe_via(via: object) -> str:
    """A report entry's causes, short: advisories by URL, severity, and title."""

    if not isinstance(via, list):
        return repr(via)
    described: list[str] = []
    for item in cast(list[object], via):
        advisory = _object(item)
        if advisory is None:
            described.append(str(item))
        else:
            described.append(
                f"{advisory.get('url')} ({advisory.get('severity')}, {advisory.get('title')!r})"
            )
    return ", ".join(described) or "nothing"


def _advisory_problems(
    name: str, advisory: dict[str, object], exception: AuditException
) -> list[str]:
    """Why *advisory*, reported on package *name*, is not the reviewed exception."""

    url = advisory.get("url")
    label = f"{name}: {url} ({advisory.get('severity')}, {advisory.get('title')!r})"
    if url != exception.url:
        return [f"{label} is not an excepted advisory"]
    problems: list[str] = []
    if name != exception.package:
        problems.append(f"{label} is reported on {name}, not {exception.package}")
    if advisory.get("name") != exception.package:
        problems.append(f"{label} names {advisory.get('name')!r}, not {exception.package}")
    reviewed: tuple[tuple[str, object, object], ...] = (
        ("severity", advisory.get("severity"), exception.severity),
        ("range", advisory.get("range"), exception.affected_range),
        ("cwe", advisory.get("cwe"), list(exception.cwe)),
        (
            "CVSS vector",
            (_object(advisory.get("cvss")) or {}).get("vectorString"),
            exception.cvss_vector,
        ),
    )
    for field, actual, expected in reviewed:
        if actual != expected:
            problems.append(f"{label} now has {field} {actual!r}, not the reviewed {expected!r}")
    return problems


def _node_problems(
    name: str, nodes: Sequence[str], hop: Hop, packages: Mapping[str, object]
) -> list[str]:
    """Why the lockfile nodes npm names for *name* are off the reviewed path."""

    problems: list[str] = []
    if not nodes:
        problems.append(f"{name}: npm names no lockfile node for it")
    for node in nodes:
        if node not in hop.nodes:
            problems.append(f"{name}: installed at {node}, outside the reviewed {list(hop.nodes)}")
            continue
        package = _object(packages.get(node))
        if package is None:
            problems.append(f"{name}: {node} is not in package-lock.json")
            continue
        if package.get("dev") is not True:
            problems.append(f"{name}: {node} is not a dev dependency in package-lock.json")
        if package.get("version") != hop.version:
            problems.append(
                f"{name}: {node} is {package.get('version')!r} in package-lock.json, not the "
                f"reviewed {hop.version!r}"
            )
    return problems


def _root_problems(packages: Mapping[str, object], exception: AuditException) -> list[str]:
    """Path packages the project depends on directly, though the review found none."""

    root = _object(packages.get("")) or {}
    named: set[str] = set()
    for field in ROOT_DEPENDENCY_FIELDS:
        named.update((_object(root.get(field)) or {}).keys())
    return [
        f"package-lock.json's root depends on {name} directly; the reviewed path reaches it "
        "only through tryscript"
        for name, hop in sorted(exception.path.items())
        if not hop.direct and name in named
    ]


def _count_problems(
    report: Mapping[str, object], vulnerabilities: Mapping[str, object]
) -> list[str]:
    """Whether the report's own counts agree with the entries this check read."""

    counts = dict.fromkeys(SEVERITIES, 0)
    for value in vulnerabilities.values():
        severity = (_object(value) or {}).get("severity")
        if isinstance(severity, str) and severity in counts:
            counts[severity] += 1
    expected: dict[str, int] = {**counts, "total": len(vulnerabilities)}
    stated = _object((_object(report.get("metadata")) or {}).get("vulnerabilities"))
    if stated is None:
        return ["the report has no metadata.vulnerabilities counts"]
    return [
        f"the report's metadata counts {stated.get(key)!r} {key}, but it lists {count}"
        for key, count in expected.items()
        if stated.get(key) != count
    ]


def check(
    report: object,
    lockfile: object,
    level: str,
    exception: AuditException = PICOMATCH_REDOS,
) -> Verdict:
    """Whether every package *report* names at or above *level* is explained by *exception*.

    *report* is the parsed ``npm audit --json`` output and *lockfile* the parsed
    ``package-lock.json`` it audited. A package below *level* is ignored, as
    ``npm audit --audit-level`` ignores it. A report with nothing at or above *level*
    has nothing to tolerate: it contradicts the failing audit that asked for this check,
    so it fails too.
    """

    threshold = _rank(level)
    if threshold is None:
        return Verdict((f"unknown audit level {level!r}",), ())
    report_object = _object(report)
    vulnerabilities = _object(report_object.get("vulnerabilities")) if report_object else None
    if (
        report_object is None
        or report_object.get("auditReportVersion") != AUDIT_REPORT_VERSION
        or vulnerabilities is None
    ):
        return Verdict(
            (
                "npm's answer is not an audit report this check reads (an endpoint or npm "
                f"error, or a report format other than version {AUDIT_REPORT_VERSION})",
            ),
            (),
            report=False,
        )
    lock_object = _object(lockfile)
    packages = _object(lock_object.get("packages")) if lock_object else None
    if packages is None:
        return Verdict(("package-lock.json has no packages map",), ())

    problems = _count_problems(report_object, vulnerabilities) + _root_problems(packages, exception)
    tolerated: list[str] = []
    for name in sorted(vulnerabilities):
        entry = _object(vulnerabilities[name])
        if entry is None:
            problems.append(f"{name}: unreadable report entry")
            continue
        severity = entry.get("severity")
        rank = _rank(severity)
        if rank is None:
            problems.append(f"{name}: unknown severity {severity!r}")
            continue
        if rank < threshold:
            continue
        hop = exception.path.get(name)
        if hop is None:
            problems.append(
                f"{name}: {severity} through {_describe_via(entry.get('via'))}, which is not "
                f"{exception.ghsa} on its reviewed path"
            )
            continue
        entry_problems: list[str] = []
        if severity != exception.severity:
            entry_problems.append(f"{name}: {severity}, not the reviewed {exception.severity}")
        if entry.get("isDirect") is not hop.direct:
            entry_problems.append(
                f"{name}: isDirect is {entry.get('isDirect')!r}, not the reviewed {hop.direct!r}"
            )
        if name == exception.package and entry.get("fixAvailable") != exception.fix_available:
            entry_problems.append(
                f"{name}: npm now offers fixAvailable {entry.get('fixAvailable')!r}, not the "
                f"reviewed {dict(exception.fix_available)!r}; a fix may have shipped"
            )
        # Whether something on the reviewed path is what puts this package at the level.
        explained = False
        via = entry.get("via")
        if not isinstance(via, list):
            entry_problems.append(f"{name}: unreadable via {via!r}")
            via = []
        for item in cast(list[object], via):
            if isinstance(item, str):
                cause = _object(vulnerabilities.get(item))
                if cause is None:
                    entry_problems.append(
                        f"{name}: vulnerable through {item}, which the report does not list"
                    )
                    continue
                cause_rank = _rank(cause.get("severity"))
                # A dependency below the level does not raise this package to it.
                if cause_rank is not None and cause_rank < threshold:
                    continue
                if item in hop.via:
                    explained = True
                else:
                    entry_problems.append(
                        f"{name}: vulnerable through {item}, not a reviewed edge {list(hop.via)}"
                    )
                continue
            advisory = _object(item)
            if advisory is None:
                entry_problems.append(f"{name}: unreadable via entry {item!r}")
                continue
            advisory_rank = _rank(advisory.get("severity"))
            if advisory_rank is not None and advisory_rank < threshold:
                continue
            advisory_problems = _advisory_problems(name, advisory, exception)
            entry_problems.extend(advisory_problems)
            explained = explained or not advisory_problems
        if not explained and not entry_problems:
            entry_problems.append(f"{name}: {severity}, but nothing on the reviewed path is why")
        nodes = _strings(entry.get("nodes"))
        if nodes is None:
            entry_problems.append(f"{name}: unreadable nodes {entry.get('nodes')!r}")
        else:
            entry_problems.extend(_node_problems(name, nodes, hop, packages))
        if entry_problems:
            problems.extend(entry_problems)
        else:
            tolerated.append(name)
    if not problems and exception.package not in tolerated:
        problems.append(
            f"the report has nothing from {exception.ghsa} at or above {level} to tolerate, "
            "so it does not explain why the audit failed"
        )
    return Verdict(tuple(problems), tuple(tolerated))


def _banner(exception: AuditException, verdict: Verdict, level: str) -> str:
    rule = "#" * 78
    return "\n".join(
        (
            "",
            rule,
            f"#  npm audit EXCEPTION APPLIED: {exception.ghsa} tolerated until bead {exception.bead}.",
            f"#  Reported on {', '.join(verdict.tolerated)}, on the reviewed path at the "
            "reviewed releases.",
            f"#  Nothing else is at or above {level}. The review is in SUPPLY-CHAIN-SECURITY.md.",
            rule,
            "",
        )
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--level", required=True, help="the npm audit level that fails the gate")
    parser.add_argument("--lockfile", type=Path, default=Path("package-lock.json"))
    args = parser.parse_args(argv)
    level = cast(str, args.level)
    lockfile_path = cast(Path, args.lockfile)

    text = sys.stdin.read()
    try:
        report: object = json.loads(text)
    except json.JSONDecodeError:
        report = None
    try:
        lockfile: object = json.loads(lockfile_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"npm audit: cannot read {lockfile_path}: {error}", file=sys.stderr)
        return 1

    exception = PICOMATCH_REDOS
    verdict = check(report, lockfile, level, exception)
    if verdict.passes:
        print(_banner(exception, verdict, level), file=sys.stderr)
        return 0
    if not verdict.report:
        print(f"npm audit: {verdict.problems[0]}.", file=sys.stderr)
        return NOT_A_REPORT
    print(
        f"npm audit: the {exception.ghsa} exception (bead {exception.bead}) does not cover "
        "this report, so it is not applied:",
        file=sys.stderr,
    )
    for problem in verdict.problems:
        print(f"  - {problem}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
