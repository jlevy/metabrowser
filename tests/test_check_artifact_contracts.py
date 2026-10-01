from __future__ import annotations

from pathlib import Path

from devtools import check_artifact_contracts
from tests.test_artifact_inventory import _registries


def _architecture_doc(tmp_path: Path, *, contract_rows: str) -> Path:
    path = tmp_path / "architecture.md"
    path.write_text(
        "# Architecture\n\n"
        "| Contract ID | Artifact profile | Envelope | Producers | Consumers | Corpus |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
        f"{contract_rows}\n",
        encoding="utf-8",
    )
    return path


_CONTRACT_ROW = (
    "| `org.example.widgets:Widget/v1` | `pure-yaml` | `widget` | `example-provider` | "
    "`example-browser,example-store` | `widget-conformance[widget]` |"
)


def test_real_architecture_inventory_passes() -> None:
    assert check_artifact_contracts.check() == []


def test_architecture_inventory_matches_exact_installed_declarations(tmp_path: Path) -> None:
    architecture_doc = _architecture_doc(
        tmp_path,
        contract_rows=_CONTRACT_ROW,
    )

    assert (
        check_artifact_contracts.check(
            registries=_registries(),
            architecture_doc=architecture_doc,
        )
        == []
    )


def test_architecture_inventory_rejects_missing_orphan_and_duplicate_rows(tmp_path: Path) -> None:
    orphan_row = _CONTRACT_ROW.replace(
        "org.example.widgets:Widget/v1",
        "org.example.widgets:Orphan/v1",
        1,
    )
    architecture_doc = _architecture_doc(
        tmp_path,
        contract_rows=f"{orphan_row}\n{orphan_row}",
    )

    problems = check_artifact_contracts.check(
        registries=_registries(),
        architecture_doc=architecture_doc,
    )

    assert any(
        _CONTRACT_ROW.split("`")[1] in problem and "no architecture row" in problem
        for problem in problems
    )
    assert any("Orphan/v1" in problem and "not installed" in problem for problem in problems)
    assert any("Orphan/v1" in problem and "duplicate" in problem for problem in problems)


def test_architecture_inventory_rejects_inexact_contract_semantics(tmp_path: Path) -> None:
    architecture_doc = _architecture_doc(
        tmp_path,
        contract_rows=_CONTRACT_ROW.replace("widget-conformance[widget]", "widget-conformance[*]"),
    )

    problems = check_artifact_contracts.check(
        registries=_registries(),
        architecture_doc=architecture_doc,
    )

    assert any("Widget/v1" in problem and "Corpus" in problem for problem in problems)
