---
type: is
id: is-01m36ma4wj1mvqw8rhgw3mqh6s
title: "Refresh and pin switching: coordinator, status/refresh/pin routes, browser offer"
kind: task
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
labels:
  - release:v0.12.0
dependencies:
  - type: blocks
    target: is-01m36k3xm77y33seww2jbwwb69
parent_id: is-01m36k3w9vgwy97c9hcj2sqrs5
created_at: 2026-09-23T07:57:31.409Z
updated_at: 2026-09-23T07:57:32.803Z
---
Delivery step 4 of the thin-mirror plan. Background refresh coordinator (single flight per store, global cap of 2), GET /api/source/status with ETag, POST /api/source/refresh, POST /api/source/pin (same-repository re-attach with generation bump), browser polling while visible, stale label and newer-revision offer, typed stale history cursors, fetch side lock tried without blocking, stale ref-lock cleanup, update via ls-remote --symref plus fetch --prune --atomic. file:// only; no network. Functional-aspect row and browserless session plus goldens. Independent review, make verify, green CI.
