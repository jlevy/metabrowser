---
type: is
id: is-01m82w3p07k6t5qv8qwxnx6n75
title: Consolidate the reviewed release fixes with current upstream
kind: task
status: in_progress
priority: 2
version: 2
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m7hgpc9550w78kmwqsvv64xh
hold: null
hold_until: null
created_at: 2026-11-23T00:15:19.554Z
updated_at: 2026-11-23T00:16:24.207Z
started_at: 2026-11-23T00:16:24.198Z
---
Fetch Metabrowser main, combine the reviewed focused PRs without changing their ownership, and verify exact ancestry and the effective diff together before refreshing the active development preview. Current upstream 0047ed0ab and the reviewed #708, #711, #712, #713 heads combined without conflicts at d115c956c.
