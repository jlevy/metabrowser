---
type: is
id: is-01kzctsqjdfn84ykr7cr4hzhxm
title: "git: Git nav panel with paging, badges, and hover cards"
kind: task
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-06-git-graph-view.md
labels: []
dependencies:
  - type: blocks
    target: is-01kzctsvynchf75k7sgg8jjw69
parent_id: is-01kzctqt5s7te6w75jm5pvg6g7
created_at: 2026-08-07T00:43:32.812Z
updated_at: 2026-08-07T01:29:03.037Z
closed_at: 2026-08-07T01:29:03.037Z
close_reason: null
---
Add static/git_panel.js: tab visibility gated on /api/git/repo, initial page fetch, scroll paging with lane continuity, reference badges, row selection, and a hover card driven by a debounced /api/git/commit/{revision} fetch behind a bounded client-side detail cache shared with the detail view.
