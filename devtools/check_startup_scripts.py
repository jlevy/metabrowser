"""Hold the startup-script budget: what the shell fetches before it can paint a tree.

A script the shell loads with a blocking ``<script>`` tag is fetched, parsed, and
evaluated on every page load, before the first tree row, whether or not anything on the
page uses it. ``explorations/performance-loop/performance-budgets.toml`` gates that
cost as ``startup_script_requests`` and ``startup_script_transfer_kb``. The gate is
applied by ``run.py compare`` to browser captures, which nothing runs on an ordinary
change, and the v0.12 stack crossed it by 12 KB without anyone seeing: a new module
joined the shell's script tags and three others grew. This check is the same budget on
every ``make lint-check``.

**What it measures.** The scripts in the HTML the server renders for a folder's shell
that the browser requests before ``DOMContentLoaded``: every ``<script src>`` that is
not ``async``, ``defer``, or a module, outside ``/static/vendor/``, read from the same
shell ``server.index`` serves. For each it takes the bytes the server sends, the file
compressed as the application's gzip middleware compresses it, and adds the 300 bytes
Resource Timing reports for a response's headers.

**How that relates to the browser's number.** It is the browser's number. The gate's
probe sums ``transferSize`` over those requests, and Chrome reports ``transferSize`` as
the encoded body plus a fixed 300 bytes, not the headers' real length. Measured
2026-10-01 in Chrome 152 on a folder's shell: 20 requests and 176,984 bytes from the
probe, 20 and 176,984 from this check, script for script. ``tests/
test_check_startup_scripts.py`` holds the other half, that the compressed size computed
here is the body the running application sends.

What this cannot see is a script some other script requests before
``DOMContentLoaded``. A folder's shell has none. A page that loads at a pull-request
address starts one, ``pull-route.js``, on purpose, and a pinned revision's shell adds
``git-path.js``; neither is the directory shell the budget is calibrated on.

**The limits** are read from the budget file. There is no second copy here to drift.

Run it through ``make lint-check``. When it fails it lists the scripts by size, because
the fix is to move code out of one of them or behind the first usable tree: see "Asset
Loading Tiers" in ``docs/development.md``.
"""

from __future__ import annotations

import asyncio
import gzip
import sys
import tomllib
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
BUDGETS = ROOT / "explorations" / "performance-loop" / "performance-budgets.toml"
REQUESTS_METRIC = "startup_script_requests"
TRANSFER_METRIC = "startup_script_transfer_kb"

# What Resource Timing adds to a response's encoded body to make ``transferSize``: a
# fixed allowance for the headers, defined by the specification so that a page cannot
# read their real length. It is a property of the measurement, not a budget.
RESOURCE_TIMING_HEADER_BYTES = 300
VENDOR_PREFIX = "/static/vendor/"
STATIC_PREFIX = "/static/"


@dataclass(frozen=True, slots=True)
class StartupScript:
    """One script the shell requests before ``DOMContentLoaded``."""

    url_path: str
    decoded_bytes: int
    transfer_bytes: int


@dataclass(frozen=True, slots=True)
class Limits:
    """The two ceilings the budget file sets on the startup scripts."""

    requests: int
    transfer_kb: int


class _BlockingScripts(HTMLParser):
    """Collect the ``src`` of every parser-blocking script, in document order."""

    def __init__(self) -> None:
        super().__init__()
        self.sources: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "script":
            return
        attributes = dict(attrs)
        source = attributes.get("src")
        if not source:
            return
        if "async" in attributes or "defer" in attributes or attributes.get("type") == "module":
            return
        self.sources.append(source)


def startup_script_paths(html: str) -> list[str]:
    """The URL paths of the scripts *html* makes a browser request before it is parsed.

    The gate's probe leaves out ``/static/vendor/``, which it reports as its own tier,
    and so does this.
    """

    parser = _BlockingScripts()
    parser.feed(html)
    paths = [urlsplit(source).path for source in parser.sources]
    return [path for path in paths if not path.startswith(VENDOR_PREFIX)]


def render_folder_shell() -> str:
    """The shell exactly as the server renders it for a folder."""

    from metabrowser import server

    # ``index`` reads the request only on a pinned revision's branch.
    response = asyncio.run(server.index(cast(Any, None)))
    return bytes(response.body).decode("utf-8")


def _gzip_settings() -> tuple[int, int]:
    """The compression level and the size floor of the application's gzip middleware."""

    from starlette.middleware.gzip import GZipMiddleware

    from metabrowser import server

    for middleware in server.app.user_middleware:
        if middleware.cls is GZipMiddleware:
            options = cast("dict[str, Any]", middleware.kwargs)
            return int(options["compresslevel"]), int(options["minimum_size"])
    raise SystemExit("the application has no gzip middleware; this check measures its output")


def sent_body_bytes(content: bytes) -> int:
    """How many bytes the application sends for *content* to a client that accepts gzip."""

    level, minimum_size = _gzip_settings()
    if len(content) < minimum_size:
        return len(content)
    return len(gzip.compress(content, compresslevel=level))


def measure(html: str) -> list[StartupScript]:
    """Every startup script of *html* with its decoded and transferred size."""

    from metabrowser import server

    scripts: list[StartupScript] = []
    for url_path in startup_script_paths(html):
        if not url_path.startswith(STATIC_PREFIX):
            raise SystemExit(
                f"startup script {url_path} is not under {STATIC_PREFIX}; "
                "this check cannot read what the server would send for it"
            )
        content = (server.STATIC_DIR / url_path.removeprefix(STATIC_PREFIX)).read_bytes()
        scripts.append(
            StartupScript(
                url_path=url_path,
                decoded_bytes=len(content),
                transfer_bytes=sent_body_bytes(content) + RESOURCE_TIMING_HEADER_BYTES,
            )
        )
    return scripts


def transfer_kb(scripts: list[StartupScript]) -> int:
    """The gate's number: transferred bytes in KiB, rounded as the probe's ``Math.round``."""

    return int(sum(script.transfer_bytes for script in scripts) / 1024 + 0.5)


def load_limits() -> Limits:
    """The gate's ceilings, from the budget file and nowhere else."""

    metrics = tomllib.loads(BUDGETS.read_text(encoding="utf-8"))["metrics"]
    return Limits(
        requests=int(metrics[REQUESTS_METRIC]["maximum"]),
        transfer_kb=int(metrics[TRANSFER_METRIC]["maximum"]),
    )


def problems(scripts: list[StartupScript], limits: Limits) -> list[str]:
    """What exceeds a ceiling, in words a reader can act on; empty when nothing does."""

    found: list[str] = []
    if len(scripts) > limits.requests:
        found.append(
            f"{REQUESTS_METRIC}: the shell requests {len(scripts)} scripts before "
            f"DOMContentLoaded; the budget is {limits.requests}"
        )
    measured = transfer_kb(scripts)
    if measured > limits.transfer_kb:
        total = sum(script.transfer_bytes for script in scripts)
        found.append(
            f"{TRANSFER_METRIC}: the shell transfers {measured} KB ({total:,} bytes) of "
            f"script before DOMContentLoaded; the budget is {limits.transfer_kb} KB"
        )
    return found


def main() -> int:
    scripts = measure(render_folder_shell())
    limits = load_limits()
    found = problems(scripts, limits)
    total = sum(script.transfer_bytes for script in scripts)
    summary = (
        f"startup scripts: {len(scripts)} requests of {limits.requests}, "
        f"{transfer_kb(scripts)} KB of {limits.transfer_kb} KB transferred ({total:,} bytes)"
    )
    if not found:
        print(summary)
        return 0
    print("Startup-script budget exceeded:", file=sys.stderr)
    for problem in found:
        print(f"  {problem}", file=sys.stderr)
    print("  by size:", file=sys.stderr)
    for script in sorted(scripts, key=lambda item: item.transfer_bytes, reverse=True):
        print(
            f"    {script.transfer_bytes:>7,} transferred  {script.decoded_bytes:>7,} decoded  "
            f"{script.url_path}",
            file=sys.stderr,
        )
    print(
        "  Move code that the first tree does not need out of these scripts; see "
        '"Asset Loading Tiers" in docs/development.md.',
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
