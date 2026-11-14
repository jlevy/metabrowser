---
type: is
id: is-01m7bs2d5xakev86yy6z2nkwg9
title: "Pulls file tree: a late absent answer leaves old rows with no notice"
kind: bug
status: open
priority: 3
version: 1
labels: []
dependencies: []
created_at: 2026-11-14T00:59:40.092Z
updated_at: 2026-11-14T00:59:40.092Z
---
Found while fixing mb-aw30 (#416): a drawn Pulls file tree whose late read answers that the list is absent (listed_from null) keeps its old rows with no line, loading line, notice or offer (probe: attic/absent-late.mjs in the pulls-empty-refresh worktree). Nothing contradicts the rows, but nothing tells the reader the list went away. Done when the tree says so (a notice, or an offer, per #406 rules), pinned in the opening session.
