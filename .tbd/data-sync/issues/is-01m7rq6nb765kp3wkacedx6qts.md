---
type: is
id: is-01m7rq6nb765kp3wkacedx6qts
title: "Add the mermaid kind: .mmd and .mermaid files get Diagram and Source views"
kind: task
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-21-mermaid-diagram-rendering.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0k3ntypp20smgz56xxw8ak5
parent_id: is-01m0k3nbmdvy9x8g3r8t9ckzjt
created_at: 2026-11-19T01:37:09.990Z
updated_at: 2026-11-19T02:37:07.800Z
closed_at: 2026-11-19T02:37:07.799Z
close_reason: Done on branch claude/mermaid-diagram-rendering-441fe6 (commit 4e0bc6391)
resolution: null
duplicate_of: null
---
GitHub renders .mmd/.mermaid blobs with a Preview tab. The Markdown plugin claims both extensions as kind mermaid with a default Diagram view (renderer over the file text; image mode when active content is off) and a Source view. Pin kind and views through /api/file in a golden; update the views/models/routes map and the parity registry.
