# pyright: standard
# This module only reshapes untyped JSON written by bench.py; strict mode would add a
# cast per key without checking anything the JSON itself does not decide.
"""Normalize the raw timed series in .bench/fdu-spike/ into evidence/performance.json.

For every metric it reports each provider's samples, the A/A ratio of each provider's
two arms within a trial (the noise band), and the fdu/Python ratio of the same-letter
arms within a trial. Arms run in a rotated order, so same-letter arms are in the same
trial but can be up to three runs apart. An effect is called only when every paired
ratio lies outside the union of both providers' A/A bands; otherwise the verdict is
"within noise". An effect under 2x called with fewer than five runs per side is marked
provisional, as the performance loop's accept rule asks for at least five.
"""

from __future__ import annotations

import argparse
import datetime
import json
import statistics
import sys
from pathlib import Path
from typing import Any, cast

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
RAW = REPO / ".bench" / "fdu-spike"


def _get(value: Any, *path: object) -> Any:
    for key in path:
        if isinstance(value, dict) and key in value:
            value = cast("dict[object, Any]", value)[key]
        elif isinstance(value, list) and isinstance(key, int) and key < len(value):
            value = cast("list[Any]", value)[key]
        else:
            return None
    return value


def synthetic_metrics(result: dict[str, Any]) -> dict[str, float | None]:
    cold, attached, settled = (
        result.get(name, {}) for name in ("cold_scan", "scan_with_client", "settled")
    )
    metrics: dict[str, float | None] = {
        "cold_walk_ms": cold.get("walk_ms"),
        "cold_peak_rss_kb": _get(cold, "diagnostics", "process", "peak_rss_kb"),
        "cold_cpu_s": _get(cold, "diagnostics", "process", "cpu_seconds"),
        "attached_first_count_s": attached.get("first_count_s"),
        "attached_scan_wall_s": attached.get("wall_s"),
        "attached_rollup_p50_ms": _get(attached, "rollup_ms", "p50"),
        "attached_rollup_p95_ms": _get(attached, "rollup_ms", "p95"),
        "attached_rollup_requests": attached.get("requests_issued"),
        "attached_peak_rss_kb": _get(attached, "diagnostics", "process", "peak_rss_kb"),
        "attached_cpu_s": _get(attached, "diagnostics", "process", "cpu_seconds"),
        "settled_rollup_aggregated_p50_ms": _get(settled, "rollup_aggregated_ms", "p50"),
        "settled_rollup_aggregated_p95_ms": _get(settled, "rollup_aggregated_ms", "p95"),
        "settled_rollup_retained_p50_ms": _get(settled, "rollup_retained_body_ms", "p50"),
        "settled_rollup_304_p50_ms": _get(settled, "rollup_revalidated_304_ms", "p50"),
        "settled_navigation_first_ms": settled.get("navigation_first_ms"),
        "settled_navigation_reused_p50_ms": _get(settled, "navigation_reused_ms", "p50"),
        "settled_catalog_first_ms": settled.get("catalog_first_ms"),
        "settled_catalog_retained_p50_ms": _get(settled, "catalog_retained_body_ms", "p50"),
        "settled_clients_staggered_p50_ms": _get(settled, "clients_staggered_ms", "p50"),
        "settled_clients_simultaneous_p50_ms": _get(settled, "clients_simultaneous_ms", "p50"),
        "settled_rss_kb": _get(settled, "diagnostics", "process", "rss_kb"),
        "settled_peak_rss_kb": _get(settled, "diagnostics", "process", "peak_rss_kb"),
        "settled_cpu_s": _get(settled, "diagnostics", "process", "cpu_seconds"),
    }
    for tree in settled.get("tree") or []:
        key = f"settled_tree_{tree['path'].replace('/', '_').strip('<>')}_d{tree['depth']}"
        metrics[f"{key}_p50_ms"] = tree.get("p50")
        metrics[f"{key}_p95_ms"] = tree.get("p95")
    return metrics


def tree_metrics(result: dict[str, Any]) -> dict[str, float | None]:
    metrics: dict[str, float | None] = {
        "listening_s": result.get("listening_s"),
        "first_useful_read_s": result.get("first_useful_read_s"),
        "first_count_s": result.get("first_count_s"),
        "settled_s": result.get("settled_s"),
        "walk_ms": _get(result, "walk", "walk_ms"),
        "settled_rss_kb": result.get("settled_rss_kb"),
        "peak_rss_kb_sampled": result.get("peak_rss_kb_sampled"),
        "settled_cpu_s": result.get("settled_cpu_s"),
        "final_cpu_s": result.get("final_cpu_s"),
        "live_change_p50_ms": _get(result, "live_change_ms", "p50"),
        "live_change_p95_ms": _get(result, "live_change_ms", "p95"),
        "live_change_missed": result.get("live_change_missed"),
    }
    for route, summary in (result.get("fresh_route_ms") or {}).items():
        metrics[f"fresh_{route}_p50_ms"] = summary.get("p50")
        metrics[f"fresh_{route}_p95_ms"] = summary.get("p95")
    for route, summary in (result.get("retained_route_ms") or {}).items():
        metrics[f"retained_{route}_p50_ms"] = summary.get("p50")
    return metrics


def _ratio(after: float | None, before: float | None) -> float | None:
    if after is None or before is None or before == 0:
        return None
    return round(after / before, 3)


def paired(runs: list[dict[str, Any]], extract: Any) -> dict[str, Any]:
    by_trial: dict[int, dict[tuple[str, str], dict[str, float | None]]] = {}
    for run in runs:
        result = run.get("result")
        if not isinstance(result, dict) or result.get("error"):
            continue
        by_trial.setdefault(run["trial"], {})[(run["provider"], run["arm"])] = extract(result)
    names: list[str] = []
    for arms in by_trial.values():
        for metrics in arms.values():
            names.extend(name for name in metrics if name not in names)
    table: dict[str, Any] = {}
    for name in names:
        python: list[float] = []
        native: list[float] = []
        aa: list[float] = []
        pair: list[float] = []
        for arms in by_trial.values():
            values = {arm: metrics.get(name) for arm, metrics in arms.items()}
            python += [v for k, v in values.items() if k[0] == "python" and v is not None]
            native += [v for k, v in values.items() if k[0] == "fdu" and v is not None]
            for provider in ("python", "fdu"):
                ratio = _ratio(values.get((provider, "B")), values.get((provider, "A")))
                if ratio is not None:
                    aa.append(ratio)
            for arm in ("A", "B"):
                ratio = _ratio(values.get(("fdu", arm)), values.get(("python", arm)))
                if ratio is not None:
                    pair.append(ratio)
        if not python and not native:
            continue
        band = (min(aa), max(aa)) if aa else None
        verdict = "insufficient"
        if pair and band:
            low, high = (
                min(band[0], 1 / band[1] if band[1] else band[0]),
                max(band[1], 1 / band[0] if band[0] else band[1]),
            )
            if all(value < low for value in pair):
                verdict = "fdu lower, beyond A/A noise"
            elif all(value > high for value in pair):
                verdict = "fdu higher, beyond A/A noise"
            else:
                verdict = "within A/A noise"
        paired_median = statistics.median(pair) if pair else None
        provisional = (
            verdict.endswith("beyond A/A noise")
            and min(len(python), len(native)) < 5
            and paired_median is not None
            and 0.5 < paired_median < 2.0
        )
        table[name] = {
            "provisional": provisional,
            "python_median": round(statistics.median(python), 2) if python else None,
            "python_range": [min(python), max(python)] if python else None,
            "fdu_median": round(statistics.median(native), 2) if native else None,
            "fdu_range": [min(native), max(native)] if native else None,
            "n_python": len(python),
            "n_fdu": len(native),
            "aa_ratio_band": list(band) if band else None,
            "paired_fdu_over_python": pair,
            "paired_median": round(statistics.median(pair), 3) if pair else None,
            "verdict": verdict,
        }
    return table


def floors() -> dict[str, Any]:
    out: dict[str, Any] = {}
    for path in sorted(RAW.glob("floor-*.json")):
        record = json.loads(path.read_text())
        engines: dict[str, list[dict[str, Any]]] = {}
        for run in record["runs"]:
            engines.setdefault(run.get("engine", "?"), []).append(run)
        summary: dict[str, Any] = {}
        for engine, runs in engines.items():
            good = [run for run in runs if "wall_s" in run]
            entry: dict[str, Any] = {"n": len(good), "errors": len(runs) - len(good)}
            for key in (
                "wall_s",
                "cpu_s",
                "max_rss_kb",
                "open_returned_s",
                "discovered_s",
                "watching_s",
            ):
                values = [run[key] for run in good if key in run]
                if values:
                    entry[f"{key}_median"] = round(statistics.median(values), 4)
                    entry[f"{key}_range"] = [min(values), max(values)]
            if good:
                entry["files"] = good[0].get("files")
                entry["entries"] = good[0].get("entries")
                entry["final_phase"] = good[0].get("final_phase")
            summary[engine] = entry
        out[record["corpus"]] = {"host": record["host"], "engines": summary}
    return out


def projections() -> dict[str, Any]:
    out: dict[str, Any] = {}
    for path in sorted(RAW.glob("projections-*.json")):
        if "smoke" in path.name:
            continue
        record = json.loads(path.read_text())
        latency = record["latency"]
        table: dict[str, Any] = {}
        for kind, python in latency["ms"]["python"].items():
            native = latency["ms"]["fdu"][kind]
            table[kind] = {
                "python_p50_ms": python["p50"],
                "python_p95_ms": python["p95"],
                "fdu_p50_ms": native["p50"],
                "fdu_p95_ms": native["p95"],
                "ratio_p50": _ratio(native["p50"], python["p50"]),
                "n": python["n"],
            }
        out[record["corpus"]] = {
            "binding": record["binding"],
            "fresh_version_read_ms": table,
            "query_limits": latency["query_limits"],
        }
    return out


def _corpus_counts(runs: list[dict[str, Any]], key: str) -> dict[str, Any]:
    counts: dict[str, Any] = {}
    for run in runs:
        result = run.get("result") or {}
        walk = result.get("walk") or result.get("cold_scan") or {}
        if walk.get("files"):
            counts[run["provider"]] = {"files": walk.get("files"), "status": walk.get("status")}
    del key
    return counts


# The script versions the recorded Linux series ran, against what the repository holds.
# series.sh now records these itself and refuses uncommitted scripts; this series ran
# before it did, so the account is kept here, stated once.
_TIMED_SOURCES_NOTE = (
    "Stage synthetic ran adapter.py c19ea02d, probe.py 6d75b74e, launcher.py ed6370c9, "
    "bench.py 7ec88bec, and projections.py 4cc120b1, all held by commit 101b476d. Stages "
    "tree, floor, projections, and discovery ran the same adapter, probe, launcher, and "
    "projections, with bench.py 0d150f94 (7ec88bec plus the tree-response key fix), "
    "discovery.py 2da2983f, and series.sh 02732cc2; the floor stage was rerun with "
    "bench.py 91baaa4a (plus the observed-phase wait). bench.py 0d150f94 and 91baaa4a "
    "and discovery.py 2da2983f were never committed: the committed bench.py 786bc8d5 and "
    "discovery.py 5cb86f76 add only ruff formatting, lint, and typing casts, and later "
    "copies add a portable host record. firstread.py and binding.py ran adapter c03c8851, "
    "held by commit b6129b1c, which has every review fix except the change-batch "
    "dirty-path fix."
)


def _asgi_exceptions(stage_started: str) -> dict[str, Any]:
    """Unhandled server exceptions per recorded tree run, from its server log."""

    started = datetime.datetime.fromisoformat(stage_started.replace("Z", "+00:00"))
    rows: list[dict[str, Any]] = []
    for log in sorted((RAW / "logs").glob("tree-*.log")):
        stamp = datetime.datetime.fromtimestamp(int(log.stem.split("-")[-1]) / 1000, datetime.UTC)
        if stamp < started:
            continue
        text = log.read_text(errors="replace")
        corpus = "project-10" if "project-10" in text[:4000] else "checkout"
        rows.append(
            {
                "provider": log.stem.split("-")[1],
                "corpus": corpus,
                "asgi_exceptions": text.count("Exception in ASGI application"),
                "raised_in_api_rollup": text.count("in api_rollup"),
            }
        )
    return {
        "source": "server logs of the recorded tree runs (adapter c19ea02d)",
        "per_run": rows,
        "cause": (
            "an unpinned /api/rollup read during discovery: the timed adapter retried a "
            "moved version four times, then raised VersionUnavailableError, which the "
            "route does not handle. Adapter c03c8851 and later retry with back-off instead; "
            "firstread-* records zero such exceptions with it."
        ),
    }


def _labelled(pattern: str, key: str) -> dict[str, Any]:
    return {
        path.stem.split("-", 1)[1]: json.loads(path.read_text())[key]
        for path in sorted(RAW.glob(pattern))
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    suffix = "" if sys.platform.startswith("linux") else f"-{sys.platform}"
    parser.add_argument(
        "--output", type=Path, default=HERE / "evidence" / f"performance{suffix}.json"
    )
    args = parser.parse_args()
    digests_file = RAW / "frozen-digests.txt"
    digests = digests_file.read_text().splitlines() if digests_file.exists() else []
    record: dict[str, Any] = {
        "schema": "fdu-provider-spike-performance-v2",
        "frozen_sources": [line for line in digests if line.strip()],
        "timed_sources_note": _TIMED_SOURCES_NOTE if sys.platform.startswith("linux") else None,
        "method": (
            "Each trial runs four arms in a rotated order (python-A, fdu-A, python-B, fdu-B); "
            "A/A is the B/A ratio of one provider within one trial; paired is fdu/python for "
            "the same arm letter within one trial. Every server run is a fresh `metab` "
            "process through the same launcher shim and interpreter."
        ),
    }
    synthetic = RAW / "synthetic-100000.json"
    if synthetic.exists():
        data = json.loads(synthetic.read_text())
        record["synthetic_100000"] = {
            "host": data["host"],
            "corpus": _get(data, "runs", 0, "result", "corpus"),
            "runs": [
                {
                    "trial": run["trial"],
                    "provider": run["provider"],
                    "arm": run["arm"],
                    "exit": run["exit"],
                    "errors": _get(run, "result", "settled", "errors"),
                }
                for run in data["runs"]
            ],
            "metrics": paired(data["runs"], synthetic_metrics),
        }
    for label in ("tree-checkout", "tree-project-10"):
        path = RAW / f"{label}.json"
        if path.exists():
            data = json.loads(path.read_text())
            record[label.replace("-", "_")] = {
                "host": data["host"],
                "rounds": data["rounds"],
                "corpus_counts": _corpus_counts(data["runs"], label),
                "runs": [
                    {
                        "trial": run["trial"],
                        "provider": run["provider"],
                        "arm": run["arm"],
                        "error": _get(run, "result", "error"),
                        "subpath": _get(run, "result", "subpath"),
                        "route_statuses": _get(run, "result", "route_statuses"),
                        "diagnostics": _get(run, "result", "diagnostics"),
                    }
                    for run in data["runs"]
                ],
                "metrics": paired(data["runs"], tree_metrics),
            }
    if "synthetic_100000" in record:
        record["synthetic_100000"]["caveats"] = [
            "attached_rollup_* and attached_rollup_requests are not comparable: bench_serving's "
            "startup probe inside Server.__enter__ absorbed every rollup fdu could not answer "
            "during discovery, so fdu's one timed rollup came after settle; use "
            "attached_first_count_s.",
            "cpu_s values come from `ps time`, which has one-second resolution.",
        ]
    record["engine_floor"] = floors()
    record["discovery"] = {
        path.stem.removeprefix("discovery-"): json.loads(path.read_text())["summary"]
        for path in sorted(RAW.glob("discovery-*.json"))
    }
    record["projections"] = projections()
    record["binding_split"] = _labelled("binding-*.json", "binding_split")
    record["first_route_answer_socket_readiness"] = _labelled("firstread-*.json", "summary")
    series2 = RAW / "series2.log"
    if series2.exists():
        record["asgi_exceptions"] = _asgi_exceptions(series2.read_text().splitlines()[0])
    text = json.dumps(record, indent=2, sort_keys=True)
    text = text.replace(str(REPO), "<METABROWSER>").replace(str(Path.home()), "<HOME>")
    out = args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text + "\n", encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
