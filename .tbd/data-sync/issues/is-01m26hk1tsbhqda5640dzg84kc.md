---
type: is
id: is-01m26hk1tsbhqda5640dzg84kc
title: Golden-pin navigation controls and live inventory composition
kind: task
status: open
priority: 1
version: 1
labels: []
dependencies: []
parent_id: is-01m26hjjvhpcf49p2x1c3390kk
created_at: 2026-09-10T20:54:15.640Z
updated_at: 2026-09-10T20:54:15.640Z
---
Extract the smallest production controller seam for filter control/clear -> request identity -> authoritative response -> mounted tree and EventSource snapshot/change/remove/resync -> FileStore/subtree/deferred rows -> focus, selection, and tallies. Run that exact seam in deterministic CLI goldens, including abort/stale-response and collapsed/deferred-tree cases. Retire source-regex assertions where the production session supersedes them.
