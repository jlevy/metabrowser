---
type: is
id: is-01m7kpmf2bmaqx2fy8f3ytp3yq
title: "CI speed 1.4: read per-module and per-golden time from a run under xdist in devtools/suite_report.py, and update the testing guide's tiers and measuring sections"
kind: task
status: closed
priority: 2
version: 5
spec_path: docs/project/specs/active/plan-2026-11-16-fast-ci.md
delegate: claude-code@vm
labels: []
dependencies: []
parent_id: is-01m7kh4k0qtd75277xcq14dt1b
hold: null
hold_until: null
created_at: 2026-11-17T02:51:01.578Z
updated_at: 2026-11-17T05:36:58.291Z
started_at: 2026-11-17T04:43:53.372Z
closed_at: 2026-11-17T05:36:58.291Z
close_reason: "153fb313 (suite_timing --file-durations, suite_report reads it and run_goldens' golden: lines, old logs by timestamps; e2e-testing markers, tiers, gates, measuring) and fa105e85 (the four targets, PYTEST_WORKERS, SHARD in docs/e2e-testing.md and docs/development.md), on PR branch claude/ci-parallel-tests."
resolution: null
duplicate_of: null
---
Phase 1 of plan-2026-11-16-fast-ci.md. parse_log takes a module's time from the gap between consecutive progress lines, which a run under xdist does not print per module, and a golden's time from the gap before tryscript's verdict, which concurrent files break. Read durations another way (for example a JUnit XML report or --durations=0) and the golden runner's own times. Update docs/e2e-testing.md (Test Tiers, Measuring the Suite) and docs/development.md for the four targets (test-parallel, test-serial, test-chrome, test-goldens), the serial and chrome markers and what each means, PYTEST_WORKERS, and SHARD.

## Notes

2026-11-17: committed 153fb313 on claude/ci-parallel-tests: tests/suite_timing.py (--file-durations, per-file time summed from reports, works under xdist), suite_report reads that section, run_goldens' golden: lines, and every pytest session of a job (old logs still read by timestamps); docs/e2e-testing.md updated for the markers, tiers, --shard, gates, golden runner, and measuring. Left open: the docs for test-parallel/test-serial/test-chrome/test-goldens, PYTEST_WORKERS, and SHARD land in mb-dz35's commit, which adds them; close this bead then.
