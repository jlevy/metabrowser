---
type: is
id: is-01m718rgbk80mnnjb8d4b1r4xz
title: Render Markdown redlines within PR Changes
kind: feature
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
labels: []
dependencies: []
parent_id: is-01kxse0w3xhsyhbksdbn2kt33e
created_at: 2026-11-09T23:02:14.117Z
updated_at: 2026-11-09T23:02:14.117Z
---
Default eligible Markdown file sections to Rendered, with a per-file Rendered | Source toggle beside the filename. Use resolved base/head Git blobs in both checkout and cached modes. Map source hunks to safe rendered blocks, use existing red/green gutter and text tokens, and fall back to exact Source for unsupported or over-budget projections. Keep full revision links (mb-01s3) separate. Verify accessibility, safe relative URLs, structural changes, limits and races.
