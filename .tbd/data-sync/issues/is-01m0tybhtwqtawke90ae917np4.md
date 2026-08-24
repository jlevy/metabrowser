---
type: is
id: is-01m0tybhtwqtawke90ae917np4
title: Align unreleased notes with exact-main evidence and aggregate intermediate fixes
kind: chore
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m0txqcnz6aef2rzesn4cmy5w
created_at: 2026-08-24T22:30:46.363Z
updated_at: 2026-08-24T22:30:46.363Z
---
Release-readiness finding on main c123ae6. CHANGELOG Unreleased calls exp-014 values from candidate bf7771b the final installed wheel, but the exact merged-main validation is exp-015 at bae51fd and reports different backend, paint, request, and transfer values. The ensureKindAssets entry also records an Overview failure introduced and corrected inside this unreleased performance cycle. Update claims to the exact-main experiment and fold that intermediate failure into the on-demand-loading outcome.
