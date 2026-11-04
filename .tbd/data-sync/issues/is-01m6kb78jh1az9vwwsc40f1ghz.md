---
type: is
id: is-01m6kb78jh1az9vwwsc40f1ghz
title: Refresh serving and full-or-borrowed source-mode architecture summaries
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m6jhctf78vq1v7ndv43jzssy
created_at: 2026-11-04T13:15:52.784Z
updated_at: 2026-11-04T13:15:52.784Z
---
Documentation review D11: maintained state/delivery and Git-source summaries still describe serving acquired pins as future and every store as a self-contained full clone. Actual serve_mirror uses a lifespan-owned GitRevisionSubject opener and supports full or borrowed stores. Missing blobs can result from lender object loss as well as corruption. Correct these current summaries, preserving typed object_unavailable and no implicit network repair on reads. Verify exact successor against serving and store source.
