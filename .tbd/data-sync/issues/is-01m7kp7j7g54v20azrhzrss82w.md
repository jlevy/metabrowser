---
type: is
id: is-01m7kp7j7g54v20azrhzrss82w
title: "Upstream fdu: open-time group (F1, F3, F5, F6, F19, F24, F26)"
kind: task
status: open
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels: []
dependencies:
  - type: blocks
    target: is-01m7kp7rgntx2bzfsp2836gyw9
parent_id: is-01m0r8xt95921dabcddjjm7csf
created_at: 2026-11-17T02:43:58.832Z
updated_at: 2026-11-17T06:24:55.408Z
---
Track the fdu changes that let a thin adapter open and answer its native kinds without shims: classification-profile registry parsing (F1), degraded observation (F3), batched lookups (F5), two maintained per-directory facts (F6), the File Rollup conformance packet (F19), exported bounds (F24), and resumable positions across versions (F26). Proposed in jlevy/fdu#215; F2 moved to the adoption gates. See docs/project/research/research-2026-11-17-fdu-backend-revisited.md.
