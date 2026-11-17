"""`devtools/inventory_digest.py` digests what a provider answers, the same way each time.

The digest is the semantic-equality precheck a provider comparison runs before timing,
so these check that it is deterministic for one provider, that it ignores only what
names the provider, and that the command compares through a fresh process per provider.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

import pytest

from devtools import inventory_digest
from tests.inventory_harness import selected_inventory_provider


def _corpus(root: Path) -> Path:
    (root / "docs" / "deep").mkdir(parents=True)
    (root / "docs" / "notes.md").write_text("notes\n")
    (root / "docs" / "deep" / "data.json").write_text("{}\n")
    (root / "main.py").write_text("print()\n")
    for path in (*root.rglob("*"), root):
        os.utime(path, ns=(1_700_000_000_000_000_000, 1_700_000_000_000_000_000))
    return root


def test_the_fields_that_name_a_provider_are_all_that_a_digest_ignores() -> None:
    meta = {"status": "done", "indexed_files": 3, "provider": "python", "watch_mode": "native"}
    renamed = {**meta, "provider": "other", "watch_mode": "poll"}
    assert inventory_digest.canonical_digest(
        "/api/index/meta", meta
    ) == inventory_digest.canonical_digest("/api/index/meta", renamed)
    assert inventory_digest.canonical_digest(
        "/api/index/meta", meta
    ) != inventory_digest.canonical_digest("/api/index/meta", {**meta, "indexed_files": 4})
    # The same field on another route describes the files and is digested.
    assert inventory_digest.canonical_digest(
        "/api/tree?depth=0", meta
    ) != inventory_digest.canonical_digest("/api/tree?depth=0", renamed)


def test_one_provider_digests_a_corpus_the_same_way_twice(tmp_path: Path) -> None:
    root = _corpus(tmp_path / "corpus")
    provider = selected_inventory_provider().value

    def digest() -> dict[str, Any]:
        return asyncio.run(
            inventory_digest.digest_routes(root, inventory_digest.ROUTES, provider=provider)
        )

    first = digest()
    assert first == digest()
    assert set(first["routes"]) == set(inventory_digest.ROUTES)
    assert inventory_digest.mismatched_routes([first, first]) == []


def test_the_command_compares_providers_in_fresh_processes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _corpus(tmp_path / "corpus")
    provider = selected_inventory_provider().value
    output = tmp_path / "digest.json"
    status = inventory_digest.main(
        [str(root), "--provider", provider, "--provider", provider, "--json", str(output)]
    )
    assert status == 0
    report = json.loads(output.read_text())
    assert report["mismatched_routes"] == []
    assert [result["provider"] for result in report["results"]] == [provider, provider]
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == len(inventory_digest.ROUTES)
    assert all(line.startswith("same") for line in lines)


def test_a_difference_names_its_route() -> None:
    same = {"sha256": "a", "bytes": 1}
    first = {"provider": "one", "routes": {"/api/catalog": same, "/api/tree?depth=0": same}}
    second = {
        "provider": "two",
        "routes": {"/api/catalog": {"sha256": "b", "bytes": 1}, "/api/tree?depth=0": same},
    }
    assert inventory_digest.mismatched_routes([first, second]) == ["/api/catalog"]
