"""One round of the load-time exploration loop.

Three commands, and the browser sits between the first two:

    explorations/run.py serve --files 100000
    # load the printed URL, evaluate explorations/probe.js, copy the JSON
    explorations/run.py record --label before --json '<paste>'
    explorations/run.py compare before after

``serve`` restarts the server on a port nothing has used this session. That is
the whole cold-cache mechanism: a port is part of the origin, so a new one
gives every static asset an empty HTTP cache without touching cache headers,
and a fresh process gives a scan that is still running. Both are what a reader
opening a large tree actually meets.

``record`` appends one run to ``results/runs.jsonl``. ``compare`` prints the
median of each metric per label with the range beside it, because on a corpus
this size a single run says very little and a median without its range says
less. The loop's accept rule is in ``explorations/README.md``; it is a
judgment, not something this file computes.
"""

from __future__ import annotations

import argparse
import json
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from statistics import median
from typing import Any, cast

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
RESULTS = HERE / "results" / "runs.jsonl"
# Every port `serve` has handed out, recorded the moment it does. A port whose
# run was never recorded has still been loaded in a browser, so reusing it would
# hand the next run a warm cache and quietly break the one property that makes
# these numbers cold.
PORTS_USED = HERE / "results" / "ports-used.txt"
PROBE = HERE / "probe.js"
# Ports climb so a rerun never reuses one and never inherits its cache.
# A run below this is refused: the tree pages its rows against the viewport, so
# numbers taken in a collapsed pane describe a layout no reader has.
MIN_VIEWPORT = (900, 600)
FIRST_PORT = 8600
LAST_PORT = 8699
# The metrics compare prints, in the order they matter to a reader.
METRICS = (
    "first_row_ms",
    "load_tree_ms",
    "dcl_ms",
    "load_ms",
    "last_resource_ms",
    "subtree_requests",
    "tree_items",
    "lazy_stubs",
    "dom_nodes",
    "transferred_kb",
    "vendor_first_start_ms",
    "viewport_w",
    "viewport_h",
)


def _corpus_dir(files: int) -> Path:
    return REPO / ".bench" / f"corpus-{files}"


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
    raise SystemExit(f"no free port in {FIRST_PORT}-{LAST_PORT}; clear results/runs.jsonl")


def _load_runs() -> list[dict[str, Any]]:
    if not RESULTS.is_file():
        return []
    runs: list[dict[str, Any]] = []
    for line in RESULTS.read_text(encoding="utf-8").splitlines():
        if line.strip():
            runs.append(json.loads(line))
    return runs


def cmd_serve(args: argparse.Namespace) -> int:
    corpus = _corpus_dir(args.files)
    if not corpus.is_dir():
        print(f"building corpus ({args.files} files) at {corpus} ...", flush=True)
        corpus.mkdir(parents=True, exist_ok=True)
        sys.path.insert(0, str(REPO))
        from devtools.bench_serving import build_corpus

        build_corpus(corpus, args.files)

    subprocess.run(["pkill", "-f", "metab .*--no-open --port"], check=False)
    while (
        subprocess.run(
            ["pgrep", "-f", "metab .*--no-open --port"], check=False, capture_output=True
        ).returncode
        == 0
    ):
        time.sleep(0.05)

    port = _next_port()
    PORTS_USED.parent.mkdir(parents=True, exist_ok=True)
    with PORTS_USED.open("a", encoding="utf-8") as handle:
        handle.write(f"{port}\n")
    log = HERE / "results" / f"server-{port}.log"
    with log.open("w", encoding="utf-8") as handle:
        subprocess.Popen(
            ["uv", "run", "--frozen", "metab", str(corpus), "--no-open", "--port", str(port)],
            cwd=REPO,
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

    print(f"port    {port}   (unused this session, so the browser cache starts empty)")
    print(f"corpus  {corpus}  ({args.files} files)")
    print(f"url     {url}")
    print()
    print("Load that URL cold, let the tree settle, then evaluate:")
    print(f"  {PROBE.relative_to(REPO)}")
    print(f"and record it with:  explorations/run.py record --label <name> --port {port}")
    return 0


def cmd_record(args: argparse.Namespace) -> int:
    payload: Any = json.loads(args.json)
    if not isinstance(payload, dict):
        raise SystemExit("probe payload must be a JSON object")
    # A browser pane that never got a size runs the app and reports plausible
    # timings while every layout-dependent number is measured against nothing.
    # That failure is silent from the numbers alone, so it is refused here
    # rather than discovered three experiments later.
    probe = cast("dict[str, Any]", payload)
    width = probe.get("viewport_w")
    height = probe.get("viewport_h")
    if not isinstance(width, int) or not isinstance(height, int):
        raise SystemExit("probe payload has no viewport; re-run with the current probe.js")
    if width < MIN_VIEWPORT[0] or height < MIN_VIEWPORT[1]:
        raise SystemExit(
            f"viewport was {width}x{height}, below the {MIN_VIEWPORT[0]}x{MIN_VIEWPORT[1]} "
            "floor. Size the browser pane and load the page again; the tree pages its "
            "rows against the viewport, so a run measured at this size is not a run."
        )
    run: dict[str, Any] = {
        "label": args.label,
        "port": args.port,
        "files": args.files,
        "note": args.note,
        **payload,
    }
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    with RESULTS.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(run, sort_keys=True) + "\n")
    print(f"recorded {args.label} run on port {args.port} -> {RESULTS.relative_to(REPO)}")
    return 0


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
    print("see the accept rule in explorations/README.md before writing one down.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="One round of the load-time exploration loop.")
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="restart the server on an unused port")
    serve.add_argument("--files", type=int, default=100_000)
    serve.set_defaults(func=cmd_serve)

    record = sub.add_parser("record", help="append one probe payload")
    record.add_argument("--label", required=True, help="condition name, e.g. before / after")
    record.add_argument("--json", required=True, help="the probe's printed JSON")
    record.add_argument("--port", type=int, required=True)
    record.add_argument("--files", type=int, default=100_000)
    record.add_argument("--note", default="")
    record.set_defaults(func=cmd_record)

    compare = sub.add_parser("compare", help="median and range per label")
    compare.add_argument("labels", nargs="+")
    compare.set_defaults(func=cmd_compare)

    args = parser.parse_args(argv)
    if shutil.which("uv") is None:
        raise SystemExit("uv is required; see docs/development.md")
    result: int = args.func(args)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
