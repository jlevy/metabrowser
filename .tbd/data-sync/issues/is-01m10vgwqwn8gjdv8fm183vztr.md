---
type: is
id: is-01m10vgwqwn8gjdv8fm183vztr
title: "Repository library Phase 5: fast cached pull-request reading"
kind: feature
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0b71xgqp0jgz007h0wtzr3z
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
created_at: 2026-08-27T05:36:42.234Z
updated_at: 2026-08-27T05:37:06.463Z
---
Render cached GitHub pull requests through the existing Git adapter, File Diff Format, and diff plugin, with title, author, state, checks, freshness, and changed Markdown at the PR head revision. Add review conversations only after their anchor model is specified; keep provider writes out of scope.
