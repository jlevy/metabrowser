---
type: is
id: is-01m0dkj0gqvpzpxm7t1tpshf30
title: "Container materialization: one transient-cache discipline"
kind: feature
status: open
priority: 2
version: 2
labels: []
dependencies:
  - type: blocks
    target: is-01m0dkj0xzgg9b6kc7ge0fm2ne
created_at: 2026-08-19T18:11:56.054Z
updated_at: 2026-08-19T18:12:16.653Z
---
From arch-nav-containers.md and diff-sources-and-anchoring.md: PR fetches (reference clones, refs/pull/N/head — mb-2f7r), patch anchoring against a base (mb-s8pq), and archive unpacking all materialize into bounded transient cache directories that the ordinary serving path routes into. Build it once: keyed cache root, size/entry bounds, eviction, release-on-close, and safe-path routing into materialized trees. The git acquisition workflow in the diff plan becomes an instance of this instead of owning its own cache.
