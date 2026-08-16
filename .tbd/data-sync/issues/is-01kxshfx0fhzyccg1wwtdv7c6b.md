---
type: is
id: is-01kxshfx0fhzyccg1wwtdv7c6b
title: Extend vendor pipeline with esbuild single-entry ESM bundling (workers, ESM-only libs)
kind: feature
status: open
priority: 2
version: 2
labels:
  - build
dependencies: []
created_at: 2026-07-18T02:39:37.485Z
updated_at: 2026-08-16T08:05:43.259Z
extensions:
  linear:
    id: 66d2a207-9a94-44a8-afcb-f3a252eb2229
    linked_at: 2026-08-16T08:05:43.259Z
---
Per research-2026-07-18-diff-ui-stacks-and-browser-build-options.md Option C: add a bundling mode to devtools/vendor_assets.py using pinned esbuild (2 pkgs, no lifecycle scripts) producing unminified single-file ESM artifacts committed with sha256 manifest + license, plus a CI rebuild-and-byte-compare job. Needed for worker entry points (import maps do not work in workers) and ESM-only libraries (Shiki subsets, @pierre/diffs if adopted). Raise vendor size caps only per-artifact.
