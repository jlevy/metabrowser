"""Obsidian-style vault fixture coverage for wiki navigation."""

from __future__ import annotations

import json
import re
import subprocess
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient

from metabrowser import server
from tests.required_tools import require_node

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "obsidian-vault"
PREPROCESSOR = Path(__file__).resolve().parent / "dom" / "markdown-preprocess-fixture.js"
# Shared with tests/dom/markdown-wiki-parser-behavior.js, which checks each case's
# source; the render comparison below checks its blocks.
HEADING_LAYOUT_CASES: list[dict[str, Any]] = json.loads(
    (Path(__file__).resolve().parent / "fixtures" / "markdown_heading_layout.json").read_text(
        encoding="utf-8"
    )
)["cases"]
_HEADING_ANCHOR = re.compile(r'<span class="metabrowser-wiki-heading" id="[^"]*"></span>')


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


_HEADINGS = frozenset({"h1", "h2", "h3", "h4", "h5", "h6"})
_VOID = frozenset({"area", "br", "col", "embed", "hr", "img", "input", "source", "track", "wbr"})


class _HeadingLayout(HTMLParser):
    """A render's prose column: the tags of its children, how many paragraphs hold
    nothing but wiki heading anchors, each heading's id and text, and each anchor's id
    with the id of the heading it sits in (None outside a heading)."""

    def __init__(self) -> None:
        super().__init__()
        self.prose_children: list[str] = []
        self.anchor_only_paragraphs = 0
        self.headings: list[tuple[str, str]] = []
        self.anchors: list[tuple[str, str | None]] = []
        self._open: list[str] = []
        self._prose_depth: int | None = None
        self._heading: tuple[str, list[str]] | None = None
        self._paragraph_content: bool | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        classes = (values.get("class") or "").split()
        if self._prose_depth is not None and len(self._open) == self._prose_depth:
            self.prose_children.append(tag)
        if tag in _VOID:
            return
        self._open.append(tag)
        if tag == "div" and "kpress-prose" in classes:
            self._prose_depth = len(self._open)
        if "metabrowser-wiki-heading" in classes:
            self.anchors.append((values.get("id") or "", self._heading and self._heading[0]))
            return
        if self._paragraph_content is not None:
            self._paragraph_content = True
        if tag in _HEADINGS:
            self._heading = (values.get("id") or "", [])
        elif tag == "p":
            self._paragraph_content = False

    def handle_endtag(self, tag: str) -> None:
        if not self._open or self._open[-1] != tag:
            return
        self._open.pop()
        if tag in _HEADINGS and self._heading:
            self.headings.append((self._heading[0], "".join(self._heading[1])))
            self._heading = None
        elif tag == "p" and self._paragraph_content is not None:
            self.anchor_only_paragraphs += not self._paragraph_content
            self._paragraph_content = None
        if self._prose_depth is not None and len(self._open) < self._prose_depth:
            self._prose_depth = None

    def handle_data(self, data: str) -> None:
        if self._heading:
            self._heading[1].append(data)
        if self._paragraph_content is not None and data.strip():
            self._paragraph_content = True


def _preprocessed(path: Path) -> dict[str, object]:
    require_node()
    result = subprocess.run(
        ["node", str(PREPROCESSOR), str(REPO_ROOT), str(path)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _preprocessed_readme() -> dict[str, object]:
    return _preprocessed(FIXTURE_ROOT / "README.md")


def test_obsidian_fixture_source_metadata_survives_safe_rendering() -> None:
    preprocessed = _preprocessed_readme()
    assert preprocessed["changed"] is True
    server._set_root_dir(FIXTURE_ROOT)
    response = TestClient(server.app).post(
        "/api/kpress/render",
        json={
            "path": "README.md",
            "view": "rendered",
            "profile": "document",
            "source_text": preprocessed["source"],
        },
    )

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


_HEADING_DOCUMENT = """\
# Title

Intro with [[#Section]] and [[#Title#Section#Child]].

## Section

Text.

### Child

- one
- two
---

Setext Heading
--------------

## Section

A second section of the same name.
"""


def _render(client: TestClient, source_text: str) -> Any:
    response = client.post(
        "/api/kpress/render",
        json={
            "path": "headings.md",
            "view": "rendered",
            "profile": "document",
            "source_text": source_text,
        },
    )
    assert response.status_code == 200
    return response.json()


@pytest.mark.parametrize(
    "case", HEADING_LAYOUT_CASES, ids=[str(case["name"]) for case in HEADING_LAYOUT_CASES]
)
def test_heading_anchors_change_no_block(tmp_path: Path, case: dict[str, Any]) -> None:
    """Each layout case, preprocessed and rendered through KPress with its heading
    anchors then removed, gives exactly the authored render's HTML: the anchors turn no
    line into another block and split no table row's cells."""
    source = str(case["source"])
    document = tmp_path / "headings.md"
    document.write_text(source, encoding="utf-8")
    preprocessed = _preprocessed(document)
    server._set_root_dir(tmp_path)
    client = TestClient(server.app)
    authored = str(_render(client, source)["html"])
    wiki = str(_render(client, str(preprocessed["source"]))["html"])

    assert len(_HEADING_ANCHOR.findall(wiki)) == case["anchors"]
    assert _HEADING_ANCHOR.sub("", wiki) == authored


def test_wiki_heading_anchors_render_inside_their_headings(tmp_path: Path) -> None:
    """The preprocessed render's blocks are the authored render's: each heading keeps its
    KPress id and title, the title is the prose column's first child (so its first-child
    margin trim applies), no paragraph holds only anchors, and every Obsidian name of a
    heading -- its hierarchical forms included, each once -- sits inside that heading,
    where `[[#Section]]` and `[[#Title#Section#Child]]` reach it."""
    document = tmp_path / "headings.md"
    document.write_text(_HEADING_DOCUMENT, encoding="utf-8")
    preprocessed = _preprocessed(document)
    assert preprocessed["changed"] is True
    server._set_root_dir(tmp_path)
    client = TestClient(server.app)
    authored = _render(client, _HEADING_DOCUMENT)
    wiki = _render(client, str(preprocessed["source"]))

    authored_layout = _HeadingLayout()
    authored_layout.feed(str(authored["html"]))
    layout = _HeadingLayout()
    layout.feed(str(wiki["html"]))

    assert layout.prose_children == authored_layout.prose_children
    assert layout.prose_children[0] == "h1"
    assert layout.anchor_only_paragraphs == 0
    assert (
        layout.headings
        == authored_layout.headings
        == [
            ("title", "Title"),
            ("section", "Section"),
            ("child", "Child"),
            ("setext-heading", "Setext Heading"),
            ("section-1", "Section"),
        ]
    )
    assert wiki["model"]["headings"] == authored["model"]["headings"]
    assert layout.anchors == [
        ("obsidian-heading-Title", "title"),
        ("obsidian-heading-Title#Section", "section"),
        ("obsidian-heading-Section", "section"),
        ("obsidian-heading-Title#Section#Child", "child"),
        ("obsidian-heading-Section#Child", "child"),
        ("obsidian-heading-Child", "child"),
        ("obsidian-heading-Title#Setext Heading", "setext-heading"),
        ("obsidian-heading-Setext Heading", "setext-heading"),
    ]


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
        assert "<title>obsidian-vault \u2022 Metabrowser</title>" in response.text

    resource = client.get("/raw?path=Attachments%2Fmap.svg")
    assert resource.status_code == 200
    assert resource.headers["content-type"].startswith("image/svg+xml")
    assert b"Obsidian vault map fixture" in resource.content
