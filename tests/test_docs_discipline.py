"""Structural discipline for durable documents.

Prose drifts silently; these are the parts of `docs/development.md`'s
documentation conventions a machine can hold: every architecture
document is reachable from the project index, states its status, and
carries the shared footer. Content review stays human — this only
prevents a document from becoming unfindable or silently stale about
whether it describes something that exists.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ARCHITECTURE_DIR = REPO_ROOT / "docs/project/architecture"
PROJECT_INDEX = REPO_ROOT / "docs/project/README.md"
FOOTER = "This document follows common-doc-guidelines.md."


def _architecture_docs() -> list[Path]:
    return sorted(ARCHITECTURE_DIR.rglob("*.md"))


def test_every_architecture_doc_is_linked_from_the_project_index() -> None:
    """A reader must reach every document from an obvious root."""
    index = PROJECT_INDEX.read_text(encoding="utf-8")
    for doc in _architecture_docs():
        relative = doc.relative_to(PROJECT_INDEX.parent).as_posix()
        assert relative in index, f"{relative} is not linked from docs/project/README.md"


def test_every_architecture_doc_states_its_status() -> None:
    """Whether a document describes built or planned work is the first
    thing a reader needs, and the thing that goes stale first."""
    for doc in _architecture_docs():
        head = doc.read_text(encoding="utf-8").split("\n\n", 3)
        assert any(part.startswith("**Status:**") for part in head[:3]), (
            f"{doc.name} needs a **Status:** line near the top"
        )


def test_every_architecture_doc_carries_the_shared_footer() -> None:
    for doc in _architecture_docs():
        assert FOOTER in doc.read_text(encoding="utf-8"), f"{doc.name} lost the guideline footer"


def test_documents_that_tabulate_registered_surfaces_name_their_check() -> None:
    """A table of what the code registers must say what keeps it honest,
    so the next reader knows the table is enforced rather than hopeful."""
    for doc in _architecture_docs():
        text = doc.read_text(encoding="utf-8")
        if "| Route |" not in text and "| Kind |" not in text:
            continue
        assert "tests/test_" in text, (
            f"{doc.name} tabulates registered surfaces but names no test that checks it"
        )
