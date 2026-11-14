---
type: is
id: is-01kzz4ejm8kxev59qawa3a9yqd
title: "Future: Add source-view line location targets"
kind: feature
status: closed
priority: 4
version: 7
spec_path: docs/project/specs/active/plan-2026-08-13-markdown-navigation-extensions.md
labels: []
dependencies: []
parent_id: is-01kzz211w19g9y39ct7qf0hy1z
created_at: 2026-08-14T03:18:32.839Z
updated_at: 2026-11-14T18:42:17.797Z
closed_at: 2026-11-14T18:42:17.796Z
close_reason: "Done in #235 and #239 (on main through #260): Source views carry GitHub-style #L line anchors; docs/architecture.md records that a line-anchor fragment wins over a heading id, as on github.com."
resolution: null
duplicate_of: null
extensions:
  linear:
    id: c7c44fca-2bb1-427c-9c3f-81c69be6b0f5
    linked_at: 2026-08-16T08:05:43.478Z
---
Introduce an explicit source-view location type for GitHub-style #L14 and #L14-L20 fragments. Integrate with canonical navigation and source rendering without overloading or shadowing genuine rendered Markdown heading IDs.
