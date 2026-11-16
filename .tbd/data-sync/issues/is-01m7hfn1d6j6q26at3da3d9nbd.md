---
type: is
id: is-01m7hfn1d6j6q26at3da3d9nbd
title: "PR #470 A2: a Checks page opened hidden never draws its summary"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7hcjv212191g3nw3tr8take
hold: null
hold_until: null
created_at: 2026-11-16T06:10:31.461Z
updated_at: 2026-11-16T06:58:49.305Z
started_at: 2026-11-16T06:42:51.204Z
closed_at: 2026-11-16T06:58:49.304Z
close_reason: "Fixed in 5fc9bc9 (wantComparison in the visibility handler); confirmed by headerSummary. Disposition reply: https://github.com/jlevy/metabrowser/pull/470#issuecomment-6909694363"
resolution: null
duplicate_of: null
---
pull-page.js:6295-6302 with :5701-5705. The visibility handler asks again only on Conversation. Severity: Medium. PR #470, review A round 1: https://github.com/jlevy/metabrowser/pull/470#pullrequestreview-5915665462
