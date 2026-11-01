---
type: is
id: is-01m6c49chhtssy29mg2sg25pnj
title: A folder past the inventory cap has a pending header tally and says No files to summarize
kind: bug
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01m402dbhn3zsc1h896f3xnrsq
created_at: 2026-11-01T18:00:01.328Z
updated_at: 2026-11-01T18:00:01.328Z
---
Found 2026-11-01 while fixing mb-1qwp in PR #275. With a capped index, a folder the walk stopped before finishing keeps a pending header tally, and File Overview says No files to summarize although it has files. The Treemap now says unavailable.
