---
type: is
id: is-01m0yjwbybpt8r9bf1pjehswr0
title: Restore strong diff-row contrast
kind: feature
status: closed
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-25-git-revision-navigation-performance.md
labels: []
dependencies: []
parent_id: is-01m0w52mbqvhdj9r2et2eh9p55
created_at: 2026-08-26T08:27:12.201Z
updated_at: 2026-08-26T08:28:27.330Z
closed_at: 2026-08-26T08:28:27.318Z
close_reason: "The clarified three-depth target is exactly the already implemented mb-l00d contract: medium 9% pure rows, light 3% refined unchanged portions, and a 9% overlay on the light row for an approximately 12% darkest intraline result. No palette code change is needed; validate it on the newly installed build instead of the older c76d9ab build."
resolution: duplicate
duplicate_of: is-01m0ycs63s5tm53hqjw2xraw1m
---
Files and interfaces: update diff palette custom properties in src/metabrowser/builtin_plugins/diff/styles.css; strengthen tests/test_syntax_palette.py; reconcile docs/design-system.md, the active Git revision plan, and CHANGELOG.md. Behavior and invariants: restore the original 12% semantic mix for wholly added/deleted rows; keep meaningful unchanged text in paired refined rows at the original 4% pale mix; use the original 8% intraline overlay so the composite changed text returns to approximately the same strong contrast as a pure row; preserve solid semantic gutter bars, syntax foreground contrast, unified/split parity, and light/dark token derivation. Acceptance: numeric palette contracts and contrast checks pass; headed light/dark unified/split validation confirms pure and intraline regions are prominent and paired unchanged regions remain pale; make format and make verify pass.
