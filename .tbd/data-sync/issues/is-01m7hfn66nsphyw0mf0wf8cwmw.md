---
type: is
id: is-01m7hfn66nsphyw0mf0wf8cwmw
title: "PR #470 A11: the header probe's summary checks run only where the stack chip flag is set"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7hcjv212191g3nw3tr8take
hold: null
hold_until: null
created_at: 2026-11-16T06:10:36.372Z
updated_at: 2026-11-16T06:58:52.888Z
started_at: 2026-11-16T06:42:54.446Z
closed_at: 2026-11-16T06:58:52.887Z
close_reason: "Fixed in a81f0dc: the header probe measures the summary on every tab by its own flag and fails on a missing measurement. Disposition reply: https://github.com/jlevy/metabrowser/pull/470#issuecomment-6909694363"
resolution: null
duplicate_of: null
---
tests/dom/github-pull-header-chrome.mjs:249, :979, :991-1010; tests/test_github_pull_header_chrome.py:99-100. Severity: Low. PR #470, review A round 1: https://github.com/jlevy/metabrowser/pull/470#pullrequestreview-5915665462
