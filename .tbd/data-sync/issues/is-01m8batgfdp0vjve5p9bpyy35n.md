---
type: is
id: is-01m8batgfdp0vjve5p9bpyy35n
title: Commit message bodies localize repository links
kind: task
status: closed
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-11-26-in-app-link-resolution.md
delegate: claude-code@vm
labels: []
dependencies:
  - type: blocks
    target: is-01m8bathnhy6pkgn4hmjd87hb1
parent_id: is-01m8bat4973h1bjzvpkwd8qjdy
hold: null
hold_until: null
created_at: 2026-11-26T07:06:23.085Z
updated_at: 2026-11-26T08:56:54.752Z
started_at: 2026-11-26T07:18:33.736Z
closed_at: 2026-11-26T08:56:54.752Z
close_reason: Implemented in https://github.com/jlevy/metabrowser/pull/874 (head 2bf458b8, CI green); merges with the epic mb-xdjt.
resolution: null
duplicate_of: null
---
git-panel.js commitKpressHost calls MetabrowserRepositoryLinks.enhance (no text context: relative references stay text as on github.com).
