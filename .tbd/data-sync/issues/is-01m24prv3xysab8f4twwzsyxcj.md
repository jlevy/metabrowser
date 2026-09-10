---
type: is
id: is-01m24prv3xysab8f4twwzsyxcj
title: Audit CLI and golden coverage for essential MetaBrowser behavior
kind: task
status: closed
priority: 1
version: 3
labels: []
dependencies:
  - type: blocks
    target: is-01m24nhxxpkrb7cvgyvtxb5d0r
parent_id: is-01m24nhxxpkrb7cvgyvtxb5d0r
created_at: 2026-09-10T03:46:19.381Z
updated_at: 2026-09-10T04:56:39.365Z
closed_at: 2026-09-10T04:56:39.364Z
close_reason: "Audited all built-in surfaces: 26 browser-consumed routes have CLI golden evidence, 5 streaming/debug routes are reasoned exemptions, and all 8 registered kinds appear in executable --show golden output. The automated gate now checks routes and kinds; docs reserve DOM tests for view behavior. Full 99-case CLI golden suite passes."
resolution: null
duplicate_of: null
---
Use the route/kind/model/state parity contract to verify every essential non-view capability is reachable through metab and pinned by broad, deterministic golden transcripts. Keep browser-only coverage limited to true view/DOM behavior, strengthen the automated parity check for any uncovered surface, and keep the suite efficient.
