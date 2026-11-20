---
type: is
id: is-01kzz4ejm8kxev59qawa3a9yqd
title: "Future: Add source-view line location targets"
kind: feature
status: closed
priority: 4
version: 8
spec_path: docs/project/specs/active/plan-2026-08-13-markdown-navigation-extensions.md
labels: []
dependencies: []
parent_id: is-01kzz211w19g9y39ct7qf0hy1z
created_at: 2026-08-14T03:18:32.839Z
updated_at: 2026-11-20T19:15:58.788Z
closed_at: 2026-11-14T18:42:17.796Z
close_reason: "Done in #235 and #239 (on main through #260): Source views carry GitHub-style #L line anchors; docs/architecture.md records that a line-anchor fragment wins over a heading id, as on github.com."
resolution: null
duplicate_of: null
extensions: {}
---
Introduce an explicit source-view location type for GitHub-style #L14 and #L14-L20 fragments. Integrate with canonical navigation and source rendering without overloading or shadowing genuine rendered Markdown heading IDs.
