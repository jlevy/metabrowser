---
type: is
id: is-01m8d3zanve7vz9fwprcdcjt8g
title: Measure exact-first origin acquisition and pack negotiation
kind: task
status: closed
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-11-26-post-load-performance.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/908
    at: 2026-11-26T23:58:31.091Z
labels: []
dependencies: []
parent_id: is-01m8cs8jdw8yh0hvdy6449jm9j
child_order_hints:
  - is-01m8d6341yzhweagpbaq2gjf8k
created_at: 2026-11-26T23:45:09.815Z
updated_at: 2026-11-27T11:22:32.752Z
closed_at: 2026-11-27T11:22:32.752Z
close_reason: "Merged in the exact reviewed performance stack #899 at main 4313286. Each owning layer passed its hosted workflow."
resolution: null
duplicate_of: null
---
H132 and H133. Compare exact-first versus broad-first origin fetching at identical diff and refs. Retain object storage and elapsed times. Any later publication experiment must preserve ownership and prove actual visible Changes improvement.

## Notes

Exp-113 retained exact ref and diff hashes in two pairs. Exact-first made the comparison readable earlier and held more bytes. Exp-114 remeasured the no-hints control after ref drift and confirmed roughly 13.8 MB saved with the fetched base and head used as hints.
