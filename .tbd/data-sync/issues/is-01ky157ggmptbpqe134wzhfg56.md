---
type: is
id: is-01ky157ggmptbpqe134wzhfg56
title: "PR13/R4: folder zoom must be real browser history"
kind: bug
status: closed
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-07-20-folder-views-and-treemap-overview.md
labels: []
dependencies: []
parent_id: is-01kxz2z9v1bbfcfmqstffkhvxp
created_at: 2026-07-21T01:39:15.092Z
updated_at: 2026-07-21T02:01:47.977Z
closed_at: 2026-07-21T02:01:47.977Z
close_reason: "Fixed in the R1-R8 review-response commit on PR #13; verified by new unit/vm assertions plus a live browser pass (hostile filenames, Back/Forward zoom trail, live header); make verify green"
---
Review finding R4 = mb-lyb0 confirmed required: centralize route writes with push|replace|none modes; folder-to-folder pushes, file selection replaces, popstate renders without writing; Back retraces zooms. Query-string migration declined for now (hash kept, in-doc anchors already disambiguated).
