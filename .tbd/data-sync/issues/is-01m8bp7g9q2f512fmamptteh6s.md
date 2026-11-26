---
type: is
id: is-01m8bp7g9q2f512fmamptteh6s
title: "PR #874 C4: decode the GitPath losslessly for an outbound URL"
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-26-in-app-link-resolution.md
delegate: claude-code@vm
labels: []
dependencies: []
parent_id: is-01m8bp7ce37pgee1zpr3wrq5q6
hold: null
hold_until: null
created_at: 2026-11-26T10:25:43.223Z
updated_at: 2026-11-26T10:28:58.604Z
started_at: 2026-11-26T10:25:46.388Z
closed_at: 2026-11-26T10:28:58.604Z
close_reason: Round 1 of https://github.com/jlevy/metabrowser/pull/874 is being addressed by the owner's mb-b6qw (4cea6585 and later on the branch); this parallel attempt was not pushed.
resolution: duplicate
duplicate_of: is-01m8bkxf108ayt40j2hhjkrxm5
---
Review C, P3, repository-links.js:579. The display decoder drops a leading U+FEFF, so a file named U+FEFF+plan.md opened plan.md on GitHub. https://github.com/jlevy/metabrowser/pull/874#pullrequestreview-6071796228
