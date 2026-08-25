---
type: is
id: is-01m0vx58kkhk4cjjk8xfexxq0r
title: "PR #76 review 76-5: avoid repeated UTF-8 encoding per diff side"
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/done/plan-2026-08-24-diff-syntax-highlighting-and-layouts.md
labels:
  - review
  - diff
dependencies: []
parent_id: is-01m0txbdd0b5cyzcp64vsje7kp
created_at: 2026-08-25T07:29:06.162Z
updated_at: 2026-08-25T07:57:28.992Z
closed_at: 2026-08-25T07:57:28.991Z
close_reason: "Fixed 76-5: diff syntax construction stays cheap; scheduled enhancement lazily measures each old/new hunk stream once with a reused encoder, caches the counts, and carries them into diff profiler spans without widening the public SDK options. The public syntax helper retains its independent trust-boundary measurement. Focused byte-count/API-shape tests and make verify pass."
resolution: null
duplicate_of: null
---
PR #76 finding 76-5 (Low), src/metabrowser/builtin_plugins/diff/diff-syntax.js syntaxInputBytes, diff-view.js profiler metadata, and plugin-sdk.js bound checking. Reuse encoders and carry one measured byte count where possible; keep model construction cheap and preserve exact bound semantics with focused tests.
