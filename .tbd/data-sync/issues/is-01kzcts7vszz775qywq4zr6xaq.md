---
type: is
id: is-01kzcts7vszz775qywq4zr6xaq
title: "nav: data-driven nav-panel tab registry"
kind: task
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-06-git-graph-view.md
labels: []
dependencies:
  - type: blocks
    target: is-01kzctsqjdfn84ykr7cr4hzhxm
parent_id: is-01kzctqt5s7te6w75jm5pvg6g7
created_at: 2026-08-07T00:43:16.728Z
updated_at: 2026-08-07T01:29:03.018Z
closed_at: 2026-08-07T01:29:03.018Z
close_reason: null
---
Replace the hardcoded Files/Recent tab markup in the index HTML and initNavTabs with a data-driven panel registry in app.js, preserving current behavior: lazy first-load per panel, aria-selected handling, and the nav scroll shadow. This is the seam a future registerNavPanel SDK surface would build on; no SDK contract is shipped here.
