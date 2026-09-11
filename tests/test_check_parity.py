"""The parity checker is not trusted on its word.

A check that cannot fail is not a check, so each rule gets a table that breaks
it and must be reported with the surface named.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from devtools import check_parity

_HEADER = "| Surface | Status | CLI | Golden or reason |\n| --- | --- | --- | --- |\n"
_FUNCTIONAL_HEADER = (
    "| Aspect | Tier | Owner | CLI command | Golden or reason |\n| --- | --- | --- | --- | --- |\n"
)


def _write_map(tmp_path: Path, rows: str) -> Path:
    doc = tmp_path / "map.md"
    doc.write_text(
        f"# Map\n\n{_HEADER}{rows}\n\n"
        f"## Functional UI parity\n\n{_FUNCTIONAL_HEADER}"
        "| `test.paint` | paint-exempt | `static/styles.css` | — | "
        "fixture reason; `tests/test_check_parity.py` |\n\n"
        "## Adding something\n",
        encoding="utf-8",
    )
    return doc


@pytest.fixture
def no_registered_kinds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(check_parity, "registered_kinds", lambda: set())


@pytest.fixture
def only_tree(monkeypatch: pytest.MonkeyPatch, no_registered_kinds: None) -> None:
    monkeypatch.setattr(check_parity, "registered_surfaces", lambda: {"/api/tree"})


def test_a_registered_route_with_no_row_is_reported(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    no_registered_kinds: None,
) -> None:
    monkeypatch.setattr(check_parity, "registered_surfaces", lambda: {"/api/tree", "/api/rollup"})
    monkeypatch.setattr(
        check_parity, "MAP_DOC", _write_map(tmp_path, "| `/api/tree` | exempt | — | streaming |")
    )

    problems = check_parity.check()

    assert any("/api/rollup" in problem and "no parity row" in problem for problem in problems)


def test_a_row_for_an_unregistered_route_is_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, only_tree: None
) -> None:
    monkeypatch.setattr(
        check_parity,
        "MAP_DOC",
        _write_map(
            tmp_path,
            "| `/api/tree` | exempt | — | streaming |\n| `/api/gone` | exempt | — | streaming |",
        ),
    )

    problems = check_parity.check()

    assert any("/api/gone" in problem and "not registered" in problem for problem in problems)


def test_a_covered_row_naming_a_missing_golden_is_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, only_tree: None
) -> None:
    monkeypatch.setattr(
        check_parity,
        "MAP_DOC",
        _write_map(tmp_path, "| `/api/tree` | covered | `--api` | `no-such.tryscript.md` |"),
    )

    problems = check_parity.check()

    assert any("/api/tree" in problem and "does not exist" in problem for problem in problems)


def test_a_covered_row_whose_golden_never_exercises_it_is_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, only_tree: None
) -> None:
    """The library-versus-wire trap: a transcript that never names the route."""

    golden_dir = tmp_path / "golden"
    golden_dir.mkdir()
    (golden_dir / "unrelated.tryscript.md").write_text("$ metab . --walk\n", encoding="utf-8")
    monkeypatch.setattr(check_parity, "GOLDEN_DIR", golden_dir)
    monkeypatch.setattr(
        check_parity,
        "MAP_DOC",
        _write_map(tmp_path, "| `/api/tree` | covered | `--api` | `unrelated.tryscript.md` |"),
    )

    problems = check_parity.check()

    assert any("/api/tree" in problem and "never exercises it" in problem for problem in problems)


def test_a_gap_row_is_rejected_outright(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, only_tree: None
) -> None:
    """Gap rows were an allowance while the debt was paid down. It is gone."""

    monkeypatch.setattr(
        check_parity, "MAP_DOC", _write_map(tmp_path, "| `/api/tree` | gap | `--api` | `mb-1234` |")
    )

    problems = check_parity.check()

    assert any("/api/tree" in problem and "is not one of" in problem for problem in problems)


def test_an_exempt_row_without_a_reason_is_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, only_tree: None
) -> None:
    monkeypatch.setattr(
        check_parity, "MAP_DOC", _write_map(tmp_path, "| `/api/tree` | exempt | — | — |")
    )

    problems = check_parity.check()

    assert any("/api/tree" in problem and "give a reason" in problem for problem in problems)


def test_an_unknown_status_is_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, only_tree: None
) -> None:
    monkeypatch.setattr(
        check_parity,
        "MAP_DOC",
        _write_map(tmp_path, "| `/api/tree` | soon | `--api` | `mb-1234` |"),
    )

    problems = check_parity.check()

    assert any("/api/tree" in problem and "is not one of" in problem for problem in problems)


def test_the_real_table_passes() -> None:
    assert check_parity.check() == []


def test_a_functional_row_whose_cli_session_is_missing_is_reported(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    only_tree: None,
) -> None:
    golden_dir = tmp_path / "golden"
    _write_golden(
        golden_dir,
        "session.tryscript.md",
        "```console\n$ node tests/dom/a-different-session.js\nOK\n```\n",
    )
    doc = _write_map(tmp_path, "| `/api/tree` | exempt | — | streaming |")
    text = doc.read_text(encoding="utf-8").replace(
        "| `test.paint` | paint-exempt | `static/styles.css` | — | "
        "fixture reason; `tests/test_check_parity.py` |",
        "| `navigation.filter` | interaction | `static/tree-filter-model.js` | "
        "`node tests/dom/filter-session.js` | `session.tryscript.md` |",
    )
    doc.write_text(text, encoding="utf-8")
    monkeypatch.setattr(check_parity, "GOLDEN_DIR", golden_dir)
    monkeypatch.setattr(check_parity, "MAP_DOC", doc)

    problems = check_parity.check()

    assert any("navigation.filter" in problem and "never runs" in problem for problem in problems)


def test_a_functional_command_named_only_in_prose_is_not_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    only_tree: None,
) -> None:
    golden_dir = tmp_path / "golden"
    _write_golden(
        golden_dir,
        "session.tryscript.md",
        "A manual example follows:\n$ node tests/dom/filter-session.js\n\n"
        "```console\n$ node tests/dom/a-different-session.js\nOK\n```\n",
    )
    doc = _write_map(tmp_path, "| `/api/tree` | exempt | — | streaming |")
    text = doc.read_text(encoding="utf-8").replace(
        "| `test.paint` | paint-exempt | `static/styles.css` | — | "
        "fixture reason; `tests/test_check_parity.py` |",
        "| `navigation.filter` | interaction | `static/tree-filter-model.js` | "
        "`node tests/dom/filter-session.js` | `session.tryscript.md` |",
    )
    doc.write_text(text, encoding="utf-8")
    monkeypatch.setattr(check_parity, "GOLDEN_DIR", golden_dir)
    monkeypatch.setattr(check_parity, "MAP_DOC", doc)

    problems = check_parity.check()

    assert any("navigation.filter" in problem and "never runs" in problem for problem in problems)


def test_a_functional_row_must_name_an_existing_source_owner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    only_tree: None,
) -> None:
    doc = _write_map(tmp_path, "| `/api/tree` | exempt | — | streaming |")
    text = doc.read_text(encoding="utf-8").replace(
        "`static/styles.css`",
        "`static/not-a-real-owner.js`",
    )
    doc.write_text(text, encoding="utf-8")
    monkeypatch.setattr(check_parity, "MAP_DOC", doc)

    problems = check_parity.check()

    assert any("test.paint" in problem and "does not exist" in problem for problem in problems)


def test_a_functional_row_must_name_existing_golden_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    only_tree: None,
) -> None:
    doc = _write_map(tmp_path, "| `/api/tree` | exempt | — | streaming |")
    text = doc.read_text(encoding="utf-8").replace(
        "| `test.paint` | paint-exempt | `static/styles.css` | — | "
        "fixture reason; `tests/test_check_parity.py` |",
        "| `navigation.filter` | data | `/api/tree` | `metab root --api /api/tree` | "
        "`missing.tryscript.md` |",
    )
    doc.write_text(text, encoding="utf-8")
    monkeypatch.setattr(check_parity, "MAP_DOC", doc)

    problems = check_parity.check()

    assert any(
        "navigation.filter" in problem and "does not exist" in problem for problem in problems
    )


def test_a_paint_exemption_without_a_specific_reason_is_reported(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    only_tree: None,
) -> None:
    doc = _write_map(tmp_path, "| `/api/tree` | exempt | — | streaming |")
    text = doc.read_text(encoding="utf-8").replace(
        "fixture reason; `tests/test_check_parity.py`", "—"
    )
    doc.write_text(text, encoding="utf-8")
    monkeypatch.setattr(check_parity, "MAP_DOC", doc)

    problems = check_parity.check()

    assert any("test.paint" in problem and "specific reason" in problem for problem in problems)


def test_a_paint_exemption_must_name_existing_focused_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    only_tree: None,
) -> None:
    doc = _write_map(tmp_path, "| `/api/tree` | exempt | — | streaming |")
    text = doc.read_text(encoding="utf-8").replace(
        "tests/test_check_parity.py", "tests/not-a-real-test.py"
    )
    doc.write_text(text, encoding="utf-8")
    monkeypatch.setattr(check_parity, "MAP_DOC", doc)

    problems = check_parity.check()

    assert any("test.paint" in problem and "paint evidence" in problem for problem in problems)


def test_a_data_aspect_must_run_through_metab(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    only_tree: None,
) -> None:
    golden_dir = tmp_path / "golden"
    _write_golden(
        golden_dir,
        "session.tryscript.md",
        "```console\n$ node tests/dom/filter-session.js\nOK\n```\n",
    )
    doc = _write_map(tmp_path, "| `/api/tree` | exempt | — | streaming |")
    text = doc.read_text(encoding="utf-8").replace(
        "| `test.paint` | paint-exempt | `static/styles.css` | — | "
        "fixture reason; `tests/test_check_parity.py` |",
        "| `navigation.filter` | data | `/api/tree` | "
        "`node tests/dom/filter-session.js` | `session.tryscript.md` |",
    )
    doc.write_text(text, encoding="utf-8")
    monkeypatch.setattr(check_parity, "GOLDEN_DIR", golden_dir)
    monkeypatch.setattr(check_parity, "MAP_DOC", doc)

    problems = check_parity.check()

    assert any(
        "navigation.filter" in problem and "must run through metab" in problem
        for problem in problems
    )


def test_a_data_command_must_name_its_route_owner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    only_tree: None,
) -> None:
    golden_dir = tmp_path / "golden"
    command = "metab root --api /api/recent"
    _write_golden(golden_dir, "session.tryscript.md", f"```console\n$ {command}\n```\n")
    doc = _write_map(tmp_path, "| `/api/tree` | exempt | — | streaming |")
    text = doc.read_text(encoding="utf-8").replace(
        "| `test.paint` | paint-exempt | `static/styles.css` | — | "
        "fixture reason; `tests/test_check_parity.py` |",
        f"| `navigation.filter` | data | `/api/tree` | `{command}` | `session.tryscript.md` |",
    )
    doc.write_text(text, encoding="utf-8")
    monkeypatch.setattr(check_parity, "GOLDEN_DIR", golden_dir)
    monkeypatch.setattr(check_parity, "MAP_DOC", doc)

    problems = check_parity.check()

    assert any("navigation.filter" in problem and "route owner" in problem for problem in problems)


def test_an_interaction_session_must_load_its_declared_owner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    only_tree: None,
) -> None:
    golden_dir = tmp_path / "golden"
    command = "node tests/dom/recent-filter-session.js"
    _write_golden(golden_dir, "session.tryscript.md", f"```console\n$ {command}\n```\n")
    doc = _write_map(tmp_path, "| `/api/tree` | exempt | — | streaming |")
    text = doc.read_text(encoding="utf-8").replace(
        "| `test.paint` | paint-exempt | `static/styles.css` | — | "
        "fixture reason; `tests/test_check_parity.py` |",
        f"| `navigation.filter` | interaction | `static/perf.js` | `{command}` | "
        "`session.tryscript.md` |",
    )
    doc.write_text(text, encoding="utf-8")
    monkeypatch.setattr(check_parity, "GOLDEN_DIR", golden_dir)
    monkeypatch.setattr(check_parity, "MAP_DOC", doc)

    problems = check_parity.check()

    assert any(
        "navigation.filter" in problem and "did not execute owner" in problem
        for problem in problems
    )


def test_an_owner_filename_in_session_source_is_not_execution_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    only_tree: None,
) -> None:
    source_root = tmp_path / "src/metabrowser"
    owner = source_root / "static/tree-filter-model.js"
    owner.parent.mkdir(parents=True)
    owner.write_text("window.Model = {};\n", encoding="utf-8")
    session = tmp_path / "tests/dom/filter-session.js"
    session.parent.mkdir(parents=True)
    session.write_text(
        "// static/tree-filter-model.js is only a comment, not executed.\n"
        "console.log(JSON.stringify({functionalParity: {protocol: 1, executedOwners: "
        "['static/tree-filter-model.js']}}));\n",
        encoding="utf-8",
    )
    golden_dir = tmp_path / "tests/golden"
    command = "node tests/dom/filter-session.js"
    _write_golden(golden_dir, "session.tryscript.md", f"```console\n$ {command}\n? 0\n```\n")
    doc = _write_map(tmp_path, "| `/api/tree` | exempt | — | streaming |")
    text = doc.read_text(encoding="utf-8").replace(
        "| `test.paint` | paint-exempt | `static/styles.css` | — | "
        "fixture reason; `tests/test_check_parity.py` |",
        f"| `navigation.filter` | interaction | `static/tree-filter-model.js` | "
        f"`{command}` | `session.tryscript.md` |",
    )
    doc.write_text(text, encoding="utf-8")
    monkeypatch.setattr(check_parity, "GOLDEN_DIR", golden_dir)
    monkeypatch.setattr(check_parity, "MAP_DOC", doc)
    monkeypatch.setattr(check_parity, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(check_parity, "SOURCE_ROOT", source_root)

    problems = check_parity.check()

    assert any(
        "navigation.filter" in problem and "did not execute owner" in problem
        for problem in problems
    )


def test_checker_controlled_coverage_proves_an_executed_owner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    only_tree: None,
) -> None:
    source_root = tmp_path / "src/metabrowser"
    owner = source_root / "static/tree-filter-model.js"
    owner.parent.mkdir(parents=True)
    owner.write_text("window.Model = {};\n", encoding="utf-8")
    session = tmp_path / "tests/dom/filter-session.js"
    session.parent.mkdir(parents=True)
    session.write_text(
        "const fs = require('node:fs');\n"
        "const path = require('node:path');\n"
        "const vm = require('node:vm');\n"
        "const root = path.resolve(__dirname, '../..');\n"
        "const filename = path.join(root, 'src/metabrowser/static/tree-filter-model.js');\n"
        "const sandbox = {window: {}}; sandbox.window = sandbox;\n"
        "vm.createContext(sandbox);\n"
        "vm.runInContext(fs.readFileSync(filename, 'utf8'), sandbox, {filename});\n"
        "console.log('{}');\n",
        encoding="utf-8",
    )
    golden_dir = tmp_path / "tests/golden"
    command = "node tests/dom/filter-session.js"
    # Tryscript omits a status marker for the normal zero-exit case.
    _write_golden(golden_dir, "session.tryscript.md", f"```console\n$ {command}\n{{}}\n```\n")
    doc = _write_map(tmp_path, "| `/api/tree` | exempt | — | streaming |")
    text = doc.read_text(encoding="utf-8").replace(
        "| `test.paint` | paint-exempt | `static/styles.css` | — | "
        "fixture reason; `tests/test_check_parity.py` |",
        f"| `navigation.filter` | interaction | `static/tree-filter-model.js` | "
        f"`{command}` | `session.tryscript.md` |",
    )
    doc.write_text(text, encoding="utf-8")
    monkeypatch.setattr(check_parity, "GOLDEN_DIR", golden_dir)
    monkeypatch.setattr(check_parity, "MAP_DOC", doc)
    monkeypatch.setattr(check_parity, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(check_parity, "SOURCE_ROOT", source_root)

    assert check_parity.check() == []


def test_coverage_filename_cannot_credit_different_vm_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    only_tree: None,
) -> None:
    source_root = tmp_path / "src/metabrowser"
    owner = source_root / "static/tree-filter-model.js"
    owner.parent.mkdir(parents=True)
    owner.write_text("window.Model = {production: true};\n", encoding="utf-8")
    session = tmp_path / "tests/dom/filter-session.js"
    session.parent.mkdir(parents=True)
    session.write_text(
        "const path = require('node:path');\n"
        "const vm = require('node:vm');\n"
        "const root = path.resolve(__dirname, '../..');\n"
        "const filename = path.join(root, 'src/metabrowser/static/tree-filter-model.js');\n"
        "vm.runInNewContext('window.Forged = true;', {window: {}}, {filename});\n",
        encoding="utf-8",
    )
    golden_dir = tmp_path / "tests/golden"
    command = "node tests/dom/filter-session.js"
    _write_golden(golden_dir, "session.tryscript.md", f"```console\n$ {command}\n```\n")
    doc = _write_map(tmp_path, "| `/api/tree` | exempt | — | streaming |")
    doc.write_text(
        doc.read_text(encoding="utf-8").replace(
            "| `test.paint` | paint-exempt | `static/styles.css` | — | "
            "fixture reason; `tests/test_check_parity.py` |",
            "| `navigation.filter` | interaction | `static/tree-filter-model.js` | "
            f"`{command}` | `session.tryscript.md` |",
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(check_parity, "GOLDEN_DIR", golden_dir)
    monkeypatch.setattr(check_parity, "MAP_DOC", doc)
    monkeypatch.setattr(check_parity, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(check_parity, "SOURCE_ROOT", source_root)

    problems = check_parity.check()

    assert any(
        "navigation.filter" in problem and "did not execute owner" in problem
        for problem in problems
    )


def _write_golden(golden_dir: Path, name: str, body: str) -> None:
    golden_dir.mkdir(exist_ok=True)
    (golden_dir / name).write_text(body, encoding="utf-8")


def test_a_route_named_only_in_prose_is_not_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, only_tree: None
) -> None:
    """A comment mentioning a route must not count as covering it."""

    golden_dir = tmp_path / "golden"
    _write_golden(
        golden_dir,
        "prose.tryscript.md",
        "This is the transcript for `/api/tree`, which drives the nav panel.\n"
        "```console\n$ metab root --api /api/rollup\n```\n",
    )
    monkeypatch.setattr(check_parity, "GOLDEN_DIR", golden_dir)
    monkeypatch.setattr(
        check_parity,
        "MAP_DOC",
        _write_map(tmp_path, "| `/api/tree` | covered | `--api` | `prose.tryscript.md` |"),
    )

    problems = check_parity.check()

    assert any("/api/tree" in problem and "never exercises it" in problem for problem in problems)


def test_a_route_named_in_a_command_is_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, only_tree: None
) -> None:
    golden_dir = tmp_path / "golden"
    _write_golden(
        golden_dir,
        "direct.tryscript.md",
        "```console\n$ metab root --api '/api/tree?depth=1'\n```\n",
    )
    monkeypatch.setattr(check_parity, "GOLDEN_DIR", golden_dir)
    monkeypatch.setattr(
        check_parity,
        "MAP_DOC",
        _write_map(tmp_path, "| `/api/tree` | covered | `--api` | `direct.tryscript.md` |"),
    )

    assert check_parity.check() == []


def test_a_mode_that_resolves_a_route_internally_is_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    no_registered_kinds: None,
) -> None:
    """`--show` issues /api/file without naming it, so the mode is the evidence."""

    monkeypatch.setattr(check_parity, "registered_surfaces", lambda: {"/api/file"})
    golden_dir = tmp_path / "golden"
    _write_golden(
        golden_dir,
        "indirect.tryscript.md",
        "```console\n$ metab root --show README.md\n? 0\n```\n",
    )
    monkeypatch.setattr(check_parity, "GOLDEN_DIR", golden_dir)
    monkeypatch.setattr(
        check_parity,
        "MAP_DOC",
        _write_map(tmp_path, "| `/api/file` | covered | `--show PATH` | `indirect.tryscript.md` |"),
    )

    assert check_parity.check() == []


def test_a_mode_is_not_evidence_for_a_route_it_cannot_issue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, only_tree: None
) -> None:
    """`--show` never issues /api/tree, so claiming it is false evidence."""

    golden_dir = tmp_path / "golden"
    _write_golden(
        golden_dir, "indirect.tryscript.md", "```console\n$ metab root --show README.md\n```\n"
    )
    monkeypatch.setattr(check_parity, "GOLDEN_DIR", golden_dir)
    monkeypatch.setattr(
        check_parity,
        "MAP_DOC",
        _write_map(tmp_path, "| `/api/tree` | covered | `--show PATH` | `indirect.tryscript.md` |"),
    )

    problems = check_parity.check()

    assert any("/api/tree" in problem and "never exercises it" in problem for problem in problems)


def test_only_the_api_option_value_is_route_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, only_tree: None
) -> None:
    golden_dir = tmp_path / "golden"
    _write_golden(
        golden_dir,
        "wrong-value.tryscript.md",
        "```console\n$ metab /api/tree --api /api/rollup\n{}\n```\n",
    )
    monkeypatch.setattr(check_parity, "GOLDEN_DIR", golden_dir)
    monkeypatch.setattr(
        check_parity,
        "MAP_DOC",
        _write_map(
            tmp_path,
            "| `/api/tree` | covered | `--api` | `wrong-value.tryscript.md` |",
        ),
    )

    problems = check_parity.check()

    assert any("/api/tree" in problem and "never exercises it" in problem for problem in problems)


def test_a_registered_kind_without_console_output_is_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    golden_dir = tmp_path / "golden"
    golden_dir.mkdir()
    monkeypatch.setattr(check_parity, "GOLDEN_DIR", golden_dir)
    monkeypatch.setattr(check_parity, "registered_surfaces", lambda: {"/api/tree"})
    monkeypatch.setattr(check_parity, "registered_kinds", lambda: {"markdown"})
    monkeypatch.setattr(
        check_parity,
        "MAP_DOC",
        _write_map(tmp_path, "| `/api/tree` | exempt | — | streaming |"),
    )

    problems = check_parity.check()

    assert any("markdown" in problem and "golden console output" in problem for problem in problems)


def test_a_kind_named_only_in_prose_is_not_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    golden_dir = tmp_path / "golden"
    _write_golden(
        golden_dir,
        "prose.tryscript.md",
        "A future selection should report kind: markdown.\n",
    )
    monkeypatch.setattr(check_parity, "GOLDEN_DIR", golden_dir)
    monkeypatch.setattr(check_parity, "registered_surfaces", lambda: {"/api/tree"})
    monkeypatch.setattr(check_parity, "registered_kinds", lambda: {"markdown"})
    monkeypatch.setattr(
        check_parity,
        "MAP_DOC",
        _write_map(tmp_path, "| `/api/tree` | exempt | — | streaming |"),
    )

    problems = check_parity.check()

    assert any("markdown" in problem and "golden console output" in problem for problem in problems)


@pytest.mark.parametrize(
    "command",
    [
        "printf /api/tree-spoof",
        "metab root --api /api/tree-spoof",
    ],
)
def test_a_route_suffix_or_non_metab_command_is_not_evidence(
    command: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    only_tree: None,
) -> None:
    golden_dir = tmp_path / "golden"
    _write_golden(
        golden_dir,
        "spoof.tryscript.md",
        f"```console\n$ {command}\n/api/tree-spoof\n? 0\n```\n",
    )
    monkeypatch.setattr(check_parity, "GOLDEN_DIR", golden_dir)
    monkeypatch.setattr(
        check_parity,
        "MAP_DOC",
        _write_map(tmp_path, "| `/api/tree` | covered | `--api` | `spoof.tryscript.md` |"),
    )

    problems = check_parity.check()

    assert any("/api/tree" in problem and "never exercises it" in problem for problem in problems)


def test_a_nonzero_route_command_is_not_successful_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    only_tree: None,
) -> None:
    golden_dir = tmp_path / "golden"
    _write_golden(
        golden_dir,
        "failed.tryscript.md",
        "```console\n$ metab root --api /api/tree\nerror\n? 1\n```\n",
    )
    monkeypatch.setattr(check_parity, "GOLDEN_DIR", golden_dir)
    monkeypatch.setattr(
        check_parity,
        "MAP_DOC",
        _write_map(tmp_path, "| `/api/tree` | covered | `--api` | `failed.tryscript.md` |"),
    )

    problems = check_parity.check()

    assert any("/api/tree" in problem and "no successful exact" in problem for problem in problems)


def test_an_error_golden_can_supplement_successful_route_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    only_tree: None,
) -> None:
    golden_dir = tmp_path / "golden"
    _write_golden(
        golden_dir,
        "success.tryscript.md",
        "```console\n$ metab root --api /api/tree\n{}\n? 0\n```\n",
    )
    _write_golden(
        golden_dir,
        "error.tryscript.md",
        "```console\n$ metab root --api /api/tree\nerror\n? 1\n```\n",
    )
    monkeypatch.setattr(check_parity, "GOLDEN_DIR", golden_dir)
    monkeypatch.setattr(
        check_parity,
        "MAP_DOC",
        _write_map(
            tmp_path,
            "| `/api/tree` | covered | `--api` | `success.tryscript.md`, `error.tryscript.md` |",
        ),
    )

    assert check_parity.check() == []


def test_an_unattached_kind_output_is_not_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    golden_dir = tmp_path / "golden"
    _write_golden(
        golden_dir,
        "spoof.tryscript.md",
        "```console\n$ printf 'kind: markdown\\n'\nkind: markdown\n? 0\n```\n",
    )
    monkeypatch.setattr(check_parity, "GOLDEN_DIR", golden_dir)
    monkeypatch.setattr(check_parity, "registered_surfaces", lambda: {"/api/tree"})
    monkeypatch.setattr(check_parity, "registered_kinds", lambda: {"markdown"})
    monkeypatch.setattr(
        check_parity,
        "MAP_DOC",
        _write_map(tmp_path, "| `/api/tree` | exempt | — | streaming |"),
    )

    problems = check_parity.check()

    assert any("markdown" in problem and "golden console output" in problem for problem in problems)


def test_a_source_owner_cannot_escape_the_production_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    only_tree: None,
) -> None:
    doc = _write_map(tmp_path, "| `/api/tree` | exempt | — | streaming |")
    doc.write_text(
        doc.read_text(encoding="utf-8").replace(
            "`static/styles.css`",
            "`../../tests/test_check_parity.py`",
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(check_parity, "MAP_DOC", doc)

    problems = check_parity.check()

    assert any("test.paint" in problem and "escapes" in problem for problem in problems)


def test_interaction_commands_cannot_smuggle_eval_before_a_session_name(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    only_tree: None,
) -> None:
    command = "node -e \"console.log('{}')\" tests/dom/recent-filter-session.js"
    golden_dir = tmp_path / "golden"
    _write_golden(
        golden_dir,
        "session.tryscript.md",
        f"```console\n$ {command}\n{{}}\n? 0\n```\n",
    )
    doc = _write_map(tmp_path, "| `/api/tree` | exempt | — | streaming |")
    doc.write_text(
        doc.read_text(encoding="utf-8").replace(
            "| `test.paint` | paint-exempt | `static/styles.css` | — | "
            "fixture reason; `tests/test_check_parity.py` |",
            "| `navigation.filter` | interaction | `static/tree-filter-model.js` | "
            f"`{command}` | `session.tryscript.md` |",
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(check_parity, "GOLDEN_DIR", golden_dir)
    monkeypatch.setattr(check_parity, "MAP_DOC", doc)

    problems = check_parity.check()

    assert any(
        "navigation.filter" in problem and "must be exactly" in problem for problem in problems
    )
