"""The PDF plugin's preview routes, in process: who gets a drawn preview, and what the image
answer carries.

Threat model T7: an untrusted source's PDF is drawn only inside an OS sandbox. The probe
that finds the platform's is replaced here (``set_sandbox_probe``), so each case runs the
same on macOS and Linux: "no sandbox" as Linux has, and a stand-in that confines nothing
where a case needs a drawn preview of an untrusted source. That the real sandbox confines
the child is ``tests/test_pdf_preview_sandbox.py``'s.
"""

from __future__ import annotations

import asyncio
import struct
import subprocess
import zlib
from collections.abc import AsyncGenerator, Iterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import pytest
from httpx2 import ASGITransport, AsyncClient

from metabrowser import paths_safe
from metabrowser.builtin_plugins.pdf import preview, preview_isolation, sidekick
from metabrowser.builtin_plugins.pdf.preview_isolation import Sandbox
from metabrowser.capabilities import UNTRUSTED_CAPABILITIES, set_capabilities
from metabrowser.paths_safe import _set_root_dir
from metabrowser.server import app
from metabrowser.source import AttachedFilesystemSubject, attach_subject, reset_source_session
from tests.git_pin_harness import git_env
from tests.required_tools import require_git
from tests.test_pdf_surfaces_session import _PDF

_STAND_IN = Sandbox(name="stand-in", prefix=())


async def _none() -> Sandbox | None:
    return None


async def _stand_in() -> Sandbox | None:
    return _STAND_IN


@pytest.fixture(autouse=True)
def _fresh_previews(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:  # pyright: ignore[reportUnusedFunction]
    monkeypatch.setenv("METABROWSER_CACHE_DIR", str(tmp_path / "cache"))
    preview.reset_for_tests()
    preview_isolation.set_sandbox_probe(_none)
    yield
    preview_isolation.set_sandbox_probe(None)
    preview.reset_for_tests()


@asynccontextmanager
async def _client(root: Path) -> AsyncGenerator[AsyncClient]:
    original = paths_safe.ROOT_DIR
    _set_root_dir(root)
    attach_subject(AttachedFilesystemSubject(root))
    try:
        async with app.router.lifespan_context(app):
            transport = ASGITransport(app=app, raise_app_exceptions=True)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                yield client
    finally:
        reset_source_session()
        _set_root_dir(original)


def _folder(tmp_path: Path) -> Path:
    root = tmp_path / "folder"
    root.mkdir()
    (root / "report.pdf").write_bytes(_PDF)
    return root


async def _preview(client: AsyncClient, **params: str) -> dict[str, Any]:
    answer = await client.get("/api/plugin/pdf/preview", params=params)
    assert answer.status_code == 200, answer.text
    assert answer.headers["cache-control"] == "no-store"
    return answer.json()


def test_a_drawn_preview_is_an_image_with_its_headers(tmp_path: Path) -> None:
    async def run() -> None:
        async with _client(_folder(tmp_path)) as client:
            ready = await _preview(client, path="report.pdf")
            assert ready["status"] == "ready" and ready["rendered"] is True
            image = await client.get(ready["image"])
            assert image.status_code == 200
            assert image.headers["content-type"] == "image/png"
            assert image.headers["cache-control"] == "private, max-age=31536000, immutable"
            for name, value in sidekick.IMAGE_HEADERS.items():
                assert image.headers[name.lower()] == value, name
            facts = preview.png_facts(image.content)
            assert (facts.width, facts.height, facts.pages) == (480, 320, 1)
            # The image data decodes to rows of the drawn page: filter 0, then RGB.
            idat = image.content.index(b"IDAT")
            (length,) = struct.unpack(">I", image.content[idat - 4 : idat])
            raw = zlib.decompress(image.content[idat + 4 : idat + 4 + length])
            assert len(raw) == 320 * (1 + 480 * 3)
            assert raw[0] == 0
            # Every error answer carries the image headers too.
            for key, status in (("bad", 400), ("0" * 64, 404)):
                refused = await client.get("/api/plugin/pdf/preview-image", params={"key": key})
                assert refused.status_code == status
                assert (
                    refused.headers["content-security-policy"]
                    == (sidekick.IMAGE_HEADERS["Content-Security-Policy"])
                )
                assert refused.headers["x-content-type-options"] == "nosniff"

    asyncio.run(run())


def test_an_untrusted_folder_is_drawn_only_in_a_sandbox(tmp_path: Path) -> None:
    root = _folder(tmp_path)

    async def run() -> None:
        set_capabilities(UNTRUSTED_CAPABILITIES)
        async with _client(root) as client:
            refused = await _preview(client, path="report.pdf")
            assert refused["reason"] == "no_sandbox"
            assert refused["message"] == preview.REASON_MESSAGES["no_sandbox"]
            # Nothing was drawn or kept.
            assert not (tmp_path / "cache/plugins/pdf/previews").exists() or not any(
                (tmp_path / "cache/plugins/pdf/previews").iterdir()
            )
            preview_isolation.set_sandbox_probe(_stand_in)
            drawn = await _preview(client, path="report.pdf")
            assert drawn["status"] == "ready" and drawn["rendered"] is True

    asyncio.run(run())


def test_a_blob_is_never_trusted_and_is_keyed_by_its_object_id(tmp_path: Path) -> None:
    require_git()
    root = _folder(tmp_path)
    env = git_env(tmp_path)
    subprocess.run(["git", "init", "-q", str(root)], check=True, env=env)
    oid = subprocess.run(
        ["git", "-C", str(root), "hash-object", "-w", "report.pdf"],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    ).stdout.strip()

    async def run() -> None:
        async with _client(root) as client:
            # The trusted folder's file is drawn bare; its blob is refused without a sandbox.
            by_path = await _preview(client, path="report.pdf")
            assert by_path["status"] == "ready"
            assert (await _preview(client, oid=oid))["reason"] == "no_sandbox"
            preview_isolation.set_sandbox_probe(_stand_in)
            by_blob = await _preview(client, oid=oid)
            assert by_blob["status"] == "ready" and by_blob["key"] != by_path["key"]
            assert (await _preview(client, oid=oid))["rendered"] is False
            invalid = await client.get("/api/plugin/pdf/preview", params={"oid": "abc"})
            assert invalid.status_code == 400
            both = await client.get(
                "/api/plugin/pdf/preview", params={"oid": oid, "path": "report.pdf"}
            )
            assert both.status_code == 400

    asyncio.run(run())


def test_a_bound_is_a_reason_and_a_failure_is_remembered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _folder(tmp_path)
    (root / "slow.pdf").write_bytes(_PDF.replace(b"0.2 0.4", b"0.3 0.4"))

    async def run() -> None:
        async with _client(root) as client:
            monkeypatch.setattr(sidekick, "MAX_INPUT_BYTES", len(_PDF) - 1)
            assert (await _preview(client, path="report.pdf"))["reason"] == "too_large"
            monkeypatch.setattr(sidekick, "MAX_INPUT_BYTES", preview.MAX_INPUT_BYTES)
            # A render past the deadline is killed and refused, and not tried again until
            # FAILURE_RETRY_SECONDS have passed.
            monkeypatch.setattr(preview, "RENDER_DEADLINE_SECONDS", 0.001)
            assert (await _preview(client, path="slow.pdf"))["reason"] == "timed_out"
            monkeypatch.setattr(preview, "RENDER_DEADLINE_SECONDS", 10.0)
            assert (await _preview(client, path="slow.pdf"))["reason"] == "timed_out"

    asyncio.run(run())
