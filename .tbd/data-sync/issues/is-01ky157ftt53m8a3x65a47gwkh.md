---
type: is
id: is-01ky157ftt53m8a3x65a47gwkh
title: "PR13/R2: filesystem names cross HTML/JS/CSS contexts unsafely"
kind: bug
status: closed
priority: 0
version: 2
spec_path: docs/project/specs/active/plan-2026-07-20-folder-views-and-treemap-overview.md
labels: []
dependencies: []
parent_id: is-01kxz2z9v1bbfcfmqstffkhvxp
created_at: 2026-07-21T01:39:14.393Z
updated_at: 2026-07-21T02:01:47.967Z
closed_at: 2026-07-21T02:01:47.967Z
close_reason: "Fixed in the R1-R8 review-response commit on PR #13; verified by new unit/vm assertions plus a live browser pass (hostile filenames, Back/Forward zoom trail, live header); make verify green"
---
Review finding R2 (high): breadcrumb/up inline onclick handlers break on apostrophe filenames (esc() then quote-replace no-ops; HTML entity decode re-opens the JS string — script execution on click). revealInTree interpolates raw paths into attribute selectors despite escapePathForSelector existing. Fix: delegated data-path listeners for breadcrumb/up (and retire the copyPath inline pattern), escapePathForSelector at both selector sites, hostile-filename DOM tests.
