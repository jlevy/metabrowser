---
type: is
id: is-01m748xqaqfxbm3rczqhp869bn
title: "Folder identity: short name, full name, and kind from a route"
kind: feature
status: in_progress
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
delegate: claude-code@spud10.local
labels: []
dependencies:
  - type: blocks
    target: is-01m748xqrh37ksb7fvh0cqdapm
  - type: blocks
    target: is-01m748xr5tt08pm5p5ykheg1fe
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
hold: null
hold_until: null
created_at: 2026-11-11T03:02:48.406Z
updated_at: 2026-11-11T03:07:29.290Z
started_at: 2026-11-11T03:07:29.288Z
---
Phase 1. A RootIdentity model in metab for the served subject: short_name (the folder's own name; for a cached Git mirror the repository name), full_name (the path with ~ for home; for a mirror an abbreviated origin such as github.com/owner/repo@ref, never the cache path), kind (folder or mirror), and kind_label (Local folder or Cached mirror), plus title. Served by GET /api/identity, reachable through metab --api, with a golden transcript for a folder and a mirror, a parity row, and the map in arch-views-models-routes.md.
