---
type: is
id: is-01m6wtacta0gcph1j42jw3vq26
title: Bind release publication instructions to the approved commit
kind: task
status: in_progress
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m6wdjwawp9g1bvnefz2hxze3
hold: null
hold_until: null
created_at: 2026-11-08T05:32:53.951Z
updated_at: 2026-11-08T05:33:30.712Z
started_at: 2026-11-08T05:33:30.711Z
---
Release-packet review R1: docs/publishing.md currently targets mutable main, even though owner approval and CI are for an exact commit. Document resolving and recording the approved full SHA, refusing an existing version tag that resolves elsewhere before publication, and selecting that SHA when creating a new tag. Verify the tag resolves to the approved commit when recording the result. Correct documentation only; do not create any release tag or publish without explicit owner approval. Include in the final release-documentation PR and independent review.
