---
type: is
id: is-01m041tjpb6dxha8h5yfjs9jqw
title: Files section lacks the pending skeleton that File Breakdown shows
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m03tqjzm7j6qkxjeath5qe0d
created_at: 2026-08-16T01:08:52.554Z
updated_at: 2026-08-16T01:08:52.554Z
---
Reported 2026-08-15: while a large folder loads slowly, the File Breakdown panel shows its pulsing skeleton bars but the Files panel above it does not, so the top of the Overview reads as empty or as settled numbers while the section below is visibly still working.

Code context: folder_totals.js renders '.folder-totals-loading' (a single 44px pulsing block) only when normalizeFolderTotals() returns pending, which requires ALL of total_files/total_size/unignored_files/unignored_size to be missing. With partial or zeroed envelope data it renders a table instead - potentially of zeros - so there is no visible pending state. File Breakdown by contrast waits for a terminal rollup generation and shows '.file-type-summary-skeleton' (multiple bars) throughout.

NOT yet reproduced under instrumentation: attempts to catch it in the browser kept losing the race once the index warmed. Reproduce with a cold server on a large root (e.g. metab /Users/levy/wrk/github) and sample both panels within the first ~2s of selecting a big unscanned folder. Confirm whether Files shows a zeroed table, an invisible skeleton, or nothing, then make its pending treatment match the Breakdown's.
