---
type: is
id: is-01m10vgwqwn8gjdv8fm183vztr
title: "Repository library Phase 6: GitHub repository, issue, and PR views"
kind: feature
status: open
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0b71xgqp0jgz007h0wtzr3z
  - type: blocks
    target: is-01m10xd6s2fy7qthahs3cz25gk
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
created_at: 2026-08-27T05:36:42.234Z
updated_at: 2026-08-27T06:09:38.593Z
---
Render cached GitHub repository and issue records plus pull requests through plugin-owned views. Reuse the Git adapter, File Diff Format, and diff plugin for comparisons; layer provider title, author, state, checks, reviews, threads, collection completeness, and freshness around Git data; render changed Markdown at the PR head; and show outdated or unresolved review anchors honestly. Provider writes remain out of scope.
