---
type: is
id: is-01m6h9cdfbssfhw070vzh342qy
title: "PR #287 Qodo4458535266: invalidate async file-tree replies when hidden"
kind: bug
status: closed
priority: 2
version: 3
labels: []
dependencies: []
parent_id: is-01m6g59qm4ewjgek4vjmndcxrj
created_at: 2026-11-03T18:05:15.626Z
updated_at: 2026-11-03T20:17:09.810Z
closed_at: 2026-11-03T20:17:09.810Z
close_reason: "Completed by forward commits in the PR-support stack; independent reviews, rechecks and dispositions are published on the owning PRs. Final integration ea771741211193a387c1771e04df29b5a9698100 passed make verify (4712 Python, 9 expected skips, 373 transcripts), 8 public live tests, installed-wheel Chrome (22 actions, 25 unchanged checkout/Git fingerprints), and all 171 CI jobs across 19 current-head runs on 14 PRs. Final clean review: https://github.com/jlevy/metabrowser/pull/288#pullrequestreview-5758664799 . No PR merged."
resolution: null
duplicate_of: null
---
Medium https://github.com/jlevy/metabrowser/pull/287#discussion_r4458535266, review5757123686 at38ab13f1f8693a1b0478490258a35a7317ac1df9. pull-files-tree.js883-908/1159-1180 keeps GET ownership on collapse/hide/visibility loss, suppressing a fresh read after reopening and accepting stale GET/POST responses. Reproduce with controlled response promises ignoring abort, then preserve current visit ownership and immediate fresh reopening reads. Writer branch codex/pulls-287-ready-state-review-01a1a051; root owns integration, publication, closure and sync.

## Notes

Confirmed/fixed in f1ae7c61188a85c319cf3870cacb32bc62402a0b, direct38ab13f1. Collapse/panel hide/document visibility loss abort and release GET ownership immediately; stale GET response/finally and stale POST success/error cannot own reopened visit. Reader intent travels with its owned read, preventing ghost fetch after a closed reader action. Controlled transport ignores abort;9GET/order/reader-intent+6POST cases pass after red collapse cancellation failure.81affected pytest+24unchangedgolden checks+full lint/types/parity+normalhooks pass. Durable ready-state-287-38ab13f1/REPORT.json records exact source/review/logs. Independent recheck/root integration/finalCI pending; root owns publication, closure and sync.
