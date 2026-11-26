---
type: is
id: is-01m8batfbvgswamcwp6dnnpqh3
title: Markdown documents localize every repository link through the core resolver
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
created_at: 2026-11-26T07:06:21.946Z
updated_at: 2026-11-26T08:56:54.739Z
started_at: 2026-11-26T07:13:05.290Z
closed_at: 2026-11-26T08:56:54.739Z
close_reason: Implemented in https://github.com/jlevy/metabrowser/pull/874 (head 2bf458b8, CI green); merges with the epic mb-xdjt.
resolution: null
duplicate_of: null
---
link-enhancer.js calls MetabrowserRepositoryLinks.localize for external links (pull, commit, pulls, repo root, tree root in-app); rendered.js ensures the asset when mb.repository is set. Update markdown-link-enhancer-behavior.js.
