"""Static export seam delegates to KPress publisher APIs."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from kpress.errors import (
    KPressInvalidRequestError as RuntimeInvalidRequestError,
)
from kpress.errors import (
    KPressOptimizerError,
    KPressPublishError,
)
from kpress.errors import (
    KPressRenderError as RuntimeRenderError,
)
from kpress.models import KPressExportRequest

from metabrowser import kpress_adapter


def _runtime_ns(export_document: object) -> SimpleNamespace:
    """Build a stand-in `_kpress_runtime` exposing the error classes the adapter
    references in its `except` clauses, plus the supplied `export_document`."""

    return SimpleNamespace(
        KPressInvalidRequestError=RuntimeInvalidRequestError,
        KPressPublishError=KPressPublishError,
        KPressRenderError=RuntimeRenderError,
        export_document=export_document,
    )


def test_metabrowser_adapter_does_not_import_optional_kpress_publish_modules() -> None:
    code = """
import json
import sys

import metabrowser.kpress_adapter

forbidden = (
    "kpress.publish",
    "kpress.publish.optimize",
    "kpress.format.pdf",
)
print(json.dumps({name: name in sys.modules for name in forbidden}, sort_keys=True))
"""
    completed = subprocess.run(
        [sys.executable, "-c", code],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(completed.stdout) == {
        "kpress.format.pdf": False,
        "kpress.publish": False,
        "kpress.publish.optimize": False,
    }


def test_kpress_export_request_captures_static_publish_options() -> None:
    req = KPressExportRequest(
        path="docs/readme.md",
        kind="markdown",
        view="rendered",
        print_profile="document",
        theme_mode="system",
        export_mode="hashed-static-hosted",
        asset_mode="hashed",
        optimize=True,
        destination=Path("public/readme.html"),
    )
    assert req.path == "docs/readme.md"
    assert req.print_profile == "document"
    assert req.export_mode == "hashed-static-hosted"
    assert req.asset_mode == "hashed"
    assert req.optimize is True


def test_export_kpress_document_delegates_to_publish_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[KPressExportRequest] = []

    def export_document(request: KPressExportRequest) -> dict[str, object]:
        seen.append(request)
        return {"ok": True, "path": request.path}

    monkeypatch.setattr(kpress_adapter, "_kpress_runtime", _runtime_ns(export_document))

    req = KPressExportRequest(
        path="doc.md",
        kind="markdown",
        view="rendered",
    )
    assert kpress_adapter.export_kpress_document(req) == {"ok": True, "path": "doc.md"}
    assert seen == [req]


def test_export_kpress_document_requires_publisher_api(monkeypatch: pytest.MonkeyPatch) -> None:
    def export_document(_request: KPressExportRequest) -> None:
        raise RuntimeRenderError("document export API unavailable")

    monkeypatch.setattr(kpress_adapter, "_kpress_runtime", _runtime_ns(export_document))
    req = KPressExportRequest(path="doc.md", kind="markdown", view="rendered")
    with pytest.raises(kpress_adapter.KPressRenderError, match="document export API"):
        kpress_adapter.export_kpress_document(req)


def test_export_kpress_document_translates_publish_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """A publish-pipeline failure (KPressPublishError, a sibling of
    KPressRenderError) must be translated to the adapter's render error so the
    export route returns a structured 502 rather than an unhandled 500."""

    def export_document(_request: KPressExportRequest) -> None:
        raise KPressOptimizerError("optimizer backend unavailable")

    monkeypatch.setattr(kpress_adapter, "_kpress_runtime", _runtime_ns(export_document))
    req = KPressExportRequest(path="doc.md", kind="markdown", view="rendered")
    with pytest.raises(kpress_adapter.KPressRenderError, match="optimizer backend"):
        kpress_adapter.export_kpress_document(req)


def test_export_kpress_document_translates_invalid_request(monkeypatch: pytest.MonkeyPatch) -> None:
    def export_document(_request: KPressExportRequest) -> None:
        raise RuntimeInvalidRequestError("bad export destination")

    monkeypatch.setattr(kpress_adapter, "_kpress_runtime", _runtime_ns(export_document))
    req = KPressExportRequest(path="doc.md", kind="markdown", view="rendered")
    with pytest.raises(kpress_adapter.KPressInvalidRequestError, match="bad export destination"):
        kpress_adapter.export_kpress_document(req)
