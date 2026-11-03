---
type: is
id: is-01m6g771qn4n0pce8m7sdmmhxy
title: Complete changed-file tree lifecycle and keyboard integration before publishing WIP
kind: bug
status: in_progress
priority: 2
version: 9
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m6g5eqspq97btjbwk0nhwcjw
child_order_hints:
  - is-01m6g885ttqy8g5xgx47079vj9
  - is-01m6g8865t5pqh8wc84xtkvkbp
  - is-01m6g886gmdr9vtphf25n922k6
  - is-01m6g886zy7pn0p851hcbk79pp
  - is-01m6g887ar5h8t061ycf05wt38
  - is-01m6gab1sz6qn15qwkpe0wtnha
hold: null
hold_until: null
created_at: 2026-11-03T08:08:08.180Z
updated_at: 2026-11-03T09:02:45.054Z
started_at: 2026-11-03T08:10:51.617Z
---
The unpublished #287 tree WIP had no tabindex=0 file anchor, no first-read recovery control, no settled freshness poll, and no diff scroll-follow lifecycle subscription. Completing these with production-controller and host golden evidence in codex/pulls-files-completion-01a1a051; measured Chrome152 tree painting at1,183 real and3,000 stress files.

## Notes

Fixed in isolated #287 completion branch: one changed-file Tab anchor, cache-read recovery, settled freshness checks, page/diff lifecycle subscriptions, and distinct navigation row CSS classes preserving inline conversation file links. Chrome152 production tree paint measured at 1,183 real and 3,000 stress files; focused 68 tests and 10 golden blocks pass, lint gate completing. Coordinator reserves sync and will request independent review.
