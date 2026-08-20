---
type: is
id: is-01m0ghvrnps0hh3m8d28xvfn2j
title: "Git history: paged extension beyond the first batch"
kind: feature
status: open
priority: 1
version: 1
labels: []
dependencies: []
created_at: 2026-08-20T21:40:01.845Z
updated_at: 2026-08-20T21:40:01.845Z
---
History stops at the first page with no way further back. Load 1000 commits per batch (up from 500) and add an extension control at the end of the list to load the next batch, modeled on the diff view's fold expander (full-width row, registry chevron, states the count). Keep it fast: the walk is skip-based, so measure the second and third batches on this repo's history and record the numbers beside the constant. Applies to whichever ref scope is active.
