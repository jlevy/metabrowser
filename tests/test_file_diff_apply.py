"""Apply-oracle side of the conformance corpus, plus refusal behavior."""

from __future__ import annotations

from typing import Any

import pytest

from metabrowser.diff.apply import (
    ApplyError,
    NotFullyHydrated,
    TreeSnapshot,
    apply_change_set,
)
from metabrowser.diff.format import load_conformance_corpus, validate_document


def _apply_cases() -> list[dict[str, Any]]:
    return list(load_conformance_corpus()["apply_cases"])


@pytest.mark.parametrize("case", _apply_cases(), ids=lambda case: str(case["name"]))
def test_apply_reproduces_the_target_tree(case: dict[str, Any]) -> None:
    document = validate_document(case["document"])
    base = TreeSnapshot.from_corpus(case["base"])
    target = TreeSnapshot.from_corpus(case["target"])
    produced = apply_change_set(document, base)
    assert produced.as_corpus() == target.as_corpus()
    assert produced.tree_hash() == target.tree_hash()


def test_apply_refuses_a_non_ready_file_as_not_hydrated() -> None:
    case = next(c for c in _apply_cases() if c["name"] == "apply-add")
    raw = case["document"]
    downgraded = {
        **raw,
        "manifest": {
            **raw["manifest"],
            "files": [{**raw["manifest"]["files"][0], "availability": "deferred"}],
        },
        "patches": {},
    }
    document = validate_document(downgraded)
    with pytest.raises(NotFullyHydrated):
        apply_change_set(document, TreeSnapshot.from_corpus(case["base"]))


def test_apply_refuses_a_hunk_that_contradicts_the_base() -> None:
    case = next(c for c in _apply_cases() if c["name"] == "apply-delete")
    document = validate_document(case["document"])
    wrong_base = TreeSnapshot.from_corpus(
        {"entries": {"b.txt": {"entry_type": "file", "mode": "100644", "content_b64": "Wg=="}}}
    )
    with pytest.raises(ApplyError):
        apply_change_set(document, wrong_base)


def test_tree_hash_distinguishes_mode_and_content() -> None:
    a = TreeSnapshot.from_corpus(
        {"entries": {"x": {"entry_type": "file", "mode": "100644", "content_b64": "aGk="}}}
    )
    b = TreeSnapshot.from_corpus(
        {"entries": {"x": {"entry_type": "file", "mode": "100755", "content_b64": "aGk="}}}
    )
    c = TreeSnapshot.from_corpus(
        {"entries": {"x": {"entry_type": "file", "mode": "100644", "content_b64": "aG8="}}}
    )
    assert len({a.tree_hash(), b.tree_hash(), c.tree_hash()}) == 3


# ── Review finding R6: refusal semantics match git apply ────────────


def _minimal(kind: str, path: str, **extra: Any) -> dict[str, Any]:
    side = {
        "path": path,
        "entry_type": "file",
        "mode": "100644",
        "content": {"kind": "empty"},
    }
    change: dict[str, Any] = {
        "id": extra.pop("id", "f1"),
        "kind": kind,
        "binary": False,
        "availability": "ready",
        "additions": extra.pop("additions", 1),
        "deletions": extra.pop("deletions", 0),
        **extra,
    }
    if kind != "added":
        change["old"] = dict(side)
    if kind != "deleted":
        change["new"] = dict(side)
    return change


def _document(files: list[dict[str, Any]], patches: dict[str, Any]) -> Any:
    return validate_document(
        {
            "schema": "file-diff-v1",
            "schema_version": 1,
            "resolved": {
                "comparison_id": "test:r6",
                "source": {"name": "test"},
                "kind": "content",
                "base_policy": "direct",
                "left": {"kind": "patch"},
                "right": {"kind": "patch"},
                "options": {"context": 3, "rename_detection": True},
            },
            "manifest": {
                "files": files,
                "totals": {
                    "files": len(files),
                    "additions": None,
                    "deletions": None,
                    "exact": False,
                },
                "truncated": False,
            },
            "patches": patches,
        }
    )


def _add_patch(file_id: str, text: str) -> dict[str, Any]:
    return {
        "file_id": file_id,
        "truncated": False,
        "hunks": [
            {
                "old_start": 0,
                "old_count": 0,
                "new_start": 1,
                "new_count": 1,
                "lines": [{"op": "add", "text": text}],
            }
        ],
    }


def test_added_over_an_existing_base_path_is_refused() -> None:
    document = _document([_minimal("added", "x.txt")], {"f1": _add_patch("f1", "hello")})
    base = TreeSnapshot.from_corpus(
        {"entries": {"x.txt": {"entry_type": "file", "mode": "100644", "content_b64": ""}}}
    )
    with pytest.raises(ApplyError, match="the base already has"):
        apply_change_set(document, base)


def test_two_changes_producing_one_path_are_refused() -> None:
    document = _document(
        [
            _minimal("added", "x.txt", id="f1"),
            _minimal("added", "x.txt", id="f2"),
        ],
        {"f1": _add_patch("f1", "one"), "f2": _add_patch("f2", "two")},
    )
    with pytest.raises(ApplyError, match="another change produced"):
        apply_change_set(document, TreeSnapshot.from_corpus({"entries": {}}))


def test_ready_delete_without_a_patch_is_not_fully_hydrated() -> None:
    document = _document(
        [_minimal("deleted", "x.txt", additions=0, deletions=1)],
        {},
    )
    base = TreeSnapshot.from_corpus(
        {"entries": {"x.txt": {"entry_type": "file", "mode": "100644", "content_b64": "YQo="}}}
    )
    with pytest.raises(NotFullyHydrated, match="patch is absent"):
        apply_change_set(document, base)
