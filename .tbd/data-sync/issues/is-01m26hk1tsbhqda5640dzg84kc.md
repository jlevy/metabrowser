---
type: is
id: is-01m26hk1tsbhqda5640dzg84kc
title: Golden-pin navigation controls and live inventory composition
kind: task
status: open
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-09-10-functional-ui-cli-parity.md
labels: []
dependencies: []
parent_id: is-01m26hjjvhpcf49p2x1c3390kk
created_at: 2026-09-10T20:54:15.640Z
updated_at: 2026-09-14T23:28:11.409Z
---
Extract the smallest production controller seam for filter control/clear -> request identity -> authoritative response -> mounted tree and EventSource snapshot/change/remove/resync -> FileStore/subtree/deferred rows -> focus, selection, and tallies. Run that exact seam in deterministic CLI goldens, including abort/stale-response and collapsed/deferred-tree cases. Retire source-regex assertions where the production session supersedes them.
