---
type: is
id: is-01m2zvffb1z2vsseb9d9nqcj6m
title: "v0.12 later phases: extend stack 218 through Phase 2A to 4C"
kind: task
status: in_progress
priority: 1
version: 6
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
delegate: codex@spud10
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: null
hold_until: null
created_at: 2026-09-20T16:48:04.959Z
updated_at: 2026-09-23T00:45:05.333Z
started_at: 2026-09-23T00:45:05.330Z
---
Coordinate publication and retargeting of the remaining v0.12 Phase 2A-4C PRs as extensions to existing Stack 218. Each phase follows the prerequisite implementation and independent review/publication beads, preserves exact parent/head evidence, and passes make verify and CI. Use docs/project/specs/active/plan-2026-09-22-v012-alpha-testing.md for incremental repository-URL and direct-PR acceptance. The direct-PR alpha does not remove bounded discovery/navigation or anchors from the full milestone. Work with mb-n2ro to hold and land the entire stabilized stack together after explicit approval, rather than creating an independent landing batch.

## Notes

2026-09-22 user direction: additional Phase 2A-4C implementation/testing PRs stay on existing Stack 218 and the whole stack remains held for stabilization. This bead coordinates later phase publication and retargeting with mb-n2ro, not a separate early landing batch. T2/direct PR view is an incremental alpha test milestone; bounded index/navigation and planned anchors remain in the full v0.12 milestone. See docs/project/specs/active/plan-2026-09-22-v012-alpha-testing.md.
