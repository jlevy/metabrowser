---
type: is
id: is-01m82w3p07k6t5qv8qwxnx6n75
title: Consolidate the reviewed release fixes with current upstream
kind: task
status: closed
priority: 2
version: 4
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m7hgpc9550w78kmwqsvv64xh
hold: null
hold_until: null
created_at: 2026-11-23T00:15:19.554Z
updated_at: 2026-11-23T01:44:50.762Z
started_at: 2026-11-23T00:16:24.198Z
closed_at: 2026-11-23T01:44:50.762Z
close_reason: All requested focused PRs merged. The consolidated tree exactly equals upstream main 44c475dd5. The active Mac development app and restored localhost server were verified on that exact version.
resolution: null
duplicate_of: null
---
Fetch Metabrowser main, combine the reviewed focused PRs without changing their ownership, and verify exact ancestry and the effective diff together before refreshing the active development preview. Current upstream 0047ed0ab and the reviewed #708, #711, #712, #713 heads combined without conflicts at d115c956c.

## Notes

Current upstream 0261d8ae3 merged into codex/stabilization-consolidated at cbbb60362 with identical tested source tree. Independently verified ancestry and effective changes across the exact PR heads. No duplicate local fixture patch. Combined browser/server checks: 61 passed, then 132 on the corrected newer reading-layout stack. Active development app restarted with the matching 0be1fb868 source and its runtime verified.
