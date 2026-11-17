---
type: is
id: is-01m7kp7mn0pb2xvh3cwa7akam7
title: Shared bounds, batched lookups, and paging under version movement (R5, D11, D13)
kind: feature
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels: []
dependencies:
  - type: blocks
    target: is-01m7kp7rgntx2bzfsp2836gyw9
parent_id: is-01m0r8xt95921dabcddjjm7csf
created_at: 2026-11-17T02:44:01.312Z
updated_at: 2026-11-17T02:44:05.269Z
---
Name every paired bound in the contract from measurements, add a batched lookup query, assemble catalog and tree responses from bounded pages under D13's re-read rule, and make broad queries resume instead of failing at the 1,000,000 work default. See docs/project/research/research-2026-11-17-fdu-backend-revisited.md.
