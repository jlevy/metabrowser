---
type: is
id: is-01kyxz0fjsxaww2zkypg8wy78m
title: "Spike 7: validate and tune finder behavior end to end"
kind: task
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-07-17-scalable-file-search.md
labels: []
dependencies:
  - type: blocks
    target: is-01kyxz0qkyygz3saxrxtzx3kqx
parent_id: is-01kyxyb67v18br7jm7w8mrwss5
created_at: 2026-08-01T06:08:31.832Z
updated_at: 2026-08-01T07:57:09.655Z
closed_at: 2026-08-01T07:57:09.654Z
close_reason: Validated the slash-to-open flow with automated DOM/controller profiles and a 2,315-file real-browser fixture. Confirmed keyboard and pointer navigation, focus and accessibility semantics, lazy observed-file discovery, duplicate paths, cancellation, stale-file recovery, bounded DOM results, responsive chunking through 50,000 candidates, and zero search fetches; documented measurements and retained the ranking policy unchanged.
---
Run DOM, integration, and real-browser validation from slash key to opened file using shallow, Recent-sized, deeply expanded, duplicate-basename, and stale-file fixtures. Measure first-result latency, input delay, cancellation, catalog size, and mounted result count; test keyboard, pointer, focus, composition, screen-reader semantics, and absence of search network traffic. Review close-call ranking scenarios with diagnostics, tune only through documented comparison-policy and fixture changes, and record any evidence for chunking or a future Worker.
