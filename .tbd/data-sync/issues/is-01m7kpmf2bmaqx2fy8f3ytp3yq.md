---
type: is
id: is-01m7kpmf2bmaqx2fy8f3ytp3yq
title: "CI speed 1.4: read per-module and per-golden time from a run under xdist in devtools/suite_report.py, and update the testing guide's tiers and measuring sections"
kind: task
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-16-fast-ci.md
labels: []
dependencies: []
parent_id: is-01m7kh4k0qtd75277xcq14dt1b
created_at: 2026-11-17T02:51:01.578Z
updated_at: 2026-11-17T02:51:01.578Z
---
Phase 1 of plan-2026-11-16-fast-ci.md. parse_log takes a module's time from the gap between consecutive progress lines, which a run under xdist does not print per module, and a golden's time from the gap before tryscript's verdict, which concurrent files break. Read durations another way (for example a JUnit XML report or --durations=0) and the golden runner's own times. Update docs/e2e-testing.md (Test Tiers, Measuring the Suite) and docs/development.md for the three targets, the serial marker, PYTEST_WORKERS, and SHARD.
