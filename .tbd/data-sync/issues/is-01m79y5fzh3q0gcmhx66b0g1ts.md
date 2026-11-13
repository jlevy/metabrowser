---
type: is
id: is-01m79y5fzh3q0gcmhx66b0g1ts
title: "Branch chips: one font size and one color system everywhere"
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-11-13T07:50:15.280Z
updated_at: 2026-11-13T07:50:15.280Z
---
The user, 2026-11-12: the branch names inside the little ref chips are not the same font size in the PR view and in the Git commit view, and the system for their colors doesn't seem consistent. Make the font size consistent for branch names everywhere, and make the color system consistent (which kind each chip gets, and what each kind looks like), documented in docs/design-system.md. Builds on #385 (colors) and #390 (merge arrows); stacked on #390's branch.
