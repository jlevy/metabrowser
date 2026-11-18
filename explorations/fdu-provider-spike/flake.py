"""Repeat timing-sensitive route tests per provider, each run in a fresh process.

Separate processes, alternating providers, so no run inherits another's module state
or event loop. Output: ``evidence/flake.json`` with pass and fail counts per test and
provider, and the failing assertion of each failure.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import cast

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
TESTS = (
    "tests/test_e2e_filesystem_to_sse.py::test_rm_directory_coalesces_descendant_removals",
    "tests/test_e2e_filesystem_to_sse.py::test_touch_existing_file_emits_one_upsert_path",
)
_CHILD = r"""
import json, sys
from probe import AdapterProbe
from routes import run_selection
outcome = run_selection((sys.argv[1],), AdapterProbe(), inject=sys.argv[2] == "fdu")
rows = outcome["results"]
print("RESULT " + json.dumps({"outcome": rows[0]["outcome"] if rows else "missing",
    "backends": rows[0]["fdu_backends_built"] if rows else 0,
    "detail": rows[0]["detail"][-300:] if rows else ""}))
"""


def _repeat(test: str, runs: int) -> dict[str, object]:
    counts: dict[str, Counter[str]] = {"python": Counter(), "fdu": Counter()}
    failures: dict[str, Counter[str]] = {"python": Counter(), "fdu": Counter()}
    backends: dict[str, Counter[int]] = {"python": Counter(), "fdu": Counter()}
    environment = {**os.environ, "PYTHONPATH": f"src:tests:{HERE}"}
    for run in range(runs):
        for provider in ("python", "fdu") if run % 2 == 0 else ("fdu", "python"):
            completed = subprocess.run(
                [sys.executable, "-c", _CHILD, test, provider],
                capture_output=True,
                text=True,
                cwd=REPO,
                env=environment,
                check=False,
            )
            line = next(
                (row for row in completed.stdout.splitlines() if row.startswith("RESULT ")), ""
            )
            result = json.loads(line.removeprefix("RESULT ")) if line else {"outcome": "error"}
            counts[provider][result["outcome"]] += 1
            backends[provider][int(result.get("backends", 0))] += 1
            if result["outcome"] == "failed":
                assertion = next(
                    (part.strip() for part in result["detail"].splitlines() if "assert" in part),
                    "?",
                )
                failures[provider][assertion] += 1
    return {
        "outcomes": {provider: dict(counter) for provider, counter in counts.items()},
        "failing_assertions": {provider: dict(counter) for provider, counter in failures.items()},
        "fdu_backends_per_run": {
            provider: {str(key): value for key, value in counter.items()}
            for provider, counter in backends.items()
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=32)
    args = parser.parse_args()
    record = {
        "runs_per_provider": args.runs,
        "isolation": "a fresh process per run, providers alternating",
        "tests": {test: _repeat(test, args.runs) for test in TESTS},
    }
    suffix = "" if sys.platform.startswith("linux") else f"-{sys.platform}"
    out = HERE / "evidence" / f"flake{suffix}.json"
    out.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(out)
    for test, result in cast("dict[str, dict[str, object]]", record["tests"]).items():
        print(test, result["outcomes"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
