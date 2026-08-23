---
type: is
id: is-01m0prmjb4h8vh85kg5mh51vpn
title: "PR #72 review R2: frame_missing_px and regions_non_empty appear in zero recorded runs"
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m0prm49eb29wxywrqtdck27b
created_at: 2026-08-23T07:33:52.611Z
updated_at: 2026-08-23T08:07:16.994Z
closed_at: 2026-08-23T08:07:16.994Z
close_reason: "Fixed in 02c3105 and 10c8c38. Three runs recorded on the fixed corpus at 1280x900 with the committed probe: frame_missing_px 532, identical across all three. README and the H52 plan row now cite the record instead of a hand-derived figure. regions_non_empty was retired rather than recorded (see mb-74m1)."
---
results/runs.jsonl has 0 occurrences of either across 56 rows; all 10 new rows still carry the retired skeleton_complete and the old flat region_heights keyed on #tree-content. The committed probe.js has never produced a recorded row, so the 615px H52 baseline in README.md:216,263 and plan-2026-08-21-load-time-performance.md:585 is hand-derived. Fix: run the committed probe once on the fixed corpus and append the row, or mark both numbers as unrecorded.
