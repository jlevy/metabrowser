from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

from devtools import check_artifact_contracts
from tests.test_artifact_inventory import _registries


def _architecture_doc(tmp_path: Path, *, contract_rows: str, profile_rows: str) -> Path:
    path = tmp_path / "architecture.md"
    path.write_text(
        "# Architecture\n\n"
        "| Contract ID | Artifact profile | Envelope | Producers | Consumers | Corpus | "
        "Browser parser |\n"
        "| --- | --- | --- | --- | --- | --- | --- |\n"
        f"{contract_rows}\n\n"
        "| Profile ID | Target kind | Result contract | Collections | Pagination | "
        "Last complete |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
        f"{profile_rows}\n",
        encoding="utf-8",
    )
    return path


_CONTRACT_ROW = (
    "| `org.example.widgets:Widget/v1` | `pure-yaml` | `widget` | `example-provider` | "
    "`example-browser,example-store` | `widget-conformance[widget]` | "
    "`widget-model:parseWidget` |"
)
_PROFILE_ROW = (
    "| `org.example.widgets:widget-detail/v1` | `provider_object` | — | "
    "`widget=org.example.widgets:Widget/v1[1..1]` | `widget=forbidden` | `widget` |"
)


def _browser_problems_for_module(
    module_bytes: bytes,
    *,
    add_typed_nested_values: bool = False,
) -> list[str]:
    registries = _registries()
    installed = registries.contracts["org.example.widgets:Widget/v1"]
    browser_parser = installed.spec.browser_parser
    assert browser_parser is not None
    spec = installed.spec
    if add_typed_nested_values:
        corpus = json.loads(spec.corpus.payload)
        corpus["base_records"]["widget"].update({"count": 1, "nested": {"enabled": True}})
        corpus_payload = json.dumps(corpus, sort_keys=True, separators=(",", ":")).encode()
        spec = replace(
            spec,
            corpus=replace(
                spec.corpus,
                payload=corpus_payload,
                payload_sha256=hashlib.sha256(corpus_payload).hexdigest(),
            ),
        )
    parser = replace(
        browser_parser,
        module_bytes=module_bytes,
        module_bytes_sha256=hashlib.sha256(module_bytes).hexdigest(),
    )
    installed = replace(installed, spec=replace(spec, browser_parser=parser))
    registries = replace(
        registries,
        contracts={installed.spec.contract_id: installed},
    )
    return check_artifact_contracts._browser_evidence_problems(registries)


def test_real_architecture_inventory_passes() -> None:
    assert check_artifact_contracts.check() == []


def test_architecture_inventory_matches_exact_installed_declarations(tmp_path: Path) -> None:
    architecture_doc = _architecture_doc(
        tmp_path,
        contract_rows=_CONTRACT_ROW,
        profile_rows=_PROFILE_ROW,
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
        profile_rows=_PROFILE_ROW,
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


def test_architecture_inventory_rejects_inexact_profile_semantics(tmp_path: Path) -> None:
    architecture_doc = _architecture_doc(
        tmp_path,
        contract_rows=_CONTRACT_ROW.replace("widget-model:parseWidget", "server-only"),
        profile_rows=_PROFILE_ROW.replace("widget=forbidden", "widget=optional"),
    )

    problems = check_artifact_contracts.check(
        registries=_registries(),
        architecture_doc=architecture_doc,
    )

    assert any("Widget/v1" in problem and "Browser parser" in problem for problem in problems)
    assert any("widget-detail/v1" in problem and "Pagination" in problem for problem in problems)


def test_browser_evidence_requires_the_declared_export_and_corpus_parity(tmp_path: Path) -> None:
    architecture_doc = _architecture_doc(
        tmp_path,
        contract_rows=_CONTRACT_ROW,
        profile_rows=_PROFILE_ROW,
    )
    registries = _registries()
    installed = registries.contracts["org.example.widgets:Widget/v1"]
    browser_parser = installed.spec.browser_parser
    assert browser_parser is not None
    defective_module = b"export function anotherParser() { return { ok: true }; }\n"
    defective_parser = replace(
        browser_parser,
        module_bytes=defective_module,
        module_bytes_sha256=hashlib.sha256(defective_module).hexdigest(),
    )
    defective_contract = replace(
        installed,
        spec=replace(installed.spec, browser_parser=defective_parser),
    )
    defective_registries = replace(
        registries,
        contracts={defective_contract.spec.contract_id: defective_contract},
    )

    problems = check_artifact_contracts.check(
        registries=defective_registries,
        architecture_doc=architecture_doc,
    )

    assert any("parseWidget" in problem and "export" in problem for problem in problems)


def test_browser_evidence_rejects_node_builtin_imports(tmp_path: Path) -> None:
    architecture_doc = _architecture_doc(
        tmp_path,
        contract_rows=_CONTRACT_ROW,
        profile_rows=_PROFILE_ROW,
    )
    registries = _registries()
    installed = registries.contracts["org.example.widgets:Widget/v1"]
    browser_parser = installed.spec.browser_parser
    assert browser_parser is not None
    node_only_module = (
        b'import fs from "node:fs";\n'
        b"export function parseWidget(value) {\n"
        b"  const ok = fs.constants.F_OK === 0 && value.name === 'accepted';\n"
        b"  return ok ? { ok: true, value } : { ok: false, error: 'invalid widget' };\n"
        b"}\n"
    )
    node_only_parser = replace(
        browser_parser,
        module_bytes=node_only_module,
        module_bytes_sha256=hashlib.sha256(node_only_module).hexdigest(),
    )
    node_only_contract = replace(
        installed,
        spec=replace(installed.spec, browser_parser=node_only_parser),
    )
    node_only_registries = replace(
        registries,
        contracts={node_only_contract.spec.contract_id: node_only_contract},
    )

    problems = check_artifact_contracts.check(
        registries=node_only_registries,
        architecture_doc=architecture_doc,
    )

    assert any("self-contained browser ESM" in problem for problem in problems)


def test_browser_evidence_rejects_node_only_globals(tmp_path: Path) -> None:
    architecture_doc = _architecture_doc(
        tmp_path,
        contract_rows=_CONTRACT_ROW,
        profile_rows=_PROFILE_ROW,
    )
    registries = _registries()
    installed = registries.contracts["org.example.widgets:Widget/v1"]
    browser_parser = installed.spec.browser_parser
    assert browser_parser is not None
    node_only_module = (
        b"export function parseWidget(value) {\n"
        b"  const ok = process.release.name === 'node' && value.name === 'accepted';\n"
        b"  return ok ? { ok: true, value } : { ok: false, error: 'invalid widget' };\n"
        b"}\n"
    )
    node_only_parser = replace(
        browser_parser,
        module_bytes=node_only_module,
        module_bytes_sha256=hashlib.sha256(node_only_module).hexdigest(),
    )
    node_only_contract = replace(
        installed,
        spec=replace(installed.spec, browser_parser=node_only_parser),
    )
    node_only_registries = replace(
        registries,
        contracts={node_only_contract.spec.contract_id: node_only_contract},
    )

    problems = check_artifact_contracts.check(
        registries=node_only_registries,
        architecture_doc=architecture_doc,
    )

    assert any("process is not defined" in problem for problem in problems)


def test_browser_evidence_blocks_constructor_chain_host_realm_escape(tmp_path: Path) -> None:
    architecture_doc = _architecture_doc(
        tmp_path,
        contract_rows=_CONTRACT_ROW,
        profile_rows=_PROFILE_ROW,
    )
    registries = _registries()
    installed = registries.contracts["org.example.widgets:Widget/v1"]
    browser_parser = installed.spec.browser_parser
    assert browser_parser is not None
    escaping_module = (
        b"export function parseWidget(value) {\n"
        b"  const capabilities = [value, TextEncoder, TextDecoder, atob, btoa, "
        b"Object, Array, Uint8Array, globalThis];\n"
        b"  const escaped = capabilities.map((capability) => {\n"
        b"    try {\n"
        b"      return capability.constructor.constructor('return process')()"
        b".release.name === 'node';\n"
        b"    } catch (_error) {\n"
        b"      return false;\n"
        b"    }\n"
        b"  }).some(Boolean);\n"
        b"  if (!escaped) { throw new Error('constructor-chain escape blocked'); }\n"
        b"  const ok = value.name === 'accepted';\n"
        b"  return ok ? { ok: true, value } : { ok: false, error: 'invalid widget' };\n"
        b"}\n"
    )
    escaping_parser = replace(
        browser_parser,
        module_bytes=escaping_module,
        module_bytes_sha256=hashlib.sha256(escaping_module).hexdigest(),
    )
    escaping_contract = replace(
        installed,
        spec=replace(installed.spec, browser_parser=escaping_parser),
    )
    escaping_registries = replace(
        registries,
        contracts={escaping_contract.spec.contract_id: escaping_contract},
    )

    problems = check_artifact_contracts.check(
        registries=escaping_registries,
        architecture_doc=architecture_doc,
    )

    assert any("constructor-chain escape blocked" in problem for problem in problems)


@pytest.mark.parametrize(
    "clone_expression",
    ["{ ...value }", "JSON.parse(JSON.stringify(value))"],
    ids=["shallow", "deep"],
)
def test_browser_evidence_accepts_complete_cross_realm_clones(clone_expression: str) -> None:
    module_bytes = (
        "export function parseWidget(value) {\n"
        "  const ok = typeof value.name === 'string' && "
        "value.name.length > 0 && value.name !== 'reserved';\n"
        f"  return ok ? {{ ok: true, value: {clone_expression} }} : "
        "{ ok: false, error: 'invalid widget' };\n"
        "}\n"
    ).encode()

    assert _browser_problems_for_module(module_bytes, add_typed_nested_values=True) == []


def test_browser_evidence_rejects_integer_to_boolean_type_change() -> None:
    module_bytes = (
        b"export function parseWidget(value) {\n"
        b"  const ok = typeof value.name === 'string' && "
        b"value.name.length > 0 && value.name !== 'reserved';\n"
        b"  return ok ? { ok: true, value: { ...value, count: value.count === 1 } } : "
        b"{ ok: false, error: 'invalid widget' };\n"
        b"}\n"
    )

    problems = _browser_problems_for_module(module_bytes, add_typed_nested_values=True)

    assert any(
        "successful parser result value must preserve its input record" in problem
        for problem in problems
    )


def test_browser_evidence_executes_invalid_cases(tmp_path: Path) -> None:
    architecture_doc = _architecture_doc(
        tmp_path,
        contract_rows=_CONTRACT_ROW,
        profile_rows=_PROFILE_ROW,
    )
    registries = _registries()
    installed = registries.contracts["org.example.widgets:Widget/v1"]
    browser_parser = installed.spec.browser_parser
    assert browser_parser is not None
    permissive_module = b"export function parseWidget(value) { return { ok: true, value }; }\n"
    permissive_parser = replace(
        browser_parser,
        module_bytes=permissive_module,
        module_bytes_sha256=hashlib.sha256(permissive_module).hexdigest(),
    )
    permissive_contract = replace(
        installed,
        spec=replace(installed.spec, browser_parser=permissive_parser),
    )
    permissive_registries = replace(
        registries,
        contracts={permissive_contract.spec.contract_id: permissive_contract},
    )

    problems = check_artifact_contracts.check(
        registries=permissive_registries,
        architecture_doc=architecture_doc,
    )

    assert any(
        "structurally-invalid-widget" in problem and "expected invalid" in problem
        for problem in problems
    )


def test_browser_evidence_requires_completion_proof(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    architecture_doc = _architecture_doc(
        tmp_path,
        contract_rows=_CONTRACT_ROW,
        profile_rows=_PROFILE_ROW,
    )

    monkeypatch.setattr(
        check_artifact_contracts.subprocess,
        "run",
        lambda *_args, **_kwargs: check_artifact_contracts.subprocess.CompletedProcess(
            args=(),
            returncode=0,
            stdout="",
            stderr="",
        ),
    )

    problems = check_artifact_contracts.check(
        registries=_registries(),
        architecture_doc=architecture_doc,
    )

    assert any("without its completion proof" in problem for problem in problems)


def test_browser_evidence_rejects_missing_and_extra_result_fields(tmp_path: Path) -> None:
    architecture_doc = _architecture_doc(
        tmp_path,
        contract_rows=_CONTRACT_ROW,
        profile_rows=_PROFILE_ROW,
    )
    registries = _registries()
    installed = registries.contracts["org.example.widgets:Widget/v1"]
    browser_parser = installed.spec.browser_parser
    assert browser_parser is not None
    malformed_module = (
        b"export function parseWidget(value) {\n"
        b"  if (value.name === 'accepted') return { ok: true };\n"
        b"  if (value.name === '') return { ok: false };\n"
        b"  return { ok: false, error: 'reserved', extra: true };\n"
        b"}\n"
    )
    malformed_parser = replace(
        browser_parser,
        module_bytes=malformed_module,
        module_bytes_sha256=hashlib.sha256(malformed_module).hexdigest(),
    )
    malformed_contract = replace(
        installed,
        spec=replace(installed.spec, browser_parser=malformed_parser),
    )
    malformed_registries = replace(
        registries,
        contracts={malformed_contract.spec.contract_id: malformed_contract},
    )

    problems = check_artifact_contracts.check(
        registries=malformed_registries,
        architecture_doc=architecture_doc,
    )

    assert any(
        "valid-widget" in problem and "exactly ok and value" in problem for problem in problems
    )
    assert any(
        "structurally-invalid-widget" in problem and "exactly ok and error" in problem
        for problem in problems
    )
    assert any(
        "semantically-invalid-widget" in problem and "exactly ok and error" in problem
        for problem in problems
    )


def test_browser_evidence_rejects_malformed_results_and_parser_throws(tmp_path: Path) -> None:
    architecture_doc = _architecture_doc(
        tmp_path,
        contract_rows=_CONTRACT_ROW,
        profile_rows=_PROFILE_ROW,
    )
    registries = _registries()
    installed = registries.contracts["org.example.widgets:Widget/v1"]
    browser_parser = installed.spec.browser_parser
    assert browser_parser is not None
    malformed_module = (
        b"export function parseWidget(value) {\n"
        b"  if (value.name === 'accepted') return null;\n"
        b"  if (value.name === '') throw new Error('synthetic parser defect');\n"
        b"  return { ok: false, error: '' };\n"
        b"}\n"
    )
    malformed_parser = replace(
        browser_parser,
        module_bytes=malformed_module,
        module_bytes_sha256=hashlib.sha256(malformed_module).hexdigest(),
    )
    malformed_contract = replace(
        installed,
        spec=replace(installed.spec, browser_parser=malformed_parser),
    )
    malformed_registries = replace(
        registries,
        contracts={malformed_contract.spec.contract_id: malformed_contract},
    )

    problems = check_artifact_contracts.check(
        registries=malformed_registries,
        architecture_doc=architecture_doc,
    )

    assert any(
        "valid-widget" in problem and "result must be an object" in problem for problem in problems
    )
    assert any(
        "structurally-invalid-widget" in problem and "synthetic parser defect" in problem
        for problem in problems
    )
    assert any(
        "semantically-invalid-widget" in problem and "nonempty string" in problem
        for problem in problems
    )


def test_browser_evidence_rejects_successful_record_loss(tmp_path: Path) -> None:
    architecture_doc = _architecture_doc(
        tmp_path,
        contract_rows=_CONTRACT_ROW,
        profile_rows=_PROFILE_ROW,
    )
    registries = _registries()
    installed = registries.contracts["org.example.widgets:Widget/v1"]
    browser_parser = installed.spec.browser_parser
    assert browser_parser is not None
    lossy_module = (
        b"export function parseWidget(value) {\n"
        b"  if (value.name === 'accepted') return { ok: true, value: {} };\n"
        b"  return { ok: false, error: 'invalid widget' };\n"
        b"}\n"
    )
    lossy_parser = replace(
        browser_parser,
        module_bytes=lossy_module,
        module_bytes_sha256=hashlib.sha256(lossy_module).hexdigest(),
    )
    lossy_contract = replace(
        installed,
        spec=replace(installed.spec, browser_parser=lossy_parser),
    )
    lossy_registries = replace(
        registries,
        contracts={lossy_contract.spec.contract_id: lossy_contract},
    )

    problems = check_artifact_contracts.check(
        registries=lossy_registries,
        architecture_doc=architecture_doc,
    )

    assert any(
        "valid-widget" in problem and "must preserve its input record" in problem
        for problem in problems
    )


def test_browser_evidence_rejects_in_place_input_mutation(tmp_path: Path) -> None:
    architecture_doc = _architecture_doc(
        tmp_path,
        contract_rows=_CONTRACT_ROW,
        profile_rows=_PROFILE_ROW,
    )
    registries = _registries()
    installed = registries.contracts["org.example.widgets:Widget/v1"]
    browser_parser = installed.spec.browser_parser
    assert browser_parser is not None
    mutating_module = (
        b"export function parseWidget(value) {\n"
        b"  if (value.name === 'accepted') {\n"
        b"    value.addedByParser = true;\n"
        b"    return { ok: true, value };\n"
        b"  }\n"
        b"  return { ok: false, error: 'invalid widget' };\n"
        b"}\n"
    )
    mutating_parser = replace(
        browser_parser,
        module_bytes=mutating_module,
        module_bytes_sha256=hashlib.sha256(mutating_module).hexdigest(),
    )
    mutating_contract = replace(
        installed,
        spec=replace(installed.spec, browser_parser=mutating_parser),
    )
    mutating_registries = replace(
        registries,
        contracts={mutating_contract.spec.contract_id: mutating_contract},
    )

    problems = check_artifact_contracts.check(
        registries=mutating_registries,
        architecture_doc=architecture_doc,
    )

    assert any("valid-widget" in problem and "mutated its input" in problem for problem in problems)


def test_python_and_browser_agree_that_document_cases_omit_record(tmp_path: Path) -> None:
    corpus = {
        "base_document": {"name": "accepted"},
        "cases": [
            {
                "name": "valid-document-case",
                "changes": [],
                "expect": "valid",
            },
            {
                "name": "explicit-null-is-not-document-scope",
                "record": None,
                "changes": [],
                "expect": "valid",
            },
        ],
    }
    payload = json.dumps(corpus, sort_keys=True, separators=(",", ":")).encode()
    installed = _registries().contracts["org.example.widgets:Widget/v1"]
    contract = replace(
        installed.spec,
        corpus=replace(
            installed.spec.corpus,
            payload=payload,
            payload_sha256=hashlib.sha256(payload).hexdigest(),
        ),
        corpus_record_selectors=(),
    )
    registries = _registries(contract)
    architecture_doc = _architecture_doc(
        tmp_path,
        contract_rows=_CONTRACT_ROW.replace("widget-conformance[widget]", "widget-conformance[*]"),
        profile_rows=_PROFILE_ROW,
    )

    problems = check_artifact_contracts.check(
        registries=registries,
        architecture_doc=architecture_doc,
    )

    assert any(
        "explicit-null-is-not-document-scope" in problem
        and "record must be a nonempty string" in problem
        for problem in problems
    )
    assert not any(problem.startswith("browser evidence") for problem in problems)
