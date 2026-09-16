"""Check installed artifact capabilities against their durable architecture inventory."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from metabrowser.plugin_loader.artifact_contracts import (
    CapabilityRegistryError,
    InstalledRegistries,
    get_installed_registries,
)
from metabrowser.plugin_loader.artifact_inventory import (
    ContractInventoryEntry,
    ResourceProfileInventoryEntry,
    check_installed_evidence,
    installed_artifact_inventory,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
ARCHITECTURE_DOC = REPO_ROOT / "docs/project/architecture/arch-external-resources-and-views.md"
BROWSER_CHECK = Path(__file__).with_name("artifact-contract-browser-check.mjs")
_NODE_TIMEOUT_SECONDS = 30

_CONTRACT_HEADER = (
    "Contract ID",
    "Artifact profile",
    "Envelope",
    "Producers",
    "Consumers",
    "Corpus",
    "Browser parser",
)
_PROFILE_HEADER = (
    "Profile ID",
    "Target kind",
    "Result contract",
    "Collections",
    "Pagination",
    "Last complete",
)


@dataclass(frozen=True, slots=True)
class _ArchitectureRow:
    identifier: str
    values: tuple[str, ...]


def _cells(line: str) -> tuple[str, ...]:
    return tuple(cell.strip() for cell in line.strip().strip("|").split("|"))


def _normalized_cell(value: str) -> str:
    stripped = value.strip()
    if len(stripped) >= 2 and stripped.startswith("`") and stripped.endswith("`"):
        return stripped[1:-1]
    return stripped


def _table_rows(document: str, header: tuple[str, ...]) -> tuple[_ArchitectureRow, ...]:
    lines = document.splitlines()
    for index, line in enumerate(lines):
        if _cells(line) != header:
            continue
        rows: list[_ArchitectureRow] = []
        for row_line in lines[index + 2 :]:
            if not row_line.strip().startswith("|"):
                break
            cells = _cells(row_line)
            if len(cells) != len(header):
                rows.append(_ArchitectureRow(identifier="", values=(row_line.strip(),)))
                continue
            normalized = tuple(_normalized_cell(cell) for cell in cells)
            rows.append(_ArchitectureRow(identifier=normalized[0], values=normalized[1:]))
        return tuple(rows)
    return ()


def _contract_values(contract: ContractInventoryEntry) -> tuple[str, ...]:
    selectors = ",".join(contract.corpus_record_selectors) or "*"
    return (
        contract.artifact_profile,
        contract.envelope,
        ",".join(contract.producer_ids),
        ",".join(contract.consumer_ids),
        f"{contract.corpus_id}[{selectors}]",
        contract.browser_parser_id or "server-only",
    )


def _profile_values(profile: ResourceProfileInventoryEntry) -> tuple[str, ...]:
    collections = ";".join(
        f"{collection.name}={collection.artifact_contract_id}"
        f"[{collection.minimum_artifacts}..{collection.maximum_artifacts}]"
        for collection in profile.collections
    )
    pagination = ";".join(
        f"{collection.name}={collection.pagination}" for collection in profile.collections
    )
    last_complete = ",".join(
        collection.name
        for collection in profile.collections
        if collection.required_for_last_complete
    )
    return (
        profile.target_kind,
        profile.target_result_contract_id or "—",
        collections,
        pagination,
        last_complete or "—",
    )


def _browser_evidence_problems(registries: InstalledRegistries) -> list[str]:
    descriptors: list[dict[str, object]] = []
    expected_case_count = 0
    with tempfile.TemporaryDirectory(prefix="metabrowser-artifact-inventory-") as temp_dir:
        evidence_root = Path(temp_dir)
        for contract_id, installed in sorted(registries.contracts.items()):
            spec = installed.spec
            parser = spec.browser_parser
            if parser is None:
                continue
            module_path = evidence_root / f"{parser.module_bytes_sha256}.mjs"
            module_path.write_bytes(parser.module_bytes)
            corpus_path = evidence_root / f"{spec.corpus.payload_sha256}.json"
            corpus_path.write_bytes(spec.corpus.payload)
            try:
                corpus = json.loads(spec.corpus.payload)
                selectors = set(spec.corpus_record_selectors)
                selected_count = sum(
                    (case.get("record") in selectors) if selectors else ("record" not in case)
                    for case in corpus["cases"]
                )
            except (json.JSONDecodeError, KeyError, TypeError, AttributeError) as exc:
                return [f"browser evidence cannot resolve {contract_id!r} corpus: {exc}"]
            expected_case_count += selected_count
            descriptors.append(
                {
                    "contract_id": contract_id,
                    "module_path": str(module_path),
                    "export_name": parser.export_name,
                    "corpus_path": str(corpus_path),
                    "record_selectors": spec.corpus_record_selectors,
                    "expected_case_count": selected_count,
                }
            )
        if not descriptors:
            return []
        descriptor_path = evidence_root / "descriptors.json"
        descriptor_path.write_text(json.dumps(descriptors), encoding="utf-8")
        try:
            result = subprocess.run(
                [
                    "node",
                    "--experimental-vm-modules",
                    "--no-warnings",
                    str(BROWSER_CHECK),
                    str(descriptor_path),
                ],
                capture_output=True,
                text=True,
                timeout=_NODE_TIMEOUT_SECONDS,
                check=False,
            )
        except FileNotFoundError:
            return ["browser evidence requires Node.js"]
        except subprocess.TimeoutExpired:
            return ["browser evidence timed out"]
        except OSError as exc:
            return [f"browser evidence could not start: {exc}"]
    expected_output = (
        f"artifact browser evidence OK ({len(descriptors)} parser(s), {expected_case_count} cases)"
    )
    if result.returncode == 0:
        if result.stdout.strip() == expected_output and not result.stderr.strip():
            return []
        return [
            "browser evidence exited successfully without its completion proof: "
            f"stdout={result.stdout.strip()!r}, stderr={result.stderr.strip()!r}"
        ]
    output = result.stderr.strip() or result.stdout.strip()
    if not output:
        return [f"browser evidence exited {result.returncode} without diagnostics"]
    return [f"browser evidence: {line}" for line in output.splitlines()]


def _reconcile_rows(
    *,
    label: str,
    header: tuple[str, ...],
    expected: dict[str, tuple[str, ...]],
    rows: Sequence[_ArchitectureRow],
) -> list[str]:
    problems: list[str] = []
    if not rows:
        return [f"architecture document has no {' | '.join(header)} table"]
    by_id: dict[str, _ArchitectureRow] = {}
    duplicate_ids: set[str] = set()
    for row in rows:
        if not row.identifier:
            problems.append(f"{label} architecture table has a malformed row")
            continue
        if row.identifier in by_id:
            duplicate_ids.add(row.identifier)
        else:
            by_id[row.identifier] = row
    for identifier in sorted(duplicate_ids):
        problems.append(f"{label} {identifier!r} has a duplicate architecture row")
    for identifier in sorted(expected.keys() - by_id.keys()):
        problems.append(f"installed {label} {identifier!r} has no architecture row")
    for identifier in sorted(by_id.keys() - expected.keys()):
        problems.append(f"architecture {label} {identifier!r} is not installed")
    for identifier in sorted(expected.keys() & by_id.keys()):
        actual_values = by_id[identifier].values
        expected_values = expected[identifier]
        if len(actual_values) != len(expected_values):
            problems.append(f"{label} {identifier!r} has a malformed architecture row")
            continue
        for column, expected_value, actual_value in zip(
            header[1:], expected_values, actual_values, strict=True
        ):
            if actual_value != expected_value:
                problems.append(
                    f"{label} {identifier!r} {column} is {actual_value!r}; "
                    f"expected {expected_value!r}"
                )
    return problems


def check(
    *,
    registries: InstalledRegistries | None = None,
    architecture_doc: Path = ARCHITECTURE_DOC,
) -> list[str]:
    """Return installed-evidence and architecture-registration problems."""
    try:
        if registries is None:
            registries = get_installed_registries()
    except CapabilityRegistryError as exc:
        return [f"installed capability registry failed: {exc}"]
    problems = list(check_installed_evidence(registries))
    problems.extend(_browser_evidence_problems(registries))
    try:
        document = architecture_doc.read_text(encoding="utf-8")
    except OSError as exc:
        return [*problems, f"cannot read architecture inventory {architecture_doc}: {exc}"]
    inventory = installed_artifact_inventory(registries)
    problems.extend(
        _reconcile_rows(
            label="artifact contract",
            header=_CONTRACT_HEADER,
            expected={
                contract.contract_id: _contract_values(contract) for contract in inventory.contracts
            },
            rows=_table_rows(document, _CONTRACT_HEADER),
        )
    )
    problems.extend(
        _reconcile_rows(
            label="resource profile",
            header=_PROFILE_HEADER,
            expected={
                profile.profile_id: _profile_values(profile)
                for profile in inventory.resource_profiles
            },
            rows=_table_rows(document, _PROFILE_HEADER),
        )
    )
    return problems


def main() -> int:
    """Run the repository gate."""
    problems = check()
    if problems:
        for problem in problems:
            print(f"artifact-contract inventory: {problem}", file=sys.stderr)
        return 1
    inventory = installed_artifact_inventory()
    print(
        f"artifact-contract inventory: {len(inventory.contracts)} contract(s), "
        f"{len(inventory.resource_profiles)} profile(s) OK"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
