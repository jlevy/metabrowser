---
type: is
id: is-01m7nnxnedw2fvq6ef6p0ka73z
title: "GitHub status check: gh path, version, account, scopes; --doctor section, route, and preflight"
kind: feature
status: in_progress
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-11-17-open-anything-from-cli-and-app.md
delegate: claude-code@spud10
labels: []
dependencies:
  - type: blocks
    target: is-01m7nnxsky2r2jf9d5n3ac3vty
  - type: blocks
    target: is-01m7r8wednnec21h8ac7xbmed6
parent_id: is-01m7nnxhaqce1g2ewec3wbaf7e
hold: null
hold_until: null
created_at: 2026-11-17T21:17:03.309Z
updated_at: 2026-11-18T21:26:55.155Z
started_at: 2026-11-18T21:02:21.507Z
---
Phase 1. gh auth status --active --hostname github.com --json hosts; report GhFailureState; registered route plus --doctor --json; check before a first clone or pull request read and stop with the fixing command instead of a silent fallback; read token scopes where gh reports them.
