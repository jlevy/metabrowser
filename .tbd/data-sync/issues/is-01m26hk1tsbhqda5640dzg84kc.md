---
type: is
id: is-01m26hk1tsbhqda5640dzg84kc
title: Golden-pin navigation controls and live inventory composition
kind: task
status: open
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-09-10-functional-ui-cli-parity.md
labels: []
dependencies: []
parent_id: is-01m26hjjvhpcf49p2x1c3390kk
created_at: 2026-09-10T20:54:15.640Z
updated_at: 2026-11-14T18:42:41.775Z
---
Extract the smallest production controller seam for filter control/clear -> request identity -> authoritative response -> mounted tree and EventSource snapshot/change/remove/resync -> FileStore/subtree/deferred rows -> focus, selection, and tallies. Run that exact seam in deterministic CLI goldens, including abort/stale-response and collapsed/deferred-tree cases. Retire source-regex assertions where the production session supersedes them.

## Notes

2026-11-14 audit: partly covered by existing rows (navigation.recent-tree, navigation.recent-continuity, navigation.catalog-continuity, navigation.inventory-snapshot-replacement, navigation.failed-expanded-folder-recovery); start from the functional table.
