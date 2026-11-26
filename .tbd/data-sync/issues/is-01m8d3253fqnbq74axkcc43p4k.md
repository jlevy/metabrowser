---
type: is
id: is-01m8d3253fqnbq74axkcc43p4k
title: Prioritize selected Conversation at the provider handoff
kind: task
status: in_progress
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-11-26-post-load-performance.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/907
    at: 2026-11-26T23:37:00.833Z
labels: []
dependencies: []
parent_id: is-01m8cs8jdw8yh0hvdy6449jm9j
created_at: 2026-11-26T23:29:13.834Z
updated_at: 2026-11-26T23:37:01.692Z
---
H128. Use the existing provider concurrency cap while giving selected Conversation metadata the next free slot during initial Git acquisition. Keep ordinary waits bounded, do not interrupt in-flight provider work, and log the actual selected slot wait.

## Notes

Independent Astra performance review A has no findings. The held-slot controls ran optional jobs first; the candidate showed the exact selected description first, then completed optional jobs in order and returned exact Changes. Eight focused and 162 provider regressions passed.
