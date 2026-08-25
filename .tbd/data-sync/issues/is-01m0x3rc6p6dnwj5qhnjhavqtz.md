---
type: is
id: is-01m0x3rc6p6dnwj5qhnjhavqtz
title: Audit preview handoff and readiness parity
kind: task
status: closed
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-08-25-git-revision-navigation-performance.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0x3rwk2zj4vweea5c0a2sq1
  - type: blocks
    target: is-01m0x3rx12rgkb5pgdasd1zwn4
parent_id: is-01m0w52mbqvhdj9r2et2eh9p55
created_at: 2026-08-25T18:43:38.325Z
updated_at: 2026-08-25T18:48:58.958Z
closed_at: 2026-08-25T18:48:58.957Z
close_reason: Audited file and Git ownership, documented shared pending and painted-readiness vocabulary, and wired the five file/function-level follow-up beads without speculative detachment, caching, or compatibility.
resolution: null
duplicate_of: null
---
Files/functions: src/metabrowser/static/app.js claimPreview, selectFile, renderFile, mountPluginView, and shell preview bridge; src/metabrowser/static/git-panel.js selectCommit, renderCommitDetail, and mountCommitDiff; docs/project/specs/active/plan-2026-08-25-git-revision-navigation-performance.md. Record the exact ownership difference: Git stages a complete detached diff and swaps atomically, while ordinary plugins mount into the connected preview and may finish asynchronously. Define one shared pending/readiness vocabulary without claiming that arbitrary plugins are safe off-DOM. Name current instrumentation gaps and the acceptance boundary for file and Git navigation. Acceptance: the active plan and bead graph state exact files, functions, invariants, dependencies, and measured follow-up work; no speculative compatibility or detachment layer; tbd sync succeeds.
