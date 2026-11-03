---
type: is
id: is-01m6g771qn4n0pce8m7sdmmhxy
title: Complete changed-file tree lifecycle and keyboard integration before publishing WIP
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m6g5eqspq97btjbwk0nhwcjw
created_at: 2026-11-03T08:08:08.180Z
updated_at: 2026-11-03T08:08:08.180Z
---
The unpublished #287 tree WIP had no tabindex=0 file anchor, no first-read recovery control, no settled freshness poll, and no diff scroll-follow lifecycle subscription. Completing these with production-controller and host golden evidence in codex/pulls-files-completion-01a1a051; measured Chrome152 tree painting at1,183 real and3,000 stress files.
