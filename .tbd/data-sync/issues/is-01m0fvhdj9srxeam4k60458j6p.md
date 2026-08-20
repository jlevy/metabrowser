---
type: is
id: is-01m0fvhdj9srxeam4k60458j6p
title: Inline change stats are always bold
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
created_at: 2026-08-20T15:09:54.120Z
updated_at: 2026-08-20T15:28:42.337Z
closed_at: 2026-08-20T15:28:42.336Z
close_reason: "Landed in 4554983: +N/-N bold in diff and commit views, stated in Inline Change Stats and test-pinned"
---
The +N/-N pair (status green/red) reads as data and must be boldface everywhere it appears: the diff summary line, per-file bars (.diff-stat-add/.diff-stat-del), and the git commit view stats (.git-stat-add/.git-stat-del). Fold into the Inline Change Stats vocabulary in design-system.md and pin in test_design_vocabulary.py.
