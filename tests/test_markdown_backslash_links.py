"""A Markdown link to a file whose POSIX name holds a backslash, end to end.

A served folder lists ``a\\b.md`` as ``a%5Cb.md`` (the inventory's escape). Markdown
writes ``[x](a\\b.md)`` as the address ``a%5Cb.md``; the production link resolver
(``builtin_plugins/markdown/links.js``) turns that address into the path the tree
listed, and the file route serves that path. Each step runs on the real served folder:
``metab --api`` for the tree, the render, and the file, and node for the resolver on the
address the render carries. Under the untrusted profile the inert allowlist drops an
escaped backslash from the address instead.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import quote

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
LINKS_JS = REPO_ROOT / "src" / "metabrowser" / "builtin_plugins" / "markdown" / "links.js"

pytestmark = [
    pytest.mark.skipif(os.name == "nt", reason="a Windows name cannot hold a backslash"),
    pytest.mark.skipif(shutil.which("node") is None, reason="node not available"),
]

_RESOLVE = r"""
const [linksUrl, sourcePath, authoredTarget] = process.argv.slice(1);
import(linksUrl).then(({ resolveStandardTarget }) => {
  process.stdout.write(JSON.stringify(resolveStandardTarget({
    action: "navigate", authoredTarget, sourcePath, syntax: "markdown",
  })));
});
"""


def _api(root: Path, home: Path, route: str, *flags: str) -> tuple[int, Any]:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from metabrowser.cli.entrypoint import main; main()",
            str(root),
            *flags,
            "--api",
            route,
        ],
        env={**os.environ, "METABROWSER_HOME": str(home)},
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    status = re.search(r"^status: (\d+)$", result.stdout, re.MULTILINE)
    assert status, f"stdout={result.stdout!r} stderr={result.stderr!r}"
    return int(status.group(1)), json.loads(result.stdout[result.stdout.index("{") :])


def _resolve(source_path: str, authored_target: str) -> dict[str, Any]:
    result = subprocess.run(
        ["node", "-e", _RESOLVE, LINKS_JS.as_uri(), source_path, authored_target],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    return json.loads(result.stdout)


def _hrefs(html: str) -> list[str]:
    return re.findall(r'<a href="([^"]*)"', html)


def test_a_backslash_link_opens_the_file_the_folder_lists(tmp_path: Path) -> None:
    root = tmp_path / "served"
    root.mkdir()
    (root / "a\\b.md").write_text("# Odd name\n", encoding="utf-8")
    (root / "README.md").write_text("[x](a\\b.md)\n", encoding="utf-8")
    home = tmp_path / "home"

    status, tree = _api(root, home, "/api/tree")
    assert status == 200
    listed = sorted(entry["path"] for entry in tree["tree"])
    assert listed == ["README.md", "a%5Cb.md"]

    status, rendered = _api(root, home, "/api/kpress/render?path=README.md&view=document")
    assert status == 200
    assert _hrefs(rendered["html"]) == ["a%5Cb.md"]

    resolved = _resolve("README.md", _hrefs(rendered["html"])[0])
    assert resolved == {"status": "internal", "path": "a%5Cb.md"}

    status, served = _api(root, home, f"/api/file?path={quote(resolved['path'], safe='')}")
    assert status == 200
    assert served["content"] == "# Odd name\n"

    # Under the untrusted profile the inert allowlist drops the escaped backslash.
    status, inert = _api(
        root, home, "/api/kpress/render?path=README.md&view=document", "--untrusted"
    )
    assert status == 200
    assert inert["inert"] is True
    assert _hrefs(inert["html"]) == []
    assert "<a>x</a>" in inert["html"]
