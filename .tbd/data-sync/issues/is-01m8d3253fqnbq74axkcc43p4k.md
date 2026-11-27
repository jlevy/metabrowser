---
type: is
id: is-01m8d3253fqnbq74axkcc43p4k
title: Prioritize selected Conversation at the provider handoff
kind: task
status: closed
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-11-26-post-load-performance.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/907
    at: 2026-11-26T23:37:00.833Z
labels: []
dependencies: []
parent_id: is-01m8cs8jdw8yh0hvdy6449jm9j
child_order_hints:
  - is-01m8d4b4wmv9ckytczde13v0hb
created_at: 2026-11-26T23:29:13.834Z
updated_at: 2026-11-27T11:22:32.746Z
closed_at: 2026-11-27T11:22:32.746Z
close_reason: "Merged in the exact reviewed performance stack #899 at main 4313286. Each owning layer passed its hosted workflow."
resolution: null
duplicate_of: null
---
H128. Use the existing provider concurrency cap while giving selected Conversation metadata the next free slot during initial Git acquisition. Keep ordinary waits bounded, do not interrupt in-flight provider work, and log the actual selected slot wait.

## Notes

Independent Astra performance review A has no findings. The held-slot controls ran optional jobs first; the candidate showed the exact selected description first, then completed optional jobs in order and returned exact Changes. Eight focused and 162 provider regressions passed.
