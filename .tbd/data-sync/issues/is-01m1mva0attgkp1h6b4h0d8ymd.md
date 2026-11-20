---
type: is
id: is-01m1mva0attgkp1h6b4h0d8ymd
title: "PR #101 R3.5: metab --walk bypasses the coordinator in both modes"
kind: bug
status: open
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-08-23-pluggable-inventory-engine.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0r8xt95921dabcddjjm7csf
parent_id: is-01m0r7eg6f4a4xee33ryv8sjfs
created_at: 2026-09-03T23:57:45.177Z
updated_at: 2026-11-20T17:01:29.768Z
---
Text-mode metab --walk (walk_collect, src/metabrowser/walk.py:110) and metab --walk --stream (stream_entries, walk.py:556) drive walk_tree directly and bypass the coordinator, so with a second provider they would describe an engine that is not running. walk_collect also omits hidden_allowlist, agreeing with the provider only by coincidence of defaults. JSON and YAML walk already select the configured provider through inventory_provider_from_environment (walk.py:411). Settle the text and stream provider semantics before native adoption, and do not describe the whole CLI as provider-selectable until then.

## Notes

JSON/YAML walk now selects the configured provider through inventory_provider_from_environment; a regression rejects an unknown configured provider rather than silently using Python. Text and --stream still expose the explicit Python walker diagnostic. Keep this bead open to settle their provider semantics before native adoption; do not describe the whole CLI as provider-selectable yet.

2026-11-20 audit: absorbs mb-v1dj (found by the documentation rewrite, closed as a duplicate): src/metabrowser/walk.py calls walker.walk_tree directly, so swapping the engine would leave metab --walk on the Python walker. Either route the text and --stream modes through the provider, or keep them on the walker deliberately and say so in arch-inventory-provider.md.
