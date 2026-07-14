from __future__ import annotations

from devtools.public_hygiene import ROOT, _text_files, find_hygiene_findings


def test_public_issue_tracking_language_is_allowed() -> None:
    text = "Track this work as an mb-abcd bead and sync it before handoff."

    assert find_hygiene_findings("AGENTS.md", text) == []


def test_private_plan_path_is_rejected() -> None:
    private_plan_path = "docs" + "/project/specs/active/example.md"

    assert find_hygiene_findings("README.md", private_plan_path) == [
        "README.md:1: private plan path"
    ]


def test_generated_tbd_document_cache_is_not_scanned() -> None:
    tbd_docs = ROOT / ".tbd" / "docs"

    assert all(not path.is_relative_to(tbd_docs) for path in _text_files())
