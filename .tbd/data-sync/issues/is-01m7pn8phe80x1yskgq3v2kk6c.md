---
type: is
id: is-01m7pn8phe80x1yskgq3v2kk6c
title: "Read-only rule gaps: lazy fetch in blobless clones and textconv notes cache in a checkout's .git"
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-11-18T06:24:50.733Z
updated_at: 2026-11-18T06:24:50.733Z
---
Reproduced on main 227853ce7 via routes (see arch-git.md Known Gaps, #558): (1) metab <blobless clone> --api /api/git/commit/<rev> lazily fetches (pack count 2->3); fix with GIT_NO_LAZY_FETCH=1. (2) /api/plugin/diff/comparison?revision=<rev> on a checkout whose .git/info/attributes selects a cachetextconv driver writes refs/notes/textconv/up; fix with --no-textconv --no-ext-diff (or equivalent attribute isolation) on served reads. Add a test for each that asserts .git is unchanged.
