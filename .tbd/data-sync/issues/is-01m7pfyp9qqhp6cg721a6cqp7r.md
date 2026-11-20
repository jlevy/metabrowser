---
type: is
id: is-01m7pfyp9qqhp6cg721a6cqp7r
title: "Shell: a tab click made while a folder's first view still holds its first paint is lost (the Overview paints over it); honor or queue it"
kind: bug
status: open
priority: 3
version: 2
spec_path: docs/project/specs/active/plan-2026-11-11-ui-apparent-performance.md
labels: []
dependencies: []
parent_id: is-01m774q0ep0jq6vhb790rart0v
created_at: 2026-11-18T04:51:59.926Z
updated_at: 2026-11-20T17:24:20.583Z
---
Found by review A of #547 (A2): in headless Chrome under CPU throttling, clicking the Treemap tab while no tab was yet active was overridden when the Overview painted; the Treemap never mounted. #547's Chrome test now waits; the shell behavior itself is untracked otherwise.
