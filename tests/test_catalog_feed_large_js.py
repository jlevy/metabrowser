"""Large-catalog scheduling contract for the production Quick File modules."""

from __future__ import annotations

import subprocess
from pathlib import Path

from tests.required_tools import require_node

CATALOG_FEED_LARGE_TEST_JS = (
    Path(__file__).resolve().parent / "dom" / "catalog-feed-large-session.js"
)


def test_large_catalog_feed_js_assertions_pass() -> None:
    require_node()
    result = subprocess.run(
        ["node", "--expose-gc", str(CATALOG_FEED_LARGE_TEST_JS)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, (
        "large catalog-feed assertions failed:\n"
        f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    assert '"catalogRows": 300000' in result.stdout, f"unexpected stdout: {result.stdout!r}"
    assert '"initialBulkWorkItems": 300003' in result.stdout
