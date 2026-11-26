---
type: is
id: is-01m8csf4ap1k7wkfyw84z1yw51
title: "PR #892 A1: Retry a failed HEAD observation on the next manual refresh"
kind: bug
status: closed
priority: 2
version: 3
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m8cq63ngbx81fcv93fspfp5j
hold: null
hold_until: null
created_at: 2026-11-26T20:41:33.261Z
updated_at: 2026-11-26T21:05:17.537Z
started_at: 2026-11-26T20:41:37.316Z
closed_at: 2026-11-26T21:05:17.486Z
close_reason: "Implemented and independently reviewed in merged Metabrowser PR #892. Exact-head CI passed."
resolution: null
duplicate_of: null
---
A rejected HEAD fetch left the closed Files selector with a stale in-flight controller, so later manual refreshes left the branch label stale. The mounted regression covers a rejection and an independent recovery press.
