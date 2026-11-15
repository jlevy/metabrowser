---
type: is
id: is-01m7b2jm7a3cgfhm87h52xcpmh
title: "H111 (exp-091): paint the diff before its first heavy enhancement task"
kind: task
status: open
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-11-ui-apparent-performance.md
labels: []
dependencies:
  - type: blocks
    target: is-01m7exbshjz1sx7r322nye458d
parent_id: is-01m774q0ep0jq6vhb790rart0v
created_at: 2026-11-13T18:26:34.345Z
updated_at: 2026-11-15T07:01:12.221Z
---
Found by the #368 diagnostic traces. After a diff mounts, yieldForEnhancement (diff-view.js) chains through setTimeout(0) into a 56-61 ms intraline task (myersDiff, diff-intraline.js). When the mount task ends before the next vsync, that task runs first and holds the diff's first paint 60-75 ms: commits.cold.1 is bimodal on both builds (about 114 ms vs 165-190 ms ready with a normal server). Proposed: yield to a frame first (requestAnimationFrame, then setTimeout) so the diff paints before enhancement; measure on commits.cold.1 and the diff-heavy transitions.
