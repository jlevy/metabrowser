"""The architecture table of installed contracts, compared with the declarations.

``make lint-check`` runs ``devtools/check_artifact_contracts.py`` on the repository's own
table and the cache's contracts. These cases give it a table for the synthetic contract in
``tests/artifact_contract_fixture.py`` and state every problem it reports.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from devtools import check_artifact_contracts
from metabrowser.plugin_loader.artifact_contracts import (
    ArtifactContractSpec,
    build_contract_registry,
)
from tests.artifact_contract_fixture import VALID_CASE, contract, corpus

_HEADER = (
    "| Contract ID | Artifact profile | Envelope | Producers | Consumers | Corpus |\n"
    "| --- | --- | --- | --- | --- | --- |\n"
)
_ROW = (
    "| `example.test:Item/v1` | `pure-yaml` | `item` | `example-provider` | "
    "`example-browser,example-store` | `item-conformance[item]` |"
)
_ORPHAN = _ROW.replace("Item/v1", "Orphan/v1")
_ITEM = "artifact contract 'example.test:Item/v1'"
_NO_ROW = f"installed {_ITEM} has no architecture row"
_TABLES: dict[str, tuple[str, list[str]]] = {
    "the-installed-declaration": (_HEADER + _ROW, []),
    "another-table-after-the-contracts": (
        f"{_HEADER}{_ROW}\n\nA second table, about something else.\n\n| Kind | View |\n"
        "| --- | --- |\n| `markdown` | `rendered` |",
        [],
    ),
    "no-table": (
        "",
        [
            "architecture document has no Contract ID | Artifact profile | Envelope | "
            "Producers | Consumers | Corpus table"
        ],
    ),
    "a-row-with-too-few-cells": (
        _HEADER + "| `example.test:Item/v1` | `pure-yaml` |",
        ["artifact contract architecture table has a malformed row", _NO_ROW],
    ),
    "another-contract-twice": (
        f"{_HEADER}{_ORPHAN}\n{_ORPHAN}",
        [
            "artifact contract 'example.test:Orphan/v1' has a duplicate architecture row",
            _NO_ROW,
            "architecture artifact contract 'example.test:Orphan/v1' is not installed",
        ],
    ),
    "every-record-where-one-selector-is-declared": (
        _HEADER + _ROW.replace("[item]", "[*]"),
        [f"{_ITEM} Corpus is 'item-conformance[*]'; expected 'item-conformance[item]'"],
    ),
}


def _check(tmp_path: Path, table: str, spec: ArtifactContractSpec) -> list[str]:
    document = tmp_path / "architecture.md"
    document.write_text(f"# Architecture\n\n{table}\n", encoding="utf-8")
    return check_artifact_contracts.check(
        contracts=build_contract_registry((spec,)), architecture_doc=document
    )


@pytest.mark.parametrize(("table", "problems"), _TABLES.values(), ids=_TABLES)
def test_the_architecture_table_has_to_match_the_installed_declarations(
    tmp_path: Path, table: str, problems: list[str]
) -> None:
    assert _check(tmp_path, table, contract()) == problems


def test_the_gate_prints_each_problem_and_exits_1(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """``make lint-check`` stops on the status, so a gate that reported and exited 0 passes."""

    monkeypatch.setattr(check_artifact_contracts, "check", lambda: ["one row", "another row"])

    assert check_artifact_contracts.main() == 1
    assert capsys.readouterr().err.splitlines() == [
        "artifact-contract inventory: one row",
        "artifact-contract inventory: another row",
    ]


def test_a_corpus_that_proves_too_little_fails_the_gate_under_a_correct_table(
    tmp_path: Path,
) -> None:
    only_valid_cases = contract(corpus=corpus(VALID_CASE))

    assert _check(tmp_path, _HEADER + _ROW, only_valid_cases) == [
        f"{_ITEM} selected corpus cases have no invalid evidence"
    ]
