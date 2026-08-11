---
type: is
id: is-01ky157g6fgv14bp30m1tmhs48
title: "PR13/R3: README detection invents casing on case-insensitive filesystems"
kind: bug
status: closed
priority: 0
version: 2
spec_path: docs/project/specs/active/plan-2026-07-20-folder-views-and-treemap-overview.md
labels: []
dependencies: []
parent_id: is-01kxz2z9v1bbfcfmqstffkhvxp
created_at: 2026-07-21T01:39:14.767Z
updated_at: 2026-07-21T02:01:47.973Z
closed_at: 2026-07-21T02:01:47.973Z
close_reason: "Fixed in the R1-R8 review-response commit on PR #13; verified by new unit/vm assertions plus a live browser pass (hostile filenames, Back/Forward zoom trail, live header); make verify green"
---
Review finding R3 (gate failure on macOS): probing README.md matches ReadMe.MD on case-insensitive filesystems and returns the invented name. Fix: single directory listing first, return the real child name for case-insensitive matches (prefer exact spellings when several exist); keep the mixed-case test.
