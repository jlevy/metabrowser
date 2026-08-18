"""Obsidian-style vault fixture coverage for wiki navigation."""

from __future__ import annotations

import json
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from metabrowser import server

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "obsidian-vault"
PREPROCESSOR = Path(__file__).resolve().parent / "dom" / "markdown_preprocess_fixture.js"


class _WikiMetadata(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.targets: list[str] = []
        self.ids: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del tag
        values = dict(attrs)
        target = values.get("data-mb-wiki-target")
        identifier = values.get("id")
        if target:
            self.targets.append(target)
        if identifier:
            self.ids.append(identifier)


def _preprocessed_readme() -> dict[str, object]:
    if shutil.which("node") is None:
        pytest.skip("node not available")
    result = subprocess.run(
        ["node", str(PREPROCESSOR), str(REPO_ROOT), str(FIXTURE_ROOT / "README.md")],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_obsidian_fixture_source_metadata_survives_safe_rendering() -> None:
    preprocessed = _preprocessed_readme()
    assert preprocessed["changed"] is True
    server._set_root_dir(FIXTURE_ROOT)
    try:
        response = TestClient(server.app).post(
            "/api/kpress/render",
            json={
                "path": "README.md",
                "view": "rendered",
                "profile": "document",
                "source_text": preprocessed["source"],
            },
        )
    finally:
        server._set_root_dir(Path())

    assert response.status_code == 200
    parser = _WikiMetadata()
    parser.feed(response.json()["html"])
    assert parser.targets == [
        "Notes/Welcome",
        "Notes/Welcome",
        "Notes/Welcome#Overview",
        "#Local heading",
        "#^home-block",
        "Résumé",
        "space note",
        "Attachments/report.pdf",
        "Duplicate",
        "Missing",
        "Attachments/map.svg",
    ]
    assert "obsidian-heading-Vault Home" in parser.ids
    assert "obsidian-heading-Local heading" in parser.ids
    assert "obsidian-block-home-block" in parser.ids


def test_obsidian_fixture_has_exact_ambiguous_and_missing_targets() -> None:
    for target in (
        "Attachments/map.svg",
        "Attachments/report.pdf",
        "Notes/Résumé.md",
        "Notes/space note.md",
        "Notes/Welcome.md",
        "One/Duplicate.md",
        "Two/Duplicate.md",
    ):
        assert (FIXTURE_ROOT / target).is_file(), target
    assert not (FIXTURE_ROOT / "Missing.md").exists()


def test_obsidian_fixture_canonical_routes_and_raw_resource_reload() -> None:
    server._set_root_dir(FIXTURE_ROOT)
    try:
        client = TestClient(server.app)
        for route in (
            "/view/README.md#obsidian-heading-Local%20heading",
            "/view/README.md#obsidian-block-home-block",
            "/view/Notes/Welcome.md#obsidian-heading-Overview",
            "/view/Notes/R%C3%A9sum%C3%A9.md",
            "/view/Notes/space%20note.md",
        ):
            response = client.get(route)
            assert response.status_code == 200, route
            assert "<title>Metabrowser</title>" in response.text

        resource = client.get("/raw?path=Attachments%2Fmap.svg")
        assert resource.status_code == 200
        assert resource.headers["content-type"].startswith("image/svg+xml")
        assert b"Obsidian vault map fixture" in resource.content
    finally:
        server._set_root_dir(Path())
