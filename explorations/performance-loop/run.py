"""One round of the load-time exploration loop.

Four commands, and a browser sits between the first two:

    explorations/performance-loop/run.py serve --exp exp-003 --label before --files 300000
    explorations/performance-loop/run.py probe          # prints probe.js; evaluate it in the page
    explorations/performance-loop/run.py record --json '<paste>'
    explorations/performance-loop/run.py compare before after
    explorations/performance-loop/run.py report         # regenerate the ledger

``serve`` restarts the server on a port nothing has used, which is the whole
cold-cache mechanism: a port is part of the origin, so a new one gives every
static asset an empty HTTP cache without touching cache headers, and a fresh
process gives a scan that is still running. It also remembers what is being
measured, so ``record`` needs only the paste -- one flag instead of five, and
no chance of filing a run under the wrong experiment.

``record`` appends one run to ``results/runs.jsonl`` with everything needed to
reproduce or discount it later: the experiment id, the git commit, a
timestamp, the corpus, the viewport, and -- read back out of the server's own
log -- how long that run's walk took and whether it had finished. A run whose
provenance is missing is a number nobody can defend, so the fields are filled
here rather than left to whoever remembers.

``compare`` prints the median of each metric per label with the range beside
it, because on a corpus this size a single run says very little and a median
without its range says less. It also enforces evidence validity and the hard
budgets in ``performance-budgets.toml`` against every candidate run.
``report`` regenerates the ledger in ``report.md`` from the recorded runs and
the experiment artifacts. The primary metric's accept rule remains a judgment;
invalid evidence and a responsiveness regression are not.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from statistics import median
from typing import Any, cast

HERE = Path(__file__).resolve().parent
# Two levels up: this loop lives at explorations/<loop-name>/, and everything it
# reaches for -- the corpus under .bench/, the git metadata it records, the paths
# it prints -- is relative to the repository root rather than to explorations/.
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))

from devtools.bench_serving import MetabBuild, resolve_metab_build
from devtools.web_performance import (
    blocking_issues,
    budget_issues,
    format_issues,
    load_performance_config,
    validity_issues,
)

RESULTS = HERE / "results" / "runs.jsonl"
# Every port `serve` has handed out, recorded the moment it does. A port whose
# run was never recorded has still been loaded in a browser, so reusing it would
# hand the next run a warm cache and quietly break the one property that makes
# these numbers cold.
PORTS_USED = HERE / "results" / "ports-used.txt"
PROBE = HERE / "probe.js"
CAPTURE_BROWSER = HERE / "capture-browser.js"
REPORT = HERE / "report.md"
EXPERIMENTS = HERE / "experiments"
PERFORMANCE_BUDGETS = HERE / "performance-budgets.toml"
# What `serve` last set up. `record` reads it so a paste cannot be filed
# against the wrong experiment, port, or corpus -- the three things that are
# invisible in the payload and expensive to get wrong.
PENDING = HERE / "results" / "pending.json"
# Bumped when a change to run.py or probe.js makes a number incomparable with
# earlier ones -- a new metric definition, a changed sampling rule. Recorded on
# every run so a later reader can tell "measured differently" from "changed".
#
# 15: correctness now includes rendered main-panel error states and uncaught
# page exceptions observed from navigation through settled profile export. A
# failed renderer cannot count as a successful paint or performance result.
#
# 14: JavaScript transfer and startup attribution classify `.js` URL paths too.
# A preloaded script has a `link` initiator and its later script tag reuses that
# response, so initiator-only classification omitted the application shell.
#
# 13: stylesheet transfer is classified by a `.css` URL path rather than by
# the Resource Timing `link` initiator. The latter also includes script and
# font preloads and double-counted the preloaded application shell as CSS.
#
# 12: the driver sends a final controlled input at the product-settle boundary,
# and the application adapter freezes the navigation-time profile before its
# own observer wait and diagnostic fetches. Fast loads no longer fail coverage
# because measurement work created an untested tail.
#
# 11: the application adapter proves the deferred Quick File catalog reached
# authoritative completion. Ready controls with a missed stream-open event are
# not a correct asset-tier result.
#
# 10: the application adapter proves its post-usable-state shell tools reached
# ready, so deferring assets cannot buy a good startup number by losing them.
#
# 9: the responsiveness profile closes before the driver's forced-GC retained
# heap sample. Measurement-only collection cannot extend the input-coverage
# denominator or appear as product main-thread blocking.
#
# 8: startup JavaScript is split from scripts loaded for the selected view,
# with bounded URL-path attribution for the slowest and latest shell requests.
# This makes an eager-plugin waterfall a named, enforceable regression.
#
# 7: acceptance input is pulsed from first usable state through client
# quiescence, and the profile proves how much of the measured window it spans.
# A single early click could miss a later inventory-delivery freeze.
#
# 6: the trusted Chrome capture adds a controlled post-GC heap measurement,
# separating retained state from the runtime-dependent collection timing in
# `performance.memory`.
#
# 5: inventory delivery adds whole-window callback count, work-item volume,
# maximum duration, total duration, and window share. These fields make an
# event storm visible even when every individual callback stays below the
# browser's Long Task threshold.
#
# 4: responsiveness comes from the profiler attached with the document rather
# than a late observer or optional console paste; exact whole-window totals no
# longer get overwritten by the late-buffer floor. App-span milestones and
# counts come from non-evicting label totals. Event Timing entries are grouped
# into logical interactions; FCP, LCP, and CLS attach at navigation; and
# loading, resource-buffer, memory, animation-frame, and retention fields join
# the record.
#
# 3: four metric definitions changed at once. `frame_missing_px` measures the
# shipped state against the markup `server.py` really ships rather than a
# paraphrase of it; `tree_region_repaints` counts only the spans that replace
# the region, where it had counted every render span and so duplicated
# `render_spans`; `cls` and `cls_shifts` are gated on visibility rather than on
# layout, which is what made them report a confident 0 in a pane that cannot
# see a shift; and `regions_non_empty` is gone, having counted screen-reader
# text and so passed on the hole it existed to catch.
HARNESS_VERSION = 15
# Ports climb so a rerun never reuses one and never inherits its cache.
# A run below this is refused: the tree pages its rows against the viewport, so
# numbers taken in a collapsed pane describe a layout no reader has.
MIN_VIEWPORT = (900, 600)
FIRST_PORT = 8600
LAST_PORT = 65_535
# The metrics compare prints, in the order they matter to a reader.
METRICS = (
    "ttfb_ms",
    "response_download_ms",
    "dom_interactive_ms",
    "first_row_ms",
    "first_row_render_ms",
    "load_tree_ms",
    "tree_fetch_srv_ms",
    "tree_fetch_wait_ms",
    "tree_fetch_total_ms",
    "tree_fetch_kb",
    "dcl_ms",
    "load_ms",
    "last_resource_ms",
    "subtree_requests",
    "tree_items",
    "lazy_stubs",
    "dom_nodes",
    "transferred_kb",
    "vendor_first_start_ms",
    "fcp_ms",
    "lcp_ms",
    "cls",
    "cls_shifts",
    "frame_missing_px",
    # What the reader gets, as distinct from when the data arrived. The three
    # shift figures are read directly rather than from a layout-shift score,
    # because that score needs a visible window and this pane is never one --
    # see the block that computes them in probe.js. Repaint count is beside
    # them because a region can hold perfectly still and still be assembled in
    # front of the reader, and only one of those two is a shift.
    "filter_bar_shift_px",
    "summary_shift_px",
    "reserved_region_shift_px",
    "tree_region_repaints",
    "long_tasks",
    "long_task_ms_total",
    "total_blocking_time_ms",
    "long_task_max_ms",
    "long_task_max_ms_first_5s",
    "long_tasks_over_200ms",
    "main_thread_blocked_pct",
    "inventory_delivery_attribution_missing",
    "inventory_delivery_batches",
    "inventory_delivery_items",
    "inventory_delivery_batch_items_max",
    "inventory_delivery_max_ms",
    "inventory_delivery_work_ms_total",
    "inventory_delivery_work_pct",
    "animation_frames",
    "animation_frame_max_ms",
    "animation_frames_over_200ms",
    "animation_frame_blocking_ms_total",
    "animation_frame_blocking_ms_max",
    "animation_frames_blocking_over_200ms",
    "forced_style_layout_ms_max",
    "interactions",
    "interaction_inputs",
    "interaction_input_first_ms",
    "interaction_input_last_ms",
    "interaction_input_span_ms",
    "interaction_input_coverage_pct",
    "interaction_samples_retained",
    "interaction_p50_ms",
    "interaction_p95_ms",
    "interaction_max_ms",
    "render_spans",
    "render_ms_total",
    "tree_reprobe_ms",
    "tree_reprobe_srv_ms",
    "srv_scanning_ms",
    "srv_settled_ms",
    "wall_scanning_ms",
    "wall_settled_ms",
    "requests",
    "fetches_in_flight",
    "fetch_network_errors",
    "fetch_aborts",
    "fetch_http_4xx",
    "fetch_http_5xx",
    "rendered_preview_errors",
    "page_exceptions",
    "resource_timing_capacity",
    "resource_timing_buffer_full",
    "script_transfer_kb",
    "startup_script_requests",
    "startup_script_transfer_kb",
    "startup_script_last_response_ms",
    "startup_script_duration_max_ms",
    "style_transfer_kb",
    "image_transfer_kb",
    "api_transfer_kb",
    "largest_resource_kb",
    "resource_duration_max_ms",
    "js_heap_mb",
    "js_heap_after_gc_mb",
    "plugin_view_containers",
    "plugin_view_nonempty",
    "shell_tools_missing",
    "file_catalog_incomplete",
    "viewport_w",
    "viewport_h",
)


def _corpus_dir(files: int) -> Path:
    return REPO / ".bench" / f"corpus-{files}"


def _corpus_shape(root: Path) -> int | None:
    """The generator version that produced this corpus, if it was generated.

    A corpus is a fixture and fixtures change. exp-006 changed the shape of the
    realistic one mid-round -- the same file count, a different arrangement --
    and a number taken before that change is not comparable with one taken
    after. The version is recorded per run so the ledger can say so instead of
    quietly averaging two different trees together.
    """
    marker = root / ".bench-corpus.json"
    if not marker.is_file():
        return None
    try:
        loaded: Any = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    shape = cast("dict[str, Any]", loaded).get("shape")
    return shape if isinstance(shape, int) else None


def _tree_label(root: Path) -> str:
    """A stable identity for a real tree that carries none of its name.

    Not the path, and not the basename either: a directory name is usually a
    project name, and AGENTS.md keeps private repository and organization names
    out of committed material. A hash of the absolute path identifies the same
    tree across runs, which is all a ledger needs; what kind of tree it was
    belongs in the experiment's prose, described rather than named.
    """
    return "tree-" + hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:8]


def _count_tree(root: Path) -> tuple[int, int]:
    """Files and directories, by the same visibility rule the walker uses."""
    files = dirs = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        if Path(dirpath) != root and Path(dirpath).name.startswith("."):
            continue
        dirs += len(dirnames)
        files += sum(1 for name in filenames if not name.startswith("."))
    return files, dirs


def _used_ports() -> set[int]:
    ports = {run.get("port") for run in _load_runs() if isinstance(run.get("port"), int)}
    if PORTS_USED.is_file():
        for line in PORTS_USED.read_text(encoding="utf-8").split():
            if line.isdigit():
                ports.add(int(line))
    return {port for port in ports if isinstance(port, int)}


def _next_port() -> int:
    """The lowest port in the range nothing has used and nothing answers."""
    used = _used_ports()
    for port in range(FIRST_PORT, LAST_PORT + 1):
        if port in used:
            continue
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=0.2).close()
        except urllib.error.URLError:
            return port
        except OSError:
            return port
    raise SystemExit(f"no unused loopback port in {FIRST_PORT}-{LAST_PORT}")


def _load_runs() -> list[dict[str, Any]]:
    if not RESULTS.is_file():
        return []
    runs: list[dict[str, Any]] = []
    for line in RESULTS.read_text(encoding="utf-8").splitlines():
        if line.strip():
            runs.append(json.loads(line))
    return runs


def _git_commit() -> str:
    """The commit the measured build came from, short form."""
    try:
        result = subprocess.run(
            ["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def _git_dirty() -> bool:
    """True when the working tree carries uncommitted changes.

    A dirty tree is the normal state mid-experiment -- the candidate is not
    committed until it is accepted -- so this is recorded rather than refused.
    It is the flag that says the commit alone does not identify the build.
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(REPO), "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return bool(result.stdout.strip())


def _build_provenance(build_version: str, *, build_ref: str, external: bool) -> dict[str, Any]:
    """Identify the artifact behind a browser benchmark run."""
    if external:
        if not build_ref:
            raise SystemExit("--build-ref is required when --metab selects an external build")
        return {
            "build_version": build_version,
            "commit": build_ref,
            "dirty": False,
        }
    return {
        "build_version": build_version,
        "commit": _git_commit(),
        "dirty": _git_dirty(),
    }


_WALK_LINE = re.compile(
    r"inventory walker complete: status=(?P<status>\w+) files=(?P<files>\d+) "
    r"entries=(?P<entries>\d+) elapsed=(?P<elapsed>\d+)ms"
)


def _walk_facts(port: int) -> dict[str, Any]:
    """What that run's own walk did, read back out of its server log.

    The scan regime decides almost every number in this loop -- root
    `/api/tree` is 15 ms settled and over a second while walking -- and it is
    not visible in anything the browser can see. The server says it plainly;
    this reads it rather than asking anyone to remember.
    """
    log = HERE / "results" / f"server-{port}.log"
    if not log.is_file():
        return {}
    try:
        text = log.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    # The last completion line, not the first: a server restarted onto the same
    # log would otherwise report the earlier run's walk.
    matches = list(_WALK_LINE.finditer(text))
    match = matches[-1] if matches else None
    if match is None:
        return {"walk_status": "unfinished"}
    return {
        "walk_status": match["status"],
        "walk_elapsed_ms": int(match["elapsed"]),
        "walk_files": int(match["files"]),
    }


def _read_pending() -> dict[str, Any]:
    if not PENDING.is_file():
        raise SystemExit(
            "no pending run: start one with `explorations/performance-loop/run.py serve --exp <id> --label <name>`"
        )
    loaded: Any = json.loads(PENDING.read_text(encoding="utf-8"))
    return cast("dict[str, Any]", loaded)


def cmd_serve(args: argparse.Namespace) -> int:
    if args.tree:
        real = Path(args.tree).expanduser().resolve()
        if not real.is_dir():
            raise SystemExit(f"not a directory: {real}")
        return _serve_root(args, real, _tree_label(real), None)
    corpus = _corpus_dir(args.files)
    if not corpus.is_dir():
        print(f"building corpus ({args.files} files) at {corpus} ...", flush=True)
        corpus.mkdir(parents=True, exist_ok=True)
        sys.path.insert(0, str(REPO))
        from devtools.bench_serving import build_corpus

        build_corpus(corpus, args.files)
    return _serve_root(args, corpus, str(corpus.relative_to(REPO)), args.files)


def _load_probe_payload(json_text: str, json_file: str) -> Any:
    """Load a browser profile from an inline paste or an exported file."""
    if json_file:
        try:
            json_text = Path(json_file).read_text(encoding="utf-8")
        except OSError as error:
            raise SystemExit(f"could not read browser profile {json_file}: {error}") from error
    return json.loads(json_text)


def _stop_pending_server() -> None:
    """Stop only the prior server this harness recorded starting."""
    if not PENDING.is_file():
        return
    try:
        loaded: Any = json.loads(PENDING.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    if not isinstance(loaded, dict):
        return
    pending = cast("dict[str, Any]", loaded)
    pid = pending.get("server_pid")
    port = pending.get("port")
    executable = pending.get("server_executable")
    root = pending.get("server_root")
    if (
        not isinstance(pid, int)
        or not isinstance(port, int)
        or not isinstance(executable, str)
        or not isinstance(root, str)
    ):
        return
    inspected = subprocess.run(
        ["ps", "-p", str(pid), "-o", "command="],
        capture_output=True,
        check=False,
        text=True,
    )
    command = inspected.stdout.strip()
    expected = (executable, root, "--no-open", "--port", str(port))
    if inspected.returncode != 0 or not all(part in command for part in expected):
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.05)
    with suppress(ProcessLookupError):
        os.kill(pid, signal.SIGKILL)


def _serve_root(args: argparse.Namespace, root: Path, corpus_label: str, files: int | None) -> int:
    requested_build = args.metab or "metab"
    build: MetabBuild = resolve_metab_build(requested_build)
    provenance = _build_provenance(
        build.version,
        build_ref=args.build_ref,
        external=bool(args.metab),
    )
    _stop_pending_server()

    port = _next_port()
    PORTS_USED.parent.mkdir(parents=True, exist_ok=True)
    with PORTS_USED.open("a", encoding="utf-8") as handle:
        handle.write(f"{port}\n")
    log = HERE / "results" / f"server-{port}.log"
    with log.open("w", encoding="utf-8") as handle:
        process = subprocess.Popen(
            [str(build.executable), str(root), "--no-open", "--port", str(port)],
            # An immutable external build must not import or discover files
            # from the candidate checkout merely because the harness lives
            # there. The served root is already an explicit CLI argument and
            # is the neutral working directory shared by both conditions.
            cwd=root if args.metab else REPO,
            stdout=handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )

    url = f"http://127.0.0.1:{port}/view/"
    # Wait for the socket, not for a rendered page. The scan is the regime this
    # loop is about, and asking for `/` during one can take most of the scan to
    # answer -- a readiness check that waits for it hands back a server that has
    # already finished walking. metab binds before it walks and serves partial
    # state on purpose, so an accepted connection is the right signal.
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        with socket.socket() as probe:
            probe.settimeout(0.25)
            if probe.connect_ex(("127.0.0.1", port)) == 0:
                break
    else:
        raise SystemExit(f"server did not come up on {port}; see {log}")

    PENDING.write_text(
        json.dumps(
            {
                "experiment": args.exp,
                "label": args.label,
                "port": port,
                "files": files,
                "corpus": corpus_label,
                "corpus_shape": _corpus_shape(root),
                **provenance,
                "note": args.note,
                "server_executable": str(build.executable),
                "server_pid": process.pid,
                "server_root": str(root),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"experiment  {args.exp or '(unset)'}   label {args.label or '(unset)'}")
    print(f"build       {build.version}   ref {provenance['commit']}")
    print(f"port        {port}   (unused, so the browser cache starts empty)")
    count = f"{files} files" if files is not None else "file count recorded from completed walk"
    print(f"corpus      {corpus_label}  ({count})")
    print(f"url         {url}")
    print()
    print("1. size the browser pane to at least 1280x900, keep it visible, and load that URL cold")
    print("2. keep exercising real interactions throughout inventory loading")
    print("3. after the inventory settles, evaluate probe.js (`run.py probe` prints it)")
    print("4. explorations/performance-loop/run.py record --json '<paste>'")
    print("   or automate 1-4 with `run.py capture --headed --output FILE --record`")
    return 0


def cmd_record(args: argparse.Namespace) -> int:
    payload = _load_probe_payload(args.json or "", args.json_file or "")
    if not isinstance(payload, dict):
        raise SystemExit("probe payload must be a JSON object")
    # A browser pane that never got a size runs the app and reports plausible
    # timings while every layout-dependent number is measured against nothing.
    # That failure is silent from the numbers alone, so it is refused here
    # rather than discovered three experiments later.
    probe = cast("dict[str, Any]", payload)
    # A `probe-server` payload is a route sample, not a page load: it has no
    # viewport by construction and the floor below does not apply to it.
    is_server_sample = "route" in probe
    config = None
    width = probe.get("viewport_w")
    height = probe.get("viewport_h")
    if is_server_sample:
        pass
    elif not isinstance(width, int) or not isinstance(height, int):
        raise SystemExit("probe payload has no viewport; re-run with the current probe.js")
    elif width < MIN_VIEWPORT[0] or height < MIN_VIEWPORT[1]:
        raise SystemExit(
            f"viewport was {width}x{height}, below the {MIN_VIEWPORT[0]}x{MIN_VIEWPORT[1]} "
            "floor. Size the browser pane and load the page again; the tree pages its "
            "rows against the viewport, so a run measured at this size is not a run."
        )
    pending = _read_pending()
    port = int(pending["port"])
    label = args.label or pending.get("label")
    if not label:
        raise SystemExit("no label: pass --label, or set one on `serve`")
    # The harness owns provenance. Put the browser payload first so pasted JSON
    # cannot replace the commit, corpus, timestamp, or other run identity that
    # `serve` established.
    walk_facts = _walk_facts(port)
    run: dict[str, Any] = {
        **payload,
        "experiment": pending.get("experiment"),
        "label": label,
        "port": port,
        "files": walk_facts.get("walk_files", pending.get("files")),
        "corpus": pending.get("corpus"),
        "commit": pending.get("commit"),
        "build_version": pending.get("build_version"),
        "dirty": pending.get("dirty"),
        "recorded_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "harness_version": HARNESS_VERSION,
        "corpus_shape": pending.get("corpus_shape"),
        "note": args.note or pending.get("note", ""),
        **walk_facts,
    }
    if not is_server_sample:
        config = load_performance_config(Path(args.budgets))
        issues = [
            *validity_issues(run, config),
            *(issue for issue in budget_issues(run, config) if issue.kind == "invalid"),
        ]
        if issues:
            raise SystemExit(
                "browser performance record is inadmissible:\n"
                f"{format_issues(issues)}\n"
                "Keep the tab visible, interact while it loads, wait for settle, and use the "
                "navigation-time profiler exposed by the current build."
            )
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    with RESULTS.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(run, sort_keys=True) + "\n")
    walk = run.get("walk_elapsed_ms")
    regime = f"walk {walk} ms" if walk else f"walk {run.get('walk_status', 'unknown')}"
    print(
        f"recorded {run['experiment'] or '-'}/{label} port {port} "
        f"({run.get('files')} files, {regime}) -> {RESULTS.relative_to(REPO)}"
    )
    hard: list[Any] = []
    if config is not None:
        misses = [issue for issue in budget_issues(run, config) if issue.kind == "budget"]
        hard = [issue for issue in misses if issue.policy == "gate"]
        targets = [issue for issue in misses if issue.policy == "target"]
        print(
            f"performance budgets: {len(hard)} hard-gate miss(es), "
            f"{len(targets)} roadmap-target miss(es)"
        )
        if hard:
            print("run retained as evidence, but its hard performance gate failed:")
            print(format_issues(hard))
    return 1 if hard else 0


def cmd_capture(args: argparse.Namespace) -> int:
    """Capture one Chrome profile with trusted input, then optionally record it."""
    if args.record and not args.headed:
        raise SystemExit("--headed is required when --record creates acceptance evidence")
    pending = _read_pending()
    port = pending.get("port")
    if not isinstance(port, int):
        raise SystemExit("pending browser run has no valid port")
    node = shutil.which("node")
    if node is None:
        raise SystemExit("node is required for browser capture")
    output = Path(args.output).expanduser().resolve()
    command = [
        node,
        str(CAPTURE_BROWSER),
        "--url",
        f"http://127.0.0.1:{port}/view/",
        "--probe",
        str(PROBE),
        "--output",
        str(output),
        "--timeout-ms",
        str(args.timeout_ms),
        "--width",
        str(args.width),
        "--height",
        str(args.height),
    ]
    if args.chrome:
        command.extend(["--chrome", args.chrome])
    if args.headed:
        command.append("--headed")
    result = subprocess.run(command, cwd=REPO, check=False)
    if result.returncode != 0 or not args.record:
        return result.returncode
    return cmd_record(
        argparse.Namespace(
            budgets=args.budgets,
            json=None,
            json_file=str(output),
            label=args.label,
            note=args.note,
        )
    )


def _summarize(runs: list[dict[str, Any]], metric: str) -> str:
    values = [r[metric] for r in runs if isinstance(r.get(metric), (int, float))]
    if not values:
        return "-"
    if len(values) == 1:
        return f"{values[0]:,}"
    return f"{round(median(values)):,} ({min(values):,}-{max(values):,})"


def cmd_compare(args: argparse.Namespace) -> int:
    runs = _load_runs()
    labels = args.labels
    by_label = {label: [r for r in runs if r.get("label") == label] for label in labels}
    missing = [label for label, rows in by_label.items() if not rows]
    if missing:
        raise SystemExit(f"no runs recorded for: {', '.join(missing)}")

    width = max(len(m) for m in METRICS) + 2
    header = "metric".ljust(width) + "".join(
        f"{label} (n={len(by_label[label])})".ljust(28) for label in labels
    )
    print(header)
    print("-" * len(header))
    for metric in METRICS:
        row = metric.ljust(width)
        for label in labels:
            row += _summarize(by_label[label], metric).ljust(28)
        print(row)
    print()
    print("Median with the range beside it. A median whose ranges overlap is not a result;")
    print("see the accept rule in explorations/performance-loop/README.md before writing one down.")

    config = load_performance_config(Path(args.budgets))
    browser_by_label = {
        label: [run for run in rows if "route" not in run] for label, rows in by_label.items()
    }
    if not any(browser_by_label.values()):
        return 0

    evidence_errors: list[str] = []
    for label, rows in browser_by_label.items():
        if len(rows) < config.requirements.minimum_runs_per_condition:
            evidence_errors.append(
                f"{label}: {len(rows)} browser run(s), need at least "
                f"{config.requirements.minimum_runs_per_condition}"
            )
        for index, run in enumerate(rows, start=1):
            invalid = [
                *validity_issues(run, config),
                *(issue for issue in budget_issues(run, config) if issue.kind == "invalid"),
            ]
            if invalid:
                evidence_errors.append(f"{label} run {index}:\n{format_issues(invalid)}")

    candidate_label = labels[-1]
    candidate_issues = [
        issue
        for run in browser_by_label[candidate_label]
        for issue in budget_issues(run, config)
        if issue.kind == "budget"
    ]
    hard_failures = blocking_issues(candidate_issues)
    target_misses = [issue for issue in candidate_issues if issue.policy == "target"]

    print()
    print(f"Performance gate ({candidate_label} is the candidate):")
    if evidence_errors:
        print("  INVALID")
        for error in evidence_errors:
            print(f"  {error}")
    if hard_failures:
        print("  FAIL")
        print(format_issues(hard_failures))
    if not evidence_errors and not hard_failures:
        print("  PASS — evidence is admissible and every hard responsiveness budget passed")
    if target_misses:
        unique_targets = sorted({issue.message for issue in target_misses})
        print("  Roadmap targets still open:")
        for message in unique_targets:
            print(f"  - {message}")
    return 1 if evidence_errors or hard_failures else 0


def _sample_route(port: int, path: str) -> tuple[float, float | None, int]:
    """One request: wall milliseconds, the server's own share, response bytes.

    ``Server-Timing: srv;dur=`` is set by the request middleware and measures
    entry to response start, which is what separates a slow handler from a
    request that merely queued behind one.
    """
    url = f"http://127.0.0.1:{port}{path}"
    request = urllib.request.Request(url, headers={"Accept-Encoding": "gzip"})
    start = time.monotonic()
    with urllib.request.urlopen(request, timeout=60) as response:
        body = response.read()
        header = response.headers.get("server-timing", "") or ""
    wall_ms = (time.monotonic() - start) * 1000.0
    match = re.search(r"srv;dur=([0-9.]+)", header)
    return wall_ms, (float(match.group(1)) if match else None), len(body)


def cmd_probe_server(args: argparse.Namespace) -> int:
    """Sample a route repeatedly across a whole scan, then once settled.

    The browser half cannot measure a server-side hypothesis honestly: the
    pane takes seconds to start, so whether a page load lands inside the walk
    or after it is luck, and a route that costs 1,500 ms while scanning and
    15 ms settled will report either number depending on that luck. This
    samples from here instead -- every ``--every`` seconds from the moment the
    socket answers until the walk ends, then again once settled -- so a run
    reports the shape of the cost in both regimes rather than one draw from
    whichever it happened to hit.
    """
    pending = _read_pending()
    port = int(pending["port"])
    samples: list[dict[str, Any]] = []
    deadline = time.monotonic() + args.timeout

    while time.monotonic() < deadline:
        try:
            status_body = urllib.request.urlopen(
                f"http://127.0.0.1:{port}/api/index/progress", timeout=10
            ).read()
            status = cast("dict[str, Any]", json.loads(status_body))
        except OSError:
            break
        complete = bool(status.get("complete"))
        wall_ms, srv_ms, size = _sample_route(port, args.path)
        samples.append(
            {
                "at_s": round(time.monotonic() - (deadline - args.timeout), 2),
                "scanning": not complete,
                "indexed_files": status.get("indexed_files"),
                "wall_ms": round(wall_ms, 1),
                "srv_ms": srv_ms,
                "bytes": size,
            }
        )
        if complete:
            break
        time.sleep(args.every)

    # Settled: give the index a beat to quiesce, then sample the same route.
    time.sleep(0.5)
    for _ in range(args.settled):
        wall_ms, srv_ms, size = _sample_route(port, args.path)
        samples.append(
            {
                "at_s": round(time.monotonic() - (deadline - args.timeout), 2),
                "scanning": False,
                "indexed_files": None,
                "wall_ms": round(wall_ms, 1),
                "srv_ms": srv_ms,
                "bytes": size,
            }
        )

    scanning = [s for s in samples if s["scanning"]]
    settled = [s for s in samples if not s["scanning"]]

    def stat(rows: list[dict[str, Any]], key: str) -> str:
        values = [float(r[key]) for r in rows if isinstance(r.get(key), (int, float))]
        if not values:
            return "-"
        return f"{median(values):,.0f} ({min(values):,.0f}-{max(values):,.0f})"

    print(f"route {args.path} on port {port}, {len(samples)} samples")
    print(
        f"  scanning n={len(scanning):<3} wall {stat(scanning, 'wall_ms')} ms   srv {stat(scanning, 'srv_ms')} ms"
    )
    print(
        f"  settled  n={len(settled):<3} wall {stat(settled, 'wall_ms')} ms   srv {stat(settled, 'srv_ms')} ms"
    )

    payload = {
        "route": args.path,
        "srv_scanning_ms": round(
            median([float(s["srv_ms"]) for s in scanning if s["srv_ms"] is not None]), 1
        )
        if any(s["srv_ms"] is not None for s in scanning)
        else None,
        "srv_settled_ms": round(
            median([float(s["srv_ms"]) for s in settled if s["srv_ms"] is not None]), 1
        )
        if any(s["srv_ms"] is not None for s in settled)
        else None,
        "wall_scanning_ms": round(median([float(s["wall_ms"]) for s in scanning]), 1)
        if scanning
        else None,
        "wall_settled_ms": round(median([float(s["wall_ms"]) for s in settled]), 1)
        if settled
        else None,
        "scanning_samples": len(scanning),
        "settled_samples": len(settled),
        "samples": samples,
    }
    print()
    print(json.dumps(payload))
    return 0


def cmd_count(args: argparse.Namespace) -> int:
    root = Path(args.tree).expanduser().resolve()
    files, dirs = _count_tree(root)
    print(f"label   {_tree_label(root)}")
    print(f"files   {files:,}")
    print(f"dirs    {dirs:,}")
    return 0


def cmd_probe(_args: argparse.Namespace) -> int:
    """Print the probe, so what runs is what is committed."""
    print(PROBE.read_text(encoding="utf-8"))
    return 0


def _experiment_records() -> list[dict[str, Any]]:
    """The YAML front matter of every experiment artifact, id-ordered.

    Parsed with a deliberately small reader rather than a YAML dependency:
    the ledger needs six scalars out of the verdict block, and the artifacts
    are schema-validated by `softschema validate` anyway, which is where a
    malformed one should fail.
    """
    records: list[dict[str, Any]] = []
    for path in sorted(EXPERIMENTS.glob("exp-*.md")):
        text = path.read_text(encoding="utf-8")
        if not text.startswith("---"):
            continue
        front = text.split("---", 2)[1]
        record: dict[str, Any] = {"path": path.name}
        for key in ("id", "title", "date"):
            match = re.search(rf"^  {key}: \"?([^\"\n]+)\"?$", front, re.MULTILINE)
            if match:
                record[key] = match.group(1).strip()
        hyps = re.search(r"^  hypotheses:\n((?:    - \w+\n)+)", front, re.MULTILINE)
        record["hypotheses"] = re.findall(r"- (\w+)", hyps.group(1)) if hyps else []
        verdict = front.split("  verdict:", 1)
        if len(verdict) == 2:
            for key in ("decision", "primary_metric", "commit"):
                match = re.search(rf"^    {key}: \"?([^\"\n]+)\"?$", verdict[1], re.MULTILINE)
                if match:
                    record[key] = match.group(1).strip()
        records.append(record)
    return records


def _headline_for(artifact: str, metric: str) -> tuple[str | None, str | None]:
    """The control and candidate medians an artifact recorded for *metric*."""
    text = (EXPERIMENTS / artifact).read_text(encoding="utf-8")
    block = re.search(rf"- metric: {re.escape(metric)}\n(?:      \w+:.*\n)+", text)
    if block is None:
        return None, None
    control = re.search(r"control_median: ([0-9.]+)", block.group(0))
    candidate = re.search(r"candidate_median: ([0-9.]+)", block.group(0))
    if control is None or candidate is None:
        return None, None
    return f"{float(control.group(1)):,.0f}", f"{float(candidate.group(1)):,.0f}"


_DECISION_MARK = {
    "accepted": "accepted",
    "rejected": "rejected",
    "superseded": "superseded",
    "baseline": "baseline",
    "unresolved": "unresolved",
}


def cmd_report(_args: argparse.Namespace) -> int:
    """Regenerate report.md from the recorded runs and the artifacts.

    Absolute numbers, not just deltas. A change recorded only as "-67%" cannot
    be checked against a later run on the same corpus, and cannot say whether
    the thing is fast now -- only that it moved.
    """
    runs = _load_runs()
    experiments = _experiment_records()
    lines: list[str] = []
    add = lines.append

    add("# Load-Time Exploration Ledger")
    add("")
    add("Generated by `explorations/performance-loop/run.py report` from the recorded runs in")
    add("[results/runs.jsonl](results/runs.jsonl) and the artifacts in")
    add("[experiments/](experiments/). Do not edit by hand.")
    add("")
    add("Each experiment is one soft-schema artifact: validated YAML front matter carries")
    add("the measured numbers and the verdict, and the Markdown body carries the reasoning")
    add("a schema cannot hold. How a round is run, and the rule that decides whether a")
    add("change is kept: [the loop's README](README.md).")
    add("")

    accepted = [r for r in experiments if r.get("decision") == "accepted"]
    if accepted:
        add("## Where it stands")
        add("")
        add("The measure each accepted round moved, as an absolute number rather than a")
        add("percentage: a percentage cannot be checked against a later run, and cannot say")
        add("whether the thing is fast -- only that it moved.")
        add("")
        add("| measure | before | after | round |")
        add("| --- | ---: | ---: | --- |")
        for record in accepted:
            metric = str(record.get("primary_metric", ""))
            before, after = _headline_for(str(record["path"]), metric)
            if before is None or after is None:
                continue
            # A round accepted on other grounds still shows the metric it named,
            # with the direction marked. Quietly swapping in whichever metric
            # passed is the exact dishonesty the accept rule forbids.
            note = ""
            if float(after.replace(",", "")) >= float(before.replace(",", "")):
                note = " (accepted on other grounds; see the round)"
            add(f"| `{metric}` | {before} | **{after}**{note} | {record.get('id')} |")
        add("")
        add("Each row is one round's own control and candidate on the same corpus and")
        add("machine, not a running total: they measure different things and do not")
        add("compose. A round whose named metric did not improve says so here rather")
        add("than being restated against one that did.")
        add("")

    add("## Experiments")
    add("")
    if experiments:
        add("| # | Experiment | Hypotheses | Primary metric | Verdict |")
        add("| --- | --- | --- | --- | --- |")
        for record in experiments:
            decision = _DECISION_MARK.get(str(record.get("decision", "")), "-")
            add(
                f"| {record.get('id', '-')} "
                f"| [{record.get('title', record['path'])}]({EXPERIMENTS.name}/{record['path']}) "
                f"| {', '.join(record.get('hypotheses', [])) or '-'} "
                f"| `{record.get('primary_metric', '-')}` "
                f"| {decision} |"
            )
    else:
        add("None recorded yet.")
    add("")

    add("## Absolute numbers, per condition")
    add("")
    add("Median with the range beside it, over every recorded run of that condition.")
    add("Absolute rather than relative on purpose: a percentage cannot be checked against")
    add("a later run, and cannot say whether the thing is fast -- only that it moved.")
    add("Conditions are grouped by corpus, because none of these numbers compare across one.")
    add("")

    by_corpus: dict[Any, list[dict[str, Any]]] = {}
    for run in runs:
        by_corpus.setdefault(run.get("files"), []).append(run)

    for files in sorted(by_corpus, key=lambda value: (value is None, value)):
        corpus_runs = by_corpus[files]
        add(f"### {files:,} files" if isinstance(files, int) else "### corpus unrecorded")
        add("")
        # Browser runs and route samples answer different questions and share no
        # metrics, so one grid holding both is mostly empty cells. Split them.
        for title, kind, is_server in (
            ("What a reader gets", "browser probe", False),
            ("What a route costs", "server probe", True),
        ):
            group = [r for r in corpus_runs if ("route" in r) == is_server]
            if not group:
                continue
            labels: list[str] = []
            for run in group:
                label = str(run.get("label"))
                if label not in labels:
                    labels.append(label)
            rows: list[tuple[str, list[str]]] = []
            for metric in METRICS:
                cells = [
                    _summarize([r for r in group if r.get("label") == label], metric)
                    for label in labels
                ]
                if not all(cell == "-" for cell in cells):
                    rows.append((metric, cells))
            if not rows:
                continue
            add(f"**{title}** — {kind}")
            add("")
            add(
                "| metric | "
                + " | ".join(
                    f"{label} (n={sum(1 for r in group if r.get('label') == label)})"
                    for label in labels
                )
                + " |"
            )
            add("| --- | " + " | ".join("---:" for _ in labels) + " |")
            for metric, cells in rows:
                add(f"| `{metric}` | " + " | ".join(cells) + " |")
            add("")
        walks = sorted(
            value
            for value in (r.get("walk_elapsed_ms") for r in corpus_runs)
            if isinstance(value, int)
        )
        if walks:
            add(
                f"Walk elapsed across these runs: {min(walks):,}-{max(walks):,} ms. "
                "A run loaded during a walk and a run loaded after one are different regimes."
            )
            add("")

    add("## Provenance")
    add("")
    add("| experiment | label | recorded | build | commit | corpus | shape | harness | walk |")
    add("| --- | --- | --- | --- | --- | --- | ---: | ---: | --- |")
    for run in runs:
        walk = run.get("walk_elapsed_ms")
        walk_text = f"{walk:,} ms" if isinstance(walk, int) else str(run.get("walk_status", "-"))
        commit = str(run.get("commit") or "-")
        if run.get("dirty"):
            commit += "+dirty"
        add(
            f"| {run.get('experiment') or '-'} | {run.get('label')} "
            f"| {str(run.get('recorded_at') or '-')[:16]} "
            f"| {run.get('build_version') or '-'} | {commit} "
            f"| {run.get('corpus') or run.get('files') or '-'} "
            f"| {run.get('corpus_shape') if run.get('corpus_shape') is not None else '-'} "
            f"| {run.get('harness_version') or '-'} | {walk_text} |"
        )
    add("")
    add("<!-- Generated file. Regenerate with `explorations/performance-loop/run.py report`. -->")
    add("")
    add("<!-- This document follows common-doc-guidelines.md.")
    add("See github.com/jlevy/practical-prose and review guidelines before editing.")
    add("-->")

    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {REPORT.relative_to(REPO)} ({len(experiments)} experiments, {len(runs)} runs)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="One round of the load-time exploration loop.")
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="restart the server on an unused port")
    serve.add_argument("--files", type=int, default=100_000)
    serve.add_argument(
        "--tree",
        default="",
        help="serve a real directory instead of a synthetic corpus; recorded by name "
        "and a hash of its path, never by the path itself",
    )
    serve.add_argument("--exp", default="", help="experiment id this run belongs to, e.g. exp-003")
    serve.add_argument("--label", default="", help="condition name, e.g. before / after")
    serve.add_argument("--note", default="")
    serve.add_argument(
        "--metab",
        default="",
        help="external Metabrowser console script; requires --build-ref",
    )
    serve.add_argument(
        "--build-ref",
        default="",
        help="immutable commit or tag identifying the external build",
    )
    serve.set_defaults(func=cmd_serve)

    probe = sub.add_parser("probe", help="print probe.js for pasting into the page")
    probe.set_defaults(func=cmd_probe)

    server_probe = sub.add_parser(
        "probe-server", help="sample one route across the scan and once settled"
    )
    server_probe.add_argument("--path", default="/api/tree?depth=1")
    server_probe.add_argument("--every", type=float, default=1.0)
    server_probe.add_argument("--settled", type=int, default=5)
    server_probe.add_argument("--timeout", type=float, default=180.0)
    server_probe.set_defaults(func=cmd_probe_server)

    record = sub.add_parser("record", help="append one probe payload")
    record_source = record.add_mutually_exclusive_group(required=True)
    record_source.add_argument("--json", help="the probe's printed JSON")
    record_source.add_argument("--json-file", help="file containing the exported probe JSON")
    record.add_argument("--label", default="", help="override the label `serve` set")
    record.add_argument("--note", default="")
    record.add_argument(
        "--budgets",
        default=str(PERFORMANCE_BUDGETS),
        help="performance requirements and budgets TOML",
    )
    record.set_defaults(func=cmd_record)

    capture = sub.add_parser(
        "capture",
        help="capture a fresh Chrome profile with trusted input for the pending serve run",
    )
    capture.add_argument("--output", required=True, help="write the exported profile JSON here")
    capture.add_argument("--chrome", default="", help="Chrome or Chromium executable")
    capture.add_argument(
        "--headed",
        action="store_true",
        help="show and foreground Chrome; required for acceptance-quality visual timing",
    )
    capture.add_argument("--timeout-ms", type=int, default=180_000)
    capture.add_argument("--width", type=int, default=1600)
    capture.add_argument("--height", type=int, default=900)
    capture.add_argument(
        "--record",
        action="store_true",
        help="append the profile and apply the current evidence and budget gates",
    )
    capture.add_argument("--label", default="", help="override the label `serve` set")
    capture.add_argument("--note", default="")
    capture.add_argument(
        "--budgets",
        default=str(PERFORMANCE_BUDGETS),
        help="performance requirements and budgets TOML",
    )
    capture.set_defaults(func=cmd_capture)

    compare = sub.add_parser("compare", help="median and range per label")
    compare.add_argument("labels", nargs="+")
    compare.add_argument(
        "--budgets",
        default=str(PERFORMANCE_BUDGETS),
        help="performance requirements and budgets TOML",
    )
    compare.set_defaults(func=cmd_compare)

    count = sub.add_parser("count", help="files and directories in a real tree")
    count.add_argument("tree")
    count.set_defaults(func=cmd_count)

    report = sub.add_parser("report", help="regenerate report.md from runs and artifacts")
    report.set_defaults(func=cmd_report)

    args = parser.parse_args(argv)
    if shutil.which("uv") is None:
        raise SystemExit("uv is required; see docs/development.md")
    result: int = args.func(args)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
