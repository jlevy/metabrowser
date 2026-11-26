---
type: is
id: is-01m8batevm97ram0xe6qr81j30
title: "Core repository link resolver: static/repository-links.js (localize, enhance)"
kind: task
status: closed
priority: 1
version: 7
spec_path: docs/project/specs/active/plan-2026-11-26-in-app-link-resolution.md
delegate: claude-code@vm
labels: []
dependencies:
  - type: blocks
    target: is-01m8batfbvgswamcwp6dnnpqh3
  - type: blocks
    target: is-01m8batfxy4fy1yjw8saszwj9z
  - type: blocks
    target: is-01m8batgfdp0vjve5p9bpyy35n
  - type: blocks
    target: is-01m8bath1w87tng37agprs65de
parent_id: is-01m8bat4973h1bjzvpkwd8qjdy
hold: null
hold_until: null
created_at: 2026-11-26T07:06:21.428Z
updated_at: 2026-11-26T08:56:54.730Z
started_at: 2026-11-26T07:06:37.602Z
closed_at: 2026-11-26T08:56:54.720Z
close_reason: Implemented in https://github.com/jlevy/metabrowser/pull/874 (head 2bf458b8, CI green); merges with the epic mb-xdjt.
resolution: null
duplicate_of: null
---
New on-demand core script MetabrowserRepositoryLinks via ensureAsset('repository-links'): localize(url, context, options) per the spec's Resolution Rules table and Texts of a Pull Request; enhance(root, mb, options) for inert texts. Register in server.py on-demand assets, type in static/types.d.ts, strict tsconfig. Move github-localizer.js cases into a behavior test and delete markdown/github-localizer.js.
