---
type: is
id: is-01m7hdmksc122stcjpd8ab03g8
title: "PR #458 A1: Commits sweep's 'the tally' case does not reliably measure the real tally"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7hcjeyyagvt3h7zcvvssfks
hold: null
hold_until: null
created_at: 2026-11-16T05:35:20.363Z
updated_at: 2026-11-16T06:16:19.897Z
started_at: 2026-11-16T05:35:28.386Z
closed_at: 2026-11-16T06:16:19.896Z
close_reason: "Fixed in 3ed205983 on PR #458; disposition reply https://github.com/jlevy/metabrowser/pull/458#issuecomment-6908956491"
resolution: null
duplicate_of: null
---
Medium. Review A https://github.com/jlevy/metabrowser/pull/458#pullrequestreview-5915435915. tests/dom/nav-metadata-chrome.mjs:220, :237, :252-256. The only wait before the Commits sweep matches the pending shimmer's .git-history-summary-count span (git-panel.js:1891-1900), and LONG_TALLY is injected in the default-font pass and never restored, so 'the tally' measures pending, injected or real text depending on timing. Fix: wait for #nav-toolbar-git .git-history-summary-first, capture the settled markup once, re-inject it in the sweep's before for 'the tally', restore after the long-tally case.
