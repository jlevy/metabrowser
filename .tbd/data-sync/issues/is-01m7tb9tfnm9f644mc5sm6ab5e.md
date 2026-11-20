---
type: is
id: is-01m7tb9tfnm9f644mc5sm6ab5e
title: "Host mode H3: discovery, with registry entries, liveness probes, and the listing mode"
kind: feature
status: open
priority: 2
version: 7
spec_path: docs/project/specs/active/plan-2026-11-18-host-mode.md
labels: []
dependencies:
  - type: blocks
    target: is-01m7tb9yx38183fpesfy0pme7a
  - type: blocks
    target: is-01m748xw1h1hx5p0eakfc0afgr
  - type: blocks
    target: is-01m748xvkxpj29cp9p8wr6vg5w
  - type: blocks
    target: is-01m748xwwxrrvvnb49fw9ez5ra
  - type: blocks
    target: is-01m748xsest94amc9cyx26j1zk
parent_id: is-01m7wysrh5ggf7dm4xvqm8dmmp
created_at: 2026-11-19T16:47:39.508Z
updated_at: 2026-11-20T17:21:26.642Z
---
Host mode plan step H3, discovery (docs/project/specs/active/plan-2026-11-18-host-mode.md, Implementation Plan and Discovery; Decisions HM-1 A and HM-3 A, taken 2026-11-19). Split from mb-5xi4, which keeps the find-or-start lock.

Delivers: every server, whoever started it, writes its server record (H2) as an owner-only state file through metabrowser.home's helpers once its socket accepts connections, never failing or delaying a serve, and removes it at an orderly exit; a reader drops an entry whose process is gone, then requires the entry's boot ID from its address's /api/identity, and skips and reports an entry of an unknown protocol; a listing mode (named --servers in the plan, an owned-model parity row) prints the live records, with --json, importing no server and signalling none. Goldens against a fixture runtime directory holding a live entry, a dead process, a reused process ID, a mismatched boot ID, an unknown protocol, and a damaged file. Lands behind the plan's measurement of what an entry adds to a server's start.

Slot: after H2; in Ordering 2, beside Tier 1 and before V5.
