---
type: is
id: is-01kzz63fym85qp99j106xkeshp
title: Add file hashes to the fdu adoption packet manifest
kind: bug
status: closed
priority: 1
version: 2
spec_path: docs/project/specs/done/plan-2026-08-13-shared-file-type-taxonomy-and-breakdowns.md
labels:
  - file-types
  - review
dependencies: []
parent_id: is-01kzyxvf9qfc627wszts904wx3
created_at: 2026-08-14T03:47:26.803Z
updated_at: 2026-08-14T03:53:09.446Z
closed_at: 2026-08-14T03:53:09.445Z
close_reason: The adoption exporter now emits deterministic packet-relative SHA-256 entries, the durable fdu contract documents the manifest shape, and focused plus full repository validation pass.
---
The fdu compatibility contract promises adopted-file hashes, but the export manifest currently lists only paths. Emit deterministic SHA-256 entries for every packet file and verify them in the contract test.
