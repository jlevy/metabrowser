---
type: is
id: is-01ky1581tnx4258ffsdvkyjnrp
title: "PR13/R8: treemap preferences lost across ports; add versioned prefs SDK"
kind: bug
status: closed
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-07-20-folder-views-and-treemap-overview.md
labels: []
dependencies: []
parent_id: is-01kxz2z9v1bbfcfmqstffkhvxp
created_at: 2026-07-21T01:39:32.821Z
updated_at: 2026-07-21T02:01:47.991Z
closed_at: 2026-07-21T02:01:47.991Z
close_reason: "Fixed in the R1-R8 review-response commit on PR #13; verified by new unit/vm assertions plus a live browser pass (hostile filenames, Back/Forward zoom trail, live header); make verify green"
---
Review finding R8: localStorage is per-origin and Metabrowser instances use different ports. Fix: small versioned mb.prefs SDK over host-only cookies (the theme mechanism), enum validation on read, one-time localStorage migration for metabrowser.folder.treemap. Richer per-root workspace state stays future work under the unified-filtering/preferences track.
