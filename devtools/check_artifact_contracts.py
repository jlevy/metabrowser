"""Check the installed artifact contracts against their durable architecture inventory."""

from __future__ import annotations

import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from metabrowser.cache.contracts import cache_contract_registry
from metabrowser.plugin_loader.artifact_contracts import ContractRegistry, ContractRegistryError
from metabrowser.plugin_loader.artifact_inventory import (
    ContractInventoryEntry,
    check_installed_evidence,
    installed_artifact_inventory,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
ARCHITECTURE_DOC = (
    REPO_ROOT / "docs/project/architecture/arch-repository-sources-and-provider-mirrors.md"
)

_CONTRACT_HEADER = (
    "Contract ID",
    "Artifact profile",
    "Envelope",
    "Producers",
    "Consumers",
    "Corpus",
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
    )


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
    contracts: ContractRegistry | None = None,
    architecture_doc: Path = ARCHITECTURE_DOC,
) -> list[str]:
    """Return corpus-evidence and architecture-registration problems.

    The installed contracts are the repository cache's enforced records, the only
    artifact contracts Metabrowser declares.
    """
    try:
        if contracts is None:
            contracts = cache_contract_registry()
    except ContractRegistryError as exc:
        return [f"installed contract registry failed: {exc}"]
    problems = list(check_installed_evidence(contracts))
    try:
        document = architecture_doc.read_text(encoding="utf-8")
    except OSError as exc:
        return [*problems, f"cannot read architecture inventory {architecture_doc}: {exc}"]
    problems.extend(
        _reconcile_rows(
            label="artifact contract",
            header=_CONTRACT_HEADER,
            expected={
                contract.contract_id: _contract_values(contract)
                for contract in installed_artifact_inventory(contracts)
            },
            rows=_table_rows(document, _CONTRACT_HEADER),
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
    print(f"artifact-contract inventory: {len(cache_contract_registry())} contract(s) OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
