---
type: is
id: is-01m39kypz26xxnehmrbk8bmj74
title: Move the app's inline onclick handlers to addEventListener so the untrusted CSP can drop 'unsafe-hashes'
kind: task
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m36k3w9vgwy97c9hcj2sqrs5
created_at: 2026-09-24T11:49:00.002Z
updated_at: 2026-09-24T11:49:00.002Z
---
The untrusted-shell Content-Security-Policy (step 8, PR #234) allows the app's three inline onclick handlers by hash, which needs 'unsafe-hashes'. Replace them with addEventListener, remove the hashes, and keep the test that fails if the app writes an inline handler the policy does not list.
