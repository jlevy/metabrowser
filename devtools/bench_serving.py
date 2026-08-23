"""Measure how fast a large tree becomes usable, and stays usable.

The costs that matter here are not visible from a single timing. Opening a
large folder is fast or slow depending on *when* you ask: the walker is still
crawling, the aggregate cache is still filling, and background scan work and
foreground requests take CPU from each other under the GIL. A mean hides all
of that. So this harness reports the shape of each cost rather than one
number, and separates the paths that only look alike:

* A cold scan with nothing attached is walker throughput alone. It is not the
  number a reader experiences, and it is not the number that regressed
  historically -- a client polling during the crawl slows the crawl down.
* A settled rollup has three distinct paths -- a real aggregation, a retained
  body served without one, and a ``304`` revalidation -- and only one of them
  costs anything. Averaging them together reports a cache hit rate, not a
  latency.
* A tree request at the root and at a subtree are different requests. Reporting
  them against response size is what makes a cost proportional to the index
  visible as one, instead of looking like a large response.

Every phase writes JSON so two runs can be diffed. Pass ``--label`` to name a
run (a branch, a commit, "before"), ``--json`` to write it somewhere, and
``--baseline`` to print the comparison directly.

The client half -- request coalescing and validator behavior as the browser
actually experiences them -- is not visible from here. ``--browser-probe``
prints the in-page probe; see ``devtools/bench-browser-probe.js``.

Usage::

    uv --config-file uv.toml run --frozen python -m devtools.bench_serving \\
        --files 100000 --label before --json bench-before.json

    uv --config-file uv.toml run --frozen python -m devtools.bench_serving \\
        --files 100000 --label after --baseline bench-before.json

Run the two on the same machine and the same corpus size; the absolute numbers
move a lot with the filesystem and the page cache, and only the comparison
carries over.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import shutil
import socket
import statistics
import subprocess
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
PROBE_PATH = Path(__file__).resolve().parent / "bench-browser-probe.js"

# The bounds the folder Overview actually asks for. Measuring a shape the
# browser never requests would report a cost no reader pays.
OVERVIEW_QUERY = "path=&depth=0&top=0&ext_top=0&filename_top=20&remaining_top=20&ext_rank=dual"
TREEMAP_QUERY = "path=&depth=3"

# Extensions spread across the file-type registry's families, so the rollup's
# classification pass does representative work rather than tallying one type.
CORPUS_EXTS = (
    ".py", ".js", ".ts", ".md", ".json", ".txt", ".yaml", ".css", ".html",
    ".go", ".rs", ".java", ".c", ".h", ".sh", ".toml", ".csv", ".log", ".png", ".bin",
)  # fmt: skip

# Long enough that a slow machine still converges, short enough that a run
# that never will reports so instead of hanging. A scan that hits this is
# itself the finding, so it is recorded rather than raised.
SCAN_TIMEOUT_S = 600.0

# The banner metab prints once it is listening, which also reports the port it
# settled on -- it picks another when the requested one is busy, so parsing
# this is more reliable than assuming the port we asked for.
_BANNER_RE = re.compile(r"http://(?P<host>[^:/]+):(?P<port>\d+)/view/")
# Emitted by InventoryIndex when the boot crawl finishes. This is the walker's
# own elapsed time, which is what a cold scan has to be measured by: polling
# for it would make it a scan with a client attached.
_WALK_DONE_RE = re.compile(
    r"inventory walker complete: status=(?P<status>\w+) "
    r"files=(?P<files>\d+) entries=\d+ elapsed=(?P<ms>\d+)ms"
)


@dataclass
class Timing:
    """One latency sample set, reported as a distribution rather than a mean."""

    samples: list[float] = field(default_factory=list)

    def add(self, ms: float) -> None:
        self.samples.append(ms)

    def summary(self) -> dict[str, Any]:
        if not self.samples:
            return {"n": 0}
        ordered = sorted(self.samples)
        return {
            "n": len(ordered),
            "p50": round(statistics.median(ordered), 1),
            "p95": round(ordered[max(0, int(len(ordered) * 0.95) - 1)], 1),
            "max": round(ordered[-1], 1),
        }


def _http(
    url: str, etag: str | None = None, timeout: float = 120.0
) -> tuple[int, str | None, bytes, float]:
    """One request, returning ``(status, etag, body, elapsed_ms)``.

    Failures are returned rather than raised: a refused connection during
    startup is a measurement outcome, not an exception the caller wants.
    """
    headers = {"If-None-Match": etag} if etag else {}
    request = urllib.request.Request(url, headers=headers)
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
            elapsed_ms = (time.perf_counter() - started) * 1000
            return response.status, response.headers.get("ETag"), body, elapsed_ms
    except urllib.error.HTTPError as error:
        elapsed_ms = (time.perf_counter() - started) * 1000
        return error.code, error.headers.get("ETag"), error.read(), elapsed_ms
    except (urllib.error.URLError, OSError, TimeoutError):
        return 0, None, b"", (time.perf_counter() - started) * 1000


# ── Corpus ───────────────────────────────────────────────────


def build_corpus(root: Path, target_files: int) -> dict[str, Any]:
    """Create (or reuse) a synthetic tree of *target_files* files.

    Wide at the top and deep in one branch, because both shapes are load
    bearing: breadth is what level-order discovery has to get through before
    the nav tree is usable, and depth is what aggregate eviction walks. A
    marker file records the size, so rerunning at the same size reuses the
    tree instead of paying to rebuild it.
    """
    marker = root / ".bench-corpus.json"
    if marker.is_file():
        try:
            existing: dict[str, Any] = json.loads(marker.read_text())
        except (OSError, ValueError):
            existing = {}
        if existing.get("files") == target_files:
            return existing

    if root.exists():
        shutil.rmtree(root)
    rng = random.Random(1234)

    directories: list[Path] = []
    for top in range(12):
        for mid in range(10):
            for leaf in range(8):
                directories.append(root / f"top{top:02d}" / f"mid{mid:02d}" / f"leaf{leaf:02d}")
    deep = root
    for level in range(12):
        deep = deep / f"deep{level:02d}"
        directories.append(deep)
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)

    made = 0
    per_directory = target_files // len(directories) + 1
    for directory in directories:
        for index in range(per_directory):
            if made >= target_files:
                break
            path = directory / f"file{index:04d}{rng.choice(CORPUS_EXTS)}"
            path.write_bytes(b"x" * rng.choice((64, 256, 1024, 4096, 16384)))
            made += 1
        if made >= target_files:
            break

    info: dict[str, Any] = {"files": made, "dirs": len(directories), "path": str(root)}
    marker.write_text(json.dumps(info))
    return info


# ── Server lifecycle ─────────────────────────────────────────


class Server:
    """A ``metab`` subprocess, with its log tailed for the facts only it knows."""

    def __init__(self, root: Path, log_path: Path) -> None:
        self._root = root
        self._log_path = log_path
        self._process: subprocess.Popen[bytes] | None = None
        self.base_url = ""

    def __enter__(self) -> Server:
        executable = shutil.which("metab")
        if executable is None:
            raise SystemExit(
                "metab is not on PATH. Run this through the locked environment:\n"
                "  uv --config-file uv.toml run --frozen python -m devtools.bench_serving"
            )
        # metab rejects port 0, so ask the kernel for a free one and hand over
        # the number. Another process can still take it in between; metab
        # falls forward to the next free port when that happens, which is why
        # the banner below is the authority on where it actually bound.
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        with self._log_path.open("wb") as handle:
            self._process = subprocess.Popen(
                [executable, str(self._root), "--no-open", "--port", str(port)],
                stdout=handle,
                stderr=subprocess.STDOUT,
                cwd=REPO,
            )
        deadline = time.time() + 60
        while time.time() < deadline:
            match = _BANNER_RE.search(self._log_text())
            if match is not None:
                self.base_url = f"http://{match['host']}:{match['port']}"
                # The banner prints before the first request is served, so
                # wait for the socket to actually answer.
                for _ in range(200):
                    if _http(f"{self.base_url}/api/rollup?{OVERVIEW_QUERY}", timeout=5)[0] == 200:
                        return self
                    time.sleep(0.05)
            if self._process.poll() is not None:
                raise SystemExit(f"metab exited during startup; see {self._log_path}")
            time.sleep(0.05)
        raise SystemExit(f"metab did not start within 60s; see {self._log_path}")

    def __exit__(self, *_exc: object) -> None:
        if self._process is not None and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._process.kill()

    def _log_text(self) -> str:
        try:
            return self._log_path.read_text(errors="replace")
        except OSError:
            return ""

    def walk_result(self) -> dict[str, Any] | None:
        """The walker's own completion record, or None while it is still crawling."""
        match = _WALK_DONE_RE.search(self._log_text())
        if match is None:
            return None
        return {
            "status": match["status"],
            "files": int(match["files"]),
            "walk_ms": int(match["ms"]),
        }

    def await_walk(self, timeout_s: float = SCAN_TIMEOUT_S) -> dict[str, Any] | None:
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            result = self.walk_result()
            if result is not None:
                return result
            time.sleep(0.05)
        return None


# ── Phases ───────────────────────────────────────────────────


# Shape parameters taken from two real working trees rather than invented.
# Measured: median 2 files per directory in both, mean depth 9.5 and 12.8 with
# maxima of 18 and 22, and 527 and 88 nested ``.gitignore`` files carrying 5,500
# and 981 patterns. ``build_corpus`` above has 309 files per directory and no
# ``.gitignore`` at all, which is why a whole class of cost -- everything paid
# per directory, and everything paid per ignore pattern -- was invisible to it.
# See explorations/performance-loop/experiments/exp-005.
REALISTIC_MEDIAN_FILES_PER_DIR = 2
REALISTIC_MAX_DEPTH = 18
# One nested .gitignore per this many directories, each with this many patterns.
# The real trees run about one per 420 directories at ten patterns apiece.
REALISTIC_DIRS_PER_GITIGNORE = 400
REALISTIC_PATTERNS_PER_GITIGNORE = 10
# Fraction of files placed under a gitignored directory. Real trees are mostly
# build output, virtualenvs, and caches; the tracked tree is the minority.
REALISTIC_IGNORED_FRACTION = 0.55
IGNORED_DIR_NAMES = ("node_modules", ".venv", "target", "dist", "__pycache__", "build")
# How many ignored subtrees, and how deep each fans. Few and enormous, not many
# and small -- that distinction turned out to decide whether pruning the
# gitignore pre-walk is a win or a loss, and only the real trees showed it.
# Measured there: one tree keeps 232,190 files under two `target` directories,
# another 191,072 under seventeen `.venv` directories. A corpus that scatters
# the same file count across hundreds of small ignored directories prunes
# almost nothing and makes the pruning look like pure overhead.
REALISTIC_IGNORED_SUBTREES = 8
# Bodies are deliberately tiny. The walker stats files and never reads them, so
# file size buys no fidelity for anything this plan measures -- and a corpus
# with realistic bodies is tens of gigabytes, which is a real constraint on a
# machine that also has to hold the tree being compared against.
REALISTIC_BODY_BYTES = 64


# How many copies of the sample project the corpus holds. Each contributes the
# repository's own locked installs plus several copies of its own source, so a
# count here is roughly 22,000 files.
PROJECT_CORPUS_DEFAULT_PROJECTS = 10
# Copies of the real source tree per project, so the tracked half is a few
# thousand files rather than a few hundred -- the proportion a real repository
# has once its dependencies are installed.
PROJECT_CORPUS_SOURCE_COPIES = 4
PROJECT_CORPUS_IGNORED = ("node_modules", ".venv", "dist", "target", "__pycache__", "build")


def build_project_corpus(
    root: Path, projects: int = PROJECT_CORPUS_DEFAULT_PROJECTS
) -> dict[str, Any]:
    """A corpus assembled from this repository's own locked installs.

    The synthetic generators above approximate a real tree's shape from summary
    statistics, and exp-006 is the record of that going wrong: a corpus can
    match files-per-directory and depth and still be wrong about the structure
    under test. This one does not approximate. It copies the actual
    ``node_modules`` that ``package-lock.json`` produces, the actual ``.venv``
    that ``uv.lock`` produces, and the repository's own Python, JavaScript, and
    Markdown as the tracked half -- so the directory shapes, name lengths,
    nesting, and file-size distribution are a real dependency tree's rather
    than a guess at one.

    Deterministic in the way that matters: the inputs are two committed
    lockfiles and a git checkout, so the same commit and the same locks produce
    the same tree. It needs no network, because ``make install`` has already
    materialized both installs.

    Copies use APFS clones where available, which makes ten copies of a
    dependency tree cost almost no additional disk.
    """
    marker = root / ".bench-corpus.json"
    shape_version = 1
    if marker.is_file():
        try:
            existing: dict[str, Any] = json.loads(marker.read_text())
        except (OSError, ValueError):
            existing = {}
        if existing.get("projects") == projects and existing.get("shape") == shape_version:
            return existing

    sources = {name: REPO / name for name in ("src", "tests", "docs")}
    installs = {name: REPO / name for name in ("node_modules", ".venv")}
    missing = [str(path) for path in (*sources.values(), *installs.values()) if not path.is_dir()]
    if missing:
        raise SystemExit(
            "build_project_corpus needs the repository's own installs: run `make install` "
            f"first (missing: {', '.join(missing)})"
        )

    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)

    def copy_tree(src: Path, dst: Path) -> None:
        # -c asks for an APFS clone: the copies share blocks, so the corpus
        # costs about one dependency tree on disk rather than `projects` of
        # them, while every file still stats and reads normally.
        result = subprocess.run(
            ["cp", "-c", "-R", str(src), str(dst)], check=False, capture_output=True
        )
        if result.returncode != 0:
            shutil.copytree(src, dst, symlinks=True)

    (root / ".gitignore").write_text(
        "\n".join(f"{name}/" for name in PROJECT_CORPUS_IGNORED) + "\n*.pyc\n.DS_Store\n"
    )
    (root / ".git").mkdir()
    (root / ".git" / "HEAD").write_text("ref: refs/heads/main\n")

    for index in range(projects):
        project = root / f"project{index:02d}"
        project.mkdir()
        # Tracked: real code, several copies, so the tracked half has the
        # thousands of files a working repository has.
        for copy_index in range(PROJECT_CORPUS_SOURCE_COPIES):
            for name, path in sources.items():
                copy_tree(path, project / f"{name}{copy_index}")
        # Nested .gitignore files, the way a real repository carries them. The
        # locked installs bring few of their own, and how many exist decides
        # how much a change to the pattern-loading path can matter -- the real
        # trees carry 88 and 527. Placed deterministically by walking the
        # tracked copies in sorted order so the same commit yields the same
        # tree.
        (project / ".gitignore").write_text("*.log\nbuild/\n.cache/\n")
        tracked_dirs = sorted(
            d for d in project.glob("src*/**/") if d.is_dir() and "__pycache__" not in d.parts
        )
        for position, directory in enumerate(tracked_dirs):
            if position % 4 == 0:
                (directory / ".gitignore").write_text(
                    "*.tmp\n*.bak\n*.orig\nbuild/\ndist/\n*.log\n.cache/\n*.pyc\ncoverage/\n*.swp\n"
                )
        # Ignored: the actual locked installs.
        for name, path in installs.items():
            copy_tree(path, project / name)

    files = dirs = 0
    for _, dirnames, filenames in os.walk(root):
        dirs += len(dirnames)
        files += len(filenames)
    info: dict[str, Any] = {
        "projects": projects,
        "shape": shape_version,
        "files": files,
        "dirs": dirs,
        "path": str(root),
    }
    marker.write_text(json.dumps(info))
    return info


def build_realistic_corpus(root: Path, target_files: int) -> dict[str, Any]:
    """A synthetic tree shaped like a real working tree, built the same way twice.

    ``build_corpus`` is wide and shallow with no ignore rules, which makes it a
    poor stand-in for the thing this project is for. Every per-directory cost is
    amortized across 309 files there and across 2 in practice, and the cost of
    loading nested ``.gitignore`` files does not exist there at all.

    Deterministic: same *target_files* in, same tree out, so two runs on it are
    comparable. A marker records the size and the shape version, and a shape
    change bumps the version so a stale tree is rebuilt rather than silently
    compared against a differently shaped one.
    """
    shape_version = 1
    marker = root / ".bench-corpus.json"
    if marker.is_file():
        try:
            existing: dict[str, Any] = json.loads(marker.read_text())
        except (OSError, ValueError):
            existing = {}
        if existing.get("files") == target_files and existing.get("shape") == shape_version:
            return existing

    if root.exists():
        shutil.rmtree(root)
    rng = random.Random(20260822)

    made = 0
    dirs_made = 0
    gitignores = 0
    ignored_files = 0
    ignored_budget = int(target_files * REALISTIC_IGNORED_FRACTION)

    def populate(directory: Path, depth: int, under_ignored: bool) -> None:
        nonlocal made, dirs_made, gitignores, ignored_files
        if made >= target_files:
            return
        directory.mkdir(parents=True, exist_ok=True)
        dirs_made += 1

        # A nested .gitignore every so often, naming the directories this level
        # actually contains, so the patterns match something.
        if dirs_made % REALISTIC_DIRS_PER_GITIGNORE == 0:
            lines = [
                f"*.{rng.choice(('tmp', 'log', 'cache', 'bak'))}"
                for _ in range(REALISTIC_PATTERNS_PER_GITIGNORE - 2)
            ]
            lines += ["build/", "*.pyc"]
            (directory / ".gitignore").write_text("\n".join(lines) + "\n")
            gitignores += 1

        # Median two, mean near three, p90 near seven -- the distribution both
        # real trees showed. The tail matters (some directories are full) but a
        # long one pulls the mean away from what a real tree does.
        count = 2 if rng.random() < 0.45 else rng.choice((0, 1, 1, 3, 4, 6, 9, 16))
        for index in range(count):
            if made >= target_files:
                return
            path = directory / f"file{index:03d}{rng.choice(CORPUS_EXTS)}"
            path.write_bytes(b"x" * REALISTIC_BODY_BYTES)
            made += 1
            if under_ignored:
                ignored_files += 1

        # Stop stochastically as well as at the cap: a real tree's depth has a
        # mean around 10 with a max near 20, which a hard cap alone cannot
        # produce -- every branch would bottom out at the same level.
        # Stop stochastically as well as at the cap, with the chance rising as
        # it gets deeper: a real tree's depth has a mean around ten under a max
        # near twenty, which a hard cap alone cannot produce -- every branch
        # would bottom out at the same level.
        if depth >= REALISTIC_MAX_DEPTH or (depth >= 3 and rng.random() < 0.06 * depth):
            return
        # Branch narrowly, which is what produces depth 10-20 at a realistic
        # file count instead of a wide shallow fan.
        # Wider near the top, narrow further down. That is what puts most
        # directories at a middling depth rather than in one long spine.
        fanout = rng.choice((2, 3, 4)) if depth <= 3 else rng.choice((1, 2, 2, 3))
        for child in range(fanout):
            if made >= target_files:
                return
            populate(directory / f"pkg{child:02d}", depth + 1, under_ignored)

    root.mkdir(parents=True, exist_ok=True)
    (root / ".gitignore").write_text(
        "\n".join(f"{name}/" for name in IGNORED_DIR_NAMES) + "\n*.pyc\n.DS_Store\n"
    )
    # A git root, so the gitignore machinery engages the way it does in practice.
    (root / ".git").mkdir(exist_ok=True)
    (root / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
    # The ignored bulk first: a handful of subtrees holding most of the files,
    # which is what a vendored or built directory looks like and what makes
    # pruning worth anything.
    per_subtree = ignored_budget // REALISTIC_IGNORED_SUBTREES
    for index in range(REALISTIC_IGNORED_SUBTREES):
        name = IGNORED_DIR_NAMES[index % len(IGNORED_DIR_NAMES)]
        holder = root / f"component{index:02d}"
        holder.mkdir(parents=True, exist_ok=True)
        target_here = made + per_subtree
        while made < target_here and made < target_files:
            populate(holder / name, 1, True)
    while made < target_files:
        populate(root / f"top{dirs_made:04d}", 1, False)

    info: dict[str, Any] = {
        "files": target_files,
        "shape": shape_version,
        "dirs": dirs_made,
        "gitignores": gitignores,
        "ignored_files": ignored_files,
        "path": str(root),
    }
    marker.write_text(json.dumps(info))
    return info


def phase_cold_scan(root: Path, log_dir: Path) -> dict[str, Any]:
    """Walker throughput with nothing attached.

    Read from the walker's own log record rather than by polling, because
    polling is exactly what the next phase deliberately does.
    """
    with Server(root, log_dir / "cold.log") as server:
        result = server.await_walk()
    if result is None:
        return {"converged": False, "timeout_s": SCAN_TIMEOUT_S}
    return {"converged": True, **result}


def phase_scan_with_client(root: Path, log_dir: Path) -> dict[str, Any]:
    """The scan a reader actually experiences.

    A client refreshing the folder view competes with the walker for CPU, so
    this is not the cold scan time. It also records when the first real count
    reached the wire -- the whole point of serving partial results -- and the
    rollup latency distribution while the index is moving, which is the case
    no cache can help because the validator changes on every request.
    """
    rollup = Timing()
    first_count_s: float | None = None
    walk: dict[str, Any] | None = None
    started = time.time()
    with Server(root, log_dir / "attached.log") as server:
        url = f"{server.base_url}/api/rollup?{OVERVIEW_QUERY}"
        while time.time() - started < SCAN_TIMEOUT_S:
            status, _etag, body, elapsed_ms = _http(url)
            if status != 200:
                continue
            rollup.add(elapsed_ms)
            payload: dict[str, Any] = json.loads(body)
            node: dict[str, Any] = payload.get("node") or {}
            if first_count_s is None and node.get("total_files"):
                first_count_s = round(time.time() - started, 2)
            if payload.get("index_status") in ("done", "truncated"):
                walk = server.walk_result()
                break
        wall_s = round(time.time() - started, 1)
    return {
        "converged": walk is not None,
        "wall_s": wall_s if walk is not None else None,
        "timed_out_at_s": None if walk is not None else SCAN_TIMEOUT_S,
        "walk_ms": walk["walk_ms"] if walk else None,
        "files": walk["files"] if walk else None,
        "first_count_s": first_count_s,
        "requests_issued": len(rollup.samples),
        "rollup_ms": rollup.summary(),
    }


def phase_settled(root: Path, log_dir: Path, clients: int) -> dict[str, Any]:
    """Costs once the index has stopped moving.

    The three rollup paths are measured apart because they are three different
    amounts of work. Forcing a fresh revision -- by touching a file -- is what
    makes the aggregating path measurable at all on a settled index; every
    other request would be answered from the retained body.
    """
    with Server(root, log_dir / "settled.log") as server:
        if server.await_walk() is None:
            return {"converged": False}
        base = server.base_url
        overview = f"{base}/api/rollup?{OVERVIEW_QUERY}"
        treemap = f"{base}/api/rollup?{TREEMAP_QUERY}"

        aggregated, retained, revalidated = Timing(), Timing(), Timing()
        marker = root / ".bench-touch"
        for round_index in range(8):
            # A write moves the index revision, so the next request cannot be
            # answered from the retained body and has to aggregate.
            marker.write_text(str(round_index))
            time.sleep(0.35)  # let the watcher apply it
            status, etag, _body, elapsed_ms = _http(treemap)
            if status != 200:
                continue
            # Recorded regardless of whether this server emits a validator:
            # a build with no caching at all still has this path, and leaving
            # the row blank there would hide the number worth comparing.
            aggregated.add(elapsed_ms)
            # The same answer again. With a retained body this is a lookup;
            # without one it is a second aggregation, which is the point.
            retained.add(_http(treemap)[3])
            if not etag:
                continue
            # The same answer with the validator: a 304, carrying no body.
            status_304, _e, body_304, ms_304 = _http(treemap, etag=etag)
            if status_304 == 304 and not body_304:
                revalidated.add(ms_304)
        marker.unlink(missing_ok=True)

        trees: list[dict[str, Any]] = []
        for path, depth in (("", 1), ("", 2), ("top00", 2), ("top00/mid00", 2)):
            timing, size = Timing(), 0
            for _ in range(10):
                _status, _etag, body, elapsed_ms = _http(
                    f"{base}/api/tree?path={path}&depth={depth}"
                )
                timing.add(elapsed_ms)
                size = len(body)
            trees.append(
                {"path": path or "<root>", "depth": depth, "bytes": size, **timing.summary()}
            )

        staggered = Timing()
        for _ in range(clients):
            staggered.add(_http(overview)[3])
            time.sleep(0.02)

        # Arriving together is the case single-flight exists for: without it
        # each client aggregates the same answer independently.
        simultaneous = Timing()

        def one_client(_index: int) -> float:
            return _http(overview)[3]

        with ThreadPoolExecutor(max_workers=clients) as pool:
            for elapsed_ms in pool.map(one_client, range(clients)):
                simultaneous.add(elapsed_ms)

    return {
        "converged": True,
        "rollup_aggregated_ms": aggregated.summary(),
        "rollup_retained_body_ms": retained.summary(),
        "rollup_revalidated_304_ms": revalidated.summary(),
        "tree": trees,
        "clients": clients,
        "clients_staggered_ms": staggered.summary(),
        "clients_simultaneous_ms": simultaneous.summary(),
    }


# ── Reporting ────────────────────────────────────────────────


def _fmt(value: Any, suffix: str = "") -> str:
    if value is None:
        return "--"
    if isinstance(value, float):
        return f"{value:g}{suffix}"
    return f"{value}{suffix}"


def _ratio(before: Any, after: Any) -> str:
    """How *after* compares to *before*, as a speedup or a slowdown."""
    if not isinstance(before, (int, float)) or not isinstance(after, (int, float)):
        return "--"
    if before <= 0 or after <= 0:
        return "--"
    if after <= before:
        return f"{before / after:.1f}x faster"
    return f"{after / before:.1f}x slower"


def _rows(result: dict[str, Any]) -> list[tuple[str, Any]]:
    """The comparable scalars, flattened, in report order."""
    attached = result.get("scan_with_client", {})
    settled = result.get("settled", {})
    rows: list[tuple[str, Any]] = [
        ("cold scan, walker only (ms)", result.get("cold_scan", {}).get("walk_ms")),
        ("scan with a client attached (s)", attached.get("wall_s")),
        ("first folder count on the wire (s)", attached.get("first_count_s")),
        ("rollup during scan p50 (ms)", attached.get("rollup_ms", {}).get("p50")),
        ("rollup during scan p95 (ms)", attached.get("rollup_ms", {}).get("p95")),
        ("settled rollup, aggregated p50 (ms)", settled.get("rollup_aggregated_ms", {}).get("p50")),
        (
            "settled rollup, retained body p50 (ms)",
            settled.get("rollup_retained_body_ms", {}).get("p50"),
        ),
        ("settled rollup, 304 p50 (ms)", settled.get("rollup_revalidated_304_ms", {}).get("p50")),
        (
            f"{settled.get('clients', '?')} clients staggered p50 (ms)",
            settled.get("clients_staggered_ms", {}).get("p50"),
        ),
        (
            f"{settled.get('clients', '?')} clients simultaneous p50 (ms)",
            settled.get("clients_simultaneous_ms", {}).get("p50"),
        ),
    ]
    for tree in settled.get("tree", []):
        # The label is the join key between two runs, so it carries only the
        # request. Response size moves a little run to run, and putting it here
        # would stop the rows lining up at all.
        rows.append((f"/api/tree {tree['path']} depth={tree['depth']} p50 (ms)", tree.get("p50")))
    return rows


def render_report(result: dict[str, Any], baseline: dict[str, Any] | None) -> str:
    corpus = result.get("corpus", {})
    lines = [
        "",
        f"Metabrowser serving benchmark -- {result.get('label')}",
        f"corpus: {corpus.get('files')} files in {corpus.get('dirs')} dirs",
        "",
    ]
    attached = result.get("scan_with_client", {})
    if not attached.get("converged", True):
        lines.append(
            f"  NOTE: the scan did not converge within {attached.get('timed_out_at_s')}s "
            f"with a client attached ({attached.get('requests_issued')} requests issued)."
        )
        lines.append("")

    rows = _rows(result)
    if baseline is None:
        width = max(len(name) for name, _ in rows)
        for name, value in rows:
            lines.append(f"  {name:<{width}}  {_fmt(value)}")
    else:
        base_rows = dict(_rows(baseline))
        width = max(len(name) for name, _ in rows)
        lines.append(
            f"  {'':<{width}}  {baseline.get('label', 'baseline'):>12}  {result.get('label'):>12}   change"
        )
        for name, value in rows:
            before = base_rows.get(name)
            lines.append(
                f"  {name:<{width}}  {_fmt(before):>12}  {_fmt(value):>12}   {_ratio(before, value)}"
            )

    # Response sizes, so the tree rows above can be read as cost against the
    # size of the answer. A root request that costs more than a larger subtree
    # response is doing work proportional to something other than its output.
    trees = result.get("settled", {}).get("tree", [])
    if trees:
        lines.append("")
        lines.append("  tree response sizes:")
        for tree in trees:
            lines.append(f"    {tree['path']} depth={tree['depth']}: {tree['bytes']} bytes")
    lines.append("")
    return "\n".join(lines)


# Every corpus shape, by the name the CLI takes. Two of these existed with no
# way to select them: the figures for scan ordering were measured on `project`,
# and reproducing them meant importing this module and calling the generator by
# hand. A measurement whose corpus has no flag does not get re-run.
#
# Each builder takes (root, size) so the CLI can treat them alike; `project`
# reads its size as a project count rather than a file count, which is why the
# caller picks which argument to pass.
CORPUS_BUILDERS = {
    "synthetic": build_corpus,
    "realistic": build_realistic_corpus,
    "project": build_project_corpus,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark Metabrowser scan and serve latency end to end.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--files", type=int, default=100_000, help="corpus size (default 100000)")
    parser.add_argument(
        "--corpus",
        choices=sorted(CORPUS_BUILDERS),
        default="synthetic",
        help=(
            "which tree shape to measure on (default synthetic). "
            "`realistic` is deep and narrow with nested .gitignore files; "
            "`project` is assembled from this repository's own locked installs "
            "and is the shape the scan-ordering figures were measured on"
        ),
    )
    parser.add_argument(
        "--projects",
        type=int,
        default=PROJECT_CORPUS_DEFAULT_PROJECTS,
        help="copies of the sample project for --corpus project (about 22000 files each)",
    )
    parser.add_argument("--label", default="run", help="name for this run, shown in the report")
    parser.add_argument("--corpus-dir", type=Path, default=None, help="where to build the tree")
    parser.add_argument("--clients", type=int, default=8, help="concurrent clients (default 8)")
    parser.add_argument("--json", type=Path, default=None, help="write the full result here")
    parser.add_argument(
        "--baseline", type=Path, default=None, help="compare against a previous --json"
    )
    parser.add_argument(
        "--skip-cold-scan",
        action="store_true",
        help="skip the unattached scan, which costs one full crawl",
    )
    parser.add_argument(
        "--browser-probe",
        action="store_true",
        help="print the in-page probe for the client-side half, then exit",
    )
    args = parser.parse_args(argv)

    if args.browser_probe:
        print(PROBE_PATH.read_text())
        return 0

    # The corpus name is part of the corpus directory and part of the saved
    # result: a timing is only comparable against another measured on the same
    # shape, and a saved run that does not say which shape it used cannot be
    # compared to anything later.
    size = args.projects if args.corpus == "project" else args.files
    corpus_dir = args.corpus_dir or (REPO / ".bench" / f"corpus-{args.corpus}-{size}")
    log_dir = REPO / ".bench" / "logs"
    corpus_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    print(f"building {args.corpus} corpus (size {size}) at {corpus_dir} ...", flush=True)
    corpus = CORPUS_BUILDERS[args.corpus](corpus_dir, size)
    corpus = {"shape": args.corpus, **corpus}

    result: dict[str, Any] = {"label": args.label, "corpus": corpus}
    if not args.skip_cold_scan:
        print("phase 1/3: cold scan, nothing attached ...", flush=True)
        result["cold_scan"] = phase_cold_scan(corpus_dir, log_dir)
    print("phase 2/3: scan with a client attached ...", flush=True)
    result["scan_with_client"] = phase_scan_with_client(corpus_dir, log_dir)
    print("phase 3/3: settled index ...", flush=True)
    result["settled"] = phase_settled(corpus_dir, log_dir, args.clients)

    baseline: dict[str, Any] | None = None
    if args.baseline is not None:
        baseline = json.loads(args.baseline.read_text())
    print(render_report(result, baseline))

    if args.json is not None:
        args.json.write_text(json.dumps(result, indent=2) + "\n")
        print(f"wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
