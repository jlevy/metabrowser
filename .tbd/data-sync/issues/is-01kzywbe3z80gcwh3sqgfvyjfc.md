---
type: is
id: is-01kzywbe3z80gcwh3sqgfvyjfc
title: Bound logical extensions to two suffix components
kind: task
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/done/plan-2026-08-13-semantic-file-type-families.md
labels:
  - file-types
  - inventory
dependencies: []
created_at: 2026-08-14T00:57:01.307Z
updated_at: 2026-08-14T01:07:26.018Z
closed_at: 2026-08-14T01:07:26.014Z
close_reason: Bound indexed logical extensions to the final two eligible suffix components, documented the contract, added boundary regression coverage, and verified locally and in CI.
---
Cap derive_ext output at the final two eligible suffix components. Preserve single extensions and common two-part forms such as .js.map, .d.ts, .min.js, and .tar.gz; normalize longer tails such as .umd.min.js.map to .js.map and .d.ts.map to .ts.map. Update durable wire/design documentation and regression coverage, then refresh PR #38.
