"""One round of the load-time exploration loop.

Four commands, and a browser sits between the first two:

    explorations/run.py serve --exp exp-003 --label before --files 300000
    explorations/run.py probe          # prints probe.js; evaluate it in the page
    explorations/run.py record --json '<paste>'
    explorations/run.py compare before after
    explorations/run.py report         # regenerate the ledger

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
without its range says less. ``report`` regenerates the ledger in
``report.md`` from the recorded runs and the experiment artifacts. The accept
rule is in ``explorations/README.md``; it is a judgment, not something this
file computes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
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
REPORT = HERE / "report.md"
EXPERIMENTS = HERE / "experiments"
# What `serve` last set up. `record` reads it so a paste cannot be filed
# against the wrong experiment, port, or corpus -- the three things that are
# invisible in the payload and expensive to get wrong.
PENDING = HERE / "results" / "pending.json"
# Bumped when a change to run.py or probe.js makes a number incomparable with
# earlier ones -- a new metric definition, a changed sampling rule. Recorded on
# every run so a later reader can tell "measured differently" from "changed".
HARNESS_VERSION = 2
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
    "long_tasks",
    "long_task_ms_total",
    "render_spans",
    "render_ms_total",
    "tree_reprobe_ms",
    "tree_reprobe_srv_ms",
    "srv_scanning_ms",
    "srv_settled_ms",
    "wall_scanning_ms",
    "wall_settled_ms",
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
    raise SystemExit(f"no free port in {FIRST_PORT}-{LAST_PORT}; clear results/runs.jsonl")


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
            "no pending run: start one with `explorations/run.py serve --exp <id> --label <name>`"
        )
    loaded: Any = json.loads(PENDING.read_text(encoding="utf-8"))
    return cast("dict[str, Any]", loaded)


def cmd_serve(args: argparse.Namespace) -> int:
    if args.tree:
        real = Path(args.tree).expanduser().resolve()
        if not real.is_dir():
            raise SystemExit(f"not a directory: {real}")
        return _serve_root(args, real, _tree_label(real), args.files)
    corpus = _corpus_dir(args.files)
    if not corpus.is_dir():
        print(f"building corpus ({args.files} files) at {corpus} ...", flush=True)
        corpus.mkdir(parents=True, exist_ok=True)
        sys.path.insert(0, str(REPO))
        from devtools.bench_serving import build_corpus

        build_corpus(corpus, args.files)
    return _serve_root(args, corpus, str(corpus.relative_to(REPO)), args.files)


def _serve_root(args: argparse.Namespace, root: Path, corpus_label: str, files: int) -> int:
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
            ["uv", "run", "--frozen", "metab", str(root), "--no-open", "--port", str(port)],
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

    PENDING.write_text(
        json.dumps(
            {
                "experiment": args.exp,
                "label": args.label,
                "port": port,
                "files": files,
                "corpus": corpus_label,
                "corpus_shape": _corpus_shape(root),
                "commit": _git_commit(),
                "dirty": _git_dirty(),
                "note": args.note,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"experiment  {args.exp or '(unset)'}   label {args.label or '(unset)'}")
    print(f"port        {port}   (unused, so the browser cache starts empty)")
    print(f"corpus      {corpus_label}  ({files} files)")
    print(f"url         {url}")
    print()
    print("1. size the browser pane to at least 1280x900 and load that URL cold")
    print("2. evaluate explorations/probe.js in the page (`run.py probe` prints it)")
    print("3. explorations/run.py record --json '<paste>'")
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
    # A `probe-server` payload is a route sample, not a page load: it has no
    # viewport by construction and the floor below does not apply to it.
    is_server_sample = "route" in probe
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
    run: dict[str, Any] = {
        "experiment": pending.get("experiment"),
        "label": label,
        "port": port,
        "files": pending.get("files"),
        "corpus": pending.get("corpus"),
        "commit": pending.get("commit"),
        "dirty": pending.get("dirty"),
        "recorded_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "harness_version": HARNESS_VERSION,
        "corpus_shape": pending.get("corpus_shape"),
        "note": args.note or pending.get("note", ""),
        **_walk_facts(port),
        **payload,
    }
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    with RESULTS.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(run, sort_keys=True) + "\n")
    walk = run.get("walk_elapsed_ms")
    regime = f"walk {walk} ms" if walk else f"walk {run.get('walk_status', 'unknown')}"
    print(
        f"recorded {run['experiment'] or '-'}/{label} port {port} "
        f"({run.get('files')} files, {regime}) -> {RESULTS.relative_to(REPO)}"
    )
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
    add("Generated by `explorations/run.py report` from the recorded runs in")
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
    add("| experiment | label | recorded | commit | corpus | shape | harness | walk |")
    add("| --- | --- | --- | --- | --- | ---: | ---: | --- |")
    for run in runs:
        walk = run.get("walk_elapsed_ms")
        walk_text = f"{walk:,} ms" if isinstance(walk, int) else str(run.get("walk_status", "-"))
        commit = str(run.get("commit") or "-")
        if run.get("dirty"):
            commit += "+dirty"
        add(
            f"| {run.get('experiment') or '-'} | {run.get('label')} "
            f"| {str(run.get('recorded_at') or '-')[:16]} | {commit} "
            f"| {run.get('corpus') or run.get('files') or '-'} "
            f"| {run.get('corpus_shape') if run.get('corpus_shape') is not None else '-'} "
            f"| {run.get('harness_version') or '-'} | {walk_text} |"
        )
    add("")
    add("<!-- Generated file. Regenerate with `explorations/run.py report`. -->")
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
    record.add_argument("--json", required=True, help="the probe's printed JSON")
    record.add_argument("--label", default="", help="override the label `serve` set")
    record.add_argument("--note", default="")
    record.set_defaults(func=cmd_record)

    compare = sub.add_parser("compare", help="median and range per label")
    compare.add_argument("labels", nargs="+")
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
