---
type: is
id: is-01m0prmjb4h8vh85kg5mh51vpn
title: "PR #72 review R2: frame_missing_px and regions_non_empty appear in zero recorded runs"
kind: bug
status: open
priority: 1
version: 1
labels: []
dependencies: []
parent_id: is-01m0prm49eb29wxywrqtdck27b
created_at: 2026-08-23T07:33:52.611Z
updated_at: 2026-08-23T07:33:52.611Z
---
results/runs.jsonl has 0 occurrences of either across 56 rows; all 10 new rows still carry the retired skeleton_complete and the old flat region_heights keyed on #tree-content. The committed probe.js has never produced a recorded row, so the 615px H52 baseline in README.md:216,263 and plan-2026-08-21-load-time-performance.md:585 is hand-derived. Fix: run the committed probe once on the fixed corpus and append the row, or mark both numbers as unrecorded.
