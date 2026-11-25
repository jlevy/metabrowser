"""The wiki preprocessor's front matter ends where KPress's does.

``builtin_plugins/markdown/wiki-parser.js`` copies a document's leading front matter as
written and reads its body as Markdown, because KPress strips that block before it
renders a document (``_strip_leading_frontmatter`` in kpress/runtime.py). If the two
disagreed, the preprocessor would write anchors into text KPress strips, or leave
unread text KPress renders. ``frontMatterLength`` mirrors KPress's pattern; this checks
the two agree on every shape, so a change to either fails here.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from kpress.runtime import _strip_leading_frontmatter  # pyright: ignore[reportPrivateUsage]

from tests.required_tools import require_node

WIKI_PARSER = (
    Path(__file__).resolve().parent.parent
    / "src/metabrowser/builtin_plugins/markdown/wiki-parser.js"
)

SHAPES = (
    "---\ntitle: A\nbead: tide-k7m2\n---\n\n# Body\n",
    "---\r\ntitle: A\r\n---\r\nBody\r\n",
    "---\ntitle: A\n---",
    "---\ntitle: A\n----\nBody\n",
    "---\ntitle: A\n--- \nBody\n---\n",
    "---\n---\nBody\n---\nMore\n",
    "--- \ntitle: A\n---\nBody\n",
    "Body\n---\ntitle: A\n---\n",
    "---\ntitle: A\n",
    "---",
    "",
    "# Only a body\n",
)


def test_front_matter_ends_where_kpress_strips_it() -> None:
    script = (
        "const [url, shapes] = process.argv.slice(1);"
        "import(url).then((m) => console.log(JSON.stringify("
        "JSON.parse(shapes).map((s) => m.frontMatterLength(s)))));"
    )
    result = subprocess.run(
        [require_node(), "-e", script, WIKI_PARSER.as_uri(), json.dumps(SHAPES)],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    lengths = json.loads(result.stdout)
    expected = [len(shape) - len(_strip_leading_frontmatter(shape)) for shape in SHAPES]
    assert dict(zip(SHAPES, lengths, strict=True)) == dict(zip(SHAPES, expected, strict=True))
    assert expected[0] > 0 and expected[-1] == 0
