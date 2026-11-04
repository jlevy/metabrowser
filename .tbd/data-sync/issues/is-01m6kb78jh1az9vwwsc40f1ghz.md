---
type: is
id: is-01m6kb78jh1az9vwwsc40f1ghz
title: Refresh serving and full-or-borrowed source-mode architecture summaries
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m6jhctf78vq1v7ndv43jzssy
created_at: 2026-11-04T13:15:52.784Z
updated_at: 2026-11-04T17:21:01.604Z
closed_at: 2026-11-04T17:21:01.604Z
close_reason: "All 17 accepted documentation findings corrected in reviewed/merged PR #298 and independently verified on its exact final-main tree. Completed against actual final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9; final independent integration review and all nine main CI jobs passed. Original evidence retains its execution pins; genuine future and release scope remains separate."
resolution: null
duplicate_of: null
---
Documentation review D11: maintained state/delivery and Git-source summaries still describe serving acquired pins as future and every store as a self-contained full clone. Actual serve_mirror uses a lifespan-owned GitRevisionSubject opener and supports full or borrowed stores. Missing blobs can result from lender object loss as well as corruption. Correct these current summaries, preserving typed object_unavailable and no implicit network repair on reads. Verify exact successor against serving and store source.
