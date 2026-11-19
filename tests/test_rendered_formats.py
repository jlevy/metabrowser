"""The format a changed file renders as: the server's route and the page read one table.

``tests/fixtures/rendered-formats.json`` holds names and renames with the format each
renders as, or none; ``tests/dom/diff-markdown-behavior.js`` checks the page's
``renderedFormat`` against the same table (mb-8274 review D5).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from metabrowser.builtin_plugins.github.pull_rendered_diff import (
    _rendered_format,  # pyright: ignore[reportPrivateUsage]
)
from metabrowser.diff.format import FileChange

_TABLE: dict[str, list[list[str | None]]] = json.loads(
    (Path(__file__).parent / "fixtures" / "rendered-formats.json").read_text(encoding="utf-8")
)


def _side(name: str, entry_type: str = "file") -> dict[str, Any]:
    return {
        "path": name,
        "entry_type": entry_type,
        "mode": {"file": "100644", "symlink": "120000", "submodule": "160000"}[entry_type],
        "content": {"kind": "git_object", "oid": "0" * 40},
    }


def _change(
    old: dict[str, Any] | None, new: dict[str, Any] | None, availability: str = "ready"
) -> FileChange:
    return FileChange.model_validate(
        {
            "id": "f1",
            "kind": "added" if old is None else "modified",
            "old": old,
            "new": new,
            "binary": False,
            "availability": availability,
        }
    )


@pytest.mark.parametrize(("name", "rendered"), _TABLE["names"])
def test_a_name_renders_as_the_page_reads_it(name: str, rendered: str | None) -> None:
    assert _rendered_format(_change(None, _side(name))) == rendered
    assert _rendered_format(_change(_side(name), _side(name))) == rendered


@pytest.mark.parametrize(("old", "new", "rendered"), _TABLE["renames"])
def test_a_rename_renders_only_within_one_format(old: str, new: str, rendered: str | None) -> None:
    assert _rendered_format(_change(_side(old), _side(new))) == rendered


@pytest.mark.parametrize("entry_type", ["symlink", "submodule"])
def test_only_files_render(entry_type: str) -> None:
    assert _rendered_format(_change(None, _side("a.json", entry_type))) is None
    assert _rendered_format(_change(_side("a.json"), _side("a.json", entry_type))) is None


@pytest.mark.parametrize("availability", ["deferred", "binary", "too_large", "failed"])
def test_only_a_ready_change_renders(availability: str) -> None:
    assert _rendered_format(_change(None, _side("a.json"), availability)) is None
