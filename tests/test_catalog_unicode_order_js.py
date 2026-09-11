"""Cross-runtime catalog ordering contract for the production browser modules."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

CATALOG_UNICODE_ORDER_TEST_JS = (
    Path(__file__).resolve().parent / "dom" / "catalog-unicode-order-session.js"
)


def test_catalog_unicode_order_js_assertions_pass() -> None:
    if shutil.which("node") is None:
        pytest.skip("node not available")
    result = subprocess.run(
        ["node", str(CATALOG_UNICODE_ORDER_TEST_JS)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env={**os.environ, "METABROWSER_TEST_UNICODE_FILES_PER_PREFIX": "100000"},
    )
    assert result.returncode == 0, (
        "catalog Unicode-order assertions failed:\n"
        f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    assert result.stdout.startswith("{"), f"unexpected stdout: {result.stdout!r}"
