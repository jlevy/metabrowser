---
type: is
id: is-01m6wtacta0gcph1j42jw3vq26
title: Bind release publication instructions to the approved commit
kind: task
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m6wdjwawp9g1bvnefz2hxze3
hold: null
hold_until: null
created_at: 2026-11-08T05:32:53.951Z
updated_at: 2026-11-08T06:38:44.645Z
started_at: 2026-11-08T05:33:30.711Z
closed_at: 2026-11-08T06:38:44.645Z
close_reason: Documentation PR332 merged at240da85cbb45b72defed0084aadc99ee0be234ed after pinned independent senior review, exacthead fullmakeverify4917 tests/9expectedskips/385goldenchecks, audits/distribution/installedsmokes and all9PRCIjobs. Landed fulltree equals gatede204ce9b5 and retains it asancestor. Current userguides/design/plans/QA/behaviorrecord reconciled; publishinginstructions targetapprovedfullSHA with existingtagpreflight. Separate release acceptance/publication remainsopen.
resolution: null
duplicate_of: null
---
Release-packet review R1: docs/publishing.md currently targets mutable main, even though owner approval and CI are for an exact commit. Document resolving and recording the approved full SHA, refusing an existing version tag that resolves elsewhere before publication, and selecting that SHA when creating a new tag. Verify the tag resolves to the approved commit when recording the result. Correct documentation only; do not create any release tag or publish without explicit owner approval. Include in the final release-documentation PR and independent review.
