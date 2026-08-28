"""The parity checker is not trusted on its word.

A check that cannot fail is not a check, so each rule gets a table that breaks
it and must be reported with the surface named.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from devtools import check_parity

_HEADER = "| Surface | Status | CLI | Golden or reason |\n| --- | --- | --- | --- |\n"


def _write_map(tmp_path: Path, rows: str) -> Path:
    doc = tmp_path / "map.md"
    doc.write_text(f"# Map\n\n{_HEADER}{rows}\n\n## Adding something\n", encoding="utf-8")
    return doc


@pytest.fixture
def only_tree(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(check_parity, "registered_surfaces", lambda: {"/api/tree"})


def test_a_registered_route_with_no_row_is_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(check_parity, "registered_surfaces", lambda: {"/api/tree", "/api/rollup"})
    monkeypatch.setattr(
        check_parity, "MAP_DOC", _write_map(tmp_path, "| `/api/tree` | gap | `--api` | `mb-1234` |")
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
            "| `/api/tree` | gap | `--api` | `mb-1234` |\n| `/api/gone` | gap | `--api` | `mb-1234` |",
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


def test_a_gap_row_without_a_bead_is_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, only_tree: None
) -> None:
    monkeypatch.setattr(
        check_parity, "MAP_DOC", _write_map(tmp_path, "| `/api/tree` | gap | `--api` | later |")
    )

    problems = check_parity.check()

    assert any("/api/tree" in problem and "name the bead" in problem for problem in problems)


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
