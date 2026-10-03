---
type: is
id: is-01m402f1j3r01mrjj2adyczdpm
title: "Review and finish PR #262, then decide its independent landing"
kind: task
status: open
priority: 1
version: 1
labels: []
dependencies: []
parent_id: is-01m402dbhn3zsc1h896f3xnrsq
created_at: 2026-10-03T05:05:52.706Z
updated_at: 2026-10-03T05:05:52.706Z
---
PR #262 is held outside the stack. Stack #260 is now merged; timing hold is satisfied. Still NOT ready as-is: P1 filtered Back landing unfilters tree; P2 redundant large snapshot/catalog parsing; lifecycle session gaps. Address the recorded P1/P2/P3 findings, run browser and focused regression coverage plus make verify and CI, then recommend landing separately. Do not merge until all blockers are resolved and merge authorization exists.
