---
type: is
id: is-01m0nw8gwp6jrdae5jwz9y8j80
title: "Accept rule: use a band stable in n, not min-max (S6)"
kind: task
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels: []
dependencies: []
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-08-22T23:17:57.781Z
updated_at: 2026-11-14T18:47:23.291Z
---
Review suggestion S6, and the sharpest one about the loop itself. The accept rule is non-overlapping ranges at n>=3 where the range is min-max (run.py). Min-max widens monotonically with n, so collecting MORE data makes a real effect harder to confirm -- the README's own exp-003 example shows it (342-413 at n=3 widening to 342-561 at n=6, same effect). Use a fixed-percentile band (IQR or p10-p90) or a rank test (Mann-Whitney U is ~15 lines, no dependency), which are stable in n. Keep printing min-max beside it: it is the honest picture of the tail.

## Notes

2026-11-14 audit: still open for run.py. The transitions harness added with #373 judges times on back-to-back pair ratios against --tolerance alongside ranges (explorations/performance-loop/README.md, the transitions compare section), which is not min-max alone; run.py compare still uses min-max.
