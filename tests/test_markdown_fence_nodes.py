"""Exercise structured excerpts at original line addresses through the plugin route."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from starlette.applications import Starlette
from starlette.testclient import TestClient

from metabrowser import server
from metabrowser.markdown_fences import structured_fences
from metabrowser.plugin_loader.static_assets import build_plugin_routes

_ROUTE = "/api/plugin/structured/parsed"


@pytest.mark.parametrize("eol", [b"\r\n", b"\r", b"\n"])
def test_fence_source_copy_and_tree_use_the_same_revision(tmp_path: Path, eol: bytes) -> None:
    server._set_root_dir(tmp_path)
    path = tmp_path / "article.md"
    lines = [
        "---",
        "title: Étude",
        "---",
        "",
        "### Résumé",
        "",
        "~~~~yml",
        "people:",
        "  - name: Zoé",
        "    roles: [host, editor]",
        "~~~~~",
        "",
        "```json",
        '{"value": null, "big": 9007199254740993}',
        "```",
        "",
        "After.",
    ]
    data = eol.join(line.encode() for line in lines)
    path.write_bytes(data)
    app = Starlette(
        routes=build_plugin_routes([p for p in server._LOADED_PLUGINS if p.name == "structured"])
    )
    with TestClient(app) as client:

        def read(line: int, **params: str) -> dict[str, Any]:
            res = client.get(
                _ROUTE,
                params={
                    "projection": "nodes",
                    "path": path.name,
                    "fence_line": str(line),
                    **params,
                },
            )
            assert res.status_code == 200, res.text
            return res.json()

        first = read(7, source="1")
        assert first["format"] == "yaml"
        assert first["source_start_line"] == 8
        excerpt = first["excerpt"]
        assert (
            first["source_text"].encode()
            == data[excerpt["start_byte"] : excerpt["end_byte"]]
            == eol.join(line.encode() for line in lines[7:10]) + eol
        )
        selected = read(
            7,
            node='["people",0,"roles"]',
            source="1",
            tree="1",
            copy="row",
            mtime_hash=first["mtime_hash"],
        )
        assert selected["source_start_line"] == 10
        assert selected["tree_value"] == ["host", "editor"]
        assert selected["copy_text"] == "roles: [host, editor]"
        span = selected["node"]["source_range"]
        assert (
            data[span["start_byte"] : span["end_byte"]]
            == selected["source_text"].encode()
            == b"[host, editor]"
        )
        assert read(13, tree="1")["tree_value"] == {"value": None, "big": "9007199254740993"}
        assert read(13, node='["value"]', tree="1")["tree_value"] is None
        assert "tree_value" not in read(13)
        path.write_bytes(data + b"\nrevision")
        stale = client.get(
            _ROUTE,
            params={
                "projection": "nodes",
                "path": path.name,
                "fence_line": "7",
                "mtime_hash": first["mtime_hash"],
            },
        )
        assert stale.status_code == 409


def test_fence_lookup_refuses_nonfences_and_unclosed_or_nested_fences() -> None:
    text = """<!--
```json
{}
```
-->

````text
```json
{}
```
````

> ~~~yaml
> key: true
> ~~~

    ```yaml
    value: not-a-fence
    ```

~~~json
{}
~~~~

~~~json
[unfinished]
"""
    found = structured_fences(text.encode())
    assert len(found) == 1
    assert text.encode()[found[0].start_byte : found[0].end_byte] == b"{}\n"
    assert structured_fences(text.encode()) is found


def test_malformed_json_fence_keeps_exact_source_and_scoped_diagnostic(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    data = "Readable ü\r\n\r\n```json\r\n[true,,]\r\n```\r\n\r\n```yaml\r\nok: yes\r\n```".encode()
    (tmp_path / "article.md").write_bytes(data)
    app = Starlette(
        routes=build_plugin_routes([p for p in server._LOADED_PLUGINS if p.name == "structured"])
    )
    with TestClient(app) as client:
        params = {"path": "article.md", "projection": "nodes", "source": "1"}
        malformed = client.get(_ROUTE, params={**params, "fence_line": "3"}).json()
        assert malformed["status"] == "invalid"
        assert malformed["source_text"] == "[true,,]\r\n"
        assert data[malformed["error_byte"] :].startswith(b",]")
        intact = client.get(
            _ROUTE, params={**params, "fence_line": "7", "node": json.dumps(["ok"])}
        ).json()
        assert intact["node"]["value"] == "yes"
        assert (
            client.get(_ROUTE, params={**params, "fence_line": "4"}).json()["status"] == "missing"
        )
        assert client.get(_ROUTE, params={**params, "fence_line": "0"}).status_code == 400
        assert (
            client.get(_ROUTE, params={**params, "fence_line": "3", "frontmatter": "1"}).status_code
            == 400
        )


def test_fence_source_respects_document_boundary_and_host_byte_budget(tmp_path: Path) -> None:
    from metabrowser.markdown_limits import MARKDOWN_DIFF_MAX_BYTES

    server._set_root_dir(tmp_path)
    path = tmp_path / "stream.md"
    path.write_bytes(b"~~~yaml\r\n---\r\nold\r\n---\r\nnew\r\n~~~\r\n")
    plugins = [p for p in server._LOADED_PLUGINS if p.name == "structured"]
    with TestClient(Starlette(routes=build_plugin_routes(plugins))) as client:
        params = {
            "path": path.name,
            "projection": "nodes",
            "fence_line": "1",
            "source": "1",
            "document": "1",
        }
        selected = client.get(_ROUTE, params=params).json()
        assert (selected["source_start_line"], selected["source_text"]) == (5, "new")
        path.write_bytes(path.read_bytes() + b"x" * MARKDOWN_DIFF_MAX_BYTES)
        assert client.get(_ROUTE, params=params).json()["status"] == "too_large"


@pytest.mark.parametrize(
    ("name", "data", "params"),
    [
        ("record.yaml", b"name: Before\n", {"copy": "row"}),
        (
            "record.md",
            b"---\nname: Before\n---\n# Body\n",
            {"frontmatter": "1", "source": "1", "copy": "row"},
        ),
        (
            "fence.md",
            b"```yaml\nname: Before\n```\n",
            {"fence_line": "1", "source": "1", "copy": "row"},
        ),
    ],
)
@pytest.mark.parametrize("change", ["before_read", "after_read", "remove_after_read"])
def test_projection_refuses_a_revision_change_during_the_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    data: bytes,
    params: dict[str, str],
    change: str,
) -> None:
    from metabrowser.builtin_plugins.structured import nodes_route
    from metabrowser.source import ContentRef, ContentWindow

    server._set_root_dir(tmp_path)
    path = tmp_path / name
    path.write_bytes(data)
    plugins = [p for p in server._LOADED_PLUGINS if p.name == "structured"]
    with TestClient(Starlette(routes=build_plugin_routes(plugins))) as client:
        query = {"projection": "nodes", "path": name, **params}
        first = client.get(_ROUTE, params=query)
        assert first.status_code == 200
        original_read = nodes_route.read_content_window

        async def raced_read(ref: ContentRef, *, max_bytes: int) -> ContentWindow:
            if change == "before_read":
                path.write_bytes(data.replace(b"Before", b"After replacement"))
            window = await original_read(ref, max_bytes=max_bytes)
            if change == "after_read":
                path.write_bytes(data.replace(b"Before", b"After replacement"))
            elif change == "remove_after_read":
                path.unlink()
            return window

        monkeypatch.setattr(nodes_route, "read_content_window", raced_read)
        response = client.get(_ROUTE, params={**query, "mtime_hash": first.json()["mtime_hash"]})
        assert response.status_code == 409, response.text
        assert response.json()["status"] == "changed"
        assert not {"source_text", "copy_text", "tree_value", "node"} & response.json().keys()
