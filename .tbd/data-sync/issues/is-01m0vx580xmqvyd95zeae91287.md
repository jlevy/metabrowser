---
type: is
id: is-01m0vx580xmqvyd95zeae91287
title: "PR #76 review 76-3: evaluate grammar readiness request semantics"
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/done/plan-2026-08-24-diff-syntax-highlighting-and-layouts.md
labels:
  - review
  - syntax-highlighting
dependencies: []
parent_id: is-01m0txbdd0b5cyzcp64vsje7kp
created_at: 2026-08-25T07:29:05.564Z
updated_at: 2026-08-25T07:48:08.635Z
closed_at: 2026-08-25T07:48:08.633Z
close_reason: "Rebutted 76-3: the shipped syntax surface is one prefetched Highlight.js registry (core plus TOML), not one on-demand asset per grammar. waitForSyntaxAssets already rechecks the requested grammar on each asset event and at terminal settlement; there is no grammar asset ID or on-demand bundle for ensureAsset to request. Every configured mapping is tested against the shipped registry, so adding an individual-loader contract would invent unavailable assets and exceed the reviewed no-new-grammar/dependency scope."
resolution: null
duplicate_of: null
---
PR #76 finding 76-3 (Low), src/metabrowser/static/plugin-sdk.js waitForSyntaxAssets/highlightSyntax. Verify whether the SDK can or should request an individual grammar on demand given the single prefetched Highlight.js registry and the no-new-grammar/dependency scope; fix the readiness contract or publish a precise technical rebuttal.
