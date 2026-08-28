---
type: is
id: is-01m12tc3v0vdxs4m1cq5m7pgm4
title: "PR #31 description misstates the planning vs implementation split"
kind: chore
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m12tc1tacfnggr44ecjnb17d
created_at: 2026-08-27T23:55:05.951Z
updated_at: 2026-08-28T00:11:18.527Z
closed_at: 2026-08-28T00:11:18.516Z
close_reason: "Fixed: PR description now opens with a blockquote naming what ships, followed by a proportion table (docs 89 percent, implementation 5 percent, tests 6 percent) and an explicit statement that the repository-library and Git-status plans are unimplemented."
resolution: null
duplicate_of: null
---
Measured: 16 files, +4737/-22. Docs are 11 files and +4456 (94 percent); source is 3 files and +122/-18; tests are 2 files and +159. The only shipped behavior change is the git history scroll-origin fix. Nothing in the repository-library or Git-status designs is implemented; both remain Draft plans. The description leads with design narrative and buries this, so a reviewer cannot tell what actually ships. Rewrite it to state the split up front.
