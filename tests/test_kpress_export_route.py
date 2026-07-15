"""POST /api/kpress/export route contract tests."""

from __future__ import annotations

import asyncio
import gzip
import json
import zlib
from pathlib import Path
from typing import Any
from unittest.mock import Mock

from metabrowser import kpress_adapter, server


def _request(
    *,
    method: str = "POST",
    body: dict[str, Any] | str | None = None,
) -> Any:
    request = Mock(spec=["method", "json"])
    request.method = method

    async def _json() -> Any:
        if isinstance(body, str):
            return json.loads(body)
        return body if body is not None else {}

    request.json = _json
    return request


def _json_body(response: Any) -> dict[str, Any]:
    return json.loads(response.body)


def test_kpress_export_rejects_non_post(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    response = asyncio.run(server.api_kpress_export(_request(method="GET")))
    assert response.status_code == 405


def test_kpress_export_rejects_deferred_single_file_mode(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    (tmp_path / "doc.md").write_text("# Doc\n")
    response = asyncio.run(
        server.api_kpress_export(
            _request(
                body={"path": "doc.md", "destination": "out.html", "export_mode": "single-file"}
            )
        )
    )
    assert response.status_code == 400
    payload = _json_body(response)
    assert payload["type"] == "kpress_export_error"
    assert "deferred" in payload["error"]


def test_kpress_export_rejects_unknown_export_mode(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    (tmp_path / "doc.md").write_text("# Doc\n")
    response = asyncio.run(
        server.api_kpress_export(
            _request(body={"path": "doc.md", "destination": "out.html", "export_mode": "magic"})
        )
    )
    assert response.status_code == 400
    assert "export_mode" in _json_body(response)["error"]


def test_kpress_export_rejects_inline_asset_mode(tmp_path: Path) -> None:
    """`asset_mode=inline` is currently part of the deferred single-file path."""

    server._set_root_dir(tmp_path)
    (tmp_path / "doc.md").write_text("# Doc\n")
    response = asyncio.run(
        server.api_kpress_export(
            _request(body={"path": "doc.md", "destination": "out.html", "asset_mode": "inline"})
        )
    )
    assert response.status_code == 400
    assert "asset_mode" in _json_body(response)["error"]


def test_kpress_export_rejects_missing_destination(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    (tmp_path / "doc.md").write_text("# Doc\n")
    response = asyncio.run(server.api_kpress_export(_request(body={"path": "doc.md"})))
    assert response.status_code == 400
    assert "destination" in _json_body(response)["error"]


def test_kpress_export_rejects_path_traversal_on_source(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    response = asyncio.run(
        server.api_kpress_export(_request(body={"path": "../escape.md", "destination": "out.html"}))
    )
    assert response.status_code == 404


def test_kpress_export_rejects_path_traversal_on_destination(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    (tmp_path / "doc.md").write_text("# Doc\n")
    response = asyncio.run(
        server.api_kpress_export(_request(body={"path": "doc.md", "destination": "../escape.html"}))
    )
    assert response.status_code == 400
    assert "destination" in _json_body(response)["error"].lower()


def test_kpress_export_delegates_to_adapter_and_returns_report(tmp_path: Path, monkeypatch) -> None:
    """Happy path: validated request becomes a KPressExportRequest, adapter is called,
    its dict is returned to the caller verbatim under `report`."""

    server._set_root_dir(tmp_path)
    source = tmp_path / "docs" / "report.md"
    source.parent.mkdir()
    source.write_text("# Report\n\nBody.\n")

    seen: list[Any] = []

    def _export(req: Any) -> dict[str, object]:
        seen.append(req)
        return {"schema_version": "kpress-build-1", "files": [], "routes": {}}

    monkeypatch.setattr(kpress_adapter, "export_kpress_document", _export)
    response = asyncio.run(
        server.api_kpress_export(
            _request(
                body={
                    "path": "docs/report.md",
                    "destination": "public/report.html",
                    "view": "rendered",
                    "profile": "document",
                    "export_mode": "page",
                    "asset_mode": "linked",
                    "optimize": True,
                    "theme_mode": "light",
                }
            )
        )
    )

    assert response.status_code == 200
    payload = _json_body(response)
    assert payload["type"] == "kpress-export-report"
    assert payload["report"] == {"schema_version": "kpress-build-1", "files": [], "routes": {}}
    # The destination string is the resolved absolute path.
    assert payload["destination"].endswith("public/report.html")

    assert len(seen) == 1
    request = seen[0]
    assert request.path == str(source)
    assert request.print_profile == "document"
    assert request.export_mode == "page"
    assert request.asset_mode == "linked"
    assert request.optimize is True
    assert request.theme_mode == "light"


def test_kpress_export_runs_against_released_runtime(tmp_path: Path) -> None:
    """Pin the route to the public KPress v0.2.2 export contract."""

    server._set_root_dir(tmp_path)
    (tmp_path / "doc.md").write_text("# Released runtime\n\nRendered by KPress.\n")

    response = asyncio.run(
        server.api_kpress_export(
            _request(
                body={
                    "path": "doc.md",
                    "destination": "public/doc.html",
                    "export_mode": "hashed-static-hosted",
                    "asset_mode": "hashed",
                }
            )
        )
    )

    assert response.status_code == 200
    payload = _json_body(response)
    assert payload["type"] == "kpress-export-report"
    output = tmp_path / "public" / "doc.html"
    assert output.is_file()
    assert "Released runtime" in output.read_text(encoding="utf-8")


def test_kpress_export_decompresses_gzip_source_for_released_runtime(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    source = tmp_path / "docs" / "compressed.md.gz"
    source.parent.mkdir()
    with gzip.open(source, "wt") as compressed:
        compressed.write("# Compressed export\n\n![Diagram](diagram.svg)\n")
    (source.parent / "diagram.svg").write_text("<svg></svg>\n", encoding="utf-8")

    response = asyncio.run(
        server.api_kpress_export(
            _request(
                body={
                    "path": "docs/compressed.md.gz",
                    "destination": "public/compressed.html",
                }
            )
        )
    )

    assert response.status_code == 200
    output = tmp_path / "public" / "compressed.html"
    assert "Compressed export" in output.read_text(encoding="utf-8")
    assert (output.parent / "diagram.svg").read_text(encoding="utf-8") == "<svg></svg>\n"


def test_kpress_export_decompresses_zlib_source_for_released_runtime(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    source = tmp_path / "docs" / "compressed.md.zlib"
    source.parent.mkdir()
    source.write_bytes(zlib.compress(b"# Zlib export\n\n![Diagram](diagram.svg)\n"))
    (source.parent / "diagram.svg").write_text("<svg></svg>\n", encoding="utf-8")

    response = asyncio.run(
        server.api_kpress_export(
            _request(
                body={
                    "path": "docs/compressed.md.zlib",
                    "destination": "public/compressed.html",
                }
            )
        )
    )

    assert response.status_code == 200
    output = tmp_path / "public" / "compressed.html"
    assert "Zlib export" in output.read_text(encoding="utf-8")
    assert (output.parent / "diagram.svg").read_text(encoding="utf-8") == "<svg></svg>\n"


def test_kpress_export_rejects_malformed_and_oversize_zlib_sources(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    (tmp_path / "broken.md.zlib").write_bytes(b"not a zlib stream")
    oversize = b"# Oversize\n" + b"x" * server._TEXT_PREVIEW_MAX_CHUNK_BYTES
    (tmp_path / "oversize.md.zlib").write_bytes(zlib.compress(oversize))

    malformed_response = asyncio.run(
        server.api_kpress_export(
            _request(body={"path": "broken.md.zlib", "destination": "broken.html"})
        )
    )
    oversize_response = asyncio.run(
        server.api_kpress_export(
            _request(body={"path": "oversize.md.zlib", "destination": "oversize.html"})
        )
    )

    assert malformed_response.status_code == 400
    assert _json_body(malformed_response)["type"] == "kpress_export_error"
    assert oversize_response.status_code == 413
    assert _json_body(oversize_response)["max_size"] == server._TEXT_PREVIEW_MAX_CHUNK_BYTES


def test_kpress_export_render_error_returns_502(tmp_path: Path, monkeypatch) -> None:
    server._set_root_dir(tmp_path)
    (tmp_path / "doc.md").write_text("# Doc\n")

    def _boom(_req: Any) -> Any:
        raise kpress_adapter.KPressRenderError("render pipeline raised")

    monkeypatch.setattr(kpress_adapter, "export_kpress_document", _boom)
    response = asyncio.run(
        server.api_kpress_export(_request(body={"path": "doc.md", "destination": "out.html"}))
    )
    assert response.status_code == 502
    assert _json_body(response)["type"] == "kpress_export_error"
