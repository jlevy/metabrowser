---
type: is
id: is-01m24v531rws8fqeztbdh3xx02
title: Consolidate performance experiment IDs after release-line merge
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m24nhxxpkrb7cvgyvtxb5d0r
created_at: 2026-09-10T05:02:55.026Z
updated_at: 2026-09-10T17:49:02.450Z
closed_at: 2026-09-10T17:49:02.449Z
close_reason: "Completed on codex/release-hardening: published experiment identities were preserved, unreleased collisions were renumbered, duplicate IDs now fail the report reader, the ledger was regenerated, and exp-031 records the final comparison."
resolution: null
duplicate_of: null
---
Merging the v0.9.1 release ancestry exposed duplicate exp-022 and exp-023 artifacts allocated independently on the release and main lines. Preserve the published release experiment identities, renumber the unreleased mainline experiments and references, add a duplicate-ID failure to the report reader, regenerate the ledger, and reserve the next unique ID for the exact v0.9.1-to-candidate comparison.
