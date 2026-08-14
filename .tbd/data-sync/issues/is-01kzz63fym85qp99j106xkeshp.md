---
type: is
id: is-01kzz63fym85qp99j106xkeshp
title: Add file hashes to the fdu adoption packet manifest
kind: bug
status: open
priority: 1
version: 1
spec_path: docs/project/specs/done/plan-2026-08-13-shared-file-type-taxonomy-and-breakdowns.md
labels:
  - file-types
  - review
dependencies: []
parent_id: is-01kzyxvf9qfc627wszts904wx3
created_at: 2026-08-14T03:47:26.803Z
updated_at: 2026-08-14T03:47:26.803Z
---
The fdu compatibility contract promises adopted-file hashes, but the export manifest currently lists only paths. Emit deterministic SHA-256 entries for every packet file and verify them in the contract test.
