---
type: is
id: is-01kxqg4gz2m7c1fz7ejrt8c4ec
title: Add standard --version support to metab and metabrowser CLIs
kind: bug
status: closed
priority: 1
version: 4
labels: []
dependencies: []
created_at: 2026-07-17T07:37:27.265Z
updated_at: 2026-07-17T07:52:57.137Z
closed_at: 2026-07-17T07:52:57.137Z
close_reason: Implemented, fully verified, pushed, and green in CI.
---

## Notes

Completed in 651d3e3. Added installed-metadata --version output for both CLI names and isolated-wheel verification. make verify passes with 674 tests; CI is green on Python 3.12-3.14, lint, and distribution.
