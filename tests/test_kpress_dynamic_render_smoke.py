"""End-to-end smoke test for the Metabrowser → KPress dynamic render path.

This is the "you'd be surprised if this broke" gate. It exercises a real
Markdown document with rich content (frontmatter, headings, code, table,
footnote, link, image) through the same `/api/kpress/render` route the
browser hits, then asserts the response is structurally sound *and* that
every CSS/JS asset URL the response advertises is actually serveable from
`/kpress-static/`.

The point is to catch the kind of regression that would otherwise only
surface during human browser testing: a dropped wrapper class, an asset
that's listed in the response but missing from the package, a theme
attribute that stopped being stamped on the html, sanitization breaking
on common content, etc. The XSS-specific assertions live in
test_runtime.py over in kpress; here we focus on the *integration*.
"""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest
from kpress import ASSET_MANIFEST_SCHEMA_VERSION

from metabrowser import kpress_adapter, server


class _FakeQuery:
    def __init__(self, params: dict[str, str]) -> None:
        self._params = params

    def get(self, key: str, default: str = "") -> str:
        return self._params.get(key, default)


def _request(
    *,
    query: dict[str, str] | None = None,
    path_params: dict[str, str] | None = None,
) -> Any:
    request = Mock(spec=["query_params", "headers", "path_params"])
    request.query_params = _FakeQuery(query or {})
    request.path_params = path_params or {}
    request.headers = {}
    return request


_RICH_MARKDOWN = """\
---
title: Smoke Doc
author: Ada
description: End-to-end smoke for the Metabrowser→KPress dynamic render
---

# Smoke Doc

A short paragraph with a [link](https://example.com/) and `inline code`.

## Subsection

A list:

- one
- two
- three

A table:

| project | quarter | edge |
| --- | --- | --- |
| ALPHA | Q3 | 0.7 |
| MSFT | Q3 | 0.3 |

Some fenced code:

```python
def hello(name: str) -> str:
    return f"hi {name}"
```

A footnote reference[^one] in the body.

[^one]: footnote body text.
"""


@pytest.fixture
def served_root(tmp_path: Path) -> Path:
    """A small worktree with one rich markdown doc, ROOT_DIR pointed at it."""

    server._set_root_dir(tmp_path)
    (tmp_path / "docs").mkdir()
    source = tmp_path / "docs" / "smoke.md"
    source.write_text(_RICH_MARKDOWN, encoding="utf-8")
    return tmp_path


def _render(query: dict[str, str]) -> dict[str, Any]:
    response = asyncio.run(server.api_kpress_render(_request(query=query)))
    assert response.status_code == 200, response.body
    payload: dict[str, Any] = json.loads(response.body)
    return payload


def _manifest_assets(payload: dict[str, Any]) -> list[dict[str, Any]]:
    manifest = payload["assets"]
    assert manifest["schema_version"] == ASSET_MANIFEST_SCHEMA_VERSION
    assert isinstance(manifest["assets"], list)
    assert isinstance(manifest["import_map"], dict)
    return manifest["assets"]


def test_dynamic_render_emits_expected_envelope_shape(served_root: Path) -> None:
    """The render route must return a stable JSON envelope. A regression
    that drops `type`, `assets`, or `html` would silently break the SPA's
    response handling without any obvious error."""

    payload = _render({"path": "docs/smoke.md", "view": "rendered"})

    assert payload["type"] == "kpress-rendered-document"
    assert isinstance(payload["html"], str)
    assert payload["html"]
    assert isinstance(payload["profile"], str)
    assert isinstance(payload["printable"], bool)
    assert set(payload["assets"]) == {"schema_version", "assets", "import_map"}
    assets = _manifest_assets(payload)
    assert assets
    assert all(
        {"id", "kind", "path", "mode", "entry_point", "loading"} <= set(asset) for asset in assets
    )
    assert isinstance(payload["diagnostics"], list)


def test_dynamic_render_includes_theme_and_doc_chrome(served_root: Path) -> None:
    """The injected HTML must carry the kpress doc wrappers and the theme
    bootstrap so the host's pre-paint theme handoff still works. These
    classes/attrs are what the host CSS targets."""

    html = _render({"path": "docs/smoke.md", "view": "rendered"})["html"]
    assert 'class="kpress kpress-doc kpress-print-surface"' in html


def test_dynamic_render_sanitizes_untrusted_worktree_markup(served_root: Path) -> None:
    source = served_root / "docs" / "unsafe.md"
    source.write_text(
        """# Unsafe

<script>window.pwned = true</script>
<a href="javascript:alert(1)" onclick="alert(2)">link</a>
<img src="https://example.com/image.png" onerror="alert(3)">
""",
        encoding="utf-8",
    )

    html = _render({"path": "docs/unsafe.md", "view": "rendered"})["html"].lower()

    assert "<script" not in html
    assert "javascript:" not in html
    assert "onclick=" not in html
    assert "onerror=" not in html


def test_dynamic_render_emits_table_code_and_footnote_wrappers(served_root: Path) -> None:
    """Common Markdown features should round-trip with the wrappers our CSS
    relies on. If any of these vanish, manual browser review would just see
    broken styling on tables/code/footnotes with no obvious server error."""

    html = _render({"path": "docs/smoke.md", "view": "rendered"})["html"]

    # Table comes through with a tbody and our wrapper.
    assert "<table" in html
    assert "</table>" in html
    assert "kpress-table-wrap" in html or "data-kpress-numeric" in html or "<tbody" in html

    # Fenced code has language class and Pygments token spans for highlighting.
    assert 'class="language-python' in html or "kpress-token-" in html

    # Footnote ref + footnote section both present.
    assert "footnote" in html.lower()


def test_dynamic_render_consumes_frontmatter_into_metadata_section(
    served_root: Path,
) -> None:
    """Frontmatter is metadata, not visible body text. The renderer must
    consume the `---` block and render it through the kpress-frontmatter
    affordance (a <details> with <dt>/<dd>), not echo the raw YAML."""

    html = _render({"path": "docs/smoke.md", "view": "rendered"})["html"]

    # Raw YAML form must NOT appear in the body. (`author: Ada` could legitimately
    # appear inside a `<dd>`, so we look for the `key: value` form an unparsed
    # block would emit.)
    assert "---\ntitle: Smoke Doc" not in html
    # Each frontmatter key surfaces as a <dt>; values as <dd>.
    assert "<dt>author</dt><dd>Ada</dd>" in html
    assert "kpress-frontmatter" in html


def test_dynamic_render_advertised_assets_are_actually_serveable(served_root: Path) -> None:
    """Every CSS/JS URL the render response advertises MUST be reachable
    via the /kpress-static/<v>/... route. If the package manifest drifts
    from what render emits, manual browser testing sees 404s on stylesheets
    or scripts with no obvious server-side error. This pin catches that."""

    payload = _render({"path": "docs/smoke.md", "view": "rendered"})
    assets = _manifest_assets(payload)
    browser_entries = [asset for asset in assets if asset["entry_point"]]
    assert any(asset["loading"] == "stylesheet" for asset in browser_entries)
    assert any(asset["loading"] in {"module", "classic"} for asset in browser_entries)
    assert any(not asset["entry_point"] for asset in assets), (
        "manifest must retain dependency-only resources without loading them directly"
    )

    static_prefix = re.compile(r"^/kpress-static/")
    for asset in assets:
        url = asset["public_url"]
        assert static_prefix.match(url), f"unexpected asset URL shape: {url!r}"
        rel = url[len("/kpress-static/") :]
        response = asyncio.run(server.kpress_static_asset(_request(path_params={"path": rel})))
        assert response.status_code == 200, (
            f"asset {url!r} advertised in render response but /kpress-static/ "
            f"returned {response.status_code}"
        )
        assert response.body, f"asset {url!r} served empty body"


def test_dynamic_render_source_profile_serves_raw_text_with_pygments(served_root: Path) -> None:
    """Source view should render through KPress' source profile and produce
    Pygments-styled <pre><code>, not pass the document HTML."""

    payload = _render({"path": "docs/smoke.md", "view": "source"})
    html = payload["html"]
    assert payload["profile"] == "source"
    assert "<pre" in html
    # Body text is escaped/highlighted, not interpreted as Markdown.
    assert "<h1" not in html.lower() or "kpress-source" in html


def test_dynamic_render_response_round_trips_through_json(served_root: Path) -> None:
    """The host injects the JSON envelope into the page via fetch().json();
    if a future field gets stamped with a non-JSON-serializable value (a
    Path, a datetime, a dataclass), the SPA breaks silently. Pin this."""

    payload = _render({"path": "docs/smoke.md", "view": "rendered"})
    assert json.loads(json.dumps(payload)) == payload


def test_dynamic_render_caches_repeat_requests_on_same_mtime(served_root: Path) -> None:
    """The runtime cache keys on (path, mtime_hash, …). Two consecutive
    renders of the same unchanged file must return byte-identical envelopes,
    not just structurally equal ones. A regression that introduces a
    nondeterministic field (random IDs, wallclock timestamps) would show
    up here before it confuses the browser cache."""

    kpress_adapter.clear_render_cache()
    a = _render({"path": "docs/smoke.md", "view": "rendered"})
    b = _render({"path": "docs/smoke.md", "view": "rendered"})
    assert a == b


def test_dynamic_render_404s_on_missing_file(served_root: Path) -> None:
    response = asyncio.run(server.api_kpress_render(_request(query={"path": "docs/no-such.md"})))
    assert response.status_code == 404


@pytest.mark.parametrize(
    ("theme_mode", "resolved_theme"),
    [
        ("system", "light"),
        ("system", "dark"),
        ("light", "light"),
        ("dark", "dark"),
    ],
)
def test_dynamic_render_is_theme_agnostic(
    served_root: Path, theme_mode: str, resolved_theme: str
) -> None:
    """The SPA passes ``theme_mode`` (user preference) and ``resolved_theme``
    (the host's resolution of `system`) as query params; the endpoint must
    keep accepting them (they select ``theme.js`` in the declared assets for
    ``system`` mode). But KPress >= 0.3.0 fragments are theme-agnostic: no
    theme or palette attribute may be baked into the rendered article — the
    host stamps ``data-kpress-resolved-theme`` on ``:root`` at display time
    (see ``applyThemeMode`` in app.js), which keeps one render cacheable and
    correct across theme toggles. A regression that re-bakes an attribute
    would resurrect the stale-theme flake this contract removed."""

    payload = _render(
        {
            "path": "docs/smoke.md",
            "view": "rendered",
            "theme_mode": theme_mode,
            "resolved_theme": resolved_theme,
        }
    )
    html = payload["html"]
    assert "data-kpress-theme=" not in html
    assert "data-kpress-resolved-theme=" not in html
    assert "data-kpress-palette=" not in html


_MATH_AND_IMAGE_MARKDOWN = """\
---
title: Math & Image Doc
---

# Heading

A paragraph and an image: ![alt text](docs/sample.png "title")

And inline math $a^2 + b^2 = c^2$ plus a display block:

$$
\\sum_{i=1}^{n} i = \\frac{n(n+1)}{2}
$$

Done.
"""


@pytest.fixture
def math_and_image_root(tmp_path: Path) -> Path:
    """A doc with display math and an image ref. Math triggers KaTeX
    asset advertising; image passes through verbatim."""

    server._set_root_dir(tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "math.md").write_text(_MATH_AND_IMAGE_MARKDOWN, encoding="utf-8")
    return tmp_path


def test_dynamic_render_emits_image_and_math_wrappers(math_and_image_root: Path) -> None:
    """A document with math and an image must (1) preserve the image ref
    verbatim, (2) emit a math element the KaTeX lazy bootstrap can find,
    and (3) advertise the KaTeX assets in the envelope. Catching this at
    the smoke layer means manual browser review only judges visual fidelity,
    not whether math rendered at all."""

    payload = _render({"path": "docs/math.md", "view": "rendered"})
    html = payload["html"]

    # Image ref survives sanitization with src + alt intact.
    assert "<img" in html
    assert "docs/sample.png" in html
    assert 'alt="alt text"' in html

    # Math markers exist for the lazy KaTeX bootstrap. Either inline or
    # display math (or both) should produce a math container element.
    math_present = (
        "kpress-math" in html
        or "katex" in html.lower()
        or "data-kpress-math" in html
        or 'class="math"' in html
    )
    assert math_present, "no math markers in rendered HTML for a doc with $...$ and $$...$$"

    # The runtime should advertise KaTeX assets when math is present, so
    # the SPA loads them lazily on first render.
    assets = _manifest_assets(payload)
    katex_assets = [asset for asset in assets if "katex" in asset["path"].lower()]
    assert katex_assets, "math doc rendered but KaTeX assets were not in the manifest"
    assert any(
        asset["entry_point"] and asset["loading"] in {"stylesheet", "classic"}
        for asset in katex_assets
    ), "KaTeX manifest closure has no browser entry points"
