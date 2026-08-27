"""Verify that the JS SDK helper ``fetchJsonl()`` calls a real route.

Regression coverage: ``plugin-sdk.js`` once advertised
``fetchJsonl(path)`` -> ``GET /api/jsonl?path=...`` but no such route
existed. Fixed by routing the helper through ``/api/file?path=...``,
which already returns ``{type: "jsonl", events, summary, ...}`` for
.jsonl files.

This test asserts:
1. ``/api/file`` returns ``type: "jsonl"`` for a .jsonl file (the
   contract fetchJsonl() depends on);
2. The static plugin-sdk.js wires the helper to ``/api/file``, not
   ``/api/jsonl``.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import Mock

from metabrowser import server

_AGENT_LOG = (
    '{"adapter":"claude","event":"init"}\n{"adapter":"claude","event":"message","text":"hi"}\n'
)


class _FakeQuery:
    def __init__(self, params: dict[str, str]) -> None:
        self._params = params

    def get(self, key: str, default: str = "") -> str:
        return self._params.get(key, default)


def test_api_file_returns_jsonl_envelope(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    log = tmp_path / "session.jsonl"
    log.write_text(_AGENT_LOG)

    request = Mock(spec=["query_params", "headers"])
    request.query_params = _FakeQuery({"path": "session.jsonl"})
    request.headers = {}

    response = asyncio.run(server.api_file(request))
    payload = json.loads(bytes(response.body))
    assert payload["type"] == "jsonl"
    # Envelope should carry events + summary so plugin code can do
    # something with it (the precise shape is part of the legacy
    # /api/file contract; we just confirm the keys exist).
    assert "summary" in payload
    assert "events" in payload


def test_plugin_sdk_fetchJsonl_uses_api_file() -> None:
    """The advertised SDK helper must hit a real endpoint."""
    sdk_js = (
        Path(__file__).resolve().parent.parent / "src" / "metabrowser" / "static" / "plugin-sdk.js"
    ).read_text()
    # Negative: no /api/jsonl reference (was the broken target)
    assert "/api/jsonl" not in sdk_js, (
        "fetchJsonl must not target /api/jsonl — that route doesn't exist"
    )
    # Positive: helper routes through /api/file
    assert "/api/file" in sdk_js
    # Helper still defined on window.metabrowser
    assert "fetchJsonl" in sdk_js
