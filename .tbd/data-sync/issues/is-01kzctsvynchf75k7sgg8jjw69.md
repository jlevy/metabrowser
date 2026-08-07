---
type: is
id: is-01kzctsvynchf75k7sgg8jjw69
title: "git: commit-detail preview renderer"
kind: task
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-06-git-graph-view.md
labels: []
dependencies:
  - type: blocks
    target: is-01kzctt14e1nb4k36bc6jy2qe1
parent_id: is-01kzctqt5s7te6w75jm5pvg6g7
created_at: 2026-08-07T00:43:37.300Z
updated_at: 2026-08-07T01:29:03.043Z
closed_at: 2026-08-07T01:29:03.043Z
close_reason: null
---
Render the selected commit in the preview pane: metadata, references, full message, stats, and the changed-file list with per-file status and additions/deletions. Changed files navigate through openPath; outside_root entries render inert. Give the view a disposal path consistent with the existing preview lifecycle.
