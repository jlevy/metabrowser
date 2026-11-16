---
type: is
id: is-01m7hdmh91rky331b89tshfgr2
title: "PR #463 A1: header Chrome fixture draws bare two-stack chips; design-system figures describe them"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7hcjqx287ha000smyytqswb
hold: null
hold_until: null
created_at: 2026-11-16T05:35:17.792Z
updated_at: 2026-11-16T05:47:55.742Z
started_at: 2026-11-16T05:47:55.284Z
closed_at: 2026-11-16T05:47:55.738Z
close_reason: "Fixed in #467 (its review A1): the header Chrome fixture's named and the two-stack figures; nothing changes on #463, per the coordinator."
resolution: null
duplicate_of: null
---
tests/dom/github-pull-header-chrome.mjs:256-262 and docs/design-system.md:1506-1510: the fixture builds the two-stack case without named: stacks.length > 1, as mountPullPage passes; the two-stack figures are the bare chips'. Severity: Medium. PR #463, Review A round 1: https://github.com/jlevy/metabrowser/pull/463#pullrequestreview-5915439143
