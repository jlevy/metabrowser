---
type: is
id: is-01m7tb9kyhdtqaapjn9bcxfxd9
title: "Host mode H1: a ready moment after bind, a boot ID, and process fields on /api/identity"
kind: feature
status: open
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-11-18-host-mode.md
labels: []
dependencies:
  - type: blocks
    target: is-01m7tb9q5c69txa1c750dqe79j
  - type: blocks
    target: is-01m748xwf9kpmst8t6jk2n95hj
parent_id: is-01m7wysrh5ggf7dm4xvqm8dmmp
created_at: 2026-11-19T16:47:32.816Z
updated_at: 2026-11-20T17:21:15.372Z
---
Host mode plan step H1 (docs/project/specs/active/plan-2026-11-18-host-mode.md, Implementation Plan; Decision HM-1 A, taken 2026-11-19). Split from mb-qzny (the ready line's moment after bind) and mb-1zyp (its first clause, the identity fields).

Delivers: a ready moment, once the server's socket accepts connections, at which later steps print the ready line (H2) and write the registry entry (H3), where today the Serving line is printed before the socket listens (cli/serve.py); a boot ID, a random value new at each start; and pid, boot_id, and version on GET /api/identity, golden-pinned through --api. Additive, with no page change.

Slot: beside Tier 0 of the implementation map's Ordering 2, outside its cap. Blocks nothing on the token: discovery waits for nothing.
