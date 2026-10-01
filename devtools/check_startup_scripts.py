"""Hold the startup-script budget: what the shell fetches before it can paint a tree.

A script the shell requests before ``DOMContentLoaded`` is fetched on every page load,
before the first tree row, whether or not anything on the page uses it.
``explorations/performance-loop/performance-budgets.toml`` gates that cost as
``startup_script_requests`` and ``startup_script_transfer_kb``. The gate is applied by
``run.py compare`` to browser captures, which nothing runs on an ordinary change, and
the v0.12 stack crossed it by 12 KB without anyone seeing: a new module joined the
shell's script tags and three others grew. This check is the same budget on every
``make lint-check``.

**What it counts.** The gate's probe counts every ``.js`` resource outside
``/static/vendor/`` whose request starts before ``DOMContentLoaded`` ends, however it
was requested. This check renders a folder's shell through the application, as a
browser's request for ``/view/`` does, and counts:

- every ``<script src>`` in it, whatever its attributes: an ``async`` or ``defer``
  script is requested as the parser meets it, the same as a blocking one. A module
  script fails the check, because its imports are requests no reading of the HTML shows.
- nothing else, and it proves there is nothing else: ``tests/dom/
  shell-startup-requests.js`` runs the shell's own scripts and its
  ``DOMContentLoaded`` handlers without a browser and reports every script a script
  asks for, through the asset loader, an appended element, a preload, or ``import()``.
  Any such request fails the check. It is not added to the total, because the session
  delivers no response and so cannot see what a requested script goes on to request.

For each script it takes the bytes the server sends, the file compressed as the
application's gzip middleware compresses it, and adds the 300 bytes Resource Timing
reports for a response's headers.

**How that relates to the browser's number.** It is the browser's number. The probe sums
``transferSize``, and Chrome reports ``transferSize`` as the encoded body plus a fixed
300 bytes, not the headers' real length. Measured 2026-10-01 in Chrome 152 on a folder's
shell: 20 requests and 176,984 bytes from the probe, 20 and 176,984 from this check,
script for script. ``tests/test_check_startup_scripts.py`` holds the two halves of that:
the compressed size computed here is the body the running application sends, and the
probe's own selection and rounding give this check's count and kilobytes.

**The shells it does not gate.** The budget is calibrated on a folder's page. Two other
shells carry one startup script more, and the summary reports each beside the budget
without failing on it: the page at a pull-request address (``pull-route.js``, rendered
here from the same folder server, whose answer at such an address is the page that says
it serves no pull request) and a pinned revision's page (``git-path.js``, which the
server names in ``PIN_STARTUP_SCRIPTS``; ``tests/test_serve_pin.py`` holds a real pin's
shell to that list). The session runs on the pull-request shell too, so a
script-initiated request there fails the check as well.

**The limits** are read from the budget file. There is no second copy here to drift.

Run it through ``make lint-check``. When it fails it lists the scripts by size, because
the fix is to move code out of one of them or behind the first usable tree: see "Asset
Loading Tiers" in ``docs/development.md``.
"""

from __future__ import annotations

import asyncio
import gzip
import json
import shutil
import subprocess
import sys
import tempfile
import tomllib
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
BUDGETS = ROOT / "explorations" / "performance-loop" / "performance-budgets.toml"
SESSION = ROOT / "tests" / "dom" / "shell-startup-requests.js"
REQUESTS_METRIC = "startup_script_requests"
TRANSFER_METRIC = "startup_script_transfer_kb"

# What Resource Timing adds to a response's encoded body to make ``transferSize``: a
# fixed allowance for the headers, defined by the specification so that a page cannot
# read their real length. It is a property of the measurement, not a budget.
RESOURCE_TIMING_HEADER_BYTES = 300
VENDOR_PREFIX = "/static/vendor/"
STATIC_PREFIX = "/static/"
# The folder shell the budget is calibrated on, and a pull-request address, whose shell
# carries that page's routes.
FOLDER_ADDRESS = "/view/"
PULL_ADDRESS = "/pull/7"
# Breaks a hung session; it is not a speed budget. The session needs well under a second
# of CPU and waits for it on a loaded host.
_SESSION_DEADLOCK_TIMEOUT_S = 300


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

    @property
    def transfer_bytes(self) -> int:
        """The most bytes the gate's rounding still reports as ``transfer_kb``."""

        return self.transfer_kb * 1024 + 511


@dataclass(frozen=True, slots=True)
class ScriptRequest:
    """A script some script of the shell asked for before ``DOMContentLoaded`` ended."""

    how: str
    url_path: str


class _ShellScripts(HTMLParser):
    """Collect the ``src`` of every script tag, in document order, and which are modules."""

    def __init__(self) -> None:
        super().__init__()
        self.sources: list[str] = []
        self.modules: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "script":
            return
        attributes = dict(attrs)
        source = attributes.get("src")
        if attributes.get("type") == "module":
            self.modules.append(source or "an inline module")
        if source:
            self.sources.append(source)


def startup_script_paths(html: str) -> list[str]:
    """The URL paths of the scripts *html*'s tags make a browser request.

    Every ``<script src>`` counts, whatever its attributes. The gate's probe leaves out
    ``/static/vendor/``, which it reports as its own tier, and so does this.
    """

    parser = _ShellScripts()
    parser.feed(html)
    if parser.modules:
        raise SystemExit(
            "the shell has a module script ("
            + ", ".join(parser.modules)
            + "): what it imports is requested before DOMContentLoaded too, and this "
            "check cannot count it. Teach it to before adding one."
        )
    paths = [urlsplit(source).path for source in parser.sources]
    return [path for path in paths if not path.startswith(VENDOR_PREFIX)]


def render_shells(*addresses: str) -> list[str]:
    """The shell a folder's server answers each of *addresses* with.

    The folder is an empty one of this function's own, so the answer does not depend on
    what the process happened to be serving, and the request goes through the
    application's routes and middleware as a browser's does.
    """

    from metabrowser import server
    from metabrowser.cli.asgi_client import InProcessClient

    async def answer() -> list[str]:
        shells: list[str] = []
        async with InProcessClient(cast(Any, server.app), label="startup scripts") as client:
            for address in addresses:
                response = await client.get(address)
                if response.status_code != 200:
                    raise SystemExit(f"{address} answered HTTP {response.status_code}, not a shell")
                shells.append(response.text())
        return shells

    with tempfile.TemporaryDirectory(prefix="metabrowser-startup-scripts-") as folder:
        server._set_root_dir(Path(folder).resolve())  # pyright: ignore[reportPrivateUsage]
        return asyncio.run(answer())


def render_folder_shell() -> str:
    """The shell exactly as the server renders it for a folder's ``/view/``."""

    return render_shells(FOLDER_ADDRESS)[0]


def run_startup_session(html: str, address: str, *, landing: str = "") -> dict[str, Any]:
    """The report of ``tests/dom/shell-startup-requests.js`` for *html* loaded at *address*.

    With *landing*, the session then lands history on that pathname and reports what
    the page asks for as ``afterLanding``.
    """

    node = shutil.which("node")
    if node is None:
        raise SystemExit("node is not on PATH; the startup-script check runs the shell with it")
    with tempfile.TemporaryDirectory(prefix="metabrowser-startup-scripts-") as directory:
        shell = Path(directory) / "shell.html"
        shell.write_text(html, encoding="utf-8")
        # The flag lets the session hear an `import()` instead of dying on it.
        result = subprocess.run(
            [
                node,
                "--experimental-vm-modules",
                "--no-warnings",
                str(SESSION),
                str(shell),
                address,
                *([landing] if landing else []),
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=_SESSION_DEADLOCK_TIMEOUT_S,
        )
    if result.returncode != 0:
        raise SystemExit(f"the startup session failed for {address}: {result.stderr.strip()}")
    return cast("dict[str, Any]", json.loads(result.stdout))


def script_requests(html: str, address: str) -> list[ScriptRequest]:
    """What the scripts of *html* ask for themselves, loaded at *address*.

    A script that throws in the session, or one the session cannot run, stops the
    check: a page whose startup failed tells nothing about what it requests.
    """

    report = run_startup_session(html, address)
    if report["errors"]:
        raise SystemExit(
            f"the shell's scripts did not run in the startup session for {address}:\n  "
            + "\n  ".join(report["errors"])
            + f"\nIf the page is right, {SESSION.relative_to(ROOT)} lacks what it calls."
        )
    return [ScriptRequest(how=entry["how"], url_path=entry["url"]) for entry in report["requested"]]


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


def measure_paths(url_paths: list[str]) -> list[StartupScript]:
    """Each of *url_paths* with its decoded and transferred size."""

    from metabrowser import server

    scripts: list[StartupScript] = []
    for url_path in url_paths:
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


def measure(html: str) -> list[StartupScript]:
    """Every startup script of *html* with its decoded and transferred size."""

    return measure_paths(startup_script_paths(html))


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


def beside_budget(scripts: list[StartupScript], limits: Limits) -> str:
    """How far *scripts* are from the transfer ceiling, in bytes and in words."""

    spare = limits.transfer_bytes - sum(script.transfer_bytes for script in scripts)
    return f"{spare:,} bytes under" if spare >= 0 else f"{-spare:,} bytes over"


def problems(
    scripts: list[StartupScript],
    limits: Limits,
    requested: dict[str, list[ScriptRequest]] | None = None,
) -> list[str]:
    """What breaks the budget, in words a reader can act on; empty when nothing does.

    *requested* maps an address to what the shell's scripts asked for there themselves.
    """

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
            f"script before DOMContentLoaded; the budget is {limits.transfer_kb} KB "
            f"({beside_budget(scripts, limits)})"
        )
    for address, asked in (requested or {}).items():
        found.extend(
            f"a script of the shell at {address} requests {request.url_path} "
            f"({request.how}) before DOMContentLoaded has been handled: the gate counts "
            "it and whatever it goes on to request, and this check cannot. Make it a "
            "script tag of the shell that needs it, or start it after the first tree"
            for request in asked
        )
    return found


def main() -> int:
    from metabrowser import server

    folder_html, pull_html = render_shells(FOLDER_ADDRESS, PULL_ADDRESS)
    scripts = measure(folder_html)
    limits = load_limits()
    requested = {
        FOLDER_ADDRESS: script_requests(folder_html, FOLDER_ADDRESS),
        PULL_ADDRESS: script_requests(pull_html, PULL_ADDRESS),
    }
    found = problems(scripts, limits, requested)
    total = sum(script.transfer_bytes for script in scripts)
    print(
        f"startup scripts: {len(scripts)} requests of {limits.requests}, "
        f"{transfer_kb(scripts)} KB of {limits.transfer_kb} KB transferred "
        f"({total:,} bytes, {beside_budget(scripts, limits)} the budget)"
    )
    # The other shells, beside the same budget: reported, not gated.
    pull_scripts = measure(pull_html)
    pin_scripts = scripts + measure_paths(
        [STATIC_PREFIX + name for name in server.PIN_STARTUP_SCRIPTS]
    )
    for label, others in (
        ("a pull-request address", pull_scripts),
        ("a pinned revision", pin_scripts),
    ):
        added = ", ".join(
            script.url_path.removeprefix(STATIC_PREFIX)
            for script in others
            if script not in scripts
        )
        print(
            f"  {label} adds {added or 'nothing'}: {len(others)} requests, "
            f"{sum(script.transfer_bytes for script in others):,} bytes "
            f"({beside_budget(others, limits)}; not gated)"
        )
    if not found:
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
